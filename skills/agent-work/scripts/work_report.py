"""Comparable phase measurements, local HTML and JSON; no service or uploader."""
import html
import json
from collections import Counter
from pathlib import Path
import statistics
import time

from process_runtime import atomic_json


def public(job):
    return {k:job.get(k) for k in ('id','task','project','state','created','closed','budget',
                'wait_reason','phases','gate','versions','profile_sha256','core_sha256','adapter_sha256',
                'admission_samples')}


def phase_totals(job):
    totals={}
    for phase in job.get('phases',[]):
        if phase.get('seconds') is not None:
            totals[phase['phase']]=totals.get(phase['phase'],0)+phase['seconds']
    return totals


def compare(first,second):
    reasons=[]
    # A lane's branch name identifies the task, not the tested product bytes.
    def product_versions(job):
        return {name: {key: value for key, value in version.items() if key != 'branch'}
                for name, version in (job.get('versions') or {}).items()}
    if first['project']!=second['project'] or first['profile_sha256']!=second['profile_sha256']:
        reasons.append('Different project/profile')
    for job in (first,second):
        if job.get('state')!='closed' or not (job.get('gate') or {}).get('passed'):
            reasons.append('A run is not fully tested and closed')
        if not job.get('phases') or any(p.get('state') != 'passed' or
                type(p.get('exit_code')) is not int or p['exit_code'] != 0
                for p in job.get('phases', [])):
            reasons.append('A run contains failed or interrupted phases')
    if (first.get('gate') or {}).get('catalog_sha256')!=(second.get('gate') or {}).get('catalog_sha256'):
        reasons.append('Different discovered case inventory')
    versions_changed = product_versions(first) != product_versions(second)
    if versions_changed:
        reasons.append('Different tested product versions')
    for job in (first, second):
        revisions = {p['core_sha256'] for p in job.get('phases', []) if p.get('core_sha256')}
        if len(revisions) > 1:
            reasons.append('Tool implementation changed within a run')
    before,after=phase_totals(first),phase_totals(second)
    if Counter(p['phase'] for p in first.get('phases', [])) != Counter(
            p['phase'] for p in second.get('phases', [])):
        reasons.append('Different measured phase execution inventory')
    rows=[]
    for phase in sorted(set(before)|set(after)):
        a,b=before.get(phase),after.get(phase)
        rows.append({'phase':phase,'before_seconds':a,'after_seconds':b,
             'delta_seconds':round(b-a,4) if a is not None and b is not None else None,
             'change_percent':round(100*(b-a)/a,2) if a and b is not None else None})
    return {'comparable':not reasons,'reasons':reasons,'before':first['id'],'after':second['id'],
            'tool_versions': {'before': first.get('core_sha256'), 'after': second.get('core_sha256')},
            'adapter_versions': {'before': first.get('adapter_sha256'), 'after': second.get('adapter_sha256')},
            'versions_changed':versions_changed, 'phases':rows}


