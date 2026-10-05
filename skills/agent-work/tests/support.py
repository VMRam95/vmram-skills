"""Shared helpers for agent-work tests; contains no product adapter behavior."""
from __future__ import annotations

import copy
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid


TESTS = Path(__file__).resolve().parent
SKILL = TESTS.parent
SCRIPTS = SKILL / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from validation import digest  # noqa: E402


def clean_evidence() -> dict:
    catalog = [
        {"suite": "unit", "id": "unit-1"},
        {"suite": "integration", "id": "integration-1"},
    ]
    return {
        "schema": 1,
        "scope": "full",
        "catalog": catalog,
        "catalog_sha256": digest(catalog),
        "required_suites": ["unit", "integration"],
        "suites": [
            {"name": "unit", "exit_code": 0, "errors": [], "skipped": 0, "pending": 0},
            {"name": "integration", "exit_code": 0, "errors": [], "skipped": 0, "pending": 0},
        ],
        "results": [
            {"suite": case["suite"], "id": case["id"], "status": "passed", "attempts": 1, "errors": []}
            for case in catalog
        ],
        "errors": [],
        "aborted": False,
    }


def profile(root: Path, *, freeze_source: bool = False) -> tuple[Path, dict]:
    adapter = TESTS / "fixture_adapter.py"
    if freeze_source:
        shutil.copy2(adapter, root / adapter.name)
        adapter = "{profile_dir}/fixture_adapter.py"
    hooks = {
        name: ["{python}", str(adapter), name]
        for name in ("prepare", "up", "health", "discover", "test", "close", "verify")
    }
    data = {
        "schema": 1,
        "test_only": True,
        "project": "agent-work-tooling-fixture",
        "hooks": hooks,
        "budgets": {
            "up": {"ram_gb": 0.01, "cpu_cores": 0.01},
            "test": {"ram_gb": 0.001, "cpu_cores": 0.001},
        },
        "reserve": {"ram_gb": 0, "cpu_cores": 0, "disk_gb": 0},
        "timeouts": {name: 20 for name in hooks},
    }
    if freeze_source:
        data["source_files"] = ["fixture_adapter.py"]
    path = root / "fixture-profile.json"
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path, data


def deterministic_capacity() -> dict:
    return {
        "observed_epoch": time.time(),
        "system": {
            "memory_effective_available_gb": 256.0,
            "logical_cpus": 256,
            "cpu_idle_percent": 100.0,
            "swapout_delta": 0,
        },
        "capacity": {"io_contention": False},
    }


def init_git_fixture(parent: Path) -> Path:
    root = parent / "project"
    remote = parent / "origin.git"
    root.mkdir()
    subprocess.run(["git", "init", "--initial-branch=main", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Agent Work Fixture"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.invalid"], check=True)
    (root / "tracked.txt").write_text("tooling fixture\n")
    (root / ".gitignore").write_text("artifacts/\n")
    subprocess.run(["git", "-C", str(root), "add", "tracked.txt", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "test: initialize fixture"], check=True, capture_output=True)
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", str(remote)], check=True)
    subprocess.run(["git", "-C", str(root), "push", "-u", "origin", "main"], check=True, capture_output=True)
    return root


def set_owner(value: str | None = None) -> str:
    value = value or "agent-work-test-" + uuid.uuid4().hex
    os.environ["AGENT_LOCAL_OWNER"] = value
    return value


def deep_copy(value):
    return copy.deepcopy(value)


def _artifact_root() -> Path:
    configured = os.environ.get("AGENT_WORK_TEST_ARTIFACTS")
    root = (Path(configured) if configured else Path(tempfile.gettempdir()) / "agent-work-test-artifacts").resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def _unique_artifact(label: str) -> Path:
    if not label or Path(label).name != label:
        raise ValueError("Artifact label must be one safe path component")
    parent = _artifact_root() / label
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = parent / f"{time.time_ns()}-{os.getpid()}-{uuid.uuid4().hex}"
    target.mkdir(mode=0o700)
    return target


def _write_run_status(path: Path, status: str) -> None:
    temporary = path / ".run-status.tmp"
    temporary.write_text(json.dumps({"status": status, "updated": time.time()}, indent=2) + "\n")
    os.replace(temporary, path / "run-status.json")


@contextmanager
def run_workspace(label: str):
    """Create evidence in its durable final location before starting resources."""
    target = _unique_artifact(label)
    _write_run_status(target, "active")
    try:
        yield target
    except BaseException:
        _write_run_status(target, "failed")
        raise
    else:
        _write_run_status(target, "complete")


def preserve_run(state_dir: Path, label: str) -> Path | None:
    state_dir = Path(state_dir).resolve()
    destination = _artifact_root()
    if destination == state_dir or destination in state_dir.parents:
        return state_dir.parent
    target = _unique_artifact(label)
    shutil.copytree(state_dir, target, dirs_exist_ok=True)
    return target
