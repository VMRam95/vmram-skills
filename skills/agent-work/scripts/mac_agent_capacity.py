#!/usr/bin/env python3
"""Measure macOS headroom and attribute CodeAgentSwarm process trees."""

import argparse
import json
import math
import os
import re
import statistics
import subprocess
import time
from collections import defaultdict
from datetime import datetime

try:
    import managed_resources
except ImportError:  # A legacy standalone installation still measures physical capacity.
    managed_resources = None


SAFE_ENV_KEYS = (
    "CODEAGENTSWARM_TERMINAL_ID",
    "CODEAGENTSWARM_CURRENT_QUADRANT",
    "CODEAGENTSWARM_AGENT_TYPE",
)


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL)


def parse_processes(text):
    processes = {}
    for line in text.splitlines():
        parts = line.split(None, 4)
        if len(parts) != 5:
            continue
        pid, ppid, cpu, rss, command = parts
        processes[int(pid)] = {
            "pid": int(pid),
            "ppid": int(ppid),
            "cpu": float(cpu),
            "rss_kb": int(rss),
            "command": command,
        }
    return processes


def descendants(root_pid, children):
    found = set()
    pending = [root_pid]
    while pending:
        parent = pending.pop()
        for child in children.get(parent, ()):
            if child not in found:
                found.add(child)
                pending.append(child)
    return found


def safe_agent_env(pid):
    try:
        raw = run("ps", "eww", "-p", str(pid), "-o", "command=")
    except subprocess.CalledProcessError:
        return {}
    result = {}
    for key in SAFE_ENV_KEYS:
        match = re.search(r"(?:^|\s)" + re.escape(key) + r"=([^\s]+)", raw)
        if match:
            result[key] = match.group(1)
    return result


def last_match(pattern, text):
    matches = re.findall(pattern, text, re.MULTILINE)
    return matches[-1] if matches else None


def parse_thread_states(text):
    runnable = uninterruptible = seen = 0
    for line in text.splitlines()[1:]:
        fields = line.split()
        if 4 <= len(fields) < 8 and fields[0].isdigit():
            seen += 1
            state = fields[2][:1]
            runnable += state == "R"
            uninterruptible += state == "U"
    if seen == 0:
        return None, None
    return runnable, uninterruptible


def count_thread_states():
    """Hilos en cola (R) y en espera ininterrumpida (U) vía `ps -axM`.

    Las líneas de hilo llevan el PID pero no COMMAND ni USER: <8 campos y
    primer campo numérico. Devuelve (None, None) si `ps` falla o su salida no
    contiene líneas de hilo reconocibles — medición inconclusa, no cero medido;
    los llamadores deben tratarlo como tal.
    """
    try:
        return parse_thread_states(run("ps", "-axM"))
    except (subprocess.CalledProcessError, IndexError):
        return None, None


def compute_capacity(
    total_gb,
    free_pct,
    idle_pct,
    agent_rss,
    args,
    swapout_delta=0,
    load1=None,
    uninterruptible_threads=None,
    pending_ram_gb=0,
    pending_cpu_cores=0,
):
    available_gb = total_gb * free_pct / 100
    median_rss = statistics.median(agent_rss) if agent_rss else 0
    agent_budget = max(args.agent_budget_gb, median_rss * 1.5)
    physical_memory_slots = max(0, math.floor((available_gb - args.reserve_gb) / agent_budget))
    memory_slots = max(0, math.floor(
        (available_gb - args.reserve_gb - pending_ram_gb) / agent_budget))
    idle_cores = args.logical_cpus * idle_pct / 100
    physical_cpu_slots = max(
        0,
        math.floor((idle_cores - args.cpu_reserve_cores) / args.agent_cpu_cores),
    )
    cpu_slots = max(
        0,
        math.floor((idle_cores - args.cpu_reserve_cores - pending_cpu_cores)
                   / args.agent_cpu_cores),
    )
    if swapout_delta > 0:
        physical_memory_slots = memory_slots = 0
    # La carga media a 1 min en macOS cuenta hilos en cola (incluido trabajo en
    # segundo plano QoS: Defender, Spotlight) y puede superar los núcleos con la
    # mitad de la CPU ociosa. Solo veta cuando además hay hilos en espera
    # ininterrumpida (estado U), que es la prueba de bloqueo real de I/O.
    # uninterruptible_threads=None = medición no disponible: no veta a ciegas.
    io_contention = (
        load1 is not None
        and load1 > args.logical_cpus
        and uninterruptible_threads is not None
        and uninterruptible_threads >= 2
    )
    if io_contention:
        additional = 0
        physical_additional = 0
        limiting = "I/O (esperas ininterrumpidas)"
    else:
        additional = min(memory_slots, cpu_slots)
        physical_additional = min(physical_memory_slots, physical_cpu_slots)
        limiting = "memoria" if memory_slots <= cpu_slots else "CPU"
    if io_contention:
        load_pressure = "saturación I/O"
    elif load1 is None:
        load_pressure = "desconocida"
    elif load1 > args.logical_cpus:
        load_pressure = "alta"
    else:
        load_pressure = "normal"
    return {
        "can_start_another": additional >= 1,
        "additional_agents_conservative": additional,
        "physical_additional_agents_conservative": physical_additional,
        "limiting_resource": limiting,
        "load_pressure": load_pressure,
        "io_contention": io_contention,
        "uninterruptible_threads": uninterruptible_threads,
        "agent_budget_gb": round(agent_budget, 2),
        "memory_slots": memory_slots,
        "cpu_slots": cpu_slots,
        "physical_memory_slots": physical_memory_slots,
        "physical_cpu_slots": physical_cpu_slots,
        "pending_ram_gb": round(pending_ram_gb, 3),
        "pending_cpu_cores": round(pending_cpu_cores, 3),
        "reserve_gb": args.reserve_gb,
        "cpu_reserve_cores": args.cpu_reserve_cores,
    }


