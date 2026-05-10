#!/usr/bin/env bash
# Install one or more skills from this repo into ~/.claude/skills (or ~/.codex/skills).
#
# Usage (after cloning):
#   ./install.sh conventional-commits review-pr web-search-plus
#   ./install.sh --target codex create-project
#   ./install.sh --all
#
# Usage (curl one-liner, no clone):
#   curl -sL https://raw.githubusercontent.com/VMRam95/vmram-skills/main/install.sh | bash -s -- conventional-commits review-pr
#   curl -sL https://raw.githubusercontent.com/VMRam95/vmram-skills/main/install.sh | bash -s -- --all

set -euo pipefail

REPO_URL="https://github.com/VMRam95/vmram-skills.git"
RAW_BASE="https://raw.githubusercontent.com/VMRam95/vmram-skills/main"
TARGET_HOST="claude"
INSTALL_ALL=0
SKILLS=()

usage() {
  cat <<EOF
Usage: $0 [--target claude|codex] [--all] <skill> [<skill> ...]

Options:
  --target <host>   Install destination: 'claude' (default) -> ~/.claude/skills
                                          'codex'           -> ~/.codex/skills
  --all             Install every skill in the repo
  -h, --help        Show this help

Examples:
  $0 conventional-commits review-pr
  $0 --target codex create-project
  $0 --all
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET_HOST="$2"; shift 2 ;;
    --all)    INSTALL_ALL=1; shift ;;
    -h|--help) usage; exit 0 ;;
    --) shift; SKILLS+=("$@"); break ;;
    -*) echo "Unknown option: $1" >&2; usage; exit 1 ;;
    *) SKILLS+=("$1"); shift ;;
  esac
done

case "$TARGET_HOST" in
  claude) DEST="$HOME/.claude/skills" ;;
  codex)  DEST="$HOME/.codex/skills" ;;
  *) echo "Invalid --target: $TARGET_HOST (expected 'claude' or 'codex')" >&2; exit 1 ;;
esac

mkdir -p "$DEST"

# Detect mode: are we running from a clone or piped via curl?
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
LOCAL_SKILLS_DIR=""
if [[ -n "$SCRIPT_DIR" && -d "$SCRIPT_DIR/skills" ]]; then
  LOCAL_SKILLS_DIR="$SCRIPT_DIR/skills"
fi

# If --all and no local clone, do a shallow clone to a temp dir
TMP_CLONE=""
cleanup() {
  if [[ -n "$TMP_CLONE" && -d "$TMP_CLONE" ]]; then
    rm -rf "$TMP_CLONE"
  fi
}
trap cleanup EXIT

if [[ "$INSTALL_ALL" -eq 1 && -z "$LOCAL_SKILLS_DIR" ]]; then
  TMP_CLONE="$(mktemp -d)"
  echo "Cloning $REPO_URL (shallow)..."
  git clone --depth=1 --quiet "$REPO_URL" "$TMP_CLONE"
  LOCAL_SKILLS_DIR="$TMP_CLONE/skills"
fi

if [[ "$INSTALL_ALL" -eq 1 ]]; then
  SKILLS=()
  while IFS= read -r d; do SKILLS+=("$(basename "$d")"); done < <(find "$LOCAL_SKILLS_DIR" -mindepth 1 -maxdepth 1 -type d)
fi

if [[ ${#SKILLS[@]} -eq 0 ]]; then
  echo "No skills specified." >&2
  usage
  exit 1
fi

install_local() {
  local name="$1"
  local src="$LOCAL_SKILLS_DIR/$name"
  if [[ ! -d "$src" ]]; then
    echo "  ✗ $name (not found in $LOCAL_SKILLS_DIR)"
    return 1
  fi
  cp -R "$src" "$DEST/"
  echo "  ✓ $name -> $DEST/$name"
}

install_remote() {
  local name="$1"
  local tmp; tmp="$(mktemp -d)"
  trap "rm -rf '$tmp'" RETURN
  if git -C "$tmp" clone --depth=1 --filter=blob:none --sparse --quiet "$REPO_URL" . >/dev/null 2>&1; then
    git -C "$tmp" sparse-checkout set "skills/$name" >/dev/null 2>&1
    if [[ -d "$tmp/skills/$name" ]]; then
      cp -R "$tmp/skills/$name" "$DEST/"
      echo "  ✓ $name -> $DEST/$name (fetched)"
      return 0
    fi
  fi
  echo "  ✗ $name (failed to fetch — does it exist in the repo?)"
  return 1
}

echo "Installing ${#SKILLS[@]} skill(s) into $DEST"
fail=0
for s in "${SKILLS[@]}"; do
  if [[ -n "$LOCAL_SKILLS_DIR" ]]; then
    install_local "$s" || fail=$((fail+1))
  else
    install_remote "$s" || fail=$((fail+1))
  fi
done

if [[ "$fail" -gt 0 ]]; then
  echo "Done with $fail failure(s)."
  exit 1
fi
echo "Done. Restart your Claude Code / Codex session to load the new skills."
