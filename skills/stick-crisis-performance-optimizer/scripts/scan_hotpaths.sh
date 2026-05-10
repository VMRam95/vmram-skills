#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

OUT_BASE=".codex/skills/stick-crisis-performance-optimizer/reports"
TS="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="$OUT_BASE/$TS"
mkdir -p "$OUT_DIR"

UPDATES="$OUT_DIR/updates.txt"
COROUTINES="$OUT_DIR/coroutines.txt"
START_COROUTINE="$OUT_DIR/start_coroutine_calls.txt"
EXPENSIVE_APIS="$OUT_DIR/expensive_runtime_apis.txt"
HOT_BY_FILE="$OUT_DIR/hotpaths_by_file.txt"
SUMMARY="$OUT_DIR/hotpaths_summary.md"

rg -n "\\bvoid\\s+(Update|LateUpdate|FixedUpdate)\\s*\\(" Assets/Scripts --glob '*.cs' > "$UPDATES" || true
rg -n "\\bIEnumerator\\s+\\w+\\s*\\(" Assets/Scripts --glob '*.cs' > "$COROUTINES" || true
rg -n "\\bStartCoroutine\\s*\\(" Assets/Scripts --glob '*.cs' > "$START_COROUTINE" || true
rg -n "FindObjectOfType|FindObjectsOfType|GameObject\\.Find|Resources\\.Load|Instantiate\\(|Destroy\\(" Assets/Scripts --glob '*.cs' > "$EXPENSIVE_APIS" || true

cat "$UPDATES" "$COROUTINES" "$START_COROUTINE" "$EXPENSIVE_APIS" \
  | awk -F: '{count[$1]++} END {for (f in count) printf "%s:%d\n", f, count[f]}' \
  | sort -t: -k2,2nr > "$HOT_BY_FILE"

UPDATE_COUNT=$(wc -l < "$UPDATES" | tr -d ' ')
COROUTINE_COUNT=$(wc -l < "$COROUTINES" | tr -d ' ')
START_COROUTINE_COUNT=$(wc -l < "$START_COROUTINE" | tr -d ' ')
EXPENSIVE_COUNT=$(wc -l < "$EXPENSIVE_APIS" | tr -d ' ')

{
  echo "# Hot Path Inventory"
  echo
  echo "- Timestamp: $TS"
  echo "- Update/LateUpdate/FixedUpdate methods: $UPDATE_COUNT"
  echo "- Coroutine definitions: $COROUTINE_COUNT"
  echo "- StartCoroutine calls: $START_COROUTINE_COUNT"
  echo "- Expensive runtime API occurrences: $EXPENSIVE_COUNT"
  echo
  echo "## Top 30 candidate files"
  echo
  echo '```'
  head -n 30 "$HOT_BY_FILE"
  echo '```'
  echo
  echo "## Suggested optimization order"
  echo
  echo "1. Fix repeated StartCoroutine patterns from Update loops."
  echo "2. Remove expensive runtime find/load calls from hot paths."
  echo "3. Convert polling to event-driven updates where feasible."
  echo "4. Re-profile and compare against baseline."
} > "$SUMMARY"

echo "Hot path report generated: $SUMMARY"
