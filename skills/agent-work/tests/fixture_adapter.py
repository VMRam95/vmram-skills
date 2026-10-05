#!/usr/bin/env python3
"""Local tooling fixture: supervised HTTP + SQLite, never a product adapter."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from urllib.request import Request, urlopen


SCRIPTS = Path(os.environ.get("AGENT_LOCAL_WORK_SCRIPTS",
                              Path(__file__).resolve().parents[1] / "scripts"))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import process_runtime as runtime  # noqa: E402
from validation import digest  # noqa: E402


def paths():
    job_path = Path(os.environ["AGENT_WORK_JOB"])
    folder = job_path.parent / "fixture"
    folder.mkdir(exist_ok=True)
    return job_path, folder


def read_job(job_path: Path) -> dict:
    return json.loads(job_path.read_text())


def update_job(job_path: Path, **changes) -> dict:
    with job_path.with_name('adapter.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        job = read_job(job_path)
        job.update(changes)
        runtime.atomic_json(job_path, job)
        return job


def fixture_paths(folder: Path) -> dict[str, Path]:
    return {
        "db": folder / "fixture.sqlite3",
        "port": folder / "port.json",
        "server": folder / "server.json",
        "server_log": folder / "server.log",
        "catalog": folder / "catalog.json",
        "evidence": folder / "test-evidence.json",
    }


def audit(event: str, **payload) -> None:
    path_value = os.environ.get("AGENT_WORK_FIXTURE_AUDIT")
    if not path_value:
        return
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = json.loads(path.read_text()) if path.exists() else {
            "fixture": "tooling-only-http-sqlite",
            "capacity_mode": "deterministic-test-only",
            "active": [],
            "max_active": 0,
            "events": [],
        }
        identifier = payload.get("job_id")
        if event == "service_started":
            if identifier in data["active"]:
                raise RuntimeError("Duplicate fixture service start")
            data["active"].append(identifier)
            data["max_active"] = max(data["max_active"], len(data["active"]))
        elif event == "service_stopped":
            if identifier not in data["active"]:
                raise RuntimeError("Fixture service stop has no matching start")
            data["active"].remove(identifier)
        data["events"].append({"event": event, "at": time.time(), **payload,
                               "active_count": len(data["active"])})
        runtime.atomic_json(path, data)


def prepare() -> int:
    job_path, folder = paths()
    job = read_job(job_path)
    item = fixture_paths(folder)
    with sqlite3.connect(item["db"]) as db:
        db.execute("create table items (value text not null unique)")
    adapter = dict(job.get("adapter", {}))
    adapter.update({
        "prepared": True,
        "fixture_kind": "tooling-only-http-sqlite",
        "db": str(item["db"]),
        "port_evidence": str(item["port"]),
        "server_record": str(item["server"]),
        "repositories": {"fixture": {"worktree": job["root"], "base": "main"}},
    })
    update_job(job_path, adapter=adapter)
    return 0


def up() -> int:
    job_path, folder = paths()
    job = read_job(job_path)
    item = fixture_paths(folder)
    item["port"].unlink(missing_ok=True)
    record = runtime.launch(
        item["server"],
        [sys.executable, "-B", str(Path(__file__).resolve()), "serve", str(item["db"]), str(item["port"])],
        job["root"],
        lease=job["generation"],
        log=item["server_log"],
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        owner_id=job["owner"],
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if item["port"].is_file():
            port = json.loads(item["port"].read_text())["port"]
            if runtime.ready(item["server"], port, owner_id=job["owner"]) and runtime.verified(record):
                audit("service_started", job_id=job["id"], generation=job["generation"], port=port,
                      supervisor_identity=record["identity"], supervisor_pid=record["pid"],
                      supervisor_start=record["start"], supervisor_owner=record["owner"])
                return 0
        time.sleep(0.05)
    return 1


def request(method: str, path: str, body: dict | None = None):
    _, folder = paths()
    port = json.loads(fixture_paths(folder)["port"].read_text())["port"]
    payload = json.dumps(body).encode() if body is not None else None
    req = Request(f"http://127.0.0.1:{port}{path}", data=payload, method=method,
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=5) as response:
        return response.status, json.loads(response.read())


def health() -> int:
    status, data = request("GET", "/health")
    return 0 if status == 200 and data == {"status": "ok", "items": 0} else 1


def discover() -> int:
    job_path, folder = paths()
    item = fixture_paths(folder)
    catalog = [{"suite": "fixture", "id": "http-sqlite-roundtrip"},
               {"suite": "fixture", "id": "isolated-inventory"}]
    runtime.atomic_json(item["catalog"], {"schema": 1, "catalog": catalog, "required_suites": ["fixture"]})
    job = read_job(job_path)
    adapter = dict(job["adapter"])
    adapter["catalog_evidence"] = str(item["catalog"])
    adapter["test_evidence"] = str(item["evidence"])
    update_job(job_path, adapter=adapter)
    return 0


def test() -> int:
    job_path, folder = paths()
    job = read_job(job_path)
    item = fixture_paths(folder)
    mode = os.environ.get("AGENT_WORK_FIXTURE_MODE", "pass")
    if mode == "block":
        time.sleep(60)
        return 0
    discovered = json.loads(item["catalog"].read_text())
    catalog = discovered["catalog"]
    status, created = request("POST", "/items", {"value": job["generation"]})
    read_status, listed = request("GET", "/items")
    clean = status == 201 and read_status == 200 and created["value"] == job["generation"]
    clean = clean and listed == {"items": [job["generation"]]}
    evidence_catalog = catalog[:1] if mode == "subset" else catalog
    results = [{"suite": c["suite"], "id": c["id"], "status": "passed", "attempts": 1, "errors": []}
               for c in evidence_catalog]
    exit_code = 7 if mode == "fail" or not clean else 0
    if exit_code:
        results[0].update(status="failed", errors=["intentional fixture failure"])
    evidence = {
        "schema": 1,
        "scope": "full",
        "catalog": evidence_catalog,
        "catalog_sha256": digest(evidence_catalog),
        "required_suites": ["fixture"],
        "suites": [{"name": "fixture", "exit_code": exit_code, "errors": [] if not exit_code else ["fixture"],
                    "skipped": 0, "pending": 0}],
        "results": results,
        "errors": [],
        "aborted": False,
        "fixture_observation": {"generation": job["generation"], "items": listed["items"],
                                "port": json.loads(item["port"].read_text())["port"]},
    }
    runtime.atomic_json(item["evidence"], evidence)
    return exit_code


def close() -> int:
    job_path, folder = paths()
    job = read_job(job_path)
    item = fixture_paths(folder)
    if item["server"].exists():
        runtime.stop(item["server"], lease=job["generation"], validate=lambda: read_job(job_path),
                     owner_id=job["owner"])
        audit("service_stopped", job_id=job["id"], generation=job["generation"])
    item["db"].unlink(missing_ok=True)
    item["port"].unlink(missing_ok=True)
    return 0


def verify() -> int:
    job_path, folder = paths()
    item = fixture_paths(folder)
    released = (not item["server"].exists() or
                json.loads(item["server"].read_text()).get("status") == "released")
    clean = released and not item["db"].exists() and not item["port"].exists()
    job = read_job(job_path)
    adapter = dict(job["adapter"])
    adapter["cleanup_verified"] = clean
    adapter["preserved_evidence"] = [str(item["catalog"]), str(item["evidence"]), str(item["server_log"])]
    update_job(job_path, adapter=adapter)
    return 0 if clean else 1


class Handler(BaseHTTPRequestHandler):
    db_path: Path

    def log_message(self, format, *args):  # noqa: A003
        return

    def send_json(self, status: int, value: dict):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        with sqlite3.connect(self.db_path) as db:
            values = [row[0] for row in db.execute("select value from items order by value")]
        if self.path == "/health":
            self.send_json(200, {"status": "ok", "items": len(values)})
        elif self.path == "/items":
            self.send_json(200, {"items": values})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path != "/items":
            self.send_json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        value = json.loads(self.rfile.read(length))["value"]
        with sqlite3.connect(self.db_path) as db:
            db.execute("insert into items(value) values (?)", (value,))
        self.send_json(201, {"value": value})


def serve(db_path: str, port_path: str) -> int:
    Handler.db_path = Path(db_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    runtime.atomic_json(Path(port_path), {"host": "127.0.0.1", "port": server.server_address[1]})
    server.serve_forever()
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        return 2
    if sys.argv[1] == "serve":
        return serve(sys.argv[2], sys.argv[3])
    actions = {"prepare": prepare, "up": up, "health": health, "discover": discover,
               "test": test, "close": close, "verify": verify}
    return actions[sys.argv[1]]()


if __name__ == "__main__":
    raise SystemExit(main())
