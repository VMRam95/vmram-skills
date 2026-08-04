#!/bin/bash
#
# status.sh — audita si la capa de agentes de un proyecto sigue en pie.
#
#   bash status.sh <ruta-al-repo-de-agentes> [--claude-home <ruta>]
#
# Responde a "¿esto sigue montado y coherente?" con hechos, no con impresiones.
# Comprueba el entorno (que la skill instalada no esté desincronizada), los charters,
# los enlaces, el hook y la base de conocimiento.
#
# Salida: una línea por comprobación.
#   ✅ correcto   ⚠️ atención, no bloquea   ❌ roto, hay que arreglarlo
#
# exit 0 si no hay ningún ❌; exit 1 si lo hay. Así se puede meter en CI.
#
# [tool-owned]

set -uo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_SKILL="$(cat "$SKILL_DIR/VERSION" 2>/dev/null || echo "?")"

AGENTS_REPO=""; CLAUDE_HOME_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --claude-home) CLAUDE_HOME_ARG="$2"; shift 2 ;;
    -h|--help) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "Opción desconocida: $1" >&2; exit 2 ;;
    *) AGENTS_REPO="$1"; shift ;;
  esac
done

[ -n "$AGENTS_REPO" ] || { echo "Uso: $0 <ruta-al-repo-de-agentes> [--claude-home <ruta>]" >&2; exit 2; }
[ -d "$AGENTS_REPO" ] || { echo "No existe: $AGENTS_REPO" >&2; exit 2; }
AGENTS_REPO="$(cd "$AGENTS_REPO" && pwd)"

if [ -t 1 ]; then C_OK=$'\033[0;32m'; C_WARN=$'\033[0;33m'; C_ERR=$'\033[0;31m'; C_DIM=$'\033[0;90m'; C_OFF=$'\033[0m'
else C_OK=''; C_WARN=''; C_ERR=''; C_DIM=''; C_OFF=''; fi

n_err=0; n_warn=0
ok()   { echo "${C_OK}✅${C_OFF} $1"; }
warn() { echo "${C_WARN}⚠️${C_OFF}  $1"; n_warn=$((n_warn+1)); }
err()  { echo "${C_ERR}❌${C_OFF} $1"; n_err=$((n_err+1)); }
seccion() { echo; echo "${C_DIM}── $1 ──${C_OFF}"; }

# ---------------------------------------------------------------- manifest ---
MANIFEST="$AGENTS_REPO/.bootstrap-manifest.json"
seccion "Manifiesto"
if [ ! -f "$MANIFEST" ]; then
  err "no hay .bootstrap-manifest.json: esto no parece un montaje de agent-bootstrap"
  echo; echo "Nada más que comprobar sin manifiesto."; exit 1
fi

