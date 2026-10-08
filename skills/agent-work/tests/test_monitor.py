from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from support import SCRIPTS
import mac_agent_capacity
import managed_resources


def write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class ManagedResourcesTests(unittest.TestCase):
    def test_active_index_ignores_broken_history_and_rejects_linked_jobs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            identifier = 'd' * 32
            history = root / 'jobs' / ('e' * 32) / 'job.json'
            history.parent.mkdir(parents=True)
            history.write_text('{broken closed history')
            write_json(root / 'active.json', [identifier])
            path = root / 'jobs' / identifier / 'job.json'
            value = {'schema': 1, 'id': identifier, 'owner': 'owner', 'generation': 'generation',
                     'state': 'queued', 'phases': [], 'adapter': {}, 'budget': {}}
            write_json(path, value)
            result = managed_resources.snapshot({}, root)
            self.assertEqual(0, result['journal_errors'])
            self.assertEqual(1, result['queued_jobs'])
            outside = root / 'outside.json'
            write_json(outside, value)
            path.unlink()
            path.symlink_to(outside)
            result = managed_resources.snapshot({}, root)
            self.assertEqual(1, result['journal_errors'])
            self.assertEqual([], result['jobs'])

    def test_exact_owner_generation_records_are_attributed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            identifier = "a" * 32
            records = root / "records"
            phase = records / "phase.json"
            manager = records / "manager.json"
            foreign = records / "foreign.json"
            write_json(phase, {"identity": "phase-id", "owner": "owner-a",
                               "lease": "generation-a", "pid": 101, "status": "active"})
            write_json(manager, {"identity": "manager-id", "owner": "manager-a",
                                 "lease": "lease-a", "pid": 201, "status": "active"})
            write_json(foreign, {"identity": "foreign-id", "owner": "manager-a",
                                 "lease": "generation-a", "pid": 301, "status": "active"})
            job = {
                "schema": 1, "id": identifier, "owner": "owner-a",
                "generation": "generation-a", "task": "CAS4958", "project": "tmf",
                "state": "testing", "reservation_pending": True,
                "budget": {"ram_gb": 4, "cpu_cores": 3},
                "phases": [{"state": "running", "supervisor_record": str(phase)}],
                "adapter": {"manager_owner_id": "manager-a", "lease_token": "lease-a",
                            "process_records": [str(manager), str(foreign)]},
            }
            write_json(root / "jobs" / identifier / "job.json", job)
            processes = {
                101: {"rss_kb": 1048576, "cpu": 3.0},
                102: {"rss_kb": 524288, "cpu": 2.0},
                201: {"rss_kb": 262144, "cpu": 1.0},
            }
            members = {101: [101, 102], 201: [201], 301: [301]}
            with patch.object(managed_resources.ProcessTable, "__init__", lambda self: None), \
                 patch.object(managed_resources.ProcessTable, "members",
                              lambda self, pid: members.get(pid, [])), \
                 patch.object(managed_resources.ProcessTable, "verified",
                              lambda self, record: record["identity"] != "foreign-id"):
                result = managed_resources.snapshot(processes, root)
            self.assertEqual(1, result["active_jobs"])
            self.assertEqual(0, result["queued_jobs"])
            self.assertEqual({"jobs": 1, "ram_gb": 4, "cpu_cores": 3},
                             result["pending_growth"])
            self.assertEqual(3, result["jobs"][0]["registered_processes"])
            self.assertEqual(1.75, result["jobs"][0]["rss_gb"])
            self.assertEqual(6.0, result["jobs"][0]["cpu_percent"])
            self.assertEqual(1, result["jobs"][0]["unverified_records"])

    def test_absent_and_partial_journals_do_not_break_sampling(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            self.assertEqual([], managed_resources.snapshot({}, root)["jobs"])
            broken = root / "jobs" / ("b" * 32) / "job.json"
            broken.parent.mkdir(parents=True)
            broken.write_text("{")
            result = managed_resources.snapshot({}, root)
            self.assertEqual([], result["jobs"])
            self.assertEqual(1, result["journal_errors"])

    def test_queue_is_reported_without_charging_unreserved_growth(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            identifier = "c" * 32
            write_json(root / "jobs" / identifier / "job.json", {
                "schema": 1, "id": identifier, "owner": "owner-c",
                "generation": "generation-c", "task": "queued", "project": "tmf",
                "state": "queued", "waiting_for_capacity": True,
                "reservation_pending": False, "budget": {"ram_gb": 8, "cpu_cores": 4},
                "phases": [], "adapter": {},
            })
            result = managed_resources.snapshot({}, root)
            self.assertEqual(0, result["active_jobs"])
            self.assertEqual(1, result["queued_jobs"])
            self.assertEqual({"jobs": 0, "ram_gb": 0, "cpu_cores": 0},
                             result["pending_growth"])


class CapacityTests(unittest.TestCase):
    def test_pending_growth_reduces_menu_capacity_only(self):
        args = argparse.Namespace(agent_budget_gb=4, reserve_gb=8,
                                  agent_cpu_cores=1.5, cpu_reserve_cores=2,
                                  logical_cpus=14)
        capacity = mac_agent_capacity.compute_capacity(
            36, 50, 70, [], args, load1=2, uninterruptible_threads=0,
            pending_ram_gb=6, pending_cpu_cores=3,
        )
        self.assertEqual(2, capacity["physical_additional_agents_conservative"])
        self.assertEqual(1, capacity["additional_agents_conservative"])
        self.assertEqual(6, capacity["pending_ram_gb"])
        self.assertEqual(3, capacity["pending_cpu_cores"])

    def test_plugin_uses_package_sampler_and_shows_jobs_and_growth(self):
        path = SCRIPTS / "agent-watch.30s.py"
        spec = importlib.util.spec_from_file_location("agent_watch_plugin_test", path)
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)
        self.assertEqual((SCRIPTS / "mac_agent_capacity.py").resolve(),
                         Path(plugin.cap.__file__).resolve())
        sample = {
            "system": {"logical_cpus": 14, "load_average": [1, 2, 3],
                       "uninterruptible_threads": 0, "runnable_threads": 1,
                       "cpu_idle_percent": 70, "memory_effective_available_gb": 20,
                       "memory_total_gb": 36},
            "capacity": {"additional_agents_conservative": 1,
                         "limiting_resource": "memoria", "load_pressure": "normal"},
            "agent_totals": {"count": 1, "rss_gb": 1, "cpu_percent": 2},
            "codeagentswarm_overhead": {"rss_gb": 0.2},
            "agents": [],
            "managed_resources": {
                "active_jobs": 1, "queued_jobs": 2, "journal_errors": 0,
                "pending_growth": {"jobs": 1, "ram_gb": 6, "cpu_cores": 2},
                "jobs": [{"project": "tmf", "task": "CAS4958", "state": "testing",
                          "waiting": False, "rss_gb": 1.5, "cpu_percent": 12}],
            },
        }
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(plugin.cap, "snapshot", return_value=sample), \
             patch.object(plugin, "STATE", Path(temporary) / "state"), \
             patch.object(plugin.subprocess, "run"):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                plugin.main()
        text = output.getvalue()
        self.assertIn("agent-work: 1 activos · 2 en cola", text)
        self.assertIn("Crecimiento reservado: 6.0 GB · 2.0 CPU", text)
        self.assertIn("tmf/CAS4958", text)

    def test_plugin_turns_yellow_then_red_by_disk_and_notifies_each_change(self):
        path = SCRIPTS / "agent-watch.30s.py"
        spec = importlib.util.spec_from_file_location("agent_watch_plugin_disk", path)
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)

        def sample(free_gb):
            args = argparse.Namespace(agent_budget_gb=2.5, reserve_gb=8, agent_cpu_cores=1.5,
                                      cpu_reserve_cores=2, logical_cpus=14)
            capacity = mac_agent_capacity.compute_capacity(
                36, 80, 90, [], args, load1=1, uninterruptible_threads=0,
                disk_free_gb=free_gb, disk_total_gb=926)
            capacity["load_pressure"] = "normal"
            return {
                "system": {"logical_cpus": 14, "load_average": [1, 1, 1],
                           "uninterruptible_threads": 0, "runnable_threads": 1,
                           "cpu_idle_percent": 90, "memory_effective_available_gb": 28,
                           "memory_total_gb": 36, "disk_free_gb": free_gb,
                           "disk_total_gb": 926, "disk_free_percent": free_gb / 9.26},
                "capacity": capacity, "agent_totals": {"count": 0, "rss_gb": 0, "cpu_percent": 0},
                "codeagentswarm_overhead": {"rss_gb": 0}, "agents": [], "managed_resources": {},
            }

        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(plugin, "STATE", Path(temporary) / "state"), \
             patch.object(plugin.subprocess, "run"), \
             patch.object(plugin, "notify") as notify:
            lines = []
            for free in (183, 93, 21):
                output = io.StringIO()
                with patch.object(plugin.cap, "snapshot", return_value=sample(free)), \
                     contextlib.redirect_stdout(output):
                    plugin.main()
                lines.append(output.getvalue())
        self.assertTrue(lines[0].startswith("🟢"))
        self.assertTrue(lines[1].startswith("🟡"))
        self.assertIn("Disco libre: 93 / 926 GiB (10%) · bajo", lines[1])
        self.assertTrue(lines[2].startswith("🔴 0"))
        self.assertIn("limita disco", lines[2])
        texts = [call.args[1] for call in notify.call_args_list]
        self.assertEqual(2, len(texts))
        self.assertIn("Disco bajo: 93 GiB", texts[0])
        self.assertIn("Disco en rojo: 21 GiB", texts[1])




