---
name: stick-crisis-performance-optimizer
description: Optimize and iteratively refine performance for the Stick Crisis Unity project. Use when auditing Debug logs, Update/Coroutine hot paths, expensive runtime lookups, and frame-time/GC bottlenecks in this repository. Use for baseline creation, prioritized optimization passes, and repeatable performance checks.
---

# Stick Crisis Performance Optimizer

Use this skill to run a repeatable optimization workflow for this repo.

## Quick Start

1. Run debug-log inventory:
```bash
./.codex/skills/stick-crisis-performance-optimizer/scripts/scan_debug_logs.sh
```
2. Run hot-path inventory:
```bash
./.codex/skills/stick-crisis-performance-optimizer/scripts/scan_hotpaths.sh
```
3. Read results under:
`./.codex/skills/stick-crisis-performance-optimizer/reports/<timestamp>/`
4. Apply fixes by priority: high-impact first.
5. Run change-build (dotnet):
```bash
./.codex/skills/stick-crisis-performance-optimizer/scripts/build_changes_dotnet.sh
```

## Mandatory Validation Per Change

Run these two actions on every code change before manual gameplay testing:

1. Unity asset refresh (not reimport):
- Execute Unity menu item: `Assets/Refresh`

2. Change build (no game build):
- Run `dotnet` build using:
- `./.codex/skills/stick-crisis-performance-optimizer/scripts/build_changes_dotnet.sh`

No test-run step is required for build validation in this workflow.

## Workflow

1. Baseline
- Profile in Development build with Unity Profiler attached.
- Capture: CPU main thread, GC alloc/frame, render overdraw, draw calls, physics and audio spikes.

2. Logging pass
- Keep only release-critical errors in runtime gameplay paths.
- Gate diagnostic logs with `UNITY_EDITOR || DEVELOPMENT_BUILD`.
- Remove frame-loop spam logs.

3. Hot-path pass
- Review `Update`, `LateUpdate`, `FixedUpdate`, coroutine loops and `StartCoroutine` patterns.
- Remove repeated expensive operations from per-frame paths.
- Cache references and avoid runtime search APIs in frequent paths.

4. Validation
- Re-profile same scenario and compare with baseline.
- Keep behavior parity for movement/combat/UI/tutorial transitions.
- Before gameplay validation, always run: `Assets/Refresh` + dotnet change-build.

## Project-specific focus

Prioritize these hotspots first:
- `Assets/Scripts/combatant/domain/Combatant.cs`
- `Assets/Scripts/enemy/domain/EnemyCombatant.cs`
- `Assets/Scripts/scene/application/find/SceneFinder.cs`
- `Assets/Scripts/tutorial/infrastructure/adapters/TutorialMonoBehaviour.cs`
- `Assets/Scripts/ui/domain/stats/infrastructure/LevelTimerUI.cs`
- `Assets/Scripts/ui/infrastructure/ResponsiveCanvasScaler.cs`

Then review log-heavy classes:
- `Assets/Scripts/level/application/generate/LevelGenerator.cs`
- `Assets/Scripts/ui/domain/menu/infrastructure/MainMenuUI.cs`
- `Assets/Scripts/ui/domain/menu/infrastructure/PauseMenuUI.cs`

## References

Read as needed:
- `references/unity-performance-playbook.md`
- `references/stick-crisis-hotspots.md`

## Acceptance Criteria

- Desktop target: stable 60 FPS in representative combat scenarios.
- Significant reduction of avoidable runtime logs.
- Lower GC pressure in gameplay hot paths.
- No gameplay regression in combat, navigation, phase transitions, or tutorial flow.
