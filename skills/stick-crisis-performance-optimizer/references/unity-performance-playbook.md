# Unity Performance Playbook (Stick Crisis)

## Objective

Reach stable 60 FPS on desktop with reproducible profiling and zero gameplay regressions.

## Measurement first

1. Measure in Development build with Profiler attached.
2. Compare same scenario before/after each optimization.
3. Track:
- CPU Main Thread
- GC Alloc/frame
- Render thread + batches/setpass
- Physics2D costs
- Audio spikes

## CPU and scripting

1. Keep Update loops minimal.
2. Avoid expensive runtime search APIs in hot paths:
- `FindObjectOfType`
- `FindObjectsOfType`
- `GameObject.Find`
- `Resources.Load` in frequent runtime paths
3. Gate debug-only diagnostics with compile flags.
4. Prefer cached references and stable data structures.

## GC and allocations

1. Avoid per-frame allocations in gameplay loops.
2. Reuse collections/buffers where practical.
3. Avoid string-building/log formatting in hot paths.
4. Keep object pooling for bullets/grenades/enemies.

## Coroutine hygiene

1. Prevent duplicate coroutine starts from Update.
2. Ensure exit conditions and cancellation on disable/destroy.
3. Replace polling coroutines with event-driven flows where feasible.

## 2D isometric shooter specifics

1. Reduce overdraw from stacked transparent sprites.
2. Favor texture atlasing/material reuse for batching.
3. Keep world-space UI update frequency controlled.
4. Validate nav and movement transitions do not cause CPU spikes.

## Release logging policy

1. Runtime release: critical errors only.
2. Keep detailed diagnostics only in editor/development builds.

## Primary Unity references

- https://docs.unity3d.com/2022.2/Documentation/Manual/overview-of-dot-net-in-unity.html
- https://docs.unity3d.com/2022.2/Documentation/Manual/performance-garbage-collection-best-practices.html
- https://docs.unity3d.com/Manual/profiler-cpu-module.html
- https://docs.unity3d.com/Manual/profiler-memory-module.html
- https://docs.unity3d.com/Manual/fixed-updates.html
- https://docs.unity3d.com/Manual/2d-optimization-overview.html
