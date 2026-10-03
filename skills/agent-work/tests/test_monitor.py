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
            with patch.object(managed_resources.runtime, "members",
                              side_effect=lambda pid: members.get(pid, [])), \
                 patch.object(managed_resources.runtime, "verified",
                              side_effect=lambda record: record["identity"] != "foreign-id"):
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


if __name__ == "__main__":
    unittest.main()
