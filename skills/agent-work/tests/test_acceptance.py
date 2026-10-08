from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest import mock

from support import deterministic_capacity, init_git_fixture, preserve_run, profile, run_workspace, set_owner
import agent_work
import fixture_adapter
import work_report
from work_state import State


def two_service_capacity(audit_path: str) -> dict:
    sample = deterministic_capacity()
    audit = Path(audit_path)
    active = len(json.loads(audit.read_text()).get("active", [])) if audit.exists() else 0
    available = max(0, 0.025 - active * 0.01)
    sample["system"]["memory_effective_available_gb"] = available
    sample["system"]["logical_cpus"] = 1
    sample["system"]["cpu_idle_percent"] = available * 100
    return sample


def benchmark_worker(state_dir: str, job_id: str, raw_owner: str, audit_path: str,
                     start, allow_close, output):
    os.environ["AGENT_LOCAL_OWNER"] = raw_owner
    os.environ["AGENT_WORK_FIXTURE_AUDIT"] = audit_path
    state = State(Path(state_dir))
    flow = agent_work.Flow(state, job_id)
    output.put(("ready", job_id))
    start.wait(20)
    result = {"job_id": job_id, "start": None, "validate": None, "close": None, "error": None}
    # Like main(), hold the job lock for the whole operation: admission treats an
    # unheld lock as a dead CLI whose reservation no longer counts.
    lock = state.locked("job-" + job_id, blocking=False)
    lock.__enter__()
    try:
        with mock.patch.object(agent_work, "capacity", side_effect=lambda: two_service_capacity(audit_path)):
            result["start"] = flow.start(120)
            result["validate"] = flow.validate(120)
            current = state.read(job_id)
            fixture_adapter.audit("preclose", job_id=job_id, generation=current["generation"],
                                  state=current["state"], gate_passed=(current.get("gate") or {}).get("passed"))
            allow_close.wait(120)
            result["close"] = flow.close()
    except BaseException as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        try:
            result["close"] = flow.close()
        except BaseException as cleanup:
            result["error"] += f"; cleanup={type(cleanup).__name__}: {cleanup}"
    lock.__exit__(None, None, None)
    output.put(("result", result))


class FixtureLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.previous_owner = os.environ.get("AGENT_LOCAL_OWNER")
        self.previous_mode = os.environ.get("AGENT_WORK_FIXTURE_MODE")

    def tearDown(self):
        if self.previous_owner is None:
            os.environ.pop("AGENT_LOCAL_OWNER", None)
        else:
            os.environ["AGENT_LOCAL_OWNER"] = self.previous_owner
        if self.previous_mode is None:
            os.environ.pop("AGENT_WORK_FIXTURE_MODE", None)
        else:
            os.environ["AGENT_WORK_FIXTURE_MODE"] = self.previous_mode

    def new_flow(self, parent: Path, task: str, owner: str, *, freeze_source: bool = False):
        root = init_git_fixture(parent)
        profile_path, profile_data = profile(root, freeze_source=freeze_source)
        set_owner(owner)
        state = State(parent / "state")
        job = state.create(task, root, profile_path, profile_data)
        return state, agent_work.Flow(state, job["id"]), job

    def run_flow(self, flow):
        with mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
            start_rc = flow.start()
            validate_rc = flow.validate()
            close_rc = flow.close()
        return start_rc, validate_rc, close_rc

    def call_main(self, *argv, capacity_sample=deterministic_capacity):
        previous_signal = signal.getsignal(signal.SIGTERM)
        try:
            with mock.patch.object(sys, "argv", [str(agent_work.HERE / "agent_work.py"), *argv]), \
                    mock.patch.object(agent_work, "capacity", side_effect=capacity_sample):
                return agent_work.main()
        finally:
            signal.signal(signal.SIGTERM, previous_signal)

    def assert_clean_closed(self, state: State, identifier: str):
        job = state.read(identifier)
        self.assertEqual("closed", job["state"])
        self.assertEqual({"ram_gb": 0, "cpu_cores": 0}, job["budget"])
        self.assertTrue(job["adapter"]["cleanup_verified"])
        record = json.loads(Path(job["adapter"]["server_record"]).read_text())
        self.assertEqual("released", record["status"])
        self.assertFalse(Path(job["adapter"]["db"]).exists())
        self.assertFalse(Path(job["adapter"]["port_evidence"]).exists())
        self.assertTrue(all(not agent_work.runtime.members(record["pid"]) for _ in [0]))
        return job

    def advance_origin(self, parent: Path, root: Path, peer: Path, marker: str):
        if not peer.exists():
            subprocess.run(["git", "clone", "--branch", "main", str(parent / "origin.git"), str(peer)],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", str(peer), "config", "user.name", "Peer Fixture"], check=True)
            subprocess.run(["git", "-C", str(peer), "config", "user.email", "peer@example.invalid"], check=True)
        (peer / "peer.txt").write_text(marker + "\n")
        subprocess.run(["git", "-C", str(peer), "add", "peer.txt"], check=True)
        subprocess.run(["git", "-C", str(peer), "commit", "-m", f"test: {marker}"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(peer), "push", "origin", "main"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(root), "fetch", "origin"], check=True, capture_output=True)

    def cleanup_and_preserve(self, state: State, label: str, *owned_jobs):
        errors = []
        for job, owner in owned_jobs:
            if job is None:
                continue
            set_owner(owner)
            try:
                if state.read(job["id"])["state"] != "closed":
                    agent_work.Flow(state, job["id"]).close()
            except BaseException as exc:
                errors.append(f"{job['id']}: {type(exc).__name__}: {exc}")
        preserve_run(state.root, label)
        if errors:
            message = "fixture cleanup failures: " + "; ".join(errors)
            active_error = sys.exception()
            if active_error is None:
                self.fail(message)
            active_error.add_note(message)

    def test_real_http_sqlite_git_lifecycle_preserves_full_evidence(self):
        with run_workspace("passing-cycle") as parent:
            try:
                state, flow, job = self.new_flow(parent, "passing-cycle", "passing-owner")
                self.assertEqual((0, 0, 0), self.run_flow(flow))
                closed = self.assert_clean_closed(state, job["id"])
                self.assertTrue(closed["gate"]["passed"], closed["gate"]["errors"])
                self.assertEqual(2, closed["gate"]["cases"])
                self.assertTrue(closed["versions"]["fixture"]["base_is_ancestor"])
                self.assertTrue(all(Path(path).is_file() for path in closed["adapter"]["preserved_evidence"]))
            finally:
                self.cleanup_and_preserve(state, "passing-cycle", (job, "passing-owner"))

    def test_prepare_tempfail_queues_without_resources_and_resumes_same_job(self):
        with run_workspace("prepare-project-capacity") as parent:
            try:
                state, flow, job = self.new_flow(parent, "prepare-project-capacity", "prepare-capacity-owner")
                state.update_adapter(job["id"], capacity_wait_reason="fixture project slots full")
                original_hook = flow.hook
                attempts = []

                def capacity_once(phase, command=None, cwd=None, timeout_override=None):
                    if phase == "prepare" and not attempts:
                        attempts.append(phase)
                        return original_hook(phase, [sys.executable, "-c", "raise SystemExit(75)"],
                                             cwd, timeout_override)
                    return original_hook(phase, command, cwd, timeout_override)

                with mock.patch.object(flow, "hook", side_effect=capacity_once), \
                        mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(75, flow.start(0))
                    queued = state.read(job["id"])
                    self.assertEqual("queued", queued["state"])
                    self.assertTrue(queued["waiting_for_capacity"])
                    self.assertEqual("fixture project slots full", queued["wait_reason"])
                    self.assertEqual({"ram_gb": 0, "cpu_cores": 0}, queued["budget"])
                    self.assertFalse(queued["reservation_pending"])
                    self.assertIsInstance(queued["allocation_realized"], float)
                    self.assertFalse(queued["adapter"].get("prepared", False))
                    self.assertFalse((state.path(job["id"]).parent / "fixture").exists())
                    prepare = [item for item in queued["phases"] if item["phase"] == "prepare"]
                    self.assertEqual([(75, "queued")],
                                     [(item["exit_code"], item["state"]) for item in prepare])
                    self.assertEqual(job["id"], flow.identifier)
                    self.assertEqual(0, flow.start(0))
                self.assertEqual(job["id"], state.read(job["id"])["id"])
                self.assertEqual(0, flow.close())
            finally:
                self.cleanup_and_preserve(state, "prepare-project-capacity",
                                          (job, "prepare-capacity-owner"))

    def test_up_tempfail_preserves_prepared_state_and_resumes_same_job(self):
        with run_workspace("up-project-capacity") as parent:
            try:
                state, flow, job = self.new_flow(parent, "up-project-capacity", "up-capacity-owner")
                original_hook = flow.hook
                attempts = []

                def capacity_once(phase, command=None, cwd=None, timeout_override=None):
                    if phase == "up" and not attempts:
                        attempts.append(phase)
                        return original_hook(phase, [sys.executable, "-c", "raise SystemExit(75)"],
                                             cwd, timeout_override)
                    return original_hook(phase, command, cwd, timeout_override)

                with mock.patch.object(flow, "hook", side_effect=capacity_once), \
                        mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(75, flow.start(0))
                    queued = state.read(job["id"])
                    self.assertEqual("queued", queued["state"])
                    self.assertTrue(queued["adapter"]["prepared"])
                    self.assertEqual({"ram_gb": 0, "cpu_cores": 0}, queued["budget"])
                    self.assertFalse(queued["reservation_pending"])
                    self.assertFalse(Path(queued["adapter"]["server_record"]).exists())
                    self.assertEqual(1, sum(item["phase"] == "prepare" for item in queued["phases"]))
                    self.assertEqual((75, "queued"),
                                     [(item["exit_code"], item["state"]) for item in queued["phases"]
                                      if item["phase"] == "up"][-1])
                    self.assertEqual(0, flow.start(0))
                ready = state.read(job["id"])
                self.assertEqual("ready", ready["state"])
                self.assertEqual(1, sum(item["phase"] == "prepare" for item in ready["phases"]))
                self.assertEqual(2, sum(item["phase"] == "up" for item in ready["phases"]))
                self.assertEqual(0, flow.close())
            finally:
                self.cleanup_and_preserve(state, "up-project-capacity", (job, "up-capacity-owner"))

    def test_finite_wait_readmits_and_recovers_project_capacity_in_same_start(self):
        with run_workspace("wait-project-capacity") as parent:
            try:
                state, flow, job = self.new_flow(parent, "wait-project-capacity", "wait-capacity-owner")
                original_hook = flow.hook
                attempts = []

                def capacity_once(phase, command=None, cwd=None, timeout_override=None):
                    if phase == "prepare" and not attempts:
                        attempts.append(phase)
                        return original_hook(phase, [sys.executable, "-c", "raise SystemExit(75)"],
                                             cwd, timeout_override)
                    return original_hook(phase, command, cwd, timeout_override)

                with mock.patch.object(flow, "hook", side_effect=capacity_once), \
                        mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity), \
                        mock.patch.object(agent_work.time, "sleep", return_value=None):
                    self.assertEqual(0, flow.start(2))
                ready = state.read(job["id"])
                prepare = [item for item in ready["phases"] if item["phase"] == "prepare"]
                self.assertEqual([(75, "queued"), (0, "passed")],
                                 [(item["exit_code"], item["state"]) for item in prepare])
                self.assertGreaterEqual(sum(item["phase"] == "queue-up" for item in ready["phases"]), 2)
                self.assertFalse(ready["waiting_for_capacity"])
                self.assertFalse(ready["reservation_pending"])
                self.assertEqual(0, flow.close())
            finally:
                self.cleanup_and_preserve(state, "wait-project-capacity", (job, "wait-capacity-owner"))

    def test_non_tempfail_prepare_error_is_not_retried_or_converted(self):
        with run_workspace("prepare-project-error") as parent:
            try:
                state, flow, job = self.new_flow(parent, "prepare-project-error", "prepare-error-owner")
                original_hook = flow.hook
                attempts = []

                def fail_once(phase, command=None, cwd=None, timeout_override=None):
                    if phase == "prepare":
                        attempts.append(phase)
                        return original_hook(phase, [sys.executable, "-c", "raise SystemExit(1)"],
                                             cwd, timeout_override)
                    return original_hook(phase, command, cwd, timeout_override)

                with mock.patch.object(flow, "hook", side_effect=fail_once), \
                        mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(1, flow.start(10))
                current = state.read(job["id"])
                self.assertEqual(["prepare"], attempts)
                self.assertEqual([(1, "failed")],
                                 [(item["exit_code"], item["state"]) for item in current["phases"]
                                  if item["phase"] == "prepare"])
                self.assertNotEqual("queued", current["state"])
                self.assertFalse(current["waiting_for_capacity"])
            finally:
                self.cleanup_and_preserve(state, "prepare-project-error",
                                          (job, "prepare-error-owner"))

    def test_pinned_base_ignores_origin_advance_before_and_during_validation(self):
        with run_workspace("pinned-origin-advance") as parent:
            try:
                state, flow, job = self.new_flow(parent, "pinned-origin-advance", "pinned-owner")
                original_hook = flow.hook

                def assert_pinned_before_hook(phase, command=None, cwd=None, timeout_override=None):
                    if phase == "up":
                        declared = state.read(job["id"])["adapter"]["repositories"]["fixture"]
                        self.assertIn("base_sha", declared)
                    return original_hook(phase, command, cwd, timeout_override)

                with mock.patch.object(flow, "hook", side_effect=assert_pinned_before_hook), \
                        mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(0, flow.start())
                ready = state.read(job["id"])
                served = agent_work.git_manifest(ready["adapter"]["repositories"])
                pinned_sha = served["fixture"]["base_sha"]
                legacy = {name: {key: value for key, value in info.items() if key != "base_sha"}
                          for name, info in ready["adapter"]["repositories"].items()}
                state.update_adapter(job["id"], repositories=legacy, repository_base_pins=None,
                                     served_source_manifest=served)
                peer = parent / "peer"
                self.advance_origin(parent, Path(job["root"]), peer, "advance-before-validation")
                up_count = sum(phase["phase"] == "up" for phase in ready["phases"])

                def advance_during_test(phase, command=None, cwd=None, timeout_override=None):
                    rc = original_hook(phase, command, cwd, timeout_override)
                    if phase == "test":
                        self.advance_origin(parent, Path(job["root"]), peer, "advance-during-validation")
                    return rc

                with mock.patch.object(flow, "hook", side_effect=advance_during_test), \
                        mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(0, flow.validate())
                validated = state.read(job["id"])
                self.assertTrue(validated["gate"]["passed"], validated["gate"]["errors"])
                self.assertEqual(pinned_sha, validated["adapter"]["repositories"]["fixture"]["base_sha"])
                self.assertEqual(pinned_sha, validated["versions"]["fixture"]["base_sha"])
                self.assertEqual(up_count, sum(phase["phase"] == "up" for phase in validated["phases"]))
                self.assertEqual(0, flow.close())
            finally:
                self.cleanup_and_preserve(state, "pinned-origin-advance", (job, "pinned-owner"))

    def test_durable_pin_rejects_later_base_or_base_sha_replacement(self):
        with run_workspace("durable-base-pin") as parent:
            try:
                state, flow, job = self.new_flow(parent, "durable-base-pin", "durable-pin-owner")
                with mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(0, flow.start())
                current = state.read(job["id"])
                original = current["adapter"]["repositories"]
                pins = current["adapter"]["repository_base_pins"]
                self.assertEqual({"base": original["fixture"]["base"],
                                  "base_sha": original["fixture"]["base_sha"]}, pins["fixture"])
                phase_count = len(current["phases"])
                for field, value in (("base", "replacement"), ("base_sha", "f" * 40)):
                    with self.subTest(field=field):
                        changed = json.loads(json.dumps(original))
                        changed["fixture"][field] = value
                        state.update_adapter(job["id"], repositories=changed)
                        with self.assertRaisesRegex(RuntimeError, "changed after it was pinned"):
                            flow.start()
                        self.assertEqual(phase_count, len(state.read(job["id"])["phases"]))
                        state.update_adapter(job["id"], repositories=original)
                state.update_adapter(job["id"], repositories={})
                with self.assertRaisesRegex(RuntimeError, "declarations disappeared"):
                    flow.start()
                self.assertEqual(phase_count, len(state.read(job["id"])["phases"]))
                state.update_adapter(job["id"], repositories=original)
                self.assertEqual(0, flow.close())
            finally:
                self.cleanup_and_preserve(state, "durable-base-pin", (job, "durable-pin-owner"))

    def test_legacy_validated_job_recovers_pin_from_versions_not_live_origin(self):
        with run_workspace("legacy-versions-pin") as parent:
            try:
                state, flow, job = self.new_flow(parent, "legacy-versions", "legacy-versions-owner")
                with mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(0, flow.start())
                ready = state.read(job["id"])
                versions = agent_work.git_manifest(ready["adapter"]["repositories"])
                original_sha = versions["fixture"]["base_sha"]
                flow.save(versions=versions)
                legacy = {name: {key: value for key, value in info.items() if key != "base_sha"}
                          for name, info in ready["adapter"]["repositories"].items()}
                state.update_adapter(job["id"], repositories=legacy, repository_base_pins=None,
                                     served_source_manifest=None, served_source_sha256=None)
                self.advance_origin(parent, Path(job["root"]), parent / "peer", "advance-after-legacy-run")
                up_count = sum(phase["phase"] == "up" for phase in ready["phases"])
                with mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(0, flow.start())
                recovered = state.read(job["id"])
                self.assertEqual(original_sha,
                                 recovered["adapter"]["repository_base_pins"]["fixture"]["base_sha"])
                self.assertEqual(original_sha,
                                 recovered["adapter"]["repositories"]["fixture"]["base_sha"])
                self.assertEqual(up_count, sum(phase["phase"] == "up" for phase in recovered["phases"]))
                self.assertEqual(0, flow.close())
            finally:
                self.cleanup_and_preserve(state, "legacy-versions-pin",
                                          (job, "legacy-versions-owner"))

    def test_corrupt_legacy_served_manifest_or_digest_never_seeds_pin(self):
        with run_workspace("invalid-served-manifest") as parent:
            try:
                state, flow, job = self.new_flow(parent, "invalid-served", "invalid-served-owner")
                self.assertEqual(0, flow.hook("prepare"))
                current = state.read(job["id"])
                valid = agent_work.git_manifest(current["adapter"]["repositories"])
                corruptions = []
                for field, value in (("head", None), ("wip_sha256", "0" * 63),
                                     ("base_is_ancestor", False)):
                    candidate = json.loads(json.dumps(valid)); candidate["fixture"][field] = value
                    corruptions.append((field, candidate, agent_work.digest(candidate)))
                corruptions.append(("digest", valid, "0" * 64))
                for label, candidate, checksum in corruptions:
                    with self.subTest(label=label):
                        state.update_adapter(job["id"], served_source_manifest=candidate,
                                             served_source_sha256=checksum,
                                             repository_base_pins=None)
                        with self.assertRaisesRegex(RuntimeError, "served source|Served source"):
                            flow.pin_repository_bases()
                        adapter = state.read(job["id"])["adapter"]
                        self.assertIsNone(adapter["repository_base_pins"])
                        self.assertNotIn("base_sha", adapter["repositories"]["fixture"])
                self.assertEqual(0, flow.close())
            finally:
                self.cleanup_and_preserve(state, "invalid-served-manifest",
                                          (job, "invalid-served-owner"))

    def test_real_source_change_during_validation_is_rejected(self):
        with run_workspace("source-change-during-validation") as parent:
            try:
                state, flow, job = self.new_flow(parent, "source-change", "source-change-owner")
                with mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(0, flow.start())
                original_hook = flow.hook

                def change_after_test(phase, command=None, cwd=None, timeout_override=None):
                    rc = original_hook(phase, command, cwd, timeout_override)
                    if phase == "test":
                        (Path(job["root"]) / "tracked.txt").write_text("changed during validation\n")
                    return rc

                with mock.patch.object(flow, "hook", side_effect=change_after_test), \
                        mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(1, flow.validate())
                failed = state.read(job["id"])
                self.assertFalse(failed["gate"]["passed"])
                self.assertTrue(any("Repository version changed" in error for error in failed["gate"]["errors"]))
                self.assertEqual(0, flow.close())
            finally:
                self.cleanup_and_preserve(state, "source-change-during-validation",
                                          (job, "source-change-owner"))

    def test_existing_non_ancestor_base_is_rejected_by_validation_gate(self):
        with run_workspace("non-ancestor-base") as parent:
            try:
                state, flow, job = self.new_flow(parent, "non-ancestor", "non-ancestor-owner")
                root = Path(job["root"])
                tree = subprocess.check_output(
                    ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"], text=True).strip()
                unrelated = subprocess.check_output(
                    ["git", "-C", str(root), "commit-tree", tree], input="unrelated base\n", text=True).strip()
                original_hook = flow.hook

                def prepare_non_ancestor(phase, command=None, cwd=None, timeout_override=None):
                    rc = original_hook(phase, command, cwd, timeout_override)
                    if phase == "prepare":
                        current = state.read(job["id"])
                        repositories = current["adapter"]["repositories"]
                        repositories["fixture"]["base_sha"] = unrelated
                        state.update_adapter(job["id"], repositories=repositories)
                    return rc

                with mock.patch.object(flow, "hook", side_effect=prepare_non_ancestor), \
                        mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(1, flow.validate())
                failed = state.read(job["id"])
                self.assertFalse(failed["gate"]["passed"])
                self.assertIn("The declared remote base is not an ancestor", failed["gate"]["errors"])
                self.assertEqual(0, flow.close())
            finally:
                self.cleanup_and_preserve(state, "non-ancestor-base", (job, "non-ancestor-owner"))

    def test_failure_closes_cleanly_and_retry_gets_new_generation(self):
        with run_workspace("failure-and-retry") as parent:
            second = None
            try:
                state, flow, first = self.new_flow(parent, "retry-cycle", "retry-owner")
                os.environ["AGENT_WORK_FIXTURE_MODE"] = "fail"
                self.assertEqual((0, 1, 0), self.run_flow(flow))
                failed = self.assert_clean_closed(state, first["id"])
                self.assertFalse(failed["gate"]["passed"])
                os.environ.pop("AGENT_WORK_FIXTURE_MODE")
                second = state.create("retry-cycle", Path(first["root"]), Path(first["profile"]), first["profile_data"])
                self.assertNotEqual(first["id"], second["id"])
                self.assertNotEqual(first["generation"], second["generation"])
                retry = agent_work.Flow(state, second["id"])
                self.assertEqual((0, 0, 0), self.run_flow(retry))
                passed = self.assert_clean_closed(state, second["id"])
                self.assertTrue(passed["gate"]["passed"])
            finally:
                self.cleanup_and_preserve(state, "failure-and-retry",
                                          (first, "retry-owner"), (second, "retry-owner"))

    def test_discovered_catalogue_rejects_self_consistent_subset(self):
        with run_workspace("subset-cycle") as parent:
            try:
                state, flow, job = self.new_flow(parent, "subset-cycle", "subset-owner")
                os.environ["AGENT_WORK_FIXTURE_MODE"] = "subset"
                self.assertEqual((0, 1, 0), self.run_flow(flow))
                closed = self.assert_clean_closed(state, job["id"])
                self.assertFalse(closed["gate"]["passed"])
                self.assertTrue(any("Executed inventory differs" in error for error in closed["gate"]["errors"]))
            finally:
                self.cleanup_and_preserve(state, "subset-cycle", (job, "subset-owner"))

    def test_cancellation_runs_exact_cleanup_without_touching_neighbor(self):
        with run_workspace("cancel-cycle") as parent:
            state, flow, job = self.new_flow(parent, "cancel-cycle", "cancel-owner")
            with mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                self.assertEqual(0, flow.start())
            neighbor_record = parent / "neighbor.json"
            neighbor_log = parent / "neighbor.log"
            neighbor = agent_work.runtime.launch(
                neighbor_record,
                [os.environ.get("PYTHON", os.sys.executable), "-c", "import time; time.sleep(60)"],
                parent,
                lease="neighbor-generation",
                log=neighbor_log,
            )
            cli_log = (parent / "killed-cli.log").open("w")
            worker = subprocess.Popen(
                [sys.executable, "-B", str(agent_work.HERE / "agent_work.py"), "validate",
                 "--job", job["id"], "--state-dir", str(parent / "state"), "--wait", "20"],
                env=dict(os.environ, AGENT_LOCAL_OWNER="cancel-owner", AGENT_WORK_FIXTURE_MODE="block",
                         PYTHONDONTWRITEBYTECODE="1"), stdout=cli_log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    current = state.read(job["id"])
                    if any(phase["phase"] == "test" and phase["state"] == "running"
                           for phase in current["phases"]):
                        break
                    time.sleep(0.05)
                else:
                    self.fail("fixture test phase did not start")
                running = [phase for phase in current["phases"] if phase["phase"] == "test"][-1]
                phase_journal = Path(running["supervisor_record"])
                active_phase = json.loads(phase_journal.read_text())
                self.assertTrue(agent_work.runtime.verified(active_phase))
                self.assertEqual(job["owner"], active_phase["owner"])
                self.assertEqual(job["generation"], active_phase["lease"])
                self.assertTrue(active_phase["identity"])
                self.assertTrue(active_phase["start"])
                worker.kill()
                self.assertEqual(-signal.SIGKILL, worker.wait(timeout=25))
                phase_count = len(current["phases"])
                retained_budget = current["budget"]
                with self.assertRaisesRegex(agent_work.UnfinishedPhaseError, "close this job"):
                    flow.start()
                with self.assertRaisesRegex(agent_work.UnfinishedPhaseError, "close this job"):
                    flow.validate()
                with self.assertRaisesRegex(agent_work.UnfinishedPhaseError, "close this job"):
                    self.call_main("exec", "--job", job["id"], "--state-dir", str(state.root),
                                   "--", sys.executable, "-c", "print('must not run')")
                blocked = state.read(job["id"])
                self.assertEqual(phase_count, len(blocked["phases"]))
                self.assertEqual(retained_budget, blocked["budget"])
                with mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(0, flow.close())
                closed = self.assert_clean_closed(state, job["id"])
                self.assertTrue(agent_work.runtime.verified(neighbor))
                self.assertTrue(agent_work.runtime.members(neighbor["pid"]))
                test_phases = [phase for phase in closed["phases"] if phase["phase"] == "test"]
                self.assertEqual("interrupted", test_phases[-1]["state"])
                self.assertEqual(130, test_phases[-1]["exit_code"])
                released_phase = json.loads(phase_journal.read_text())
                self.assertEqual("released", released_phase["status"])
                for field in ("owner", "lease", "identity", "pid", "start"):
                    self.assertEqual(active_phase[field], released_phase[field])
            finally:
                if worker.poll() is None:
                    worker.kill()
                    worker.wait()
                cli_log.close()
                agent_work.runtime.stop(neighbor_record, lease="neighbor-generation")
                self.assertFalse(agent_work.runtime.members(neighbor["pid"]))
                self.cleanup_and_preserve(state, "cancel-cycle", (job, "cancel-owner"))

    def test_profile_change_cannot_disable_frozen_cleanup_hooks(self):
        with run_workspace("profile-change") as parent:
            try:
                state, flow, job = self.new_flow(parent, "profile-change", "profile-owner")
                with mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(0, flow.start())
                Path(job["profile"]).write_text('{"schema": 999}\n')
                self.assertEqual(0, flow.close())
                closed = self.assert_clean_closed(state, job["id"])
                self.assertEqual("closed", closed["state"])
            finally:
                self.cleanup_and_preserve(state, "profile-change", (job, "profile-owner"))

    def test_source_edit_after_start_uses_frozen_adapter_for_cleanup(self):
        with run_workspace("source-change") as parent:
            try:
                state, flow, job = self.new_flow(parent, "source-change", "source-owner",
                                                 freeze_source=True)
                with mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(0, flow.start())
                original_adapter = Path(job["profile"]).parent / "fixture_adapter.py"
                original_adapter.write_text("raise RuntimeError('edited after start')\n")
                self.assertEqual(0, flow.close())
                closed = self.assert_clean_closed(state, job["id"])
                self.assertNotEqual(original_adapter.parent, Path(closed["profile_source"]))
                self.assertIn("fixture_adapter.py", closed["source_manifest"])
            finally:
                self.cleanup_and_preserve(state, "source-change", (job, "source-owner"))

    def test_changed_frozen_source_is_rejected_before_any_hook_runs(self):
        with run_workspace("snapshot-tamper") as parent:
            try:
                state, flow, job = self.new_flow(parent, "snapshot-tamper", "snapshot-owner",
                                                 freeze_source=True)
                frozen_adapter = Path(job["profile_source"]) / "fixture_adapter.py"
                original = frozen_adapter.read_bytes()
                frozen_adapter.write_text("raise RuntimeError('tampered frozen source')\n")
                with mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity), \
                        self.assertRaisesRegex(RuntimeError, "Frozen profile source changed"):
                    flow.start()
                phases = state.read(job["id"])["phases"]
                self.assertEqual(["queue-up"], [phase["phase"] for phase in phases])
                self.assertTrue(all(not phase.get("supervisor_record") for phase in phases))
                frozen_adapter.write_bytes(original)
                self.assertEqual(0, flow.close())
            finally:
                self.cleanup_and_preserve(state, "snapshot-tamper", (job, "snapshot-owner"))

    def test_failed_cli_validation_invalidates_old_gate_and_closes_resources(self):
        with run_workspace("cli-failed-validation") as parent:
            try:
                state, _, job = self.new_flow(parent, "cli-failed-validation", "cli-fail-owner")
                current = state.read(job["id"])
                current.update(gate={"passed": True, "catalog_sha256": "stale"},
                               delivery={"passed": True})
                state.save(current)
                os.environ["AGENT_WORK_FIXTURE_MODE"] = "fail"
                rc = self.call_main("validate", "--job", job["id"], "--state-dir", str(state.root))
                self.assertEqual(1, rc)
                closed = self.assert_clean_closed(state, job["id"])
                self.assertFalse(closed["gate"]["passed"])
                self.assertIsNone(closed.get("delivery"))
                self.assertTrue(any("Product test command exit 7" in error
                                    for error in closed["gate"]["errors"]))
            finally:
                self.cleanup_and_preserve(state, "cli-failed-validation", (job, "cli-fail-owner"))

    def test_product_job_rejects_custom_state_dir_but_empty_close_releases_it(self):
        with run_workspace("product-custom-state") as parent:
            root = init_git_fixture(parent)
            profile_path, profile_data = profile(root)
            profile_data.pop("test_only")
            profile_path.write_text(json.dumps(profile_data, indent=2) + "\n")
            set_owner("product-state-owner")
            state = State(parent / "custom-state")
            job = state.create("product-custom-state", root, profile_path, profile_data)
            with self.assertRaisesRegex(RuntimeError, "single host registry"):
                self.call_main("start", "--job", job["id"], "--state-dir", str(state.root))
            untouched = state.read(job["id"])
            self.assertEqual([], untouched["phases"])
            self.assertEqual(0, agent_work.Flow(state, job["id"]).close())
            closed = state.read(job["id"])
            self.assertEqual("closed", closed["state"])
            self.assertTrue(closed["adapter"]["cleanup_verified"])
            self.assertEqual("No project hook or resource was opened", closed["adapter"]["cleanup_note"])

    def test_cli_exec_drains_real_child_output_and_records_exit_code(self):
        with run_workspace("cli-exec") as parent:
            try:
                state, flow, job = self.new_flow(parent, "cli-exec", "cli-exec-owner")
                with mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(0, flow.start())
                child = ("import sys; "
                         "[print(f'output-{index:04}') for index in range(4000)]; "
                         "print('stderr-drained', file=sys.stderr); sys.exit(7)")
                rc = self.call_main("exec", "--job", job["id"], "--state-dir", str(state.root),
                                    "--timeout", "20", "--", sys.executable, "-c", child)
                self.assertEqual(7, rc)
                current = state.read(job["id"])
                command = [phase for phase in current["phases"] if phase["phase"] == "command"][-1]
                self.assertEqual(7, command["exit_code"])
                self.assertEqual("failed", command["state"])
                output = Path(command["log"]).read_text()
                self.assertIn("output-0000", output)
                self.assertIn("output-3999", output)
                self.assertIn("stderr-drained", output)
                self.assertFalse(current["reservation_pending"])
                self.assertEqual(0, flow.close())
            finally:
                self.cleanup_and_preserve(state, "cli-exec", (job, "cli-exec-owner"))

    def test_cli_exec_resumes_capacity_queue_without_restarting_owned_stack(self):
        with run_workspace("cli-exec-queue") as parent:
            try:
                state, flow, job = self.new_flow(parent, "cli-exec-queue", "cli-exec-queue-owner")
                with mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(0, flow.start())
                marker = parent / "executed"
                argv = ("exec", "--job", job["id"], "--state-dir", str(state.root),
                        "--", sys.executable, "-c", "from pathlib import Path; Path(__import__('sys').argv[1]).write_text('ran')", str(marker))
                sample = deterministic_capacity()
                sample['system']['cpu_idle_percent'] = 0
                self.assertEqual(75, self.call_main(*argv, capacity_sample=lambda: sample))
                self.assertFalse(marker.exists())
                queued = state.read(job['id'])
                self.assertEqual('queued', queued['state'])
                self.assertTrue(queued['waiting_for_capacity'])
                up_count = sum(p['phase'] == 'up' for p in queued['phases'])
                with mock.patch.object(agent_work, "capacity", side_effect=deterministic_capacity):
                    self.assertEqual(0, self.call_main(*argv))
                current = state.read(job['id'])
                self.assertEqual('ran', marker.read_text())
                self.assertEqual('ready', current['state'])
                self.assertFalse(current['waiting_for_capacity'])
                self.assertEqual(up_count, sum(p['phase'] == 'up' for p in current['phases']))
                self.assertEqual(0, flow.close())
            finally:
                self.cleanup_and_preserve(state, "cli-exec-queue", (job, "cli-exec-queue-owner"))

    def test_source_reload_waits_for_growth_capacity_before_health(self):
        with run_workspace("source-reload-capacity") as parent:
            try:
                state, flow, job = self.new_flow(parent, "source-reload-capacity", "reload-owner")
                with mock.patch.object(agent_work, 'capacity', side_effect=deterministic_capacity):
                    self.assertEqual(0, flow.start())
                current = state.read(job['id'])
                original = agent_work.git_manifest(current['adapter']['repositories'])
                state.update_adapter(job['id'], served_source_manifest=original)
                repo = Path(current['adapter']['repositories']['fixture']['worktree'])
                (repo / 'reload-proof.txt').write_text('changed source')
                before = state.read(job['id'])
                sample = deterministic_capacity()
                sample['system']['cpu_idle_percent'] = 0
                with mock.patch.object(agent_work, 'capacity', return_value=sample):
                    self.assertEqual(75, flow.start())
                queued = state.read(job['id'])
                self.assertEqual('queued', queued['state'])
                self.assertEqual(len(before['phases']), len(queued['phases']))
                with mock.patch.object(agent_work, 'capacity', side_effect=deterministic_capacity):
                    self.assertEqual(0, flow.start())
                ready = state.read(job['id'])
                self.assertEqual('ready', ready['state'])
                self.assertEqual(['queue-up', 'health'], [p['phase'] for p in ready['phases'][-2:]])
                self.assertEqual(job['profile_data']['budgets']['up'], ready['budget'])
                self.assertFalse(ready['reservation_pending'])
                self.assertFalse(ready['waiting_for_capacity'])
                self.assertEqual(0, flow.close())
            finally:
                self.cleanup_and_preserve(state, "source-reload-capacity", (job, "reload-owner"))

    def test_failed_source_reload_keeps_the_job_for_a_retry(self):
        with run_workspace("source-reload-failure") as parent:
            try:
                state, flow, job = self.new_flow(parent, "source-reload-failure", "reload-failure-owner")
                with mock.patch.object(agent_work, 'capacity', side_effect=deterministic_capacity):
                    self.assertEqual(0, flow.start())
                current = state.read(job['id'])
                state.update_adapter(job['id'],
                                     served_source_manifest=agent_work.git_manifest(current['adapter']['repositories']))
                repo = Path(current['adapter']['repositories']['fixture']['worktree'])
                (repo / 'reload-proof.txt').write_text('changed source')
                original = agent_work.Flow.hook
                def refused(self, phase, *args, **kwargs):
                    return 1 if phase == 'health' else original(self, phase, *args, **kwargs)
                with mock.patch.object(agent_work.Flow, 'hook', refused):
                    self.assertEqual(1, self.call_main("start", "--job", job["id"], "--state-dir", str(state.root)))
                kept = state.read(job['id'])
                self.assertEqual('ready', kept['state'])
                self.assertNotIn('close', [p['phase'] for p in kept['phases']])
                self.assertEqual(0, self.call_main("start", "--job", job["id"], "--state-dir", str(state.root)))
                self.assertEqual('ready', state.read(job['id'])['state'])
                self.assertEqual(0, flow.close())
            finally:
                self.cleanup_and_preserve(state, "source-reload-failure", (job, "reload-failure-owner"))

    def test_pending_restart_readmits_and_invalidates_gate_with_unchanged_source(self):
        with run_workspace('pending-restart') as parent:
            try:
                state, flow, job = self.new_flow(parent, 'pending-restart', 'pending-restart-owner')
                with mock.patch.object(agent_work, 'capacity', side_effect=deterministic_capacity):
                    self.assertEqual(0, flow.start())
                current = state.read(job['id'])
                state.update_adapter(job['id'], source_restart_pending=True,
                    served_source_manifest=agent_work.git_manifest(current['adapter']['repositories']))
                state.save(dict(state.read(job['id']), state='validated',
                                gate={'passed': True}, delivery={'passed': True}))
                with mock.patch.object(agent_work.Flow, 'hook', return_value=1) as health:
                    self.assertEqual(1, self.call_main('start', '--job', job['id'], '--state-dir', str(state.root)))
                    health.assert_called_once_with('health')
                kept = state.read(job['id'])
                self.assertEqual('validated', kept['state'])
                self.assertIsNone(kept['gate']); self.assertIsNone(kept['delivery'])
                self.assertTrue(kept['adapter']['source_restart_pending'])
                self.assertNotIn('close', [p['phase'] for p in kept['phases']])
                denied = deterministic_capacity(); denied['system']['cpu_idle_percent'] = 0
                with mock.patch.object(agent_work.Flow, 'hook') as health:
                    self.assertEqual(75, self.call_main('start', '--job', job['id'], '--state-dir', str(state.root),
                                                       capacity_sample=lambda: denied))
                    health.assert_not_called()
                self.assertEqual('queued', state.read(job['id'])['state'])
                original = agent_work.Flow.hook
                def verified(self, phase, *args, **kwargs):
                    rc = original(self, phase, *args, **kwargs)
                    if phase == 'health' and rc == 0:
                        state.update_adapter(job['id'], source_restart_pending=False)
                    return rc
                with mock.patch.object(agent_work.Flow, 'hook', verified):
                    self.assertEqual(0, self.call_main('start', '--job', job['id'], '--state-dir', str(state.root)))
                ready = state.read(job['id'])
                self.assertEqual('ready', ready['state'])
                self.assertIsNone(ready['gate']); self.assertIsNone(ready['delivery'])
                self.assertFalse(ready['adapter']['source_restart_pending'])
                self.assertEqual(['queue-up', 'health'], [p['phase'] for p in ready['phases'][-2:]])
                self.assertEqual(0, flow.close())
            finally:
                self.cleanup_and_preserve(state, 'pending-restart', (job, 'pending-restart-owner'))

    def test_cli_exec_keeps_reservation_when_phase_cleanup_is_denied(self):
        with run_workspace("cli-exec-cleanup-denied") as parent:
            state, _, job = self.new_flow(parent, "cli-exec-cleanup-denied", "cli-exec-denied-owner")
            state.update_adapter(job["id"], prepared=True)
            current = state.read(job["id"])
            current["state"] = "ready"
            state.save(current)
            try:
                with mock.patch.object(agent_work.Flow, "hook", side_effect=PermissionError("survivors")), \
                        self.assertRaisesRegex(PermissionError, "survivors"):
                    self.call_main("exec", "--job", job["id"], "--state-dir", str(state.root),
                                   "--", sys.executable, "-c", "print('never')")
                retained = state.read(job["id"])
                self.assertEqual("cleanup_pending", retained["state"])
                self.assertTrue(retained["reservation_pending"])
                self.assertEqual(job["profile_data"]["budgets"]["test"], retained["budget"])
            finally:
                self.cleanup_and_preserve(state, "cli-exec-cleanup-denied",
                                          (job, "cli-exec-denied-owner"))

    def test_node_detached_browser_style_child_stays_in_registered_phase(self):
        with run_workspace('node-process-group') as parent:
            state, _, job = self.new_flow(parent, 'node-process-group', 'node-group-owner')
            profile_path = Path(job['profile'])
            data = job['profile_data']
            data['node_process_group'] = True
            profile_path.write_text(json.dumps(data))
            # Freeze the opted-in profile before any resource has been launched.
            job['profile_sha256'] = agent_work.digest(data)
            state.save(job)
            output = Path(job['root']) / 'browser-child.json'
            program = ("const cp=require('node:child_process'),fs=require('node:fs');"
                       "const c=cp.spawn(process.execPath,['-e','setTimeout(()=>{},60000)'],"
                       "{detached:true,stdio:'ignore'});c.unref();"
                       "const group=Number(cp.execFileSync('ps',['-p',String(c.pid),'-o','pgid=']).toString().trim());"
                       "fs.writeFileSync(process.argv[1],JSON.stringify({pid:c.pid,group}));")
            try:
                flow = agent_work.Flow(state, job['id'])
                self.assertEqual(0, flow.hook('command', ['node', '-e', program, str(output)]))
                phase = state.read(job['id'])['phases'][-1]
                record = json.loads(Path(phase['supervisor_record']).read_text())
                child = json.loads(output.read_text())
                self.assertEqual(record['pid'], child['group'])
                self.assertEqual([], agent_work.runtime.members(record['pid']))
                self.assertEqual('released', record['status'])
                self.assertEqual(0, flow.close())
            finally:
                self.cleanup_and_preserve(state, 'node-process-group', (job, 'node-group-owner'))

    def test_fifteen_real_lifecycles_queue_at_two_services_and_clean(self):
        with run_workspace("benchmark-15-real-lifecycles") as parent:
            state_dir = parent / "state"
            audit_path = state_dir / "benchmark-audit.json"
            root = init_git_fixture(parent)
            profile_path, profile_data = profile(root)
            state = State(state_dir)
            jobs = []
            for index in range(15):
                set_owner(f"benchmark-owner-{index}")
                jobs.append(state.create(f"benchmark-{index:02}", root, profile_path, profile_data))
            context = multiprocessing.get_context("spawn")
            starts = [context.Event() for _ in jobs]
            allow_close = context.Event()
            output = context.Queue()
            workers = [context.Process(target=benchmark_worker,
                       args=(str(state_dir), job["id"], f"benchmark-owner-{index}", str(audit_path),
                             starts[index], allow_close, output))
                       for index, job in enumerate(jobs)]
            try:
                for worker in workers:
                    worker.start()
                ready = [output.get(timeout=30) for _ in workers]
                self.assertEqual({"ready"}, {item[0] for item in ready})
                starts[0].set()
                starts[1].set()
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if audit_path.exists() and json.loads(audit_path.read_text()).get("max_active") == 2:
                        break
                    time.sleep(0.05)
                else:
                    self.fail("first two real fixture services did not become active")
                for start in starts[2:]:
                    start.set()
                deadline = time.monotonic() + 30
                queued_snapshot = []
                while time.monotonic() < deadline:
                    current = state.all()
                    queued_snapshot = [job for job in current if job["state"] == "queued"]
                    preclose = [event for event in json.loads(audit_path.read_text())["events"]
                                if event["event"] == "preclose"]
                    if len(queued_snapshot) == 13 and len(preclose) >= 2:
                        break
                    time.sleep(0.05)
                else:
                    self.fail(f"expected 13 queued real lifecycles, found {len(queued_snapshot)}")
                agent_work.runtime.atomic_json(state_dir / "benchmark-before-close.json", {
                    "fixture": "tooling-only-http-sqlite",
                    "capacity_mode": "deterministic-test-only",
                    "active_services": json.loads(audit_path.read_text())["active"],
                    "queued_jobs": [job["id"] for job in queued_snapshot],
                })
                allow_close.set()
                results = [output.get(timeout=150) for _ in workers]
                self.assertEqual({"result"}, {item[0] for item in results})
                for worker in workers:
                    worker.join(20)
                    self.assertEqual(0, worker.exitcode)
                outcomes = [item[1] for item in results]
                self.assertTrue(all(item["error"] is None for item in outcomes), outcomes)
                self.assertTrue(all((item["start"], item["validate"], item["close"]) == (0, 0, 0)
                                    for item in outcomes), outcomes)
                final_jobs = sorted(state.all(), key=lambda item: item["task"])
                audit = json.loads(audit_path.read_text())
                started = {event["job_id"]: event for event in audit["events"]
                           if event["event"] == "service_started"}
                self.assertEqual(2, audit["max_active"])
                self.assertEqual([], audit["active"])
                self.assertEqual(15, len(started))
                self.assertEqual(15, len([event for event in audit["events"] if event["event"] == "preclose"]))
                generations = set()
                for job in final_jobs:
                    self.assertEqual("closed", job["state"])
                    self.assertTrue(job["gate"]["passed"], job["gate"]["errors"])
                    self.assertTrue(job["adapter"]["cleanup_verified"])
                    evidence = json.loads(Path(job["adapter"]["test_evidence"]).read_text())
                    observation = evidence["fixture_observation"]
                    self.assertEqual([observation["generation"]], observation["items"])
                    server = json.loads(Path(job["adapter"]["server_record"]).read_text())
                    event = started[job["id"]]
                    self.assertEqual(job["owner"], event["supervisor_owner"])
                    self.assertEqual(server["identity"], event["supervisor_identity"])
                    self.assertEqual(server["pid"], event["supervisor_pid"])
                    self.assertEqual(server["start"], event["supervisor_start"])
                    generations.add(observation["generation"])
                self.assertEqual(15, len(generations))
                comparison = work_report.compare(final_jobs[0], final_jobs[1])
                self.assertTrue(comparison["comparable"], comparison["reasons"])
                summary = {
                    "fixture": "tooling-only-http-sqlite",
                    "capacity_mode": "deterministic-test-only-max-2",
                    "jobs": len(final_jobs),
                    "max_active_services": audit["max_active"],
                    "queued_before_first_close": len(queued_snapshot),
                    "all_closed_clean": all(job["state"] == "closed" and job["adapter"]["cleanup_verified"]
                                                for job in final_jobs),
                    "baseline_repeat": comparison,
                }
                agent_work.runtime.atomic_json(state_dir / "benchmark-summary.json", summary)
            finally:
                allow_close.set()
                for start in starts:
                    start.set()
                for worker in workers:
                    if worker.is_alive():
                        worker.join(3)
                    if worker.is_alive():
                        worker.kill()
                        worker.join()
                cleanup_errors = []
                for index, job in enumerate(jobs):
                    set_owner(f"benchmark-owner-{index}")
                    try:
                        if state.read(job["id"])["state"] != "closed":
                            agent_work.Flow(state, job["id"]).close()
                    except BaseException as exc:
                        cleanup_errors.append(f"{job['id']}: {type(exc).__name__}: {exc}")
                preserve_run(state_dir, "benchmark-15-real-lifecycles")
                if cleanup_errors:
                    active_error = sys.exception()
                    message = "benchmark cleanup failures: " + "; ".join(cleanup_errors)
                    if active_error is None:
                        self.fail(message)
                    active_error.add_note(message)


if __name__ == "__main__":
    unittest.main()
