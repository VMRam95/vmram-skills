"""Bounded read-only attribution from the host agent-work journal."""
import json
import math
from pathlib import Path
import subprocess
import time

import process_runtime as runtime


TERMINAL_STATES = {"closed", "cancelled"}


def empty(note=None, errors=0):
    return {
        "jobs": [],
        "active_jobs": 0,
        "queued_jobs": 0,
        "pending_jobs": 0,
        "pending_ram_gb": 0,
        "pending_cpu_cores": 0,
        "pending_growth": {"jobs": 0, "ram_gb": 0, "cpu_cores": 0},
        "journal_errors": errors,
        "observed_epoch": time.time(),
        "note": note or "Only exact verified registered process groups are attributed; physical usage remains authoritative.",
    }


def finite_budget(job):
    budget = job.get("budget") or {}
    values = []
    for field in ("ram_gb", "cpu_cores"):
        value = budget.get(field, 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            return 0, 0, False
        values.append(value)
    return values[0], values[1], True


def record_specs(job):
    """Return journal paths with the only owner/generation pairs they may use."""
    specs = []
    owner, generation = job.get("owner"), job.get("generation")
    for phase in job.get("phases") or []:
        if not isinstance(phase, dict) or phase.get("state") not in ("running", "registering"):
            continue
        if phase.get("supervisor_record"):
            specs.append((phase["supervisor_record"], {(owner, generation)}))
    adapter = job.get("adapter") or {}
    manager = (adapter.get("manager_owner_id"), adapter.get("lease_token"))
    core = (owner, generation)
    allowed = {pair for pair in (core, manager) if all(pair)}
    for item in adapter.get("process_records") or []:
        if isinstance(item, str):
            specs.append((item, allowed))
    return specs


def read_record(raw_path):
    path = Path(raw_path).absolute()
    if path.resolve() != path or not path.is_file():
        raise ValueError("record is absent or linked")
    record = json.loads(path.read_text())
    if not isinstance(record, dict):
        raise ValueError("record is not an object")
    return record


def inspect_job(job, processes):
    unknown = 0
    pids = set()
    seen = set()
    for raw_path, allowed in record_specs(job):
        if raw_path in seen:
            continue
        seen.add(raw_path)
        try:
            record = read_record(raw_path)
            if record.get("status") in ("released", "finished"):
                continue
            identity = record.get("identity")
            if (not isinstance(identity, str) or not identity or
                    (record.get("owner"), record.get("lease")) not in allowed):
                unknown += 1
                continue
            pid = record.get("pid")
            members = runtime.members(pid) if isinstance(pid, int) and pid > 1 else []
            if members and runtime.verified(record):
                pids.update(members)
            elif members:
                unknown += 1
        except (OSError, ValueError, KeyError, json.JSONDecodeError,
                RuntimeError, TypeError, subprocess.SubprocessError):
            unknown += 1
    observed = [processes[pid] for pid in pids if pid in processes]
    pending = job.get("reservation_pending") is True
    queued = job.get("state") == "queued" or bool(job.get("waiting_for_capacity"))
    ram, cpu, valid_budget = finite_budget(job)
    if not valid_budget:
        unknown += 1
        ram = cpu = 0
    return {
        "id": str(job.get("id") or "")[:32],
        "task": str(job.get("task") or "")[:120],
        "project": str(job.get("project") or "")[:120],
        "state": str(job.get("state") or "unknown")[:40],
        "waiting": queued,
        "registered_processes": len(pids),
        "rss_gb": round(sum(item.get("rss_kb", 0) for item in observed) / (1024 ** 2), 3),
        "cpu_percent": round(sum(item.get("cpu", 0) for item in observed), 1),
        "unverified_records": unknown,
        "pending_growth": pending,
        "reserved_growth": {
            "ram_gb": ram if pending else 0,
            "cpu_cores": cpu if pending else 0,
        },
    }


def snapshot(processes=None, state_root=None):
    root = Path(state_root or Path.home() / ".local/state/agent-work").absolute()
    processes = processes or {}
    if not root.exists():
        return empty("Host agent-work journal is absent; physical sampling is still valid.")
    try:
        linked = root.resolve() != root
    except OSError:
        return empty("Host agent-work journal could not be resolved; physical sampling is still valid.", errors=1)
    if linked:
        return empty("Host agent-work journal is linked and was not read.", errors=1)
    try:
        index=root/'active.json'
        if index.is_file():
            if index.resolve()!=index.absolute():raise ValueError('Linked active registry')
            ids=json.loads(index.read_text())
            if not isinstance(ids,list) or any(not isinstance(i,str) or len(i)!=32 or any(c not in '0123456789abcdef' for c in i) for i in ids):
                raise ValueError('Invalid active registry')
            paths=[root/'jobs'/i/'job.json' for i in ids]
        else:paths = sorted((root / "jobs").glob("*/job.json"))
    except (OSError,ValueError,json.JSONDecodeError):
        return empty("Host agent-work journal could not be listed; physical sampling is still valid.", errors=1)
    jobs = []
    journal_errors = 0
    for path in paths:
        try:
            if path.resolve() != path.absolute():
                raise ValueError('Linked job journal')
            job = json.loads(path.read_text())
            if (not isinstance(job, dict) or job.get("schema") != 1 or
                    job.get("id") != path.parent.name or not job.get("owner") or
                    not job.get("generation")):
                raise ValueError("invalid job identity")
            if job.get("state") in TERMINAL_STATES:
                continue
            jobs.append(inspect_job(job, processes))
        except (OSError, ValueError, KeyError, json.JSONDecodeError, RuntimeError, TypeError):
            journal_errors += 1
    pending = [job for job in jobs if job["pending_growth"]]
    ram = sum(job["reserved_growth"]["ram_gb"] for job in pending)
    cpu = sum(job["reserved_growth"]["cpu_cores"] for job in pending)
    queued = sum(job["waiting"] for job in jobs)
    result = empty(errors=journal_errors)
    result.update(
        jobs=jobs,
        active_jobs=len(jobs) - queued,
        queued_jobs=queued,
        pending_jobs=len(pending),
        pending_ram_gb=round(ram, 3),
        pending_cpu_cores=round(cpu, 3),
        pending_growth={"jobs": len(pending), "ram_gb": round(ram, 3),
                        "cpu_cores": round(cpu, 3)},
    )
    return result
