---
name: stick-crisis-add-skin
description: Register a new character skin in Stick Crisis by updating SkinType and SkinConfig using existing AnimatorOverrideControllers.
---

# Stick Crisis Add Skin

Use this skill with: `SKIN_NAME`.

## Required assets

- `Assets/Resources/Animations/Skins/{SKIN_NAME}/`
- `{SKIN_NAME}-Gun-AOC.overrideController`
- `{SKIN_NAME}-Grenade-AOC.overrideController`
- `{SKIN_NAME}-MachineGun-AOC.overrideController`

## Steps

1. Validate `SKIN_NAME` exists and required assets are present.
2. Check `Assets/Scripts/shared/domain/skin/SkinType.cs` and stop if skin already exists.
3. Read `.meta` files and extract GUIDs for Gun/Grenade/MachineGun AOCs.
4. Compute next enum value from `SkinType.cs`.
5. Update `SkinType.cs` by adding:
```csharp
/// <summary>
/// {SKIN_NAME} character skin
/// </summary>
{SKIN_NAME} = {ENUM_VALUE},
```
6. Update `Assets/Resources/Config/SkinConfig.asset` by appending new `SkinAnimationSet` with extracted GUIDs.
7. Run build workflow skill: `stick-crisis-build`.
8. Confirm result with `SkinType.{SKIN_NAME} = {ENUM_VALUE}`.

## Files modified

- `Assets/Scripts/shared/domain/skin/SkinType.cs`
- `Assets/Resources/Config/SkinConfig.asset`
