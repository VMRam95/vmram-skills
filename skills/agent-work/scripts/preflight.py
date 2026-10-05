#!/usr/bin/env python3
"""Inspect explicit Git/workspace scopes without traversing caches or changing resources."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

CACHES = ('node_modules', '.next', '.turbo', '__pycache__', 'obj',
          'Library/Artifacts', 'Library/Bee', 'Library/BurstCache',
          'Library/PackageCache', 'Library/ShaderCache')


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=20)
    if result.returncode != 0:
        # Do not echo commands, argv or environment containing possible secrets.
        raise RuntimeError(f'{args[0]} inspection failed (exit {result.returncode})')
    return result.stdout


def scope(value):
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_dir() or path in {Path('/'), Path('/Users'), Path('/Applications'),
                                    Path('/Library'), Path.home(), Path.home().parent}:
        raise ValueError('Use an exact repository or workspace, not a broad system/home root')
    return path


def worktrees(repo):
    common = run('git', '-C', str(repo), 'rev-parse', '--path-format=absolute', '--git-common-dir').strip()
    raw = run('git', '-C', str(repo), 'worktree', 'list', '--porcelain', '-z')
    result = []
    current = None
    for field in raw.split('\0'):
        key, _, value = field.partition(' ')
        if key == 'worktree':
            current = {'root': value, 'main': not result, 'locked': False, 'prunable': False}
            result.append(current)
        elif current is not None and key in ('locked', 'prunable'):
            current[key] = True
        elif current is not None and key in ('branch', 'HEAD'):
            current[key] = value
    return common, result


def candidates(root):
    if not root.is_dir() or root.is_symlink():
        return []
    bases = [root]
    for name in ('apps', 'packages', 'scripts'):
        parent = root / name
        if parent.is_dir() and not parent.is_symlink():
            bases.extend(p for p in parent.iterdir() if p.is_dir() and not p.is_symlink()
                         and p.name not in CACHES and not p.name.startswith('.'))
    found = []
    for base in bases:
        for name in CACHES:
            path = base / name
            # Presence only: do not du/walk dependencies or follow linked trees.
            if path.exists() or path.is_symlink():
                found.append({'path': str(path), 'symlink': path.resolve() != path,
                              'disposable_verified': False})
    return found


def activity(roots):
    ancestors = {os.getpid()}
    parents = dict(line.split() for line in run('ps', '-axo', 'pid=,ppid=').splitlines())
    pid = str(os.getpid())
    while parents.get(pid, '0') != '0' and parents[pid] not in {str(p) for p in ancestors}:
        pid = parents[pid]
        ancestors.add(int(pid))
    with subprocess.Popen(['lsof', '-nP', '-Fpn'], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True) as probe:
        ancestors.add(probe.pid)
        try:
            output, error = probe.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            probe.kill()  # Only the probe created by this call, held as a Popen object.
            probe.communicate()
            raise RuntimeError('Open-file inspection timed out')
    if probe.returncode != 0 or error.strip():
        raise RuntimeError('Open-file inspection incomplete; inactivity not established')
    found = {str(root): set() for root in roots}
    pid = None
    for line in output.splitlines():
        if line.startswith('p'):
            pid = int(line[1:])
        elif line.startswith('n/') and pid not in ancestors:
            path = Path(line[1:])
            # Assign nested roots to the most specific registered worktree.
            matches = [root for root in roots if path == root or root in path.parents]
            if matches:
                found[str(max(matches, key=lambda p: len(p.parts)))].add(pid)
    return {root: sorted(pids) for root, pids in found.items()}


def record(path):
    if path.resolve() != path or path.stat().st_size > 1024 * 1024:
        raise ValueError('Linked or oversized resource record; inspect explicitly')
    text = path.read_text()
    data = json.loads(text) if path.suffix == '.json' else dict(
        line.split('=', 1) for line in text.splitlines() if '=' in line)
    if not isinstance(data, dict):
        raise ValueError('Resource record must be an object')
    safe = {key: data[key] for key in ('task', 'slug', 'ticket', 'slot', 'owner_id', 'owner',
                                     'anchor_pid', 'worktree', 'lane_dir', 'status', 'closed',
                                     'kind', 'name', 'context', 'namespace', 'id')
            if key in data and isinstance(data[key], (str, int, float, bool, type(None)))}
    resources = []
    for resource in data.get('resources', []):
        if not isinstance(resource, dict):
            raise ValueError('Resource entry must be an object')
        resources.append({key: resource[key] for key in ('kind', 'path', 'id', 'status')
                          if key in resource and isinstance(resource[key], (str, int, bool))})
    return {'record': str(path), 'fields': safe, 'resources': resources,
            'ownership_verified': False}


def records(directory):
    directory = scope(directory)
    return [record(path) for path in sorted([*directory.glob('*.json'), *directory.glob('*/owner')])]


def containers(roots):
    contexts = [c for c in run('docker', 'context', 'ls', '--format', '{{.Name}}').splitlines() if c]
    result = {'contexts_checked': [], 'contexts_unavailable': [], 'contexts_inactive': [],
              'remote_contexts_skipped': [], 'matching_containers': []}
    for context in contexts:
        try:
            config = json.loads(run('docker', 'context', 'inspect', context))
            endpoint = config[0]['Endpoints']['docker']['Host']
            if not endpoint.startswith('unix://'):
                result['remote_contexts_skipped'].append(context)
                continue
            # Docker Desktop's two aliases can remain configured while its VM is off.
            # Prove the known socket absent AND its app/VM processes absent; arbitrary
            # missing sockets, refused connections and inspection errors remain unknown.
            if desktop_inactive(endpoint) or colima_inactive(context, endpoint):
                result['contexts_inactive'].append(context)
                continue
            ids = run('docker', '--context', context, 'ps', '-q').split()
            data = json.loads(run('docker', '--context', context, 'inspect', *ids)) if ids else []
        except (OSError, RuntimeError, ValueError, KeyError, IndexError, subprocess.TimeoutExpired):
            # An offline context must not hide another context's running containers.
            result['contexts_unavailable'].append(context)
            continue
        result['contexts_checked'].append(context)
        for container in data:
            sources = [m.get('Source', '') for m in container.get('Mounts', [])]
            matching = [str(root) for root in roots if any(s and (
                Path(s) == root or root in Path(s).parents or Path(s) in root.parents) for s in sources)]
            if matching:
                result['matching_containers'].append({'context': context, 'id': container['Id'],
                                                     'roots': matching, 'ownership_verified': False})
    return result


def desktop_inactive(endpoint):
    if sys.platform != 'darwin':
        return False
    socket = Path.home() / '.docker/run/docker.sock'
    if socket.resolve() != socket or Path(endpoint[7:]).resolve() != socket:
        return False
    try:
        socket.stat()
    except FileNotFoundError:
        pass
    else:
        return False
    processes = [line.split(None, 1) for line in run('ps', '-axo', 'pid=,comm=').splitlines()]
    engines = {'com.docker.backend', 'com.docker.virtualization', 'com.docker.krun', 'com.docker.sailor'}
    if any('Docker.app/Contents/' in cmd or Path(cmd).name in engines for pid, cmd in processes):
        return False
    for pid, cmd in processes:
        if Path(cmd).name == 'com.apple.Virtualization.VirtualMachine' and not colima_vm(pid):
            return False  # A native VM without attribution could still be Docker's.
    try:
        socket.stat()  # Recheck after the native process snapshot.
    except FileNotFoundError:
        return True
    return False


def colima_inactive(context, endpoint):
    if sys.platform != 'darwin':
        return False
    if context == 'colima':
        profile = 'default'
    elif re.fullmatch(r'colima-[a-z0-9][a-z0-9._-]{0,48}', context):
        profile = context[len('colima-'):]
    else:
        return False
    socket = Path.home() / '.colima' / profile / 'docker.sock'
    disk = Path.home() / '.colima/_lima' / context / 'disk'
    if endpoint != 'unix://' + str(socket) or socket.resolve() != socket:
        return False

    def stopped():
        profiles = [json.loads(line) for line in run('colima', 'list', '--json').splitlines() if line]
        matches = [item for item in profiles if item.get('name') == profile]
        return len(matches) == 1 and matches[0].get('status') == 'Stopped'

    if not stopped():
        return False
    try:
        socket.lstat()
    except FileNotFoundError:
        pass
    else:
        return False
    if not disk.is_file() or disk.resolve() != disk:
        return False
    probe = subprocess.run(['lsof', '-nP', '-Fpn', str(disk)],
                           capture_output=True, text=True, timeout=20)
    if probe.returncode != 1 or probe.stdout.strip() or probe.stderr.strip():
        return False
    if not stopped() or socket.resolve() != socket:
        return False
    try:
        socket.lstat()
    except FileNotFoundError:
        return True
    return False


def colima_vm(pid):
    probe = subprocess.run(['lsof', '-nP', '-p', pid, '-Fn'],
                           capture_output=True, text=True, timeout=20)
    if probe.returncode or probe.stderr.strip():
        return False
    paths = [Path(line[1:]) for line in probe.stdout.splitlines() if line.startswith('n/')]
    lima = Path.home() / '.colima/_lima'
    if lima.resolve() != lima or any('com.docker.docker' in str(path) or '/.docker/' in str(path) for path in paths):
        return False
    disks = [path for path in paths if path.name == 'disk' and path.parent.parent == lima]
    if len(disks) != 1 or disks[0].resolve() != disks[0]:
        return False
    instance = disks[0].parent.name
    if instance != 'colima' and not instance.startswith('colima-'):
        return False
    profile = 'default' if instance == 'colima' else instance[len('colima-'):]
    profiles = [json.loads(line) for line in run('colima', 'list', '--json').splitlines() if line]
    if not any(item.get('name') == profile and item.get('status') == 'Running'
               and item.get('runtime') == 'docker' for item in profiles):
        return False
    context = instance
    config = json.loads(run('docker', 'context', 'inspect', context))
    expected = 'unix://' + str(Path.home() / '.colima' / profile / 'docker.sock')
    if config[0]['Endpoints']['docker']['Host'] != expected:
        return False
    run('docker', '--context', context, 'ps', '-q')
    return True


def inspect(args):
    report = {'mode': 'read-only', 'errors': [], 'worktrees': [], 'reservations': [], 'task_records': [],
              'docker': {'checked': False}, 'ownership_verified': False}
    scopes = []
    for value in args.repo:
        repo = scope(value)
        common, entries = worktrees(repo)
        for entry in entries:
            entry['git_common_dir'] = common
            if not any(w['root'] == entry['root'] for w in report['worktrees']):
                report['worktrees'].append(entry)
        scopes.append(repo)
    for value in args.workspace:
        root = scope(value)
        report['worktrees'].append({'root': str(root), 'git_common_dir': None, 'main': True,
                                    'locked': None, 'prunable': None})
        scopes.append(root)
    roots = [Path(w['root']) for w in report['worktrees']]
    for entry in report['worktrees']:
        root = Path(entry['root'])
        entry['exists'] = root.exists()
        entry['cache_candidates'] = candidates(root)
        entry['activity'] = 'unverified'
        artifacts = root / 'artifacts'
        if artifacts.is_dir() and not artifacts.is_symlink():
            # Exact journal names, at two bounded task depths; never walk caches/assets.
            paths = {path for pattern in ('*/local-resources.json', '*/*/local-resources.json',
                                          '*/*/pod.json', '*/*/container.json')
                     for path in artifacts.glob(pattern)}
            for path in sorted(paths):
                try:
                    report['task_records'].append(record(path))
                except (OSError, ValueError, TypeError) as exc:
                    report['errors'].append(f'Task record inspection failed: {type(exc).__name__}')
    try:
        opened = activity(roots)
        for entry in report['worktrees']:
            entry['open_file_pids'] = opened.get(entry['root'], [])
            entry['activity'] = 'open-files-found' if entry['open_file_pids'] else 'no-open-files-observed'
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        report['errors'].append(str(exc))
    for value in args.state_dir:
        try:
            report['reservations'].extend(records(value))
        except (OSError, ValueError, TypeError) as exc:
            report['errors'].append(f'Reservation inspection failed: {type(exc).__name__}')
    if args.docker:
        try:
            data = containers(roots)
            report['docker'] = {'checked': not data['contexts_unavailable'], **data}
            if data['contexts_unavailable']:
                report['errors'].append('Some local Docker contexts unavailable; Docker inspection incomplete')
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
            report['errors'].append(str(exc))
    report['disk_free_bytes'] = {str(root): shutil.disk_usage(root).free for root in scopes}
    report['next_action'] = 'Review candidates and reservations through the project manager; no deletion authorized'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', action='append', default=[])
    parser.add_argument('--workspace', action='append', default=[])
    parser.add_argument('--state-dir', action='append', default=[])
    parser.add_argument('--docker', action='store_true')
    args = parser.parse_args()
    if not args.repo and not args.workspace:
        parser.error('Provide at least one exact --repo or --workspace')
    try:
        report = inspect(args)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'mode': 'read-only', 'errors': [str(exc)]}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
