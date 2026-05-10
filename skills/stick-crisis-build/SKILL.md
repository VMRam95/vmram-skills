---
name: stick-crisis-build
description: Compile C# changes for Stick Crisis using dotnet and then refresh Unity assets. Use after any C# code change in this project.
---

# Stick Crisis Build

Mandatory workflow for C# changes.

## Steps

1. Compile C#:
```bash
~/.dotnet/dotnet build Assembly-CSharp.csproj -c Debug
```

2. Evaluate result:
- If there are errors, report them as `file:line:column` and stop.
- If compilation succeeds with 0 errors, continue.

3. Refresh Unity assets:
- Execute Unity menu item: `Assets/Refresh`

4. Confirm to user that changes are applied in Unity.

## Notes

- This workflow is mandatory after any C# change.
- Do not run Unity game builds as part of this step.
