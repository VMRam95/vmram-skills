#!/bin/bash
#
# install.sh — enlaza los agentes de este repo dentro de ~/.claude/agents/
#              y cablea el hook write-guard en settings.json.
#
#   bash install.sh              # instala
#   bash install.sh --dry-run    # enseña lo que haría, sin tocar nada
#
# Idempotente: se puede ejecutar las veces que haga falta. Nunca borra un fichero real
# que ya esté en el destino sin hacerle copia de seguridad primero.
# Recorre dinámicamente agents/, así que añadir un agente NO requiere tocar este script.
#
# [tool-owned] — lo actualiza `agent-bootstrap upgrade`.

set -uo pipefail

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run|-n) DRY_RUN=1 ;;
    -h|--help) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Opción desconocida: $arg" >&2; exit 2 ;;
  esac
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_HOME:-$HOME/.claude}"
AGENTS_DIR="$CLAUDE_DIR/agents"
SETTINGS="$CLAUDE_DIR/settings.json"

if [ -t 1 ]; then
  C_OK=$'\033[0;32m'; C_WARN=$'\033[0;33m'; C_ERR=$'\033[0;31m'; C_DIM=$'\033[0;90m'; C_OFF=$'\033[0m'
else
  C_OK=''; C_WARN=''; C_ERR=''; C_DIM=''; C_OFF=''
fi

[ "$DRY_RUN" -eq 1 ] && echo "${C_DIM}=== DRY RUN: no se modifica nada ===${C_OFF}"
echo "Repo:    $REPO_DIR"
echo "Destino: $AGENTS_DIR"
echo

n_linked=0; n_ok=0; n_skipped=0

[ "$DRY_RUN" -eq 0 ] && mkdir -p "$AGENTS_DIR"

# --- 1. Symlink de cada charter -------------------------------------------------
for agent_dir in "$REPO_DIR"/agents/*/; do
  [ -d "$agent_dir" ] || continue
  agent_name="$(basename "$agent_dir")"
  charter="$agent_dir$agent_name.md"

  if [ ! -f "$charter" ]; then
    echo "${C_WARN}⚠  $agent_name: no encuentro $agent_name.md, me lo salto${C_OFF}"
    n_skipped=$((n_skipped + 1)); continue
  fi

  dest="$AGENTS_DIR/$agent_name.md"

  if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$charter" ]; then
    echo "${C_DIM}✓  $agent_name (ya enlazado)${C_OFF}"; n_ok=$((n_ok + 1)); continue
  fi

  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    echo "${C_WARN}⚠  $agent_name: ya existe un fichero REAL en el destino${C_OFF}"
    if [ "$DRY_RUN" -eq 0 ]; then
      cp "$dest" "$dest.bak.$(date +%Y%m%d%H%M%S)"
      echo "   copia de seguridad hecha"
    fi
  fi

  if [ "$DRY_RUN" -eq 0 ]; then
    ln -sfn "$charter" "$dest" && echo "${C_OK}→  $agent_name${C_OFF}" && n_linked=$((n_linked + 1))
  else
    echo "→  $agent_name (se enlazaría)"; n_linked=$((n_linked + 1))
  fi
done

# --- 2. Hook write-guard --------------------------------------------------------
GUARD="$REPO_DIR/agents/<PREFIJO>-architect/scripts/write-guard.sh"
echo
if [ -f "$GUARD" ]; then
  [ "$DRY_RUN" -eq 0 ] && chmod +x "$GUARD"
  if command -v jq >/dev/null 2>&1; then
    echo "${C_DIM}Hook write-guard: $GUARD${C_OFF}"
    echo "${C_WARN}   Cablearlo en $SETTINGS como hook PreToolUse global.${C_OFF}"
    echo "${C_WARN}   Después abre /hooks o reinicia para que cargue.${C_OFF}"
  else
    echo "${C_WARN}⚠  falta 'jq': el write-guard permitirá siempre (fail-safe). Instálalo para que actúe.${C_OFF}"
  fi
else
  echo "${C_DIM}(sin write-guard en este montaje)${C_OFF}"
fi

echo
echo "${C_OK}Enlazados: $n_linked${C_OFF} · ya estaban: $n_ok · saltados: $n_skipped"
[ "$n_linked" -gt 0 ] && [ "$DRY_RUN" -eq 0 ] && echo "${C_WARN}Recuerda recargar (/hooks o reiniciar) para que Claude los descubra.${C_OFF}"
exit 0
