#!/usr/bin/env python3
"""SwiftBar plugin: semáforo de capacidad de agentes en la barra de menús.

Reutiliza mac_agent_capacity.py (misma carpeta), que lleva el criterio entero:
memoria por presión + swapouts, CPU por % ociosa real, y veto de I/O solo si la
cola supera los núcleos Y hay hilos en espera ininterrumpida (estado U). Una
carga alta sola, con CPU y RAM libres, se muestra como aviso pero no veta.
El disco libre del volumen de datos también manda: amarillo avisa, rojo pone 0
agentes. Notifica con osascript al cambiar de estado (verde/amarillo/rojo).
"""

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_capacity_module():
    canonical = HERE / "mac_agent_capacity.py"
    candidates = [canonical]
    if not canonical.is_file():
        candidates.extend([
            Path.home() / ".claude/skills/agent-watch/scripts/mac_agent_capacity.py",
            Path.home() / ".codex/skills/agent-watch/scripts/mac_agent_capacity.py",
        ])
    for path in candidates:
        if not path.is_file():
            continue
        scripts = str(path.parent)
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        spec = importlib.util.spec_from_file_location("agent_watch_capacity", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    raise FileNotFoundError("mac_agent_capacity.py is not installed")


cap = load_capacity_module()

STATE = Path.home() / ".cache" / "agent-watch" / "state"
FONT = "| font=Menlo size=11"


def label(value, limit=46):
    return str(value or "").replace("|", "/").replace("\n", " ")[:limit]


def notify(title, text):
    subprocess.run(
        ["osascript", "-e", f'display notification "{text}" with title "{title}"'],
        check=False,
    )


def main():
    args = argparse.Namespace(
        agent_budget_gb=2.5, reserve_gb=8, agent_cpu_cores=1.5, cpu_reserve_cores=2
    )
    try:
        data = cap.snapshot(args)
    except Exception as exc:  # SwiftBar muestra el error en vez de morir en silencio
        print("⚪️ ?")
        print("---")
        print(f"agent-watch falló: {exc} | color=red")
        return

    sysinfo, capacity = data["system"], data["capacity"]
    cores = sysinfo["logical_cpus"]
    slots = capacity["additional_agents_conservative"]
    limit = capacity["limiting_resource"]
    disk = capacity.get("disk_state")
    free = sysinfo.get("disk_free_gb")
    state = "red" if slots < 1 else "yellow" if disk in ("yellow", "red") else "green"
    icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}[state]

    prev = STATE.read_text().strip() if STATE.exists() else ""
    if prev and prev != state:
        if state == "red" and limit == "disco":
            text = f"Disco en rojo: {free:.0f} GiB libres. Limpia antes de abrir agentes o carriles"
        elif state == "red":
            text = f"No entran más agentes: limita {limit}"
        elif state == "yellow":
            text = f"Disco bajo: {free:.0f} GiB libres. Revisa la limpieza de los proyectos"
        else:
            text = f"Ya entran {slots} agentes"
        notify("Agent Watch", text)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(state)

    # --- barra de menús ---
    print(f"{icon} {slots}")
    print("---")
    verdict = f"SÍ entran {slots} agentes" if slots else f"NO entra ninguno · limita {limit}"
    print(f"{verdict} | color={'green' if slots else 'red'} size=13")
    print("---")
    load = sysinfo["load_average"]
    load_str = " / ".join(f"{x:.1f}" for x in load) if load else "n/d"
    print(f"Carga 1/5/15 min: {load_str}  (núcleos: {cores}) {FONT}")
    u = sysinfo.get("uninterruptible_threads")
    u_str = "n/d" if u is None else str(u)
    r = sysinfo.get("runnable_threads")
    r_str = "n/d" if r is None else str(r)
    print(f"Presión de cola: {capacity['load_pressure']} · hilos en cola: {r_str} · esperas I/O: {u_str} {FONT}")
    if capacity["load_pressure"] == "alta":
        print(f"⚠ cola > núcleos sin bloqueo I/O probado: la carga sola no veta {FONT}")
    print(f"CPU libre: {sysinfo['cpu_idle_percent']:.0f}%   RAM efectiva: {sysinfo['memory_effective_available_gb']:.1f} / {sysinfo['memory_total_gb']:.0f} GB {FONT}")
    if free is None:
        print(f"Disco libre: n/d {FONT}")
    else:
        mark = {"red": " · ROJO: 0 agentes", "yellow": " · bajo"}.get(disk, "")
        color = {"red": " color=red", "yellow": " color=orange"}.get(disk, "")
        print(f"Disco libre: {free:.0f} / {sysinfo['disk_total_gb']:.0f} GiB "
              f"({sysinfo['disk_free_percent']:.0f}%){mark} {FONT}{color}")
    t = data["agent_totals"]
    o = data["codeagentswarm_overhead"]
    print(f"Agentes: {t['count']} · {t['rss_gb']:.1f} GB · {t['cpu_percent']:.0f}% CPU   CAS: {o['rss_gb']:.1f} GB {FONT}")
    managed = data.get("managed_resources") or {}
    growth = managed.get("pending_growth") or {}
    print(f"agent-work: {managed.get('active_jobs', 0)} activos · {managed.get('queued_jobs', 0)} en cola {FONT}")
    print(f"Crecimiento reservado: {growth.get('ram_gb', 0):.1f} GB · {growth.get('cpu_cores', 0):.1f} CPU ({growth.get('jobs', 0)} jobs) {FONT}")
    if managed.get("journal_errors"):
        print(f"⚠ journals parciales/no válidos: {managed['journal_errors']} {FONT}")
    for job in managed.get("jobs", []):
        marker = "cola" if job.get("waiting") else label(job.get("state"), 12)
        print(f"  {label(job.get('project'), 14)}/{label(job.get('task'), 28)} · {marker} · {job.get('rss_gb', 0):.1f} GB {job.get('cpu_percent', 0):.0f}% {FONT}")
    print("---")
    for a in data["agents"]:
        print(f"Q{a['quadrant']:<2} {a['agent_type']:<6} {a['rss_gb']:>4.1f} GB {a['cpu_percent']:>5.1f}% {FONT}")
    print("---")
    top = subprocess.run(
        ["ps", "-Aro", "%cpu=,comm="], capture_output=True, text=True
    ).stdout.splitlines()[:3]
    for line in top:
        pct, _, comm = line.strip().partition(" ")
        print(f"{float(pct):>5.0f}%  {os.path.basename(comm)} {FONT}")
    print("---")
    print("Refrescar | refresh=true")


if __name__ == "__main__":
    main()
