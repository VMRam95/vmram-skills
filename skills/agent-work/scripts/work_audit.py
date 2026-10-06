"""Read-only inventory of what agent-work and its project manager still hold.

Jobs come from the host registry with their live/abandoned status (an unheld job
lock proves its CLI is gone). Project resources come from the profile's optional
`audit` argv, which prints a JSON list of {kind, name, job, owner, retained,
detail}. Nothing is stopped, removed or reserved here.
"""
import json
from pathlib import Path
import subprocess
import sys

from process_runtime import atomic_json
from work_state import TERMINAL_STATES


def jobs(state):
    rows = []
    for job in state.all():
        if job['state'] in TERMINAL_STATES:
            continue
        alive = state.holder_alive(job['id'])
        rows.append({'id': job['id'], 'task': job['task'], 'owner': job['owner'], 'state': job['state'],
                     'status': ('abandoned' if not alive else
                                'queued' if job.get('waiting_for_capacity') else 'active'),
                     'budget': job['budget'], 'reservation_pending': bool(job.get('reservation_pending')),
                     'wait_reason': job.get('wait_reason', ''), 'created': job['created']})
    return rows


def project_resources(profile_data, profile_dir, root):
    argv = profile_data.get('audit')
    if not argv:
        return []
    substitutions = {'python': sys.executable, 'profile_dir': str(profile_dir), 'root': str(root)}
    result = subprocess.run([a.format_map(substitutions) for a in argv], capture_output=True,
                            text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f'Project audit failed (exit {result.returncode})')
    items = json.loads(result.stdout)
    if not isinstance(items, list) or any(not isinstance(i, dict) or 'kind' not in i for i in items):
        raise RuntimeError('Project audit returned an invalid inventory')
    return items


def leftovers(job):
    """Resources still owned by this job without a recorded reason to keep them."""
    package = Path(job.get('profile_source') or Path(job['profile']).parent)
    return [item for item in project_resources(job['profile_data'], package, job['root'])
            if item.get('job') == job['id'] and not item.get('retained')]


def command(state, args, load_profile):
    if args.job:
        job = state.read(args.job)
        report = {'job': job['id'], 'leftovers': leftovers(job)}
        print(json.dumps(report, indent=2))
        if args.output:
            atomic_json(args.output, report)
        return 1 if report['leftovers'] else 0
    resources = []
    if args.profile:
        if not args.root:
            raise RuntimeError('audit --profile needs --root')
        path, profile = load_profile(args.profile)
        resources = project_resources(profile, path.parent, args.root.resolve())
    rows = jobs(state)
    report = {'jobs': rows, 'resources': resources, 'summary': {
        'active': sum(r['status'] == 'active' for r in rows),
        'queued': sum(r['status'] == 'queued' for r in rows),
        'abandoned': [r['id'] for r in rows if r['status'] == 'abandoned'],
        'unexplained_resources': sum(1 for r in resources if not r.get('retained')),
    }}
    print(json.dumps(report, indent=2))
    if args.output:
        atomic_json(args.output, report)
    return 0
