"""Private journals and brief atomic capacity admission; project managers own slots."""
import contextlib
import fcntl
import json
import hashlib
import math
import os
from pathlib import Path
import time
import uuid

from process_runtime import atomic_json
from validation import digest, package_version

TERMINAL_STATES = {'closed', 'cancelled'}


def owner():
    for key in ('AGENT_LOCAL_OWNER', 'TMF_LANE_OWNER_ID', 'CODEAGENTSWARM_TERMINAL_ID', 'CODEX_THREAD_ID',
                'CODEX_SESSION_ID', 'CLAUDE_CODE_SESSION_ID', 'TERM_SESSION_ID'):
        value = os.environ.get(key, '').strip()
        if value:
            if '\n' in value or '\r' in value:
                raise RuntimeError('Invalid stable session identity')
            if key in ('AGENT_LOCAL_OWNER','TMF_LANE_OWNER_ID') and value.startswith(('agent_local_owner:','codeagentswarm_terminal_id:','codex_thread_id:','codex_session_id:','claude_code_session_id:','term_session_id:')):
                return value
            return key.lower() + ':' + value
    raise RuntimeError('Set AGENT_LOCAL_OWNER to a stable identity for this independent session')


class State:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get('AGENT_WORK_STATE_DIR',
                         Path.home() / '.local/state/agent-work')).absolute()
        if self.root.resolve() != self.root:
            raise RuntimeError('State root must be an unlinked private directory')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        (self.root/'jobs').mkdir(exist_ok=True, mode=0o700)

    @contextlib.contextmanager
    def locked(self, name='admission', blocking=True):
        path = self.root/(name+'.lock')
        if path.resolve() != path.absolute():
            raise RuntimeError('Linked state lock rejected')
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, 'a') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            except BlockingIOError as exc:
                raise RuntimeError('This task already has an operation in progress') from exc
            yield

    def path(self, identifier):
        if len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier):
            raise RuntimeError('Use the job ID returned by start')
        path = self.root/'jobs'/identifier/'job.json'
        if path.resolve() != path.absolute():
            raise RuntimeError('Linked task journal rejected')
        return path

    def read(self, identifier, require_owner=True):
        data = json.loads(self.path(identifier).read_text())
        if data.get('id') != identifier or not data.get('generation'):
            raise RuntimeError('Invalid task journal')
        if require_owner and data.get('owner') != owner():
            raise RuntimeError('Task belongs to a different session; no resources changed')
        return data

    def save(self, job, fields=None):
        path = self.path(job['id'])
        fd=os.open(path.parent/'adapter.lock',os.O_CREAT|os.O_RDWR,0o600)
        with os.fdopen(fd,'a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if path.exists():
                previous = self.read(job['id'])
                if (previous['owner'], previous['generation']) != (job['owner'], job['generation']):
                    raise RuntimeError('Task generation changed; resources preserved')
                # Core, adapter and resource managers share this brief lock but
                # publish only their owned fields. A stale core snapshot cannot
                # erase a newer adapter update or exact resource claim.
                selected = set(job) - {'adapter','resource_claims'} if fields is None else set(fields)
                if 'adapter' in selected or any(name not in job for name in selected):
                    raise RuntimeError('Invalid explicit task fields')
                data=dict(previous)
                data.update({name:job[name] for name in selected})
            elif job['owner'] != owner():
                raise RuntimeError('Cannot create a foreign task journal')
            else:
                if fields is not None:
                    raise RuntimeError('Initial task journal requires the complete record')
                data=dict(job)
            atomic_json(path, data)

    def update_adapter(self, identifier, **changes):
        path=self.path(identifier)
        fd=os.open(path.parent/'adapter.lock',os.O_CREAT|os.O_RDWR,0o600)
        with os.fdopen(fd,'a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            current=self.read(identifier);current['adapter'].update(changes)
            atomic_json(path,current)

    def claim_ports(self, identifier, ports):
        values=sorted(set(ports))
        if not values or len(values)>512 or any(type(p) is not int or not 1<=p<=65535 for p in values):
            raise RuntimeError('Invalid exact host port claim')
        with self.locked():
            job=self.read(identifier)
            if job['state'] in TERMINAL_STATES:raise RuntimeError('A closed generation cannot claim resources')
            existing=job.get('resource_claims',{}).get('tcp',[])
            if existing and existing!=values:
                raise RuntimeError('Close the existing resource claim before replacing it')
            for other in self.active():
                if other['id']!=identifier and other['state'] not in TERMINAL_STATES and set(values)&set(other.get('resource_claims',{}).get('tcp',[])):
                    raise RuntimeError('Host resource already claimed by another job')
            job['resource_claims']={'tcp':values};self.save(job,fields={'resource_claims'})

    def all(self):
        return [self.read(p.parent.name, require_owner=False)
                for p in sorted((self.root/'jobs').glob('*/job.json'))]

    def active(self):
        """Called under admission lock; historical case inventories stay cold."""
        path=self.root/'active.json'
        if path.exists():
            if path.resolve()!=path.absolute():raise RuntimeError('Linked active registry rejected')
            ids=json.loads(path.read_text())
            jobs=[self.read(i,require_owner=False) for i in ids]
        else:jobs=self.all()
        live=[j for j in jobs if j['state'] not in TERMINAL_STATES]
        atomic_json(path,[j['id'] for j in live])
        return live

    def create(self, task, root, profile_path, profile):
        if not task or len(task) > 120 or any(c in task for c in '\n\r\0'):
            raise RuntimeError('Invalid task ID')
        root = str(Path(root).resolve())
        with self.locked():
            matches = [j for j in self.all() if j['task'] == task and j['root'] == root
                       and j['state'] not in TERMINAL_STATES]
            if matches:
                job = self.read(matches[0]['id'])
                if job['profile_sha256'] != digest(profile):
                    raise RuntimeError('Profile changed; close or recover the previous generation first')
                return job
            identifier = uuid.uuid4().hex
            job = {'schema':1, 'id':identifier, 'generation':uuid.uuid4().hex,
                   'owner':owner(), 'task':task, 'root':root, 'project':profile['project'],
                   'profile':str(profile_path), 'profile_sha256':digest(profile),
                   'profile_data':profile, 'created':time.time(), 'state':'registered',
                   'core_sha256': package_version(),
                   'budget':{'ram_gb':0, 'cpu_cores':0}, 'phases':[], 'adapter':{}, 'gate':None}
            self.path(identifier).parent.mkdir(mode=0o700)
            patterns=profile.get('source_files',[])
            if patterns:
                source=Path(profile_path).parent
                package=self.path(identifier).parent/'profile-source'
                package.mkdir(mode=0o700)
                files={}
                for pattern in patterns:
                    if not isinstance(pattern,str) or Path(pattern).is_absolute() or '..' in Path(pattern).parts:
                        raise RuntimeError('Profile source patterns must stay inside the package')
                    matches=[p for p in source.glob(pattern) if p.is_file()]
                    if not matches:raise RuntimeError('Profile source pattern matched no files')
                    for path in matches:
                        if path.resolve()!=path.absolute():raise RuntimeError('Linked profile source rejected')
                        relative=path.relative_to(source)
                        contents=path.read_bytes()
                        target=package/relative;target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                        target.write_bytes(contents);target.chmod(path.stat().st_mode & 0o700)
                        if path.read_bytes()!=contents:raise RuntimeError('Profile source changed while freezing')
                        files[str(relative)]=hashlib.sha256(contents).hexdigest()
                atomic_json(package/'source-manifest.json',{'files':files,'original':str(source)})
                job['profile_source']=str(package);job['source_manifest']=files
                job['adapter_sha256'] = digest(files)
            self.save(job)
            live=self.active()
            if identifier not in {j['id'] for j in live}:
                atomic_json(self.root/'active.json',[j['id'] for j in live]+[identifier])
            return job

    def admit(self, identifier, budget, snapshot):
        """Reserve pending phase growth, then use fresh physical usage for ready jobs.

        A ready stack is already included in physical usage. Its claim stays charged
        until the measurement is newer than its verified ready transition. Pending
        starts/tests retain the complete growth budget throughout that phase.
        """
        for field in ('ram_gb','cpu_cores'):
            if isinstance(budget.get(field),bool) or not isinstance(budget.get(field),(int,float)) or not math.isfinite(budget[field]) or budget[field] <= 0:
                raise RuntimeError('Invalid admission budget')
        with self.locked():
            job = self.read(identifier)
            if job['state'] in TERMINAL_STATES:
                raise RuntimeError('A closed generation cannot reserve capacity')
            live = [j for j in self.active() if j['id'] != identifier]
            atomic_json(self.root/'active.json',[j['id'] for j in live]+[identifier])
            waiting = sorted([j for j in live if j.get('waiting_for_capacity')], key=lambda j:j['created'])
            system = snapshot['system']
            for field in ('memory_effective_available_gb','logical_cpus','cpu_idle_percent'):
                if not isinstance(system.get(field),(int,float)) or not math.isfinite(system[field]) or system[field]<0:
                    raise RuntimeError('Physical measurement is inconclusive')
            reserve = job['profile_data'].get('reserve', {'ram_gb':8, 'cpu_cores':2, 'disk_gb':5})
            available = system['memory_effective_available_gb'] - reserve['ram_gb']
            cpu = system['logical_cpus']*system['cpu_idle_percent']/100 - reserve['cpu_cores']
            pending = [j for j in live if j.get('reservation_pending',True) or
                       snapshot.get('observed_epoch',0) < j.get('allocation_realized',float('inf'))]
            ram_claimed = sum(j['budget']['ram_gb'] for j in pending)
            cpu_claimed = sum(j['budget']['cpu_cores'] for j in pending)
            reasons = []
            if not 0 <= time.time() - snapshot.get('observed_epoch', 0) <= 30:
                reasons.append('capacity measurement expired')
            # An already admitted stack can finish and release capacity ahead of
            # queued starts; strict FIFO among starts must not deadlock completion.
            completing=bool(job.get('adapter',{}).get('prepared'))
            if not completing and waiting and waiting[0]['created'] < job['created']:
                reasons.append('an earlier queued task has priority')
            if available < ram_claimed + budget['ram_gb']:
                reasons.append('memory')
            if cpu < cpu_claimed + budget['cpu_cores']:
                reasons.append('CPU')
            if system.get('swapout_delta', 0) or snapshot['capacity'].get('io_contention'):
                reasons.append('memory pressure or verified I/O contention')
            free_gb = os.statvfs(job['root']).f_bavail*os.statvfs(job['root']).f_frsize/(1024**3)
            if free_gb < reserve.get('disk_gb',5):
                reasons.append('disk')
            job['waiting_for_capacity'] = bool(reasons)
            job['wait_reason'] = ', '.join(reasons)
            job['capacity_at_admission'] = snapshot
            job.setdefault('admission_samples',[]).append({'epoch':time.time(),'budget':budget,
                'available_ram_gb':system['memory_effective_available_gb'],'cpu_idle_percent':system['cpu_idle_percent'],
                'pending_ram_gb':ram_claimed,'pending_cpu_cores':cpu_claimed,'disk_free_gb':round(free_gb,3),'reasons':reasons})
            if not reasons:
                job['budget'] = budget
                job['reservation_pending'] = True
            self.save(job)
            return not reasons, job

    def release(self, identifier, *, verified):
        if not verified:
            raise RuntimeError('Capacity is retained until cleanup is verified')
        with self.locked():
            job = self.read(identifier)
            job.update(budget={'ram_gb':0,'cpu_cores':0}, waiting_for_capacity=False,
                       wait_reason='', resource_claims={},state='closed', closed=time.time())
            self.save(job,fields={'budget','waiting_for_capacity','wait_reason','resource_claims','state','closed'})
            self.active()
            return job