def snapshot(args):
    observed_epoch=time.time()
    processes = parse_processes(run("ps", "-axo", "pid=,ppid=,%cpu=,rss=,comm="))
    children = defaultdict(list)
    for process in processes.values():
        children[process["ppid"]].append(process["pid"])

    app_roots = [
        pid
        for pid, process in processes.items()
        if os.path.basename(process["command"]) == "CodeAgentSwarm"
    ]
    all_app_pids = set(app_roots)
    for root in app_roots:
        all_app_pids.update(descendants(root, children))

    agents = []
    agent_pids = set()
    for app_root in app_roots:
        for pid in children.get(app_root, ()):
            env = safe_agent_env(pid)
            if not all(key in env for key in SAFE_ENV_KEYS):
                continue
            tree = {pid} | descendants(pid, children)
            agent_pids.update(tree)
            members = [processes[item] for item in tree if item in processes]
            agents.append(
                {
                    "terminal_id": env["CODEAGENTSWARM_TERMINAL_ID"],
                    "quadrant": int(env["CODEAGENTSWARM_CURRENT_QUADRANT"]),
                    "agent_type": env["CODEAGENTSWARM_AGENT_TYPE"],
                    "root_pid": pid,
                    "processes": len(members),
                    "rss_gb": round(sum(item["rss_kb"] for item in members) / 1048576, 2),
                    "cpu_percent": round(sum(item["cpu"] for item in members), 1),
                }
            )
    agents.sort(key=lambda item: item["quadrant"])

    platform_pids = all_app_pids - agent_pids
    platform = [processes[pid] for pid in platform_pids if pid in processes]
    top = run("top", "-l", "2", "-n", "0", "-s", "1")
    cpu = last_match(
        r"CPU usage:\s*([\d.]+)% user,\s*([\d.]+)% sys,\s*([\d.]+)% idle",
        top,
    )
    load = last_match(r"Load Avg:\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)", top)
    vm = last_match(r"VM:.*?(\d+)\((\d+)\) swapins,\s*(\d+)\((\d+)\) swapouts", top)
    pressure = run("memory_pressure", "-Q")
    free_pct = float(re.search(r"free percentage:\s*(\d+)%", pressure).group(1))
    total_bytes = int(run("sysctl", "-n", "hw.memsize").strip())
    logical_cpus = int(run("sysctl", "-n", "hw.logicalcpu").strip())
    total_gb = total_bytes / 1073741824
    args.logical_cpus = logical_cpus
    idle_pct = float(cpu[2])
    swapout_delta = int(vm[3]) if vm else 0
    runnable_threads, uninterruptible_threads = count_thread_states()
    load1 = float(load[0]) if load else None
    if managed_resources is None:
        managed = {
            "jobs": [], "active_jobs": 0, "queued_jobs": 0, "pending_jobs": 0,
            "pending_ram_gb": 0, "pending_cpu_cores": 0,
            "pending_growth": {"jobs": 0, "ram_gb": 0, "cpu_cores": 0},
            "journal_errors": 0,
            "note": "Managed-resource integration is unavailable in this legacy installation.",
        }
    else:
        try:
            managed = managed_resources.snapshot(processes=processes)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError,
                subprocess.SubprocessError) as exc:
            managed = managed_resources.empty(
                f"Managed-resource journal could not be sampled: {type(exc).__name__}", errors=1)
    capacity = compute_capacity(
        total_gb,
        free_pct,
        idle_pct,
        [agent["rss_gb"] for agent in agents],
        args,
        swapout_delta,
        load1,
        uninterruptible_threads,
        managed["pending_ram_gb"],
        managed["pending_cpu_cores"],
    )

    return {
        "snapshot_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "system": {
            "model": run("sysctl", "-n", "hw.model").strip(),
            "logical_cpus": logical_cpus,
            "memory_total_gb": round(total_gb, 2),
            "memory_effective_available_gb": round(total_gb * free_pct / 100, 2),
            "memory_effective_available_percent": free_pct,
            "cpu_user_percent": float(cpu[0]),
            "cpu_system_percent": float(cpu[1]),
            "cpu_idle_percent": idle_pct,
            "load_average": [float(item) for item in load] if load else None,
            "swapout_delta": swapout_delta,
            "runnable_threads": runnable_threads,
            "uninterruptible_threads": uninterruptible_threads,
        },
        "agents": agents,
        "agent_totals": {
            "count": len(agents),
            "rss_gb": round(sum(agent["rss_gb"] for agent in agents), 2),
            "cpu_percent": round(sum(agent["cpu_percent"] for agent in agents), 1),
        },
        "codeagentswarm_overhead": {
            "processes": len(platform),
            "rss_gb": round(sum(item["rss_kb"] for item in platform) / 1048576, 2),
            "cpu_percent": round(sum(item["cpu"] for item in platform), 1),
        },
        "capacity": capacity,
        "managed_resources": managed,
        "observed_epoch": observed_epoch,
        "notes": ["RSS es aproximada y puede duplicar memoria compartida."],
    }


