from __future__ import annotations

import multiprocessing
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from support import deterministic_capacity, preserve_run, profile, run_workspace, set_owner
from work_state import State, owner


def admission_worker(state_dir: str, root: str, profile_path: str, profile_data: dict,
                     index: int, start, release, output):
    os.environ["AGENT_LOCAL_OWNER"] = f"concurrent-owner-{index}"
    state = State(Path(state_dir))
    job = state.create(f"concurrent-{index}", Path(root), Path(profile_path), profile_data)
    output.put(("created", index, job["id"], job["generation"]))
    start.wait(10)
    admitted, current = state.admit(job["id"], {"ram_gb": 0.01, "cpu_cores": 0.01}, deterministic_capacity())
    output.put(("admitted", index, admitted, current["wait_reason"]))
    release.wait(10)
    closed = state.release(job["id"], verified=True)
    output.put(("released", index, closed["state"], closed["budget"]))


def stale_save_worker(state_dir: str, raw_owner: str, job: dict, start):
    os.environ["AGENT_LOCAL_OWNER"] = raw_owner
    start.wait(10)
    job["state"] = "queued"
    State(Path(state_dir)).save(job)


def adapter_update_worker(state_dir: str, raw_owner: str, identifier: str, start):
    os.environ["AGENT_LOCAL_OWNER"] = raw_owner
    start.wait(10)
    State(Path(state_dir)).update_adapter(identifier, prepared=True, marker="adapter-writer")


def port_claim_worker(state_dir: str, raw_owner: str, identifier: str, start):
    os.environ["AGENT_LOCAL_OWNER"] = raw_owner
    start.wait(10)
    State(Path(state_dir)).claim_ports(identifier, [43124])


