#!/bin/bash
#
# write-guard.sh — hook PreToolUse que impide al arquitecto escribir fuera de su KB.
#
# DISEÑO FAIL-SAFE: bloquea SOLO si se cumplen TODAS las condiciones. Ante cualquier
# duda —otro agente, JSON ilegible, falta jq, herramienta que no escribe— PERMITE.
# Es imposible que sobre-bloquee.
#
# Matchea por SUFIJO de ruta, no por ruta absoluta: así el repo de agentes se puede
# mover, renombrar o clonar en otra máquina sin que el guard deje de proteger.
#
# Cableado (lo hace install.sh en cada máquina, con la ruta absoluta de ESA máquina):
#   hooks.PreToolUse[].matcher       = "Write|Edit|NotebookEdit"
#   hooks.PreToolUse[].hooks[].command = ruta absoluta a este script
#
# [tool-owned]

set -uo pipefail

AGENTE_PROTEGIDO="<PREFIJO>-architect"
KB_SUFIJO="<KB_REL>"

permitir() { exit 0; }

command -v jq >/dev/null 2>&1 || permitir
payload="$(cat 2>/dev/null)" || permitir
[ -n "$payload" ] || permitir
printf '%s' "$payload" | jq -e . >/dev/null 2>&1 || permitir

agent_type="$(printf '%s' "$payload" | jq -r '.agent_type // empty' 2>/dev/null)"
[ "$agent_type" = "$AGENTE_PROTEGIDO" ] || permitir

tool="$(printf '%s' "$payload" | jq -r '.tool_name // empty' 2>/dev/null)"
case "$tool" in
  Write|Edit|NotebookEdit) ;;
  *) permitir ;;
esac

ruta="$(printf '%s' "$payload" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' 2>/dev/null)"
[ -n "$ruta" ] || permitir

# Dentro de la KB → permitir. El sufijo lleva barra final, así que /kb-otra-cosa NO matchea.
case "$ruta" in
  */"$KB_SUFIJO"*) permitir ;;
esac

cat <<JSON
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"El arquitecto solo escribe en su base de conocimiento ($KB_SUFIJO). Ruta rechazada: $ruta. Si el cambio es necesario, produce un ADR o una recomendacion precisa y que lo ejecute un especialista o el hilo principal."}}
JSON
exit 0
