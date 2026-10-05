from __future__ import annotations

import binascii
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest import mock
import zlib

from support import init_git_fixture
import delivery
from validation import git_manifest


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)


def write_png(path: Path, width: int, height: int) -> None:
    row = b"\0" + b"\x36\x8a\xc7" * width
    data = b"\x89PNG\r\n\x1a\n"
    data += png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    data += png_chunk(b"IDAT", zlib.compress(row * height, 9))
    data += png_chunk(b"IEND", b"")
    path.write_bytes(data)


class DeliveryTests(unittest.TestCase):
    def test_failed_account_check_prevents_the_github_operation(self):
        error = subprocess.CalledProcessError(1, ['gh', 'auth', 'status'])
        with mock.patch.object(delivery.subprocess, 'check_output', side_effect=error) as command:
            with self.assertRaises(subprocess.CalledProcessError):
                delivery.github('api', 'repos/owner/project/pulls/7')
        command.assert_called_once_with(['gh', 'auth', 'status'], text=True, timeout=60)

    def case(self, parent: Path, *, width: int = 390, height: int = 844, prs=True, gate=True):
        root = init_git_fixture(parent)
        artifacts = root / "artifacts" / "delivery"
        artifacts.mkdir(parents=True)
        screenshot = artifacts / "mobile.png"
        write_png(screenshot, width, height)
        pr_list = ([{"repository": "fixture", "repo": "owner/project", "number": 7}] if prs else [])
        evidence = {
            "changed_repositories": ["fixture"],
            "prs": pr_list,
            "screenshots": [{
                "path": str(screenshot),
                "inspected": True,
                "demonstrates": "The complete tooling fixture flow at a mobile viewport",
                "sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
            }],
        }
        manifest_path = artifacts / "delivery.json"
        manifest_path.write_text(json.dumps(evidence, indent=2) + "\n")
        subprocess.run(["git", "-C", str(root), "add", "-f", "artifacts/delivery/mobile.png",
                        "artifacts/delivery/delivery.json"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-m", "test: add delivery evidence"],
                       check=True, capture_output=True)
        head = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        base_sha = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "origin/main"], text=True).strip()
        repositories = {"fixture": {"worktree": str(root), "base": "main", "base_sha": base_sha}}
        job = {
            "root": str(root),
            "gate": {"passed": gate, "errors": [] if gate else ["skipped cases"]},
            "adapter": {"repositories": repositories},
            "versions": git_manifest(repositories),
            "profile_data": {"github_login": "fixture-user", "mobile_first": True},
        }
        pull = {
            "state": "open",
            "base": {"ref": "main", "repo": {"full_name": "owner/project"}},
            "head": {"sha": head, "ref": "main"},
        }
        return job, manifest_path, pull, root

    def github_reads(self, pull):
        def response(*argv):
            if argv == ("auth", "status"):
                return "authenticated"
            if argv == ("api", "user"):
                return json.dumps({"login": "fixture-user"})
            if argv == ("api", "repos/owner/project/pulls/7"):
                return json.dumps(pull)
            raise AssertionError(f"unexpected gh read: {argv}")
        return response

    def test_matching_pr_local_version_and_real_mobile_png_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            job, manifest, pull, _ = self.case(Path(temporary).resolve())
            with mock.patch.object(delivery, "github", side_effect=self.github_reads(pull)):
                result = delivery.verify(job, manifest)
            self.assertTrue(result["passed"], result["errors"])

    def test_explicit_published_ref_can_certify_the_same_commit_from_an_acceptance_lane(self):
        with tempfile.TemporaryDirectory() as temporary:
            job, manifest, pull, _ = self.case(Path(temporary).resolve())
            # Preserve the already-tested local manifest, including its branch.
            original = json.loads(json.dumps(job['versions']))
            pull['head']['ref'] = 'feature/existing-pr'
            with mock.patch.object(delivery, 'github', side_effect=self.github_reads(pull)):
                self.assertFalse(delivery.verify(job, manifest)['passed'])
                for ref, expected in [('feature/existing-pr', True), ('another-pr', False), ('', False), (None, False)]:
                    evidence = json.loads(manifest.read_text())
                    evidence['prs'][0]['head_ref'] = ref
                    # Test evidence is normally outside product Git. Keep this
                    # fixture's tracked manifest constant by using a second file.
                    external = Path(temporary) / 'explicit-delivery.json'
                    external.write_text(json.dumps(evidence))
                    result = delivery.verify(job, external)
                    self.assertEqual(expected, result['passed'], result['errors'])
                self.assertEqual(original, job['versions'])
                evidence['prs'][0]['head_ref'] = pull['head']['ref']
                external.write_text(json.dumps(evidence))
                pull['head']['sha'] = '0' * 40
                self.assertFalse(delivery.verify(job, external)['passed'])

    def test_remote_base_advance_does_not_change_pinned_delivery_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            job, manifest, pull, root = self.case(parent)
            peer = parent / "peer"
            subprocess.run(["git", "clone", "--branch", "main", str(parent / "origin.git"), str(peer)],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", str(peer), "config", "user.name", "Peer Fixture"], check=True)
            subprocess.run(["git", "-C", str(peer), "config", "user.email", "peer@example.invalid"], check=True)
            (peer / "peer.txt").write_text("advance remote after validation\n")
            subprocess.run(["git", "-C", str(peer), "add", "peer.txt"], check=True)
            subprocess.run(["git", "-C", str(peer), "commit", "-m", "test: advance remote"],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", str(peer), "push", "origin", "main"],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "fetch", "origin"], check=True, capture_output=True)
            with mock.patch.object(delivery, "github", side_effect=self.github_reads(pull)):
                result = delivery.verify(job, manifest)
            self.assertTrue(result["passed"], result["errors"])

    def test_missing_pr_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            job, manifest, pull, _ = self.case(Path(temporary).resolve(), prs=False)
            with mock.patch.object(delivery, "github", side_effect=self.github_reads(pull)):
                result = delivery.verify(job, manifest)
            self.assertFalse(result["passed"])
            self.assertIn("Every declared changed repository requires its own matching PR", result["errors"])

    def test_wrong_pr_head_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            job, manifest, pull, _ = self.case(Path(temporary).resolve())
            pull["head"]["sha"] = "0" * 40
            with mock.patch.object(delivery, "github", side_effect=self.github_reads(pull)):
                result = delivery.verify(job, manifest)
            self.assertFalse(result["passed"])
            self.assertIn("PR head/base/state mismatch: fixture", result["errors"])

    def test_local_gate_with_skips_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            job, manifest, pull, _ = self.case(Path(temporary).resolve(), gate=False)
            with mock.patch.object(delivery, "github", side_effect=self.github_reads(pull)):
                result = delivery.verify(job, manifest)
            self.assertFalse(result["passed"])
            self.assertIn("A full clean local validation is required", result["errors"])

    def test_local_change_after_validation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            job, manifest, pull, root = self.case(Path(temporary).resolve())
            (root / "changed-after-validation.txt").write_text("changed\n")
            with mock.patch.object(delivery, "github", side_effect=self.github_reads(pull)):
                result = delivery.verify(job, manifest)
            self.assertFalse(result["passed"])
            self.assertIn("PR source differs from the exact version tested locally", result["errors"])
            self.assertIn("Product source must be clean and committed before testing and PR delivery", result["errors"])

    def test_desktop_only_png_is_rejected_for_mobile_first_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            job, manifest, pull, _ = self.case(Path(temporary).resolve(), width=1200, height=800)
            with mock.patch.object(delivery, "github", side_effect=self.github_reads(pull)):
                result = delivery.verify(job, manifest)
            self.assertFalse(result["passed"])
            self.assertIn("Mobile local flow evidence is required", result["errors"])


if __name__ == "__main__":
    unittest.main()
