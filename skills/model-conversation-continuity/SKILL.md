---
name: model-conversation-continuity
description: Create, refresh, and resume cross-model handoff files so another model can continue work without loss of context. Use when you need to persist current status, decisions, pending work, validation steps, and exact next actions.
---

# Model Conversation Continuity

Use this skill to transfer working context between models (Codex, Claude, etc.) in a deterministic, decision-complete format.

## Inputs

Use these runtime parameters in your prompt:
- `mode`: `create | refresh | resume`
- `handoff_path`: markdown file path
- `scope`: `full | technical-only | executive`
- `include_parallel_changes`: `true | false` (default `true`)
- `commit_policy`: `none | handoff-only` (default `none`)

Defaults:
- `mode=refresh`
- `scope=full`
- `include_parallel_changes=true`
- `commit_policy=none`

Stick Crisis preset:
- If repo name is `stick-crisis`, default `handoff_path=docs/HANDOFF-OPTIMIZACION.md`.

## Required Handoff Section Contract

The handoff file must contain these sections in this order:
1. `# Handoff <Project>`
2. `## Snapshot`
3. `## Objective`
4. `## Current Status`
5. `## Done (Published)`
6. `## Pending (Local)`
7. `## Validation Protocol`
8. `## Manual QA Checklist`
9. `## Next Exact Steps`
10. `## Risks / Notes`
11. `## Commands`
12. `## Conversation Continuity Notes`

Use `templates/handoff-template.md` as skeleton.

## Workflow

### Mode: create
1. Detect repo and branch.
2. Collect current status (`git status --short`, recent commits, key diffs).
3. Create handoff file from template.
4. Fill each required section with concrete values.

### Mode: refresh
1. Read existing handoff file.
2. Refresh Snapshot, Current Status, Done/Pending, and Next Exact Steps.
3. Preserve useful historical context in Conversation Continuity Notes.
4. Keep section order unchanged.

### Mode: resume
1. Read handoff file.
2. Produce resume output in this exact structure:
- `State Summary`
- `Immediate Next Action`
- `Validation Command(s)`
- `What To Test Now`
- `What Not To Mix In This Commit`
3. Do not mutate files in `resume` mode.

## Rules

- Separate published work from local pending changes.
- Do not mix unrelated pending changes into the same suggested commit.
- Prefer exact commands and file paths over prose.
- Record explicit assumptions and defaults.
- If validation protocol exists for the repo, keep it explicit and unambiguous.

For additional constraints and quality bar, read `references/continuity-rules.md`.
