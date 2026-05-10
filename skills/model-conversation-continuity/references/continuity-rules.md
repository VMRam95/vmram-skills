# Continuity Rules

## 1) Determinism
- Use concrete facts from environment, not guesses.
- Include exact commit IDs, paths, and command lines.
- Keep section order fixed.

## 2) Decision Completeness
- The next model must not need to make choices that are already known.
- Capture defaults and assumptions explicitly.
- Specify commit separation if there are parallel pending changes.

## 3) Snapshot Hygiene
Always refresh before writing:
- `git status --short`
- recent commit log
- diffs for key pending files
- active task status if task tooling exists

## 4) Separation of Concerns
- `Done (Published)` = already committed/pushed.
- `Pending (Local)` = working tree changes not published.
- Do not collapse both into one list.

## 5) Validation Fidelity
- Persist the actual project validation protocol.
- If there is a mandatory order (e.g., build then asset refresh), keep it explicit.

## 6) Resume Output Contract
When asked to resume from handoff, output exactly:
- State Summary
- Immediate Next Action
- Validation Command(s)
- What To Test Now
- What Not To Mix In This Commit

## 7) Update Cadence
Refresh handoff:
- after each validated micro-step
- before ending a session
- before handing work to another model
