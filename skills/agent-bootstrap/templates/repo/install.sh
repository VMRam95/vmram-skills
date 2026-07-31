#!/bin/bash
#
# install.sh — enlaza los agentes de este repo en el workspace y cablea el
#              write-guard como hook de usuario.
#
# Dos ámbitos distintos, y es deliberado:
#   · AGENTES  → <workspace>/.claude/agents/  (solo aparecen en este proyecto)
#   · HOOK     → ~/.claude/settings.json      (ámbito de usuario)
#
# El hook va a usuario porque Claude Code NO lee settings.json de directorios
# padre: solo de la raíz del repo de la sesión, del ámbito de usuario y de la
# política gestionada. Un hook en el workspace no se cargaría nunca.
# Que sea global es inofensivo: el guard filtra por agent_type y es fail-safe,
# así que solo actúa sobre el arquitecto de ESTE proyecto y ante cualquier duda
# permite. Es exactamente la vía que prescribe el handoff (§9).
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
# Ámbito WORKSPACE, no usuario: los agentes de este proyecto no deben aparecer en
# todas tus sesiones de Claude Code. El workspace es el directorio que contiene este
# repo de agentes y el repo de código, como hermanos.
WORKSPACE="$(cd "$REPO_DIR/.." && pwd)"
CLAUDE_DIR="${CLAUDE_HOME:-$WORKSPACE/.claude}"
AGENTS_DIR="$CLAUDE_DIR/agents"
# El hook, en ámbito de usuario: es el único que Claude Code carga siempre.
SETTINGS="${HOME}/.claude/settings.json"
MATCHER="Write|Edit|NotebookEdit"

if [ -t 1 ]; then
  C_OK=$'\033[0;32m'; C_WARN=$'\033[0;33m'; C_ERR=$'\033[0;31m'; C_DIM=$'\033[0;90m'; C_OFF=$'\033[0m'
else
  C_OK=''; C_WARN=''; C_ERR=''; C_DIM=''; C_OFF=''
fi

[ "$DRY_RUN" -eq 1 ] && echo "${C_DIM}=== DRY RUN: no se modifica nada ===${C_OFF}"
echo "Repo:      $REPO_DIR"
echo "Workspace: $WORKSPACE"
echo "Agentes:   $AGENTS_DIR"
echo "Hook:      $SETTINGS"
echo

n_linked=0; n_ok=0; n_skipped=0

# R8: si el "workspace" resulta ser una carpeta con muchos repos dentro, los agentes
# de este proyecto acabarían compartidos con todos ellos — justo lo contrario de lo
# que se busca. Avisamos: lo correcto es una carpeta paraguas por proyecto.
n_hermanos="$(find "$WORKSPACE" -maxdepth 1 -type d -not -path "$WORKSPACE" 2>/dev/null | wc -l | tr -d ' ')"
if [ "${n_hermanos:-0}" -gt 6 ]; then
  echo "${C_WARN}⚠  $WORKSPACE contiene $n_hermanos carpetas: no parece un workspace por proyecto.${C_OFF}"
  echo "${C_WARN}   Los agentes se compartirían con todo lo que cuelgue de ahí.${C_OFF}"
  echo "${C_WARN}   Recomendado: mover este repo y el de código a una carpeta paraguas propia,${C_OFF}"
  echo "${C_WARN}   o exportar CLAUDE_HOME apuntando al .claude que quieras usar.${C_OFF}"
  echo
fi

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

# --- 2. Hook write-guard: se cablea aquí, con la ruta absoluta de ESTA máquina ----
GUARD="$REPO_DIR/agents/<PREFIJO>-architect/scripts/write-guard.sh"
echo
echo "-- Hook (PreToolUse: $MATCHER) --"
if [ ! -f "$GUARD" ]; then
  echo "${C_DIM}(sin write-guard en este montaje)${C_OFF}"
elif ! command -v jq >/dev/null 2>&1; then
  echo "${C_WARN}⚠  falta 'jq': no puedo cablearlo sin riesgo de romper settings.json.${C_OFF}"
  echo "${C_WARN}   Sin cablear, el límite del arquitecto queda solo en su charter.${C_OFF}"
elif [ "$DRY_RUN" -eq 1 ]; then
  echo "   se cablearía: $GUARD"
else
  chmod +x "$GUARD"
  mkdir -p "$CLAUDE_DIR"
  [ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
  if ! jq -e . "$SETTINGS" >/dev/null 2>&1; then
    echo "${C_ERR}✗  $SETTINGS no es JSON válido. No lo toco.${C_OFF}"
  else
    # ¿Ya estaba? Entonces no tocamos nada y no dejamos copia de más.
    if jq -e --arg m "$MATCHER" --arg c "$GUARD" \
         '[.hooks.PreToolUse[]? | select(.matcher == $m) | .hooks[]? | select(.command == $c)] | length > 0' \
         "$SETTINGS" >/dev/null 2>&1; then
      echo "${C_DIM}✓  ya estaba cableado${C_OFF}"
    else
      copia="$SETTINGS.bak.$(date +%Y%m%d%H%M%S)"
      cp "$SETTINGS" "$copia"
      if jq --arg m "$MATCHER" --arg c "$GUARD" '
            .hooks //= {} | .hooks.PreToolUse //= [] |
            .hooks.PreToolUse += [{"matcher": $m, "hooks": [{"type": "command", "command": $c}]}]
          ' "$SETTINGS" > "$SETTINGS.tmp" 2>/dev/null && [ -s "$SETTINGS.tmp" ]; then
        mv "$SETTINGS.tmp" "$SETTINGS"
        echo "${C_OK}→  cableado en $SETTINGS${C_OFF} ${C_DIM}(copia en $(basename "$copia"))${C_OFF}"
      else
        rm -f "$SETTINGS.tmp"; rm -f "$copia"
        echo "${C_ERR}✗  el merge falló: settings.json intacto, hook SIN cablear.${C_OFF}"
        echo "${C_ERR}   Revisa la forma de .hooks.PreToolUse (debe ser una lista).${C_OFF}"
      fi
    fi
  fi
fi

# --- 3. Ancla de ruta: los charters aprenden dónde vive este repo, en esta máquina ---
if [ "$DRY_RUN" -eq 0 ]; then
  for charter in "$REPO_DIR"/agents/*/*.md; do
    [ -f "$charter" ] || continue
    grep -q '<!--RUTA-AGENTES-->' "$charter" || continue
    python3 - "$charter" "$REPO_DIR" <<'PYEOF'
import re, sys, pathlib
p, ruta = pathlib.Path(sys.argv[1]), sys.argv[2]
t = p.read_text(encoding="utf-8")
t = re.sub(r'<!--RUTA-AGENTES-->.*?<!--/RUTA-AGENTES-->',
           f'<!--RUTA-AGENTES-->`{ruta}`<!--/RUTA-AGENTES-->', t, flags=re.S)
p.write_text(t, encoding="utf-8")
PYEOF
  done
  echo
  echo "${C_DIM}Rutas de esta máquina escritas en los charters.${C_OFF}"
fi

echo
echo "${C_OK}Enlazados: $n_linked${C_OFF} · ya estaban: $n_ok · saltados: $n_skipped"
[ "$n_linked" -gt 0 ] && [ "$DRY_RUN" -eq 0 ] && echo "${C_WARN}Recuerda recargar (/hooks o reiniciar) para que Claude los descubra.${C_OFF}"
exit 0
