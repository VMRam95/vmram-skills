#!/usr/bin/env python3
"""Recorded local process groups; shared by project adapters and tunnel skills."""
import argparse
import errno
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import uuid

# Keep handles until verified closure, so in-process callers reap their children.
# Durable journals remain authoritative when the launching CLI itself exits.
_HANDLES = {}


def owner():
    for key in ('AGENT_LOCAL_OWNER', 'TMF_LANE_OWNER_ID', 'CODEX_THREAD_ID',
                'CODEX_SESSION_ID', 'CLAUDE_CODE_SESSION_ID', 'CODEAGENTSWARM_TERMINAL_ID', 'TERM_SESSION_ID'):
        value = os.environ.get(key, '').strip()
        if value:
            return key.lower() + ':' + value
    raise RuntimeError('Set a stable AGENT_LOCAL_OWNER for this session')


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(data, handle, indent=2)
            handle.write('\n')
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def ps_query(args):
    # Bounded retries for transient kernel query delays; never assume a timeout means no process.
    for attempt in range(3):
        query = subprocess.Popen(['ps', *args], stdout=subprocess.PIPE, text=True)
        try:
            output, _ = query.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            query.kill()
            query.communicate(timeout=3)
            if attempt == 2:
                raise
            continue
        return query.returncode, output, query.pid


def process_start(pid):
    rc, output, _ = ps_query(['-p', str(pid), '-o', 'lstart='])
    return output.strip() if rc == 0 else ''


def members(pgid):
    # The query inherits our group: counting it keeps a finished supervisor alive.
    rc, output, query_pid = ps_query(['-Ao', 'pid=,pgid=,stat='])
    if rc:
        raise subprocess.CalledProcessError(rc, 'ps', output)
    return [int(p[0]) for line in output.splitlines()
            if len(p := line.split()) == 3 and int(p[1]) == pgid
            and int(p[0]) != query_pid and not p[2].startswith('Z')]


def verified(record):
    pid = record.get('pid', 0)
    if not isinstance(pid, int) or pid <= 1 or pid == os.getpid() or not record.get('start'):
        return False
    if process_start(pid) != record['start']:
        return False
    try:
        if os.getpgid(pid) != pid or pid == os.getpgrp():
            return False
        rc, args, _ = ps_query(['-p', str(pid), '-o', 'args='])
        if rc:
            return False
    except (ProcessLookupError, subprocess.CalledProcessError):
        return False
    # Existing journals must survive installing the canonical helper. These are
    # exact installation paths, never a process-name or PID-only match.
    paths = {str(Path(__file__).resolve()), str(Path.home() / '.codeagentswarm/sandbox/agent-local-work/scripts/process_runtime.py')}
    return any(f'{path} supervise {record["identity"]} ' in args for path in paths)


def ready(path, port=None, *, owner_id=None):
    record = json.loads(Path(path).read_text())
    if record.get('owner') != (owner_id or owner()) or record.get('status') != 'active' or not verified(record):
        return False
    if port is None:
        return True
    result = subprocess.run(['lsof', '-nP', '-t', f'-iTCP:{port}', '-sTCP:LISTEN'],
                            capture_output=True, text=True, timeout=10)
    if result.returncode not in (0, 1) or result.stderr.strip():
        raise RuntimeError('Cannot identify listener')
    listeners = {int(p) for p in result.stdout.split()}
    return bool(listeners) and listeners <= set(members(record['pid'])) and verified(record)


