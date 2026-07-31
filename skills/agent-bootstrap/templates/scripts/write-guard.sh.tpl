#!/bin/bash
#
# write-guard.sh — hook PreToolUse que impide al arquitecto escribir fuera de su KB.
#
# DISEÑO FAIL-SAFE: bloquea SOLO si se cumplen TODAS las condiciones. Ante cualquier
# duda —otro agente, JSON ilegible, falta jq, herramienta que no escribe— PERMITE.
# Es imposible que sobre-bloquee.
#
# La ruta de la KB se CALCULA en tiempo de ejecución desde la ubicación de este propio
# script, no se hornea al generar el proyecto. Así:
#   · sobrevive a mover, renombrar o clonar el repo de agentes,
#   · y NO es eludible construyendo una ruta que contenga el sufijo de la KB, que es
#     lo que pasaba matcheando por sufijo.
# La comparación es por prefijo absoluto y con la ruta normalizada, de modo que un
# traversal con `..` no se cuela.
#
# [tool-owned]

set -uo pipefail

AGENTE_PROTEGIDO="<PREFIJO>-architect"

permitir() { exit 0; }

# Este script vive en <repo-agentes>/agents/<agente>/scripts/, así que la KB está
# tres niveles por encima. Si no se puede resolver, permitimos: fail-safe.
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd -P)" || permitir
KB_DIR="$(cd "$AQUI/../knowledge-base" 2>/dev/null && pwd -P)" || permitir
[ -n "${KB_DIR:-}" ] || permitir

command -v jq >/dev/null 2>&1 || permitir
payload="$(cat 2>/dev/null)" || permitir
[ -n "$payload" ] || permitir
printf '%s' "$payload" | jq -e . >/dev/null 2>&1 || permitir

agent_type="$(printf '%s' "$payload" | jq -r 'if (.agent_type|type)=="string" then .agent_type else empty end' 2>/dev/null)"
[ "$agent_type" = "$AGENTE_PROTEGIDO" ] || permitir

tool="$(printf '%s' "$payload" | jq -r 'if (.tool_name|type)=="string" then .tool_name else empty end' 2>/dev/null)"
case "$tool" in
  Write|Edit|NotebookEdit) ;;
  *) permitir ;;
esac

ruta="$(printf '%s' "$payload" | jq -r '(.tool_input.file_path // .tool_input.notebook_path // "") | if type=="string" then . else "" end' 2>/dev/null)"
[ -n "$ruta" ] || permitir

# Normaliza la ruta. Si el directorio padre ya existe, se resuelve de verdad
# (así se deshacen también los symlinks). Si NO existe —fichero nuevo en una
# carpeta nueva—, se normaliza léxicamente: colapsar `.` y `..` a mano. Antes
# esto caía en "permitir", y era un agujero: bastaba apuntar a una ruta
# inexistente fuera de la KB para saltarse el guard.
normalizar_lexico() {
  local ruta="$1" segmento salida=""
  case "$ruta" in /*) ;; *) ruta="$PWD/$ruta" ;; esac
  local IFS=/
  for segmento in $ruta; do
    case "$segmento" in
      ""|.) ;;
      ..)   salida="${salida%/*}" ;;
      *)    salida="$salida/$segmento" ;;
    esac
  done
  printf '%s' "${salida:-/}"
}

dir_padre="$(cd "$(dirname "$ruta")" 2>/dev/null && pwd -P)"
if [ -n "${dir_padre:-}" ]; then
  ruta_real="$dir_padre/$(basename "$ruta")"
else
  ruta_real="$(normalizar_lexico "$ruta")"
fi

# Dentro de la KB → permitir. Comparación por prefijo absoluto ya normalizado.
case "$ruta_real" in
  "$KB_DIR"/*) permitir ;;
esac

cat <<JSON
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"El arquitecto solo escribe en su base de conocimiento ($KB_DIR). Ruta rechazada: $ruta_real. Si el cambio es necesario, produce un ADR o una recomendacion precisa y que lo ejecute un especialista o el hilo principal."}}
JSON
exit 0
