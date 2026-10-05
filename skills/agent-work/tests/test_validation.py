from __future__ import annotations

import json
import unittest
from pathlib import Path
import subprocess
import sys
import tempfile

from support import clean_evidence, deep_copy, init_git_fixture
import agent_work
from validation import git_manifest, validate_tests


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


class GitManifestTests(unittest.TestCase):
    def test_pinned_base_survives_remote_advance_but_rejects_invalid_sha(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            root = init_git_fixture(parent)
            base_sha = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "origin/main"], text=True).strip()
            repositories = {"fixture": {"worktree": str(root), "base": "main", "base_sha": base_sha}}
            before = git_manifest(repositories)

            peer = parent / "peer"
            subprocess.run(["git", "clone", "--branch", "main", str(parent / "origin.git"), str(peer)],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", str(peer), "config", "user.name", "Peer Fixture"], check=True)
            subprocess.run(["git", "-C", str(peer), "config", "user.email", "peer@example.invalid"], check=True)
            (peer / "peer.txt").write_text("remote advanced\n")
            subprocess.run(["git", "-C", str(peer), "add", "peer.txt"], check=True)
            subprocess.run(["git", "-C", str(peer), "commit", "-m", "test: advance remote"],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", str(peer), "push", "origin", "main"],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "fetch", "origin"], check=True, capture_output=True)

            self.assertEqual(before, git_manifest(repositories))
            self.assertNotEqual(base_sha, git_manifest({
                "fixture": {"worktree": str(root), "base": "main"}
            })["fixture"]["base_sha"])
            for invalid in (base_sha[:12], "f" * len(base_sha)):
                with self.subTest(invalid=invalid), self.assertRaisesRegex(RuntimeError, "Pinned base"):
                    git_manifest({"fixture": {
                        "worktree": str(root), "base": "main", "base_sha": invalid,
                    }})

    def test_existing_unrelated_commit_is_reported_as_non_ancestor(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = init_git_fixture(Path(temporary).resolve())
            tree = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"], text=True).strip()
            unrelated = subprocess.check_output(
                ["git", "-C", str(root), "commit-tree", tree], input="unrelated base\n", text=True).strip()
            manifest = git_manifest({"fixture": {
                "worktree": str(root), "base": "main", "base_sha": unrelated,
            }})
            self.assertEqual(unrelated, manifest["fixture"]["base_sha"])
            self.assertFalse(manifest["fixture"]["base_is_ancestor"])


if __name__ == "__main__":
    unittest.main()