class ProcessTableTests(unittest.TestCase):
    def test_one_query_retains_start_and_supervisor_identity(self):
        runtime = managed_resources.runtime
        start = 'Thu Oct  8 21:03:00 2026'
        pid = 43210
        path = Path(runtime.__file__).resolve()
        output = (f'{pid} {pid} Ss {start} {path} supervise own-id --command-file fixture.json\n'
                  f'43211 {pid} S {start} node worker.js\n'
                  f'43212 {pid} Z {start} <defunct>\n'
                  f'43213 {pid} S {start} ps -Aww\n')
        with patch.object(runtime, 'ps_query', return_value=(0, output, 43213)) as query, \
             patch.object(managed_resources.os, 'getpid', return_value=90000), \
             patch.object(managed_resources.os, 'getpgrp', return_value=90000):
            table = managed_resources.ProcessTable()
            self.assertEqual(1, query.call_count)
            self.assertEqual(start, table.rows[pid][2])
            self.assertEqual([pid, 43211], table.members(pid))
            record = {'pid': pid, 'start': start, 'identity': 'own-id'}
            self.assertTrue(table.verified(record))
            for field, value in [('start', 'Thu Oct  8 21:03:01 2026'),
                                 ('identity', 'other-id'), ('pid', 43211), ('pid', 1)]:
                self.assertFalse(table.verified(dict(record, **{field: value})))
            with patch.object(managed_resources.os, 'getpgrp', return_value=pid):
                self.assertFalse(table.verified(record))
            del table.rows[pid]
            self.assertFalse(table.verified(record))
            self.assertEqual([43211], table.members(pid))

    def test_incomplete_duplicate_and_failed_tables_fail_closed(self):
        start = 'Thu Oct  8 21:03:00 2026'
        row = f'43210 43210 Ss {start} worker\n'
        for output in ('43210 43210 Ss\n', row + row):
            with self.subTest(output=output), \
                 patch.object(managed_resources.runtime, 'ps_query', return_value=(0, output, 43213)):
                with self.assertRaises(ValueError):
                    managed_resources.ProcessTable()
        with patch.object(managed_resources.runtime, 'ps_query', return_value=(1, '', 43213)):
            with self.assertRaises(managed_resources.subprocess.CalledProcessError):
                managed_resources.ProcessTable()

    def test_real_table_matches_runtime_for_this_process_group(self):
        import os
        import managed_resources
        table = managed_resources.ProcessTable()
        group = os.getpgrp()
        self.assertIn(os.getpid(), table.members(group))
        self.assertFalse(table.queries & set(table.members(group)))
        self.assertEqual(managed_resources.runtime.process_start(os.getpid()), table.rows[os.getpid()][2])
        self.assertFalse(table.verified({"pid": os.getpid(), "start": table.rows[os.getpid()][2],
                                         "identity": "not-a-supervisor"}))

if __name__ == "__main__":
    unittest.main()
