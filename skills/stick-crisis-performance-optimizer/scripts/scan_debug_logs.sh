#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

OUT_BASE=".codex/skills/stick-crisis-performance-optimizer/reports"
TS="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="$OUT_BASE/$TS"
mkdir -p "$OUT_DIR"

LOG_RAW="$OUT_DIR/debug_logs_raw.txt"
LOG_ACTIVE="$OUT_DIR/debug_logs_active.txt"
LOG_BY_FILE="$OUT_DIR/debug_logs_by_file.txt"
LOG_SUMMARY="$OUT_DIR/debug_logs_summary.md"

RG_BIN="rg"
if ! command -v rg >/dev/null 2>&1; then
  RG_BIN="grep"
fi

if [[ "$RG_BIN" == "rg" ]]; then
  rg -n "Debug\\.(Log|LogWarning|LogError|Assert)\\(" Assets --glob '*.cs' > "$LOG_RAW" || true
else
  grep -RInE "Debug\\.(Log|LogWarning|LogError|Assert)\\(" Assets --include='*.cs' > "$LOG_RAW" || true
fi

# Filter out commented lines (simple heuristic)
awk -F: 'index($0, "//") == 0 || index($0, "Debug.") < index($0, "//")' "$LOG_RAW" > "$LOG_ACTIVE" || true

awk -F: '{count[$1]++} END {for (f in count) printf "%s:%d\n", f, count[f]}' "$LOG_ACTIVE" | sort -t: -k2,2nr > "$LOG_BY_FILE"

TOTAL=$(wc -l < "$LOG_ACTIVE" | tr -d ' ')
FILES=$(awk -F: '{print $1}' "$LOG_ACTIVE" | sort -u | wc -l | tr -d ' ')

{
  echo "# Debug Log Inventory"
  echo
  echo "- Timestamp: $TS"
  echo "- Active debug calls: $TOTAL"
  echo "- Files with debug calls: $FILES"
  echo
  echo "## Top 30 files by debug calls"
  echo
  echo '```'
  head -n 30 "$LOG_BY_FILE"
  echo '```'
  echo
  echo "## Next actions"
  echo
  echo "1. Keep release-critical errors only in runtime gameplay paths."
  echo "2. Gate diagnostic logs with UNITY_EDITOR || DEVELOPMENT_BUILD."
  echo "3. Remove logs in frame loops/coroutine loops first."
} > "$LOG_SUMMARY"

echo "Debug log report generated: $LOG_SUMMARY"