leer_manifest() { python3 -c "
import json,sys
d=json.load(open('$MANIFEST'))
print(d.get('$1',''))" 2>/dev/null; }

VERSION_PROYECTO="$(leer_manifest version)"
PREFIJO="$(leer_manifest prefijo)"
REPO_CODIGO="$(leer_manifest repo_codigo)"
ok "proyecto '$(leer_manifest proyecto)' · prefijo '$PREFIJO' · generado con v$VERSION_PROYECTO"

# ------------------------------------------------------------------ entorno ---
# El fallo más caro que ha tenido esta herramienta no fue un bug: fue una copia
# instalada que se quedó vieja sin que nada lo dijera. Se comprueba primero.
seccion "Entorno"
if [ "$VERSION_PROYECTO" != "$VERSION_SKILL" ]; then
  warn "el proyecto se generó con v$VERSION_PROYECTO y esta skill es v$VERSION_SKILL → considera UPGRADE"
else
  ok "el proyecto está a la versión de la metodología (v$VERSION_SKILL)"
fi

SKILL_INSTALADA="$HOME/.claude/skills/agent-bootstrap"
if [ -L "$SKILL_INSTALADA" ]; then
  ok "la skill instalada es un enlace ($(readlink "$SKILL_INSTALADA")): no puede desincronizarse"
elif [ -d "$SKILL_INSTALADA" ]; then
  if [ "$(cat "$SKILL_INSTALADA/VERSION" 2>/dev/null)" != "$VERSION_SKILL" ]; then
    err "la skill instalada es una COPIA y su versión difiere de esta ($(cat "$SKILL_INSTALADA/VERSION" 2>/dev/null || echo '?') vs $VERSION_SKILL)"
  elif ! diff -rq "$SKILL_DIR" "$SKILL_INSTALADA" >/dev/null 2>&1; then
    err "la skill instalada es una COPIA con el MISMO número de versión pero contenido distinto — reinstálala con: install.sh --link agent-bootstrap"
  else
    warn "la skill instalada es una copia, hoy idéntica. Con --link no podría quedarse atrás"
  fi
fi

# ----------------------------------------------------------------- charters ---
seccion "Charters"
n_agentes=0
for dir in "$AGENTS_REPO"/agents/*/; do
  [ -d "$dir" ] || continue
  nombre="$(basename "$dir")"; charter="$dir$nombre.md"; n_agentes=$((n_agentes+1))
  if [ ! -f "$charter" ]; then err "$nombre: falta $nombre.md"; continue; fi
  # El frontmatter YAML tiene que abrir en la LÍNEA 1 o Claude Code no reconoce el
  # fichero como agente: no aparece en la lista y falla con "Agent type not found".
  if [ "$(head -1 "$charter")" != "---" ]; then
    err "$nombre: el frontmatter no abre en la línea 1 → este agente NO es descubrible"
  else
    declarado="$(grep -m1 '^name:' "$charter" | sed 's/^name:[[:space:]]*//')"
    if [ "$declarado" != "$nombre" ]; then
      err "$nombre: el charter declara name '$declarado', que no coincide con el directorio"
    else
      ok "$nombre"
    fi
  fi
done
[ "$n_agentes" -eq 0 ] && err "no hay ningún agente en $AGENTS_REPO/agents/"

# ------------------------------------------------------------------ enlaces ---
seccion "Instalación"
if [ -n "$CLAUDE_HOME_ARG" ]; then CLAUDE_DIR="$CLAUDE_HOME_ARG"
elif [ -d "$(dirname "$AGENTS_REPO")/.claude" ]; then CLAUDE_DIR="$(dirname "$AGENTS_REPO")/.claude"
else CLAUDE_DIR="$HOME/.claude"; fi
echo "${C_DIM}   (mirando en $CLAUDE_DIR)${C_OFF}"

for dir in "$AGENTS_REPO"/agents/*/; do
  [ -d "$dir" ] || continue
  nombre="$(basename "$dir")"; enlace="$CLAUDE_DIR/agents/$nombre.md"
  if [ ! -e "$enlace" ] && [ ! -L "$enlace" ]; then
    err "$nombre: sin enlazar → corre install.sh (y recarga la sesión después)"
  elif [ -L "$enlace" ] && [ ! -e "$enlace" ]; then
    err "$nombre: el enlace está roto (apunta a $(readlink "$enlace"))"
  elif [ -L "$enlace" ]; then
    ok "$nombre enlazado"
  else
    warn "$nombre: en el destino hay un fichero real, no un enlace: no seguirá los cambios del repo"
  fi
done

# --------------------------------------------------------------------- hook ---
seccion "Write-guard"
GUARD="$AGENTS_REPO/agents/$PREFIJO-architect/scripts/write-guard.sh"
if [ ! -f "$GUARD" ]; then
  warn "sin write-guard en este montaje"
else
  [ -x "$GUARD" ] && ok "el guard existe y es ejecutable" || err "el guard existe pero NO es ejecutable: chmod +x"
  SETTINGS="$CLAUDE_DIR/settings.json"
  if [ -f "$SETTINGS" ] && grep -q "write-guard.sh" "$SETTINGS" 2>/dev/null; then
    ok "cableado como hook en $SETTINGS"
  else
    err "NO está cableado en $SETTINGS: el arquitecto puede escribir fuera de su KB"
  fi
  command -v jq >/dev/null 2>&1 || warn "falta 'jq': el guard permite siempre (fail-safe por diseño)"
fi

# ----------------------------------------------------------------------- KB ---
seccion "Base de conocimiento"
KB="$AGENTS_REPO/agents/$PREFIJO-architect/knowledge-base"
if [ ! -d "$KB" ]; then
  err "no hay knowledge-base en $KB"
else
  # Solo los tokens que esta herramienta sustituye. Buscar cualquier <MAYÚSCULAS> daría
  # falsos positivos con texto legítimo: una KB puede mencionar <CLAUDE_HOME> a propósito.
  TOKENS_RE='<(PROYECTO|PREFIJO|STACK|KB_PATH|KB_REL|REPO_CODIGO|REGLA_DE_ORO|FF_TOOL|COMANDO_FITNESS|COMANDO_VERIFICACION|FUENTES_NORMATIVAS|FUENTES_CONSTRUCCION|TABLERO_DESC|AREAS_LATENTES|MODELO_ARQUITECTO|MODELO_ESPECIALISTA|MODELO_REVIEWER|AREA_DESC|RUTAS_AREA|AREA)>'
  residual="$(grep -rlE "$TOKENS_RE" "$KB" 2>/dev/null | grep -v '_TEMPLATE' | head -3)"
  [ -n "$residual" ] && err "quedan placeholders sin sustituir: $(echo "$residual" | tr '\n' ' ')" \
                      || ok "sin placeholders residuales"

  fichas=$(find "$KB/contexts" -name '*.md' ! -name '_TEMPLATE.md' 2>/dev/null | wc -l | tr -d ' ')
  modulos=$(grep -cE '^\| .+ \| `[^`]+` \|' "$KB/system-map.md" 2>/dev/null || echo 0)
  if [ "$fichas" -eq 0 ]; then err "la KB no tiene ninguna ficha de contexto: sin sembrar"
  elif [ "$modulos" -gt "$fichas" ]; then warn "$modulos módulos en el system-map y solo $fichas fichas: hay módulos sin onboardar"
  else ok "$fichas fichas de contexto para $modulos módulos mapeados"; fi

  adrs=$(find "$KB/adr" -name 'ADR-*.md' 2>/dev/null | wc -l | tr -d ' ')
  props=$(grep -l '^\*\*Estado\*\*: Proposed' "$KB"/adr/ADR-*.md 2>/dev/null | wc -l | tr -d ' ')
  [ "$adrs" -eq 0 ] && warn "no hay ningún ADR: ninguna decisión registrada" \
                    || ok "$adrs ADRs ($props en Proposed, esperando al humano)"

  if [ -f "$KB/BOOTSTRAP.md" ] && grep -q '✅ OPERATIVO' "$KB/BOOTSTRAP.md" 2>/dev/null; then
    ok "bootstrap superado: el arquitecto validó su KB"
  else
    err "el BOOTSTRAP no está superado: el arquitecto no debería operar todavía"
  fi
fi

# ------------------------------------------------------------------- áreas ---
seccion "Áreas"
while IFS='|' read -r estado texto; do
  case "$estado" in
    ok)   ok "$texto" ;;
    err)  err "$texto" ;;
    dim)  echo "${C_DIM}   $texto${C_OFF}" ;;
  esac
done < <(python3 - "$MANIFEST" "$REPO_CODIGO" <<'PY'
import json, sys, os
d = json.load(open(sys.argv[1])); repo = sys.argv[2]
inst = d.get('areas_instanciadas', []); lat = d.get('areas_latentes', [])
for a in inst:
    primera = a.get('rutas', '').split(',')[0].strip()
    existe = os.path.isdir(os.path.join(repo, primera))
    estado = 'ok' if existe else 'err'
    sufijo = '' if existe else '  ← su territorio NO existe en el código'
    print(f"{estado}|{a['area']} → {a.get('rutas')}{sufijo}")
print("dim|latentes: " + (", ".join(lat) if lat else "ninguna"))
if lat:
    print("dim|se activan con ADD-AREA cuando nazca su código, no antes")
PY
)

# ------------------------------------------------------------------ resumen ---
echo
if [ "$n_err" -gt 0 ]; then
  echo "${C_ERR}$n_err problema(s)${C_OFF} · $n_warn aviso(s)"
  exit 1
fi
[ "$n_warn" -gt 0 ] && echo "${C_OK}Sin problemas${C_OFF} · $n_warn aviso(s)" || echo "${C_OK}Todo en orden.${C_OFF}"
exit 0
