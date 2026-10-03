from __future__ import annotations

import json
import unittest
from pathlib import Path
import subprocess
import sys
import tempfile

from support import clean_evidence, deep_copy
import agent_work
from validation import validate_tests


class StrictCatalogueTests(unittest.TestCase):
    def assert_rejected(self, evidence, fragment: str):
        gate = validate_tests(evidence)
        self.assertFalse(gate["passed"])
        self.assertTrue(any(fragment in error for error in gate["errors"]), gate["errors"])

    def test_clean_full_catalogue_passes(self):
        gate = validate_tests(clean_evidence())
        self.assertTrue(gate["passed"], gate["errors"])
        self.assertEqual(2, gate["cases"])
        self.assertEqual(2, gate["suites"])

    def test_rejects_skipped_case_count(self):
        evidence = clean_evidence()
        evidence["suites"][0]["skipped"] = 1
        self.assert_rejected(evidence, "skipped")

    def test_rejects_run_errors(self):
        evidence = clean_evidence()
        evidence["errors"] = ["collection failed"]
        self.assert_rejected(evidence, "Run has errors")

    def test_rejects_missing_case(self):
        evidence = clean_evidence()
        evidence["results"].pop()
        self.assert_rejected(evidence, "Case inventory differs")

    def test_rejects_flaky_retry(self):
        evidence = clean_evidence()
        evidence["results"][0]["attempts"] = 2
        self.assert_rejected(evidence, "not a clean pass")

    def test_boolean_schema_and_attempt_count_are_not_integers(self):
        evidence = clean_evidence()
        evidence['schema'] = True
        self.assert_rejected(evidence, 'schema=1')
        evidence = clean_evidence()
        evidence['results'][0]['attempts'] = True
        self.assert_rejected(evidence, 'not a clean pass')

    def test_rejects_failed_suite_and_case(self):
        evidence = deep_copy(clean_evidence())
        evidence["suites"][0]["exit_code"] = 1
        evidence["results"][0]["status"] = "failed"
        gate = validate_tests(evidence)
        self.assertFalse(gate["passed"])
        self.assertTrue(any("Suite failed" in error for error in gate["errors"]))
        self.assertTrue(any("not a clean pass" in error for error in gate["errors"]))

    def test_profile_rejects_invalid_timeout_reserve_and_wait_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "profile.json"
            base = {
                "schema": 1,
                "project": "validation-fixture",
                "hooks": {name: ["true"] for name in
                          ("prepare", "up", "health", "discover", "test", "close", "verify")},
                "budgets": {phase: {"ram_gb": 1, "cpu_cores": 1} for phase in ("up", "test")},
                "reserve": {"ram_gb": 1, "cpu_cores": 1, "disk_gb": 1},
                "timeouts": {"test": 10},
            }
            for mutate in (
                lambda p: p["timeouts"].update(test=0),
                lambda p: p["reserve"].update(ram_gb=True),
            ):
                candidate = deep_copy(base)
                mutate(candidate)
                path.write_text(json.dumps(candidate))
                with self.assertRaises((RuntimeError, ValueError)):
                    agent_work.load_profile(path)
            state_dir = Path(temporary).resolve() / "state"
            result = subprocess.run(
                [sys.executable, str(agent_work.HERE / "agent_work.py"), "status",
                 "--state-dir", str(state_dir), "--wait", "-1"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("finite nonnegative", result.stderr)


if __name__ == "__main__":
    unittest.main()