class StateTests(unittest.TestCase):
    def test_normalized_identity_keeps_ownership_during_recovery(self):
        for key in ('TMF_LANE_OWNER_ID', 'AGENT_LOCAL_OWNER', 'CODEX_THREAD_ID'):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary, \
                    mock.patch.dict(os.environ, {key: 'stable-session'}, clear=True):
                root = Path(temporary).resolve()
                profile_path, profile_data = profile(root)
                state = State(root / 'state')
                job = state.create('owner-recovery', root, profile_path, profile_data)
                normalized = job['owner']
                os.environ['AGENT_LOCAL_OWNER'] = normalized
                self.assertEqual(normalized, owner())
                self.assertEqual(job['id'], state.read(job['id'])['id'])

    def test_closed_generation_cannot_readmit_and_active_index_ignores_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            root = parent / 'root'
            root.mkdir()
            profile_path, profile_data = profile(root)
            set_owner('index-owner')
            state = State(parent / 'state')
            old = state.create('old', root, profile_path, profile_data)
            state.release(old['id'], verified=True)
            with self.assertRaisesRegex(RuntimeError, 'closed generation'):
                state.admit(old['id'], {'ram_gb': 1, 'cpu_cores': 1}, deterministic_capacity())
            current = state.create('current', root, profile_path, profile_data)
            state.path(old['id']).write_text('{broken historical report')
            with state.locked():
                self.assertEqual([current['id']], [j['id'] for j in state.active()])
            self.assertTrue(state.admit(current['id'], {'ram_gb': .01, 'cpu_cores': .01}, deterministic_capacity())[0])

    def test_preserved_runs_are_unique_and_never_overwrite_red_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            artifacts = parent / "artifacts"
            first = parent / "first-state"
            second = parent / "second-state"
            first.mkdir()
            second.mkdir()
            (first / "result.txt").write_text("failed-first\n")
            (second / "result.txt").write_text("passed-second\n")
            with mock.patch.dict(os.environ, {"AGENT_WORK_TEST_ARTIFACTS": str(artifacts)}):
                first_target = preserve_run(first, "same-label")
                second_target = preserve_run(second, "same-label")
            self.assertNotEqual(first_target, second_target)
            self.assertEqual("failed-first\n", (first_target / "result.txt").read_text())
            self.assertEqual("passed-second\n", (second_target / "result.txt").read_text())

    def test_keyboard_interrupt_keeps_original_durable_journal(self):
        with tempfile.TemporaryDirectory() as temporary:
            artifacts = Path(temporary).resolve() / "artifacts"
            durable = None
            with mock.patch.dict(os.environ, {"AGENT_WORK_TEST_ARTIFACTS": str(artifacts)}):
                with self.assertRaises(KeyboardInterrupt):
                    with run_workspace("interrupted-run") as durable:
                        (durable / "supervisor.json").write_text(
                            json.dumps({"identity": "exact", "start": "observed", "status": "active"}) + "\n")
                        raise KeyboardInterrupt("fixture caller interrupted")
            self.assertTrue((durable / "supervisor.json").is_file())
            self.assertEqual("failed", json.loads((durable / "run-status.json").read_text())["status"])

    def test_fifteen_simultaneous_low_budget_requests_are_unique(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            root = parent / "root"
            root.mkdir()
            profile_path, profile_data = profile(root)
            state_dir = parent / "state"
            context = multiprocessing.get_context("spawn")
            start = context.Event()
            release = context.Event()
            output = context.Queue()
            workers = [context.Process(target=admission_worker,
                       args=(str(state_dir), str(root), str(profile_path), profile_data, index, start, release, output))
                       for index in range(15)]
            for worker in workers:
                worker.start()
            created = [output.get(timeout=20) for _ in workers]
            self.assertEqual({"created"}, {row[0] for row in created})
            start.set()
            admitted = [output.get(timeout=20) for _ in workers]
            jobs = State(state_dir).all()
            self.assertEqual(15, len(jobs))
            self.assertTrue(all(job["budget"] == {"ram_gb": 0.01, "cpu_cores": 0.01} for job in jobs))
            release.set()
            released = [output.get(timeout=20) for _ in workers]
            for worker in workers:
                worker.join(20)
                self.assertEqual(0, worker.exitcode)
            self.assertEqual(15, len({row[2] for row in created}))
            self.assertEqual(15, len({row[3] for row in created}))
            self.assertTrue(all(row[2] for row in admitted), admitted)
            self.assertEqual({"released"}, {row[0] for row in released})
            jobs = State(state_dir).all()
            self.assertTrue(all(job["state"] == "closed" and job["budget"] == {"ram_gb": 0, "cpu_cores": 0}
                                for job in jobs))

    def test_fifo_blocks_a_neighbor_until_earlier_waiter_is_admitted(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            root = parent / "root"
            root.mkdir()
            profile_path, profile_data = profile(root)
            state = State(parent / "state")
            set_owner("fifo-first")
            first = state.create("first", root, profile_path, profile_data)
            time.sleep(0.01)
            set_owner("fifo-second")
            second = state.create("second", root, profile_path, profile_data)
            scarce = deterministic_capacity()
            scarce["system"]["memory_effective_available_gb"] = 0
            set_owner("fifo-first")
            admitted, _ = state.admit(first["id"], {"ram_gb": 1, "cpu_cores": 1}, scarce)
            self.assertFalse(admitted)
            set_owner("fifo-second")
            admitted, current = state.admit(second["id"], {"ram_gb": 0.01, "cpu_cores": 0.01}, deterministic_capacity())
            self.assertFalse(admitted)
            self.assertIn("earlier queued task", current["wait_reason"])
            set_owner("fifo-first")
            self.assertTrue(state.admit(first["id"], {"ram_gb": 0.01, "cpu_cores": 0.01}, deterministic_capacity())[0])
            set_owner("fifo-second")
            self.assertTrue(state.admit(second["id"], {"ram_gb": 0.01, "cpu_cores": 0.01}, deterministic_capacity())[0])

    def test_owner_and_generation_prevent_neighbor_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            root = parent / "root"
            root.mkdir()
            profile_path, profile_data = profile(root)
            state = State(parent / "state")
            set_owner("owner-a")
            job = state.create("owned", root, profile_path, profile_data)
            set_owner("owner-b")
            with self.assertRaisesRegex(RuntimeError, "different session"):
                state.read(job["id"])
            set_owner("owner-a")
            stale = state.read(job["id"])
            stale["generation"] = "0" * 32
            with self.assertRaisesRegex(RuntimeError, "generation changed"):
                state.save(stale)

    def test_realized_claim_is_charged_only_until_a_newer_physical_sample(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            root = parent / "root"
            root.mkdir()
            profile_path, profile_data = profile(root)
            state = State(parent / "state")
            set_owner("realized-first")
            first = state.create("realized-first", root, profile_path, profile_data)
            self.assertTrue(state.admit(first["id"], {"ram_gb": 0.01, "cpu_cores": 0.01},
                                        deterministic_capacity())[0])
            first = state.read(first["id"])
            first.update(state="ready", reservation_pending=False, allocation_realized=time.time() - 1)
            state.save(first)
            set_owner("realized-second")
            second = state.create("realized-second", root, profile_path, profile_data)
            stale = deterministic_capacity()
            stale["observed_epoch"] = first["allocation_realized"] - 0.1
            stale["system"]["memory_effective_available_gb"] = 0.015
            stale["system"]["logical_cpus"] = 1
            stale["system"]["cpu_idle_percent"] = 1.5
            admitted, current = state.admit(second["id"], {"ram_gb": 0.01, "cpu_cores": 0.01}, stale)
            self.assertFalse(admitted)
            self.assertIn("memory", current["wait_reason"])
            fresh = deterministic_capacity()
            fresh["system"].update(memory_effective_available_gb=0.015, logical_cpus=1, cpu_idle_percent=1.5)
            admitted, current = state.admit(second["id"], {"ram_gb": 0.01, "cpu_cores": 0.01}, fresh)
            self.assertTrue(admitted, current["wait_reason"])

    def test_concurrent_state_save_preserves_adapter_owned_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            root = parent / "root"
            root.mkdir()
            profile_path, profile_data = profile(root)
            set_owner("adapter-owner")
            state_dir = parent / "state"
            state = State(state_dir)
            job = state.create("adapter-sharing", root, profile_path, profile_data)
            stale = state.read(job["id"])
            context = multiprocessing.get_context("spawn")
            start = context.Event()
            saver = context.Process(target=stale_save_worker,
                                    args=(str(state_dir), "adapter-owner", stale, start))
            adapter = context.Process(target=adapter_update_worker,
                                      args=(str(state_dir), "adapter-owner", job["id"], start))
            claimer = context.Process(target=port_claim_worker,
                                      args=(str(state_dir), "adapter-owner", job["id"], start))
            saver.start()
            adapter.start()
            claimer.start()
            start.set()
            saver.join(15)
            adapter.join(15)
            claimer.join(15)
            self.assertEqual(0, saver.exitcode)
            self.assertEqual(0, adapter.exitcode)
            self.assertEqual(0, claimer.exitcode)
            current = state.read(job["id"])
            self.assertEqual("adapter-writer", current["adapter"]["marker"])
            self.assertTrue(current["adapter"]["prepared"])
            self.assertEqual([43124], current["resource_claims"]["tcp"])

    def test_prepared_stack_can_complete_ahead_of_fifo_starts(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            root = parent / "root"
            root.mkdir()
            profile_path, profile_data = profile(root)
            state = State(parent / "state")
            set_owner("fifo-old")
            old = state.create("old-start", root, profile_path, profile_data)
            time.sleep(0.01)
            set_owner("prepared-owner")
            prepared = state.create("prepared-completion", root, profile_path, profile_data)
            state.update_adapter(prepared["id"], prepared=True)
            time.sleep(0.01)
            set_owner("fifo-new")
            new = state.create("new-start", root, profile_path, profile_data)
            scarce = deterministic_capacity()
            scarce["system"].update(memory_effective_available_gb=0, cpu_idle_percent=0)
            set_owner("fifo-old")
            self.assertFalse(state.admit(old["id"], {"ram_gb": 1, "cpu_cores": 1}, scarce)[0])
            set_owner("prepared-owner")
            admitted, current = state.admit(prepared["id"], {"ram_gb": 0.01, "cpu_cores": 0.01},
                                            deterministic_capacity())
            self.assertTrue(admitted, current["wait_reason"])
            set_owner("fifo-new")
            admitted, current = state.admit(new["id"], {"ram_gb": 0.01, "cpu_cores": 0.01},
                                            deterministic_capacity())
            self.assertFalse(admitted)
            self.assertIn("earlier queued task", current["wait_reason"])

    def test_port_claim_is_global_exclusive_and_release_makes_it_reusable(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            root = parent / "root"
            root.mkdir()
            profile_path, profile_data = profile(root)
            state = State(parent / "state")
            set_owner("port-a")
            first = state.create("port-a", root, profile_path, profile_data)
            state.claim_ports(first["id"], [43123])
            set_owner("port-b")
            second = state.create("port-b", root, profile_path, profile_data)
            with self.assertRaisesRegex(RuntimeError, "already claimed"):
                state.claim_ports(second["id"], [43123])
            set_owner("port-a")
            released = state.release(first["id"], verified=True)
            self.assertEqual({}, released["resource_claims"])
            set_owner("port-b")
            state.claim_ports(second["id"], [43123])
            self.assertEqual([43123], state.read(second["id"])["resource_claims"]["tcp"])

    def test_failed_source_snapshot_does_not_publish_job_and_retry_succeeds(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            root = parent / "root"
            root.mkdir()
            profile_path, profile_data = profile(root)
            profile_data["source_files"] = ["missing-adapter.py"]
            profile_path.write_text(json.dumps(profile_data, indent=2) + "\n")
            state = State(parent / "state")
            set_owner("snapshot-retry-owner")
            with self.assertRaisesRegex(RuntimeError, "matched no files"):
                state.create("snapshot-retry", root, profile_path, profile_data)
            self.assertEqual([], state.all())
            profile_path, profile_data = profile(root, freeze_source=True)
            job = state.create("snapshot-retry", root, profile_path, profile_data)
            self.assertTrue(Path(job["profile_source"]).is_dir())
            self.assertIn("fixture_adapter.py", job["source_manifest"])
            state.release(job["id"], verified=True)


if __name__ == "__main__":
    unittest.main()
