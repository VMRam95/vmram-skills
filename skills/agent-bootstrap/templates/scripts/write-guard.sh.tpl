#!/bin/bash
#
# write-guard.sh — hook PreToolUse que impide al arquitecto escribir fuera de su KB.
#
# DISEÑO FAIL-SAFE: bloquea SOLO si se cumplen TODAS las condiciones. Ante cualquier
# duda —otro agente, JSON ilegible, falta jq, herramienta que no escribe— PERMITE.
# Es imposible que sobre-bloquee.
#
# [tool-owned]

set -uo pipefail

AGENTE_PROTEGIDO="<PREFIJO>-architect"
KB_PATH="<KB_PATH>"

permitir() { exit 0; }

command -v jq >/dev/null 2>&1 || permitir          # sin jq no juzgamos
payload="$(cat 2>/dev/null)" || permitir
[ -n "$payload" ] || permitir
echo "$payload" | jq -e . >/dev/null 2>&1 || permitir   # JSON inválido → permitir

agent_type="$(echo "$payload" | jq -r '.agent_type // empty' 2>/dev/null)"
[ "$agent_type" = "$AGENTE_PROTEGIDO" ] || permitir      # otro agente → permitir

tool="$(echo "$payload" | jq -r '.tool_name // empty' 2>/dev/null)"
case "$tool" in
  Write|Edit|NotebookEdit) ;;
  *) permitir ;;                                          # no escribe → permitir
esac

ruta="$(echo "$payload" | jq -r '.tool_input.file_path // empty' 2>/dev/null)"
[ -n "$ruta" ] || permitir

case "$ruta" in
  "$KB_PATH"*) permitir ;;                                # dentro de la KB → permitir
esac

# Única vía de bloqueo
cat <<JSON
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"El arquitecto sólo escribe en su base de conocimiento ($KB_PATH). Ruta rechazada: $ruta. Si el cambio es necesario, produce un ADR o una recomendación y que lo ejecute un especialista."}}
JSON
exit 0