def launch(path, command, cwd, *, lease=None, log=None, env=None, owner_id=None):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise RuntimeError('Process record or parent is linked; preserve it')
    expected_owner = owner_id or owner()
    if path.exists():
        old = json.loads(path.read_text())
        if old.get('owner') != expected_owner or old.get('lease') != lease:
            raise RuntimeError('Process record belongs to another owner/generation')
        if verified(old) or (old.get('pid') and members(old['pid'])):
            raise RuntimeError('Previous process group still exists; stop it first')
    identity = uuid.uuid4().hex
    # Journal exists before the supervisor is allowed to execute the command.
    record = {'owner': expected_owner, 'lease': lease, 'identity': identity,
              'worktree': str(Path(cwd).resolve()), 'status': 'preparing',
              'resources': [{'kind': 'process', 'record': str(path.absolute()), 'status': 'preparing'}]}
    atomic_json(path, record)
    log_path = (Path(log) if log else path.with_suffix('.log')).absolute()
    if log_path.resolve() != log_path:
        raise RuntimeError('Process log or parent must not be linked')
    fd = os.open(log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'a') as output:
        proc = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                                 'supervise', identity, str(path.absolute()), *command],
                                cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=output, stderr=output, start_new_session=True)
        _HANDLES[proc.pid] = proc
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            published = json.loads(path.read_text())
            if published.get('identity') != identity or published.get('status') == 'released':
                raise RuntimeError('Process registration was cancelled')
            if published.get('pid') == proc.pid and published.get('status') == 'active':
                record = published
                break
            time.sleep(.05)
        else:
            raise RuntimeError('Cannot register supervisor start identity')
    except BaseException:
        # Cancellation and publication use one lock. If birth has not published,
        # release the journal before stopping our held Popen, so the supervisor
        # cannot start the command later. Once active, leave the exact group and
        # journal recoverable by stop; killing only the leader could orphan children.
        cancel_prebirth = False
        with path.with_suffix('.publish.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            published = json.loads(path.read_text())
            if (published.get('identity') == identity and
                    published.get('status') == 'preparing' and not published.get('pid')):
                published['status'] = 'released'
                published['resources'][0]['status'] = 'released'
                atomic_json(path, published)
                cancel_prebirth = True
            elif (published.get('identity') == identity and
                  published.get('status') == 'released' and not published.get('pid')):
                cancel_prebirth = True
        if cancel_prebirth:
            if proc.poll() is None:
                proc.kill()  # The released journal prevents command birth.
            proc.wait()
            _HANDLES.pop(proc.pid, None)
        raise
    return record


def stop(path, *, lease=None, validate=lambda: None, grace=3, owner_id=None):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise RuntimeError('Process record or parent is linked; preserve it')
    record = json.loads(path.read_text())
    if record.get('owner') != (owner_id or owner()) or record.get('lease') != lease:
        raise RuntimeError('Process record belongs to another owner/generation')
    if record.get('status') == 'released':
        return
    pid = record.get('pid')
    if not pid:
        # Registration and cancellation share an exact-journal lock. A late
        # supervisor sees released and cannot execute the resource command.
        with path.with_suffix('.publish.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            validate()
            current = json.loads(path.read_text())
            if (current.get('owner'),current.get('lease'),current.get('identity')) != (record.get('owner'),lease,record.get('identity')):
                raise RuntimeError('Process generation changed during registration')
            if not current.get('pid') and current.get('status')=='preparing':
                current['status']='released';current['resources'][0]['status']='released'
                atomic_json(path,current)
                return
            record=current;pid=record.get('pid')
        if not pid:
            raise RuntimeError('Incomplete process registration; inspect before recovery')
    for sig in (signal.SIGTERM, signal.SIGKILL):
        validate()
        if not members(pid):
            break
        if not verified(record):
            if not members(pid):
                break
            raise RuntimeError('Unverified/reused process group; no signal sent')
        try:
            os.killpg(pid, sig)
        except OSError as exc:
            # A naturally finished group can disappear after verification. macOS
            # may return EPERM as well as ESRCH for this race. A surviving group
            # still retains its claim; never retry a denial against another PID.
            if exc.errno not in (errno.ESRCH, errno.EPERM) or members(pid):
                raise
            break
        deadline = time.monotonic() + grace
        while members(pid) and time.monotonic() < deadline:
            time.sleep(.1)
    if members(pid):
        raise RuntimeError('Recorded process group did not stop')
    handle = _HANDLES.pop(pid, None)
    if handle is not None:
        handle.wait(timeout=grace)
    validate()
    record['status'] = 'released'
    record['resources'][0]['status'] = 'released'
    atomic_json(path, record)


def supervise(identity, path, command):
    # Hold the identity-bearing leader until TERM-resistant children also exit.
    signal.signal(signal.SIGTERM, lambda *_: None)
    path = Path(path)
    with path.with_suffix('.publish.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        record = json.loads(path.read_text())
        if record.get('identity') != identity or record.get('status')=='released':
            return 1
        if record.get('status')=='preparing' and not record.get('pid'):
            record.update(pid=os.getpid(),start=process_start(os.getpid()),status='active')
            if not record['start']: return 1
            record['resources'][0]['status']='active'
            atomic_json(path,record)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        record = json.loads(Path(path).read_text())
        if record.get('identity') != identity:
            return 1
        if record.get('pid') == os.getpid() and record.get('status') == 'active':
            break
        time.sleep(.05)
    else:
        return 1
    child = subprocess.Popen(command)
    while child.poll() is None or any(p != os.getpid() for p in members(os.getpgrp())):
        time.sleep(.1)
    return child.returncode


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'supervise':
        return supervise(sys.argv[2], sys.argv[3], sys.argv[4:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'stop', 'check'))
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--cwd', type=Path, default=Path.cwd())
    parser.add_argument('--lease')
    parser.add_argument('--port', type=int)
    argv = sys.argv[1:]
    split = argv.index('--') if '--' in argv else len(argv)
    args = parser.parse_args(argv[:split])
    command = argv[split + 1:]
    args.record = args.record.absolute()
    if args.record.resolve() != args.record or args.record.suffix != '.json':
        parser.error('Use an unlinked .json record in the task artifacts')
    if args.action == 'check':
        return 0 if ready(args.record, args.port) else 1
    args.record.parent.mkdir(parents=True, exist_ok=True)
    with args.record.with_suffix('.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if args.action == 'stop':
            stop(args.record, lease=args.lease)
        else:
            if not command:
                parser.error('start needs -- command')
            launch(args.record, command, args.cwd, lease=args.lease)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f'[local-process] {exc}' if isinstance(exc, RuntimeError) else
              '[local-process] Operation failed; keep private record for diagnosis', file=sys.stderr)
        sys.exit(1)
