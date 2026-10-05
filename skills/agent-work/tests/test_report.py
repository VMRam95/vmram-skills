from __future__ import annotations

import unittest

from support import deep_copy
import work_report


def completed(identifier: str, seconds: float = 2.0) -> dict:
    return {
        "id": identifier,
        "task": "fixture <task>",
        "project": "agent-work-tooling-fixture",
        "state": "closed",
        "created": 1,
        "closed": 2,
        "budget": {"ram_gb": 0, "cpu_cores": 0},
        "wait_reason": "",
        "profile_sha256": "profile",
        "phases": [{"phase": "test", "state": "passed", "seconds": seconds, "exit_code": 0}],
        "gate": {"passed": True, "cases": 2, "catalog_sha256": "catalog", "errors": []},
        "versions": {"fixture": {"head": "abc"}},
    }


class ReportTests(unittest.TestCase):
    def test_compare_requires_equivalent_complete_runs(self):
        first = completed("a" * 32, 2)
        second = completed("b" * 32, 1)
        result = work_report.compare(first, second)
        self.assertTrue(result["comparable"], result["reasons"])
        self.assertEqual(-1, result["phases"][0]["delta_seconds"])
        partial = deep_copy(second)
        partial["gate"]["catalog_sha256"] = "subset"
        rejected = work_report.compare(first, partial)
        self.assertFalse(rejected["comparable"])
        self.assertIn("Different discovered case inventory", rejected["reasons"])

    def test_html_escapes_fixture_values_and_exposes_gate(self):
        document = work_report.render([completed("c" * 32)])
        self.assertIn("fixture &lt;task&gt;", document)
        self.assertNotIn("fixture <task>", document)
        self.assertIn("PASS", document)
        self.assertIn("2.00s", document)

    def test_report_keeps_failed_timings_without_aggregating_incompatible_runs(self):
        passed, failed = completed("a" * 32, 100), completed("b" * 32, 1)
        failed["gate"]["passed"] = False
        failed["phases"][0].update(state="failed", exit_code=1)
        document = work_report.render([passed, failed])
        self.assertIn("100.00s", document)
        self.assertIn("1.00s", document)
        self.assertIn("PENDING / FAIL", document)
        self.assertNotIn("Median closed run", document)
        self.assertFalse(work_report.compare(passed, failed)["comparable"])

    def test_compare_rejects_different_tested_product_versions(self):
        first = completed("d" * 32)
        second = completed("e" * 32)
        second["versions"]["fixture"]["head"] = "def"
        result = work_report.compare(first, second)
        self.assertFalse(result["comparable"])
        self.assertTrue(result["versions_changed"])
        self.assertIn("Different tested product versions", result["reasons"])

    def test_compare_rejects_different_runtime_toolchains(self):
        first, second = completed('a' * 32), completed('b' * 32)
        first['adapter'] = {'toolchain': {'node_version': 'v24.5.0'}}
        second['adapter'] = {'toolchain': {'node_version': 'v24.6.0'}}
        result = work_report.compare(first, second)
        self.assertFalse(result['comparable'])
        self.assertIn('Different runtime toolchain', result['reasons'])

    def test_different_lane_branches_preserve_comparable_product_and_base_identity(self):
        first, second = completed("a" * 32), completed("b" * 32)
        for job, branch in ((first, "agent-work/first"), (second, "agent-work/second")):
            job["versions"]["fixture"].update(branch=branch, base="develop",
                                              base_sha="base", content_sha256="content")
        self.assertTrue(work_report.compare(first, second)["comparable"])
        for field in ("base_sha", "content_sha256"):
            with self.subTest(field=field):
                changed = deep_copy(second)
                changed["versions"]["fixture"][field] = "different"
                result = work_report.compare(first, changed)
                self.assertFalse(result["comparable"])
                self.assertTrue(result["versions_changed"])

    def test_compare_rejects_a_recovered_failed_phase(self):
        first, second = completed("a" * 32), completed("b" * 32)
        second["phases"].insert(0, {"phase": "test", "state": "failed", "seconds": 1, "exit_code": 1})
        result = work_report.compare(first, second)
        self.assertFalse(result["comparable"])
        self.assertIn("A run contains failed or interrupted phases", result["reasons"])

    def test_compare_rejects_a_tool_change_within_the_run(self):
        first, second = completed("a" * 32), completed("b" * 32)
        second["phases"][0]["core_sha256"] = "v1"
        second["phases"].append({"phase": "close", "state": "passed", "seconds": 1,
                                  "exit_code": 0, "core_sha256": "v2"})
        result = work_report.compare(first, second)
        self.assertFalse(result["comparable"])
        self.assertIn("Tool implementation changed within a run", result["reasons"])

    def test_compare_rejects_different_numbers_of_complete_attempts(self):
        first, second = completed("a" * 32), completed("b" * 32)
        second["phases"].append(dict(second["phases"][0]))
        result = work_report.compare(first, second)
        self.assertFalse(result["comparable"])
        self.assertIn("Different measured phase execution inventory", result["reasons"])


if __name__ == "__main__":
    unittest.main()
