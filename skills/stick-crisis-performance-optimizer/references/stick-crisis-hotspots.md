# Stick Crisis Hotspots

## Priority 1

1. `Assets/Scripts/combatant/domain/Combatant.cs`
- Review OffMeshLink traversal trigger from `Update`.
- Prevent duplicate coroutine starts per frame.

2. `Assets/Scripts/enemy/domain/EnemyCombatant.cs`
- Validate movement state transitions and coroutine churn.
- Ensure no unnecessary path/movement recalculation.

3. `Assets/Scripts/scene/application/find/SceneFinder.cs`
- Reduce runtime search operations and LINQ fallback usage in gameplay-time paths.

## Priority 2

1. `Assets/Scripts/tutorial/infrastructure/adapters/TutorialMonoBehaviour.cs`
- Reduce per-frame input polling where event-based logic is possible.

2. `Assets/Scripts/ui/domain/stats/infrastructure/LevelTimerUI.cs`
- Keep UI updates throttled and avoid unnecessary class/style churn.

3. `Assets/Scripts/ui/infrastructure/ResponsiveCanvasScaler.cs`
- Avoid full polling updates if resolution is stable.

## Priority 3 (log-heavy)

1. `Assets/Scripts/level/application/generate/LevelGenerator.cs`
2. `Assets/Scripts/ui/domain/menu/infrastructure/MainMenuUI.cs`
3. `Assets/Scripts/ui/domain/menu/infrastructure/PauseMenuUI.cs`

## Runtime API patterns to minimize in hot paths

- `FindObjectOfType`, `FindObjectsOfType`
- `GameObject.Find`
- `Resources.Load`
- `Instantiate`/`Destroy` bursts

## Acceptance checks

1. Stable 60 FPS in representative combat scenario.
2. Lower CPU spikes vs baseline.
3. Reduced GC alloc/frame in active gameplay.
4. No regression in movement, cover, shooting, phase transitions, tutorial.