def render(jobs):
    escape=lambda value:html.escape(str(value))
    rows=[];details=[]
    for job in sorted(jobs,key=lambda j:j['created'],reverse=True):
        totals=phase_totals(job);seconds=sum(totals.values());gate=job.get('gate') or {}
        rows.append(f"<tr><td><a href='#{escape(job['id'])}'>{escape(job['task'])}</a><small>{escape(job['project'])}</small></td><td>{escape(job['state'])}</td><td>{seconds:.2f}s</td><td>{gate.get('cases','—')}</td><td>{escape(job.get('wait_reason') or '—')}</td><td>{'PASS' if gate.get('passed') else 'PENDING / FAIL'}</td></tr>")
        phases=''.join(f"<tr><td>{escape(p['phase'])}</td><td>{escape(p.get('state','—'))}</td><td>{p.get('seconds',0):.2f}s</td><td>{escape(p.get('exit_code','—'))}</td></tr>" for p in job.get('phases',[]))
        errors=''.join('<li>'+escape(e)+'</li>' for e in gate.get('errors',[]))
        chart=''.join(f"<div class='barrow'><span>{escape(name)}</span><div class='bar' style='width:{max(1,100*t/max(totals.values())):.2f}%'></div><b>{t:.2f}s</b></div>" for name,t in totals.items()) if totals else '<p>No measured phases yet.</p>'
        versions=escape(json.dumps(job.get('versions',{}),indent=2))
        samples=escape(json.dumps(job.get('admission_samples',[]),indent=2))
        tool=escape((job.get('core_sha256') or 'legacy / unrecorded')[:16])
        adapter=escape((job.get('adapter_sha256') or 'legacy / external')[:16])
        details.append(f"<section id='{escape(job['id'])}'><h2>{escape(job['task'])}</h2><p>{escape(job['state'])} · {escape(job['project'])} · {escape(job['id'])}</p><p>Tool {tool} · Adapter {adapter}</p>{chart}<div class='scroll'><table><thead><tr><th>Phase</th><th>State</th><th>Duration</th><th>Exit</th></tr></thead><tbody>{phases}</tbody></table></div><ul class='errors'>{errors}</ul><details><summary>Physical admission measurements</summary><pre>{samples}</pre></details><details><summary>Tested repository versions</summary><pre>{versions}</pre></details></section>")
    states={state:sum(j['state']==state for j in jobs) for state in ('ready','testing','queued','closed','cleanup_pending')}
    duration=[sum(phase_totals(j).values()) for j in jobs if j['state']=='closed']
    cards=''.join(f"<div class='card'><b>{n}</b><span>{escape(s)}</span></div>" for s,n in states.items())
    median=f'{statistics.median(duration):.2f}s' if duration else '—'
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Agent Work · local runs</title><style>
*{{box-sizing:border-box}}body{{font:15px system-ui;margin:0;background:#0d1423;color:#e6edf8}}main{{max-width:1200px;margin:auto;padding:28px}}h1{{font-size:30px}}p{{color:#b1c1db}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(125px,1fr));gap:12px}}.card,section{{background:#17233a;border:1px solid #334563;border-radius:12px;padding:18px;margin:18px 0}}.card b{{display:block;font-size:29px;color:#81dfbc}}.card span{{color:#b1c1db}}table{{width:100%;border-collapse:collapse;min-width:590px}}th,td{{padding:12px;text-align:left;border-bottom:1px solid #334563}}th{{background:#20304c}}small{{display:block;color:#a7b9d5}}a{{color:#87bfff}}.scroll{{overflow-x:auto}}.barrow{{display:grid;grid-template-columns:120px 1fr 80px;gap:12px;align-items:center;margin:9px 0}}.bar{{height:12px;background:#81dfbc;border-radius:6px}}.errors{{color:#ffb0a6}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;color:#c7d4e8}}footer{{color:#a7b9d5}}@media(max-width:500px){{main{{padding:16px}}h1{{font-size:24px}}.barrow{{grid-template-columns:90px 1fr 65px;font-size:12px}}}}
</style><main><h1>Agent Work · local runs</h1><p>Measured phases, test coverage and verified cleanup. Median closed run: {median}. Generated {time.strftime('%Y-%m-%d %H:%M:%S')}.</p><div class="cards">{cards}</div><div class="scroll"><table><thead><tr><th>Task / project</th><th>Now</th><th>Measured time</th><th>Cases</th><th>Wait / blocker</th><th>Test gate</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>{''.join(details)}<footer>Durations include queue and retries. Faster partial or failed runs do not qualify as performance improvements.</footer></main></html>'''


def command(state,args):
    if args.action=='compare':
        if not args.job or not args.other:raise RuntimeError('compare needs --job and --other')
        result=compare(state.read(args.job),state.read(args.other))
        print(json.dumps(result,indent=2))
        if args.output:atomic_json(args.output,result)
        return 0 if result['comparable'] else 1
    jobs=[state.read(args.job)] if args.job else state.all()
    output=(args.output or state.root/'report.html').absolute()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(render(jobs),encoding='utf-8')
    atomic_json(output.with_suffix('.json'),[public(j) for j in jobs])
    print(str(output));return 0
