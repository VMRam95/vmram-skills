---
name: stick-crisis-check-arch
description: Validate DDD + Hexagonal placement rules before creating or modifying classes in Stick Crisis.
---

# Stick Crisis Check Architecture

Use before implementation.

## Golden rule

If the class uses `UnityEngine`, `MonoBehaviour`, `ScriptableObject`, or Unity APIs:
- place in `infrastructure/`

If not:
- place in `domain/` or `application/`

## Quick checks

1. Read architecture rules:
- `docs/architecture-rules.md`
- `docs/architecture.md`
- `docs/coding-standards.md`

2. Layer constraints:
- `domain/`: pure C#, no Unity API
- `application/`: use cases/services, no Unity API
- `infrastructure/`: Unity integration

3. MonoBehaviour naming:
- must be in `infrastructure/`
- suffix must be `MonoBehaviour`
