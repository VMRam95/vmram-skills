#!/usr/bin/env python3
"""One local work cycle; managers retain control of their project resources."""
import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import process_runtime as runtime
from validation import digest, git_manifest, validate_tests, package_version
from work_state import State, owner, host_budgets

HERE = Path(__file__).resolve().parent
CORE_SHA256 = package_version()


class UnfinishedPhaseError(RuntimeError):
    pass


def capacity():
    # The same physical sampler is used by the CLI and menu bar integration.
    import mac_agent_capacity as sampler
    args = argparse.Namespace(agent_budget_gb=2.5, reserve_gb=8, agent_cpu_cores=1.5, cpu_reserve_cores=2)
    sample = sampler.snapshot(args)
    if 'observed_epoch' not in sample:raise RuntimeError('Physical sampler must record its actual observation time')
    return sample


def load_profile(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text())
    if data.get('schema') != 1 or not data.get('project'):
        raise RuntimeError('Profile requires schema=1 and a project name')
    hooks = data.get('hooks', {})
    for name in ('prepare', 'up', 'health', 'discover', 'test', 'close', 'verify'):
        argv = hooks.get(name)
        if not isinstance(argv, list) or not argv or any(not isinstance(s, str) or '\0' in s for s in argv):
            raise RuntimeError(f'Profile requires an argv hook: {name}')
    for phase in ('up', 'test'):
        budget = data.get('budgets', {}).get(phase, {})
        for field in ('ram_gb','cpu_cores'):
            value = budget.get(field)
            if isinstance(value, bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value <= 0:
                raise RuntimeError(f'Invalid {phase} budget: {field}')
    reserve = data.get('reserve', {'ram_gb':8,'cpu_cores':2,'disk_gb':5})
    for field in ('ram_gb','cpu_cores','disk_gb'):
        if isinstance(reserve.get(field), bool) or not isinstance(reserve.get(field), (int,float)) or not math.isfinite(reserve[field]) or reserve[field] < 0:
            raise RuntimeError('Invalid physical reserve')
    for value in data.get('timeouts', {}).values():
        if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or value <= 0:
            raise RuntimeError('Invalid phase timeout')
    return path, data


class Flow:
    def __init__(self, state, identifier):
        self.state, self.identifier = state, identifier
        self.recovering = False
        self.in_admission = False
        self.reload_failed = False

    def job(self):
        data = self.state.read(self.identifier)
        if not self.recovering:
            _, profile = load_profile(data['profile'])
            if digest(profile) != data['profile_sha256']:
                raise RuntimeError('Profile changed during this generation; close using the frozen original hooks')
        return data

    def save(self, **changes):
        job = self.job(); job.update(changes); self.state.save(job); return job

    def require_released_phases(self):
        job = self.job()
        for phase in job.get('phases', []):
            record_path = phase.get('supervisor_record')
            if not record_path:
                continue
            path = Path(record_path)
            if not path.exists():
                raise UnfinishedPhaseError('A previous phase journal is missing; close or recover this job before another operation')
            record = json.loads(path.read_text())
            if (record.get('owner'),record.get('lease')) != (job['owner'],job['generation']):
                raise UnfinishedPhaseError('A previous phase journal changed identity; preserve it and close this job')
            if record.get('status') != 'released':
                raise UnfinishedPhaseError('A previous phase is still active; close this job before another operation')

    def pin_repository_bases(self):
        """Persist immutable repository bases before any stack hook uses them."""
        job = self.job()
        adapter = job.get('adapter', {})
        repositories = adapter.get('repositories', {})
        if not isinstance(repositories, dict):
            raise RuntimeError('Adapter repositories must be a mapping')
        if not repositories:
            if (adapter.get('repository_base_pins') is not None
                    or adapter.get('served_source_manifest') is not None
                    or job.get('versions') is not None):
                raise RuntimeError('Repository declarations disappeared after they were pinned')
            return {}
        def full_sha(value):
            return isinstance(value,str) and len(value) in (40,64) and all(c in '0123456789abcdef' for c in value)
        def historical(label, value):
            if value is None:return None
            if not isinstance(value,dict) or set(value)!=set(repositories):
                raise RuntimeError(f'Invalid {label}')
            result={}
            for name, entry in value.items():
                if (not isinstance(entry,dict) or not full_sha(entry.get('head'))
                        or not full_sha(entry.get('base_sha'))
                        or not isinstance(entry.get('branch'),str) or not entry['branch']
                        or not isinstance(entry.get('base'),str) or not entry['base']
                        or entry.get('base_is_ancestor') is not True
                        or not isinstance(entry.get('wip_sha256'),str) or len(entry['wip_sha256'])!=64
                        or any(c not in '0123456789abcdef' for c in entry['wip_sha256'])
                        or not isinstance(entry.get('content_sha256'),str) or len(entry['content_sha256'])!=64
                        or any(c not in '0123456789abcdef' for c in entry['content_sha256'])):
                    raise RuntimeError(f'Invalid {label} for repository: {name}')
                result[name]={'base':entry['base'],'base_sha':entry['base_sha']}
            return result
        served=adapter.get('served_source_manifest')
        served_pairs=historical('served source manifest',served)
        served_digest=adapter.get('served_source_sha256')
        if served_digest is not None and (served is None or served_digest!=digest(served)):
            raise RuntimeError('Served source manifest digest mismatch')
        version_pairs=historical('tested repository versions',job.get('versions'))
        if served_pairs is not None and version_pairs is not None and served_pairs!=version_pairs:
            raise RuntimeError('Served and tested repository bases differ')

        stored=adapter.get('repository_base_pins')
        if stored is not None:
            if (not isinstance(stored,dict) or set(stored)!=set(repositories)
                    or any(not isinstance(pair,dict) or set(pair)!= {'base','base_sha'}
                           or not isinstance(pair['base'],str) or not pair['base']
                           or not full_sha(pair['base_sha']) for pair in stored.values())):
                raise RuntimeError('Invalid durable repository base pins')
            if ((served_pairs is not None and served_pairs!=stored)
                    or (version_pairs is not None and version_pairs!=stored)):
                raise RuntimeError('Historical repository bases differ from durable pins')
            base_pins=stored
        else:
            launched=(job.get('state') not in ('registered','preparing','queued') or
                      any(p.get('phase') in ('up','health','discover','test','command')
                          for p in job.get('phases',[])))
            base_pins=served_pairs or version_pairs
            if base_pins is None and launched:
                raise RuntimeError('Started job has no durable repository base evidence')

        pinned={}
        for name, raw in repositories.items():
            if not isinstance(raw,dict) or not isinstance(raw.get('base'),str) or not raw['base']:
                raise RuntimeError(f'Invalid repository declaration: {name}')
            info=dict(raw)
            if base_pins is not None:
                pair=base_pins[name]
                if info['base']!=pair['base'] or ('base_sha' in info and info['base_sha']!=pair['base_sha']):
                    raise RuntimeError(f'Repository base changed after it was pinned: {name}')
                info['base_sha']=pair['base_sha']
            elif 'base_sha' not in info:
                info['base_sha']=git_manifest({name:info})[name]['base_sha']
            pinned[name]=info
        manifest=git_manifest(pinned)
        if base_pins is None:
            base_pins={name:{'base':entry['base'],'base_sha':entry['base_sha']}
                       for name,entry in manifest.items()}
        latest=self.job().get('adapter',{})
        if latest.get('repositories',{})!=repositories or latest.get('repository_base_pins')!=stored:
            raise RuntimeError('Repository declarations changed while bases were being pinned')
        if repositories!=pinned or stored!=base_pins:
            self.state.update_adapter(self.identifier,repositories=pinned,repository_base_pins=base_pins)
        return manifest

    def hook(self, phase, command=None, cwd=None, timeout_override=None):
        job = self.job()
        folder = self.state.path(self.identifier).parent
        index = len(job['phases'])
        label = f'{index:03}-{phase}'
        log, journal, result = (folder/(label+suffix) for suffix in ('.log','.json','.result.json'))
        if job.get('profile_source'):
            import hashlib
            package=Path(job['profile_source'])
            if package.resolve()!=package.absolute():raise RuntimeError('Linked frozen profile rejected')
            for name,expected in job['source_manifest'].items():
                path=package/name
                if path.resolve()!=path.absolute() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                    raise RuntimeError('Frozen profile source changed; preserve resources')
        substitutions = {'python':sys.executable,'root':job['root'], 'job':str(self.state.path(self.identifier)),
                         'profile_dir':job.get('profile_source',str(Path(job['profile']).parent)),'phase':phase,'task':job['task']}
        argv = command or [a.format_map(substitutions) for a in job['profile_data']['hooks'][phase]]
        env = dict(os.environ, AGENT_LOCAL_OWNER=job['owner'], AGENT_WORK_GENERATION=job['generation'],
                   AGENT_WORK_JOB=str(self.state.path(self.identifier)), PYTHONDONTWRITEBYTECODE='1',
                   AGENT_WORK_PHASE_RECORD=str(journal),
                   AGENT_LOCAL_WORK_SCRIPTS=str(HERE))
        if job['profile_data'].get('node_process_group'):
            preload = (HERE/'node_process_group.mjs').as_uri()
            env['NODE_OPTIONS'] = env.get('NODE_OPTIONS', '') + ' --import=' + preload
        started = time.time(); clock = time.monotonic()
        entry = {'phase':phase, 'started':started, 'state':'registering', 'log':str(log),
                 'core_sha256': CORE_SHA256,
                 'supervisor_record':str(journal),'exit_code':None}
        job['phases'].append(entry); self.state.save(job)
        print(f"[{job['task']}] {phase} started",flush=True)
        rc, problem = 1, None
        timeout = timeout_override or job['profile_data'].get('timeouts',{}).get(phase,7200 if phase=='test' else 1200)
        record = None
        try:
            record = runtime.launch(journal, [sys.executable,'-B',str(HERE/'agent_work.py'),
                    '_child',str(result),*argv], str(cwd or job['root']), lease=job['generation'],log=log,env=env,owner_id=job['owner'])
            current=self.job();current['phases'][index]['state']='running';self.state.save(current)
            while not result.exists():
                current = self.job()
                if current['generation'] != job['generation']:
                    raise RuntimeError('Task generation changed')
                if not runtime.verified(record):
                    # The result may be published between the loop condition and
                    # process inspection. A finished process is not a missing exit.
                    if result.exists(): break
                    if runtime.members(record['pid']):
                        raise RuntimeError('Unverified surviving phase supervisor; preserve resources')
                    if result.exists(): break
                    raise RuntimeError('Phase exited without a recorded exit code')
                if time.monotonic()-clock > timeout:
                    rc = 124
                    raise TimeoutError(f'{phase} timed out')
                time.sleep(.2)
            rc = json.loads(result.read_text())['exit_code']
            if type(rc) is not int:
                raise RuntimeError('Phase has no integer exit code')
        except BaseException as exc:
            problem = f'{type(exc).__name__}: {exc}'
            if isinstance(exc, KeyboardInterrupt): rc = 130
            elif not isinstance(exc, TimeoutError): rc = 1
            raise
        finally:
            try:
                if journal.exists():
                    runtime.stop(journal, lease=job['generation'], validate=lambda:self.job(),owner_id=job['owner'])
            except BaseException as exc:
                rc = 1; problem = f'Phase cleanup unverified: {type(exc).__name__}: {exc}'
                raise
            finally:
                current = self.job()
                current['phases'][index].update(finished=time.time(), seconds=round(time.monotonic()-clock,4),
                     exit_code=rc, state='passed' if rc==0 else 'failed', error=problem)
                self.state.save(current)
                print(f"[{job['task']}] {phase}: exit {rc}, {current['phases'][index]['seconds']:.2f}s",flush=True)
        return rc

    def admit(self, phase, wait):
        start = time.monotonic(); job = self.job(); attempts = 0
        self.in_admission = True  # stays set if the wait is interrupted
        while True:
            attempts += 1
            # The host may resize a phase budget (host.json "budgets"), read every sample.
            budget = dict(job['profile_data']['budgets'][phase]); budget.update(host_budgets().get(phase, {}))
            admitted, current = self.state.admit(self.identifier,budget,capacity())
            if admitted:
                current['phases'].append({'phase':'queue-'+phase,'started':time.time()-(time.monotonic()-start),
                    'finished':time.time(),'seconds':round(time.monotonic()-start,4),'exit_code':0,
                    'state':'passed','samples':attempts})
                self.state.save(current)
                self.in_admission = False
                return True
            print(f"[{job['task']}] queued: {current['wait_reason']}",flush=True)
            self.save(state='queued')
            if time.monotonic()-start >= wait:
                self.in_admission = False
                return False
            time.sleep(min(5,wait-(time.monotonic()-start)))

    def start_phase(self, phase, deadline):
        while True:
            rc = self.hook(phase)
            if rc != 75:
                return rc
            current = self.job()
            for entry in reversed(current['phases']):
                if entry.get('phase') == phase and entry.get('exit_code') == 75:
                    entry['state'] = 'queued'
                    break
            reason = current.get('adapter',{}).get('capacity_wait_reason') or 'project capacity'
            current.update(state='queued',waiting_for_capacity=True,wait_reason=reason,
                           budget={'ram_gb':0,'cpu_cores':0},reservation_pending=False,
                           allocation_realized=time.time())
            self.state.save(current)
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                return 75
            time.sleep(min(5,remaining))
            if not self.admit('up',max(0,deadline-time.monotonic())):
                return 75

    def start(self, wait=0):
        deadline = time.monotonic()+wait
        self.require_released_phases()
        job = self.job()
        if job['state'] == 'closed':
            raise RuntimeError('This generation is closed; start a new generation from its preserved source')
        health = next((p for p in reversed(job['phases']) if p.get('phase') == 'health'), {})
        resume_ready = (job['state'] == 'queued' and job['adapter'].get('prepared')
                        and job.get('allocation_realized') and not job.get('reservation_pending')
                        and health.get('state') == 'passed' and health.get('exit_code') == 0)
        if job['state'] in ('ready', 'validated', 'validation_failed') or resume_ready:
            current = self.pin_repository_bases()
            job = self.job()
            served = job['adapter'].get('served_source_manifest')
            reloads = served is not None and served != current
            if reloads and not self.admit('up', max(0,deadline-time.monotonic())):
                return 75
            rc = self.hook('health')
            if not rc:
                self.save(state='ready' if reloads or resume_ready else job['state'],
                          reservation_pending=False, allocation_realized=time.time())
                if reloads:
                    self.save(gate=None, delivery=None)
            elif reloads:
                # A refused or failed reload must not destroy a lane that was
                # serving: the project keeps its resources and data, the owner fixes
                # the change and reloads again (or closes the job explicitly).
                self.reload_failed = True
                log = Path(self.job()['phases'][-1].get('log') or '')
                lines = [l for l in log.read_text(errors='replace').splitlines() if l.strip()] if log.is_file() else []
                reason = next((l for l in reversed(lines) if not l.startswith('[')), lines[-1] if lines else '')
                print(f"[{job['task']}] reload failed; the job is kept. {reason}\nFix the change and run "
                      f"`agent-work start --job {job['id']}` again, or close it", file=sys.stderr, flush=True)
            return rc
        if not self.admit('up',max(0,deadline-time.monotonic())): return 75
        if not job['adapter'].get('prepared'):
            self.save(state='preparing')
            rc = self.start_phase('prepare',deadline)
            if rc: return 75 if rc==75 else 1
            if not self.job()['adapter'].get('prepared'):
                raise RuntimeError('Prepare hook did not record its resources')
        self.pin_repository_bases()
        self.save(state='starting')
        rc = self.start_phase('up',deadline)
        if rc: return 75 if rc==75 else 1
        if self.hook('health'): return 1
        self.save(state='ready',reservation_pending=False,allocation_realized=time.time()); return 0

    def validate(self, wait=0):
        self.require_released_phases()
        self.save(gate=None,delivery=None)
        if self.start(wait): return 75 if self.job()['state']=='queued' else 1
        if not self.admit('test',wait): return 75
        self.save(state='testing')
        if self.hook('discover'):
            self.save(state='validation_failed');return 1
        catalog_path = self.job()['adapter'].get('catalog_evidence')
        if not catalog_path or not Path(catalog_path).is_file():
            raise RuntimeError('The expected test inventory must be discovered before execution')
        discovered = json.loads(Path(catalog_path).read_text())
        self.save(discovered_catalog=discovered)
        before = git_manifest(self.job()['adapter'].get('repositories',{}))
        self.save(versions=before)
        rc = self.hook('test')
        job = self.job()
        evidence_path = job['adapter'].get('test_evidence')
        if not evidence_path or not Path(evidence_path).is_file():
            gate = {'passed':False,'errors':['No full test evidence recorded']}
        else:
            evidence = json.loads(Path(evidence_path).read_text())
            gate = validate_tests(evidence)
            if (digest(evidence.get('catalog')) != digest(discovered.get('catalog')) or
                    evidence.get('required_suites') != discovered.get('required_suites')):
                gate['passed']=False;gate['errors'].append('Executed inventory differs from the discovery saved before tests')
        after = git_manifest(job['adapter'].get('repositories',{}))
        if not before or before != after:
            gate['passed']=False;gate.setdefault('errors',[]).append('Repository version changed during tests or is missing')
        if any(not r['base_is_ancestor'] for r in after.values()):
            gate['passed']=False;gate.setdefault('errors',[]).append('The declared remote base is not an ancestor')
        if rc:
            gate['passed']=False;gate.setdefault('errors',[]).append(f'Product test command exit {rc}')
        self.save(gate=gate,state='validated' if gate['passed'] else 'validation_failed',
                  reservation_pending=False,allocation_realized=time.time())
        return 0 if gate['passed'] else 1

    def close(self):
        # Configuration edits must not disable closure. Resource ownership is
        # checked by the original frozen hooks and again by the project manager.
        self.recovering = True
        if self.job()['state']=='closed': return 0
        if not any(p.get('supervisor_record') for p in self.job()['phases']):
            self.state.update_adapter(self.identifier,cleanup_verified=True,cleanup_note='No project hook or resource was opened')
            self.state.release(self.identifier,verified=True)
            return 0
        self.save(state='closing')
        try:
            # A killed CLI may have left a registered phase running. Recover only
            # that exact owner/generation before touching its project resources.
            current=self.job()
            for phase in current['phases']:
                record = phase.get('supervisor_record')
                if record:
                    # launch writes its journal before permitting any command. An
                    # absent registering journal therefore opened no resource.
                    if Path(record).exists():
                        runtime.stop(record, lease=self.job()['generation'], validate=lambda:self.job(),owner_id=self.job()['owner'])
                    elif phase.get('state')!='registering':
                        raise RuntimeError('Published phase journal is missing; preserve resources')
                    if phase.get('state') not in ('running','registering'):continue
                    phase.update(state='interrupted',exit_code=130,finished=time.time(),
                                 seconds=round(time.time()-phase['started'],4))
            self.state.save(current)
        except BaseException:
            self.save(state='cleanup_pending')
            raise
        results, problems = [], []
        for phase in ('close','verify'):
            try: results.append(self.hook(phase))
            except BaseException as exc:
                results.append(1);problems.append(f'{phase}: {type(exc).__name__}: {exc}')
        if any(results) or not self.job()['adapter'].get('cleanup_verified'):
            self.save(state='cleanup_pending',cleanup_errors=problems)
            return 1
        # Verified hooks prove the manager's own checks; the project audit proves
        # that nothing of this job survives elsewhere without a recorded reason.
        import work_audit
        remaining = work_audit.leftovers(self.job())
        if remaining:
            self.save(state='cleanup_pending',cleanup_errors=[f"{r['kind']} {r['name']} remains" for r in remaining])
            return 1
        self.state.release(self.identifier,verified=True)
        return 0


def summary(job):
    return {k:job.get(k) for k in ('id','task','project','root','state','created','closed','budget',
            'waiting_for_capacity','wait_reason','phases','gate','versions')}


def main():
    if len(sys.argv)>1 and sys.argv[1]=='_child':
        result=Path(sys.argv[2]); command=sys.argv[3:]
        rc=subprocess.run(command).returncode
        runtime.atomic_json(result,{'exit_code':rc});return rc
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('start','validate','deliver','close','run','status','report','compare','exec','audit'))
    parser.add_argument('--profile',type=Path);parser.add_argument('--root',type=Path)
    parser.add_argument('--task');parser.add_argument('--job');parser.add_argument('--other')
    parser.add_argument('--state-dir',type=Path);parser.add_argument('--wait',type=float,default=0)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--evidence',type=Path)
    parser.add_argument('--cwd',type=Path);parser.add_argument('--timeout',type=float,default=1200)
    parser.add_argument('--budget',choices=('up','test'),default='test',
                        help='exec reservation: test (default, heavy suites) or up (light auxiliary commands)')
    arguments=sys.argv[1:]
    separator=arguments.index('--') if '--' in arguments else len(arguments)
    args=parser.parse_args(arguments[:separator]);args.command=arguments[separator+1:]
    if args.command and args.action!='exec':parser.error('Only exec accepts a command after --')
    state=State(args.state_dir)
    if not math.isfinite(args.wait) or args.wait < 0:
        parser.error('--wait must be a finite nonnegative duration')
    if args.action=='status':
        print(json.dumps([summary(j) for j in state.all()],indent=2));return 0
    if args.action=='audit':
        import work_audit
        return work_audit.command(state,args,load_profile)
    if args.action in ('report','compare'):
        import work_report
        return work_report.command(state,args)
    if args.job:
        job=state.read(args.job)
    elif args.action in ('start','run') and args.profile and args.root and args.task:
        profile_path,profile=load_profile(args.profile)
        if state.root!=(Path.home()/'.local/state/agent-work').absolute() and not profile.get('test_only'):
            raise RuntimeError('Product admission must use the single host registry; custom state directories are only for explicit tooling fixtures')
        root=args.root.resolve()
        if not root.is_dir() or root in (Path('/'),Path.home(),Path('/Users')):
            raise RuntimeError('Use an exact project workspace root')
        job=state.create(args.task,root,profile_path,profile)
    else:
        parser.error('start/run need --profile, --root, --task; other operations need --job')
    host_state=(Path.home()/'.local/state/agent-work').absolute()
    if args.action in ('start','run','validate','deliver','exec') and state.root!=host_state and not job['profile_data'].get('test_only'):
        raise RuntimeError('Product admission must use the single host registry; custom state directories are only for explicit tooling fixtures')
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt('Cancelled')))
    flow=Flow(state,job['id'])
    with state.locked('job-'+job['id'],blocking=False):
        rc=1
        try:
            if args.action=='run':
                try: rc=flow.validate(args.wait)
                finally:
                    if flow.close(): rc=1
            else:
                if args.action=='exec':
                    command=args.command[1:] if args.command[:1]==['--'] else args.command
                    cwd=(args.cwd or Path(job['root'])).resolve()
                    if not command or not cwd.is_dir() or (cwd!=Path(job['root']) and Path(job['root']) not in cwd.parents):
                        parser.error('exec requires argv after -- and a cwd inside its workspace')
                    if not math.isfinite(args.timeout) or args.timeout<=0:parser.error('Invalid exec timeout')
                    flow.require_released_phases()
                    health = next((p for p in reversed(job['phases']) if p.get('phase') == 'health'), {})
                    resume_ready = (job['state'] == 'queued' and job['adapter'].get('prepared')
                                    and job.get('allocation_realized') and not job.get('reservation_pending')
                                    and health.get('state') == 'passed' and health.get('exit_code') == 0)
                    if job['state'] not in ('ready','validated') and not resume_ready:
                        raise RuntimeError('Start and verify the local stack before exec')
                    current_source=flow.pin_repository_bases()
                    job=state.read(job['id'])
                    served=job['adapter'].get('served_source_manifest')
                    if served is not None and served!=current_source:
                        # Unit tests or git on WIP are fine; anything using the stack is not.
                        print(f"[{job['task']}] warning: source changed since the stack was loaded; "
                              f"run `agent-work start --job {job['id']}` to reload and reseal before "
                              "commands that use the running stack",file=sys.stderr,flush=True)
                    rc=75
                    if flow.admit(args.budget,args.wait):
                        flow.save(state='running')
                        try:
                            rc=flow.hook('command',command,cwd,args.timeout)
                        except BaseException:
                            flow.save(state='cleanup_pending')
                            raise
                        else:
                            flow.save(state=('validated' if (job.get('gate') or {}).get('passed') else 'ready'),
                                      reservation_pending=False,allocation_realized=time.time())
                elif args.action=='deliver':
                    if not args.evidence: parser.error('deliver needs --evidence')
                    from delivery import verify
                    flow.pin_repository_bases()
                    job=state.read(job['id'])
                    delivery=verify(job,args.evidence)
                    job=state.read(job['id']);job['delivery']=delivery;state.save(job)
                    rc=0 if delivery['passed'] else 1
                else:
                    rc=getattr(flow,args.action)(*([args.wait] if args.action in ('start','validate') else []))
                if args.action in ('start','validate') and rc not in (0,75) and not flow.reload_failed:
                    if flow.close(): rc=1
        except BaseException as exc:
            # Interrupting only the wait for capacity must not tear down a prepared
            # stack: the job stays queued and resumes with the same ID.
            waiting=(isinstance(exc,KeyboardInterrupt) and args.action in ('start','validate')
                     and flow.in_admission and state.read(job['id'])['adapter'].get('prepared'))
            if waiting:
                print(f"[{job['task']}] interrupted while queued; stack kept, resume with --job {job['id']}",
                      file=sys.stderr)
            elif args.action in ('start','run','validate') and not isinstance(exc,UnfinishedPhaseError):
                try:flow.close()
                except BaseException as cleanup:print(f'Cleanup pending: {type(cleanup).__name__}: {cleanup}',file=sys.stderr)
            raise
        finally:
            current=state.read(job['id'])
            print(json.dumps(summary(current),indent=2))
            if args.output: runtime.atomic_json(args.output,summary(current))
        return rc


if __name__=='__main__':
    try:raise SystemExit(main())
    except KeyboardInterrupt:raise SystemExit(130)
    except (RuntimeError,OSError,ValueError,KeyError,subprocess.SubprocessError) as exc:
        print(f'agent-work: {type(exc).__name__}: {exc}',file=sys.stderr);raise SystemExit(1)
