"""Delivery evidence is a complete inventory, not a minimum passing count."""
import hashlib
import json
from pathlib import Path
import re
import subprocess


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def package_version():
    fingerprint = hashlib.sha256()
    for path in sorted(Path(__file__).parent.iterdir()):
        if path.is_file() and path.suffix in ('.py', '.mjs'):
            fingerprint.update(path.name.encode() + b'\0' + hashlib.sha256(path.read_bytes()).digest())
    return fingerprint.hexdigest()


def validate_tests(evidence):
    errors = []
    if type(evidence.get('schema')) is not int or evidence['schema'] != 1 or evidence.get('scope') != 'full':
        errors.append('A full schema=1 test run is required')
    catalog = evidence.get('catalog', [])
    results = evidence.get('results', [])
    suites = evidence.get('suites', [])
    required = evidence.get('required_suites', [])
    if not catalog or not required:
        errors.append('Required suites and the discovered case inventory cannot be empty')
    if len(required) != len(set(required)):
        errors.append('Duplicate required suite')
    expected = [(c.get('suite'), c.get('id')) for c in catalog]
    actual = [(c.get('suite'), c.get('id')) for c in results]
    for label, keys in [('catalog', expected), ('results', actual)]:
        if any(not s or not i for s, i in keys) or len(keys) != len(set(keys)):
            errors.append(f'Invalid or duplicate case identity in {label}')
    if set(expected) != set(actual):
        errors.append(f'Case inventory differs: missing={len(set(expected)-set(actual))}, extra={len(set(actual)-set(expected))}')
    names = [s.get('name') for s in suites]
    if len(names) != len(set(names)) or set(names) != set(required):
        errors.append('Executed suites differ from the required suite inventory')
    if set(s for s, _ in expected) != set(required):
        errors.append('Each required suite needs discovered cases; no unclaimed suite is allowed')
    for suite in suites:
        if type(suite.get('exit_code')) is not int or suite['exit_code'] != 0:
            errors.append(f"Suite failed or has no real exit code: {suite.get('name')}")
        if suite.get('errors') or suite.get('skipped', 0) or suite.get('pending', 0):
            errors.append(f"Suite has errors, skipped or pending cases: {suite.get('name')}")
    for case in results:
        if case.get('status') != 'passed' or type(case.get('attempts')) is not int or case['attempts'] != 1 or case.get('errors'):
            errors.append(f"Case is not a clean pass: {case.get('suite')}/{case.get('id')}")
    if evidence.get('errors') or evidence.get('aborted'):
        errors.append('Run has errors or was aborted')
    if evidence.get('catalog_sha256') != digest(catalog):
        errors.append('The discovered inventory hash is missing or changed')
    return {'passed': not errors, 'errors': errors, 'cases': len(catalog), 'suites': len(required),
            'catalog_sha256': digest(catalog)}


def git_manifest(repositories):
    """Hash WIP privately; never include diff contents or environment values."""
    manifest = {}
    for name, info in repositories.items():
        root = Path(info['worktree']).resolve()
        def git(*args):
            return subprocess.check_output(['git', '-C', str(root), *args], timeout=60,
                                           stderr=subprocess.PIPE)
        head = git('rev-parse', 'HEAD').decode().strip()
        branch = git('branch', '--show-current').decode().strip()
        patch = hashlib.sha256(git('diff', '--binary', 'HEAD'))
        content = hashlib.sha256()
        tracked = git('ls-files', '-z').split(b'\0')
        untracked = git('ls-files', '--others', '--exclude-standard', '-z').split(b'\0')
        for raw in sorted(p for p in untracked if p):
            path = root / raw.decode()
            if path.is_symlink():
                data = str(path.readlink()).encode()
            elif path.is_file():
                data = path.read_bytes()
            else:
                raise RuntimeError('Cannot fingerprint an untracked resource')
            patch.update(raw + b'\0' + hashlib.sha256(data).digest())
        for raw in sorted(set(p for p in tracked + untracked if p)):
            path = root / raw.decode()
            if path.is_symlink():
                data, mode = str(path.readlink()).encode(), b'link'
            elif path.is_file():
                data = path.read_bytes()
                mode = b'executable' if path.stat().st_mode & 0o111 else b'file'
            elif not path.exists():
                data, mode = b'', b'deleted'
            else:
                raise RuntimeError('Nested repository needs its own declared version')
            content.update(raw + b'\0' + mode + b'\0' + hashlib.sha256(data).digest())
        base = info.get('base')
        if 'base_sha' in info:
            base_sha = info['base_sha']
            if not isinstance(base_sha, str) or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', base_sha):
                raise RuntimeError(f'Pinned base for {name} must be a complete commit SHA')
            try:
                resolved = git('rev-parse', '--verify', base_sha + '^{commit}').decode().strip()
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(f'Pinned base for {name} is not an existing commit') from exc
            if resolved != base_sha:
                raise RuntimeError(f'Pinned base for {name} is not an exact commit SHA')
        else:
            base_sha = git('rev-parse', 'origin/' + base).decode().strip() if base else None
        aligned = subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor',
                                  base_sha, head], capture_output=True).returncode == 0 if base_sha else False
        manifest[name] = {'head': head, 'branch': branch, 'base': base, 'base_sha': base_sha,
                          'base_is_ancestor': aligned, 'wip_sha256': patch.hexdigest(),
                          'content_sha256': content.hexdigest()}
    return manifest
