"""Verify PR heads and inspected real screenshot files against a full local run."""
import hashlib
import os
import subprocess as sp
import json
from pathlib import Path
import re
import struct
import subprocess

from validation import git_manifest


def github(*argv):
    if argv != ('auth', 'status'):
        subprocess.check_output(['gh', 'auth', 'status'], text=True, timeout=60)
    return subprocess.check_output(['gh', *argv], text=True, timeout=60)


def verify(job, manifest_path):
    errors = []
    if not (job.get('gate') or {}).get('passed'):
        errors.append('A full clean local validation is required')
    current = git_manifest(job['adapter'].get('repositories', {}))
    for info in job['adapter'].get('repositories',{}).values():
        if sp.check_output(['git','-C',info['worktree'],'status','--porcelain','--untracked-files=all'],text=True).strip():
            errors.append('Product source must be clean and committed before testing and PR delivery')
    if current != job.get('versions'):
        errors.append('PR source differs from the exact version tested locally')
    evidence = json.loads(Path(manifest_path).read_text())
    # Each person delivers with their own account; the profile keeps the default.
    login = os.environ.get('AGENT_WORK_GITHUB_LOGIN') or job['profile_data'].get('github_login')
    if not login:
        errors.append('Profile must declare the authorized GitHub login')
    else:
        # Read the live active account before every use of GitHub operations.
        github('auth', 'status')
        actual = json.loads(github('api', 'user'))['login']
        if actual.lower() != login.lower():
            raise RuntimeError('Active GitHub account differs from the authorized profile')
    prs = evidence.get('prs', [])
    claimed = set()
    for item in prs:
        name, repo, number = item.get('repository'), item.get('repo',''), item.get('number')
        if name not in current or name in claimed or not re.fullmatch(r'[\w.-]+/[\w.-]+', repo) or type(number) is not int or number <= 0:
            errors.append('Invalid or duplicate PR identity'); continue
        claimed.add(name)
        if not login: continue
        pr = json.loads(github('api', f'repos/{repo}/pulls/{number}'))
        version = current[name]
        expected_ref = item.get('head_ref', version['branch'])
        if not isinstance(expected_ref, str) or not expected_ref:
            errors.append(f'Invalid published PR branch: {name}')
            continue
        if (pr['state'] != 'open' or pr['base']['ref'] != version['base'] or
            pr['head']['sha'] != version['head'] or pr['head']['ref'] != expected_ref):
            errors.append(f'PR head/base/state mismatch: {name}')
        if pr['base']['repo']['full_name'].lower() != repo.lower():
            errors.append(f'PR repository mismatch: {name}')
    required = set(evidence.get('changed_repositories', []))
    if not required or claimed != required or not required <= set(current):
        errors.append('Every declared changed repository requires its own matching PR')
    shots = evidence.get('screenshots', [])
    if not shots: errors.append('Real inspected local screenshots are required')
    mobile = False
    root = Path(job['root'])
    for shot in shots:
        path = Path(shot.get('path','')).absolute()
        if not path.is_file() or path.resolve() != path or root not in path.parents or 'artifacts' not in path.relative_to(root).parts:
            errors.append('Screenshot must be a real unlinked artifact in the workspace'); continue
        data = path.read_bytes()
        if data[:8] != b'\x89PNG\r\n\x1a\n' or len(data) < 24:
            errors.append('Screenshot must be an actual PNG'); continue
        width, height = struct.unpack('>II', data[16:24])
        mobile |= 300 <= width <= 480 and height >= 600
        if (shot.get('inspected') is not True or not shot.get('demonstrates') or
                shot.get('sha256') != hashlib.sha256(data).hexdigest()):
            errors.append(f'Missing inspected screenshot provenance: {path.name}')
    if job['profile_data'].get('mobile_first') and not mobile:
        errors.append('Mobile local flow evidence is required')
    return {'passed':not errors,'errors':errors,'prs':prs,'screenshots':shots,
            'manifest_sha256':hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest()}
