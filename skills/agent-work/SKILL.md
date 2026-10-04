---
name: agent-work
description: Start, validate, measure and close isolated local work through the project profile. Use for parallel agents, worker assignments, full local delivery, resource admission, recovery or verified cleanup, inside and outside CAS.
---

# Autonomous local work

Use the project's installed profile and canonical manager. Read its instructions and
`agent-local-work` for bounded inspection and resource ownership. Missing profiles
are a concrete setup task: never guess a database, port or teardown command.

```sh
python3 -B ~/.agents/skills/agent-work/scripts/agent_work.py start \
  --profile /exact/project/profile.json --root /exact/workspace --task TICKET \
  --wait 300 --output /exact/workspace/artifacts/TICKET/start.json
```

Keep the returned job ID. The private journal remembers the session, generation,
manager reservation, resources and frozen profile. Do not export its tokens into
reports. Independent terminals need a stable `AGENT_LOCAL_OWNER`; CAS/Codex/Claude
session IDs are recognized automatically. Changing model does not change ownership.

Wait for `start` to finish with exit 0 and state `ready` before editing a recorded
worktree or running a probe. A tool's running `session_id` only means the CLI is
still executing; it does not mean the stack is ready. Editing during `prepare`,
`up` or initial `health` invalidates the startup source manifest and triggers a
failed start with cleanup. Persist that failure rather than counting it as a pass.

A queued job returns exit 75. Initial admission opens no project resources;
capacity queues for an existing ready stack retain its verified resources. Resume `start`
with the same job, or use bounded `--wait`. Tasks can coexist while expensive
stacks/tests wait for physically measured RAM, CPU and disk. No TTL, dead-owner
reclamation, background polling or chat watchers are installed.
Only queued or active generations can resume; a `closed` generation needs a new
job with the same stable session owner after its cleanup is verified.

Work inside the recorded project worktrees. After implementation, use `start --job`
to verify the served revision and `exec` for the real local flow and mobile captures
before `validate`. Some project suites stop their database in their final cleanup:
afterward review saved evidence and capture offline reports. More live checks need
a fresh generation of the same source; never bypass an inactive resource journal.
Then run:

```sh
python3 -B ~/.agents/skills/agent-work/scripts/agent_work.py validate --job JOB --wait 300
python3 -B ~/.agents/skills/agent-work/scripts/agent_work.py deliver --job JOB --evidence /exact/workspace/artifacts/TICKET/delivery.json
python3 -B ~/.agents/skills/agent-work/scripts/agent_work.py close --job JOB
python3 -B ~/.agents/skills/agent-work/scripts/agent_work.py report --output /exact/workspace/artifacts/TICKET/runs.html
python3 -B ~/.agents/skills/agent-work/scripts/agent_work.py compare --job BASELINE --other NEW --output /exact/workspace/artifacts/TICKET/comparison.json
```

`run` combines start, full validation and finally closure for unattended checks.
Use `start`/`validate`/`close` for implementation. Close at delivery, cancellation or
failure; a retained WIP worktree still needs its services and regenerable caches
cleaned. If the CLI was killed, `close` recovers only its registered process groups.
A failed verification retains the claim and reports `cleanup_pending`.

Run auxiliary commands and visual capture helpers through the same journal:

```sh
python3 -B ~/.agents/skills/agent-work/scripts/agent_work.py exec --job JOB \
  --cwd /exact/workspace/recorded-worktree --timeout 300 -- python3 capture.py
```

`exec` records its real exit and drains only its registered group. It requires a
ready stack and measured test capacity; it does not replace the full `validate`
gate. After an interrupted phase, resume with `close` before starting more work.

Full validation requires the inventory discovered **before** execution, all required
suites, every case passed once, actual zero exit codes, zero skips/pending/errors,
and unchanged Git source/version during the run. Partial suites and retries cannot
produce a passing gate. The test gate does not alone prove product delivery: open
its PR against the declared fresh base, exercise its real local UI/API flow, check
responsive behavior and save/inspect screenshots under `artifacts/TICKET/`. Follow
the project's approval and Kanban gates. Never merge or complete by elapsed time.

A worker closes its own job before reporting and includes job ID, tested versions,
case/suite counts, logs, PR/ticket, real screenshot links, cleanup and pending work.
The coordinator verifies evidence and postconditions before closing the worker.

Profiles and evidence: [contract](references/contract.md).
Measurements: [performance](references/performance.md).
