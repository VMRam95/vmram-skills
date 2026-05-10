#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

DOTNET_BIN="${DOTNET_BIN:-$HOME/.dotnet/dotnet}"
if [[ ! -x "$DOTNET_BIN" ]]; then
  echo "ERROR: dotnet binary not found at '$DOTNET_BIN'"
  echo "Set DOTNET_BIN to your dotnet executable path."
  exit 1
fi

changed_cs_files="$(
  {
    git diff --name-only -- '*.cs'
    git diff --name-only --cached -- '*.cs'
    git ls-files --others --exclude-standard -- '*.cs'
  } | awk 'NF' | sort -u
)"

declare -a projects=()
need_solution_build=false

if [[ -z "$changed_cs_files" ]]; then
  projects+=("Assembly-CSharp.csproj")
else
  while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    if [[ "$file" == Assets/NavMeshComponents/* ]]; then
      projects+=("NavMeshPlus.csproj")
      if [[ "$file" == *"/Editor/"* || "$file" == *Editor.cs ]]; then
        projects+=("NavMeshPlusEditor.csproj")
      fi
    elif [[ "$file" == Assets/* ]]; then
      if [[ "$file" == *"/Editor/"* || "$file" == *Editor.cs ]]; then
        projects+=("Assembly-CSharp-Editor.csproj")
      else
        projects+=("Assembly-CSharp.csproj")
      fi
    else
      need_solution_build=true
    fi
  done <<< "$changed_cs_files"
fi

if [[ "$need_solution_build" == true ]]; then
  projects=("stick-crisis.sln")
fi

unique_projects="$(printf '%s\n' "${projects[@]}" | awk 'NF' | sort -u)"

echo "Using dotnet: $DOTNET_BIN"
echo "Build targets:"
while IFS= read -r project; do
  [[ -z "$project" ]] && continue
  echo "  - $project"
done <<< "$unique_projects"

while IFS= read -r project; do
  [[ -z "$project" ]] && continue
  "$DOTNET_BIN" build "$project" --nologo --verbosity minimal
done <<< "$unique_projects"

echo "dotnet change-build completed successfully."