def self_test():
    sample = " 10  1  2.5 1024 /app/CodeAgentSwarm\n 11 10 10.0 2048 node\n"
    processes = parse_processes(sample)
    assert processes[11]["ppid"] == 10
    assert descendants(10, {10: [11], 11: [12]}) == {11, 12}
    args = argparse.Namespace(
        agent_budget_gb=4,
        reserve_gb=8,
        agent_cpu_cores=1.5,
        cpu_reserve_cores=2,
        logical_cpus=14,
    )
    result = compute_capacity(36, 40, 70, [1, 2, 3], args)
    assert result["can_start_another"] is True
    assert result["additional_agents_conservative"] == 1

    claimed = compute_capacity(
        36, 50, 70, [], args, load1=2, uninterruptible_threads=0,
        pending_ram_gb=6, pending_cpu_cores=3,
    )
    assert claimed["physical_additional_agents_conservative"] == 2
    assert claimed["additional_agents_conservative"] == 1
    assert claimed["pending_ram_gb"] == 6

    # Escenario observado el 2026-09-29: load1≈88 en 14 núcleos con CPU ~47%
    # ociosa, RAM 81% libre y 0 hilos en espera ininterrumpida. La cola larga
    # (Defender/Spotlight en QoS fondo) se informa como "alta" pero NO veta.
    seen = compute_capacity(
        36, 81, 47, [3] * 6, args, load1=88, uninterruptible_threads=0
    )
    assert seen["can_start_another"] is True
    assert seen["additional_agents_conservative"] == 3
    assert seen["load_pressure"] == "alta"
    assert seen["io_contention"] is False

    # Saturación real de CPU: sin holgura ociosa no entra nadie, limita CPU.
    cpu = compute_capacity(
        36, 81, 5, [3] * 6, args, load1=88, uninterruptible_threads=0
    )
    assert cpu["can_start_another"] is False
    assert cpu["limiting_resource"] == "CPU"

    # Contención real de I/O: cola > núcleos Y esperas ininterrumpidas → rojo.
    io = compute_capacity(
        36, 81, 47, [3] * 6, args, load1=88, uninterruptible_threads=5
    )
    assert io["can_start_another"] is False
    assert io["limiting_resource"] == "I/O (esperas ininterrumpidas)"
    assert io["load_pressure"] == "saturación I/O"

    # Agotamiento real de memoria: swapouts recientes → memoria en 0.
    mem = compute_capacity(
        36, 81, 47, [3] * 6, args, swapout_delta=4, load1=88,
        uninterruptible_threads=0,
    )
    assert mem["can_start_another"] is False
    assert mem["limiting_resource"] == "memoria"

    # Medición inconclusa: sin dato de esperas U no se veta a ciegas.
    unknown = compute_capacity(
        36, 81, 47, [3] * 6, args, load1=88, uninterruptible_threads=None
    )
    assert unknown["can_start_another"] is True
    assert unknown["io_contention"] is False
    assert unknown["uninterruptible_threads"] is None

    # ps sin hilos reconocibles (solo cabecera) = inconclusa, no cero medido.
    header = "USER PID TT %CPU STAT PRI STIME UTIME COMMAND\n"
    assert parse_thread_states(header) == (None, None)
    runnable, uninterruptible = parse_thread_states(
        header
        + "root   1  ?? 0.0 S 31T 0:00.01 0:00.00 /sbin/launchd\n"
        + "         1     0.0 R 37T 0:00.20 0:00.03\n"
        + "         1     0.0 U 37T 0:00.05 0:00.04\n"
    )
    assert (runnable, uninterruptible) == (1, 1)

    print("self-test: OK")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-budget-gb", type=float, default=4)
    parser.add_argument("--reserve-gb", type=float, default=8)
    parser.add_argument("--agent-cpu-cores", type=float, default=1.5)
    parser.add_argument("--cpu-reserve-cores", type=float, default=2)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if os.uname().sysname != "Darwin":
        raise SystemExit("Esta versión mide macOS; no inventa una estimación en otro sistema.")
    print(json.dumps(snapshot(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
