#!/bin/bash
#
# scaffold.sh — genera el repo <proyecto>-agents a partir de los templates de la skill.
#
#   bash scaffold.sh params.env
#
# El fichero de parámetros lo escribe la skill tras la entrevista. Ejemplo:
#
#   DESTINO=/ruta/al/pcfutbol-agents
#   PROYECTO="PC Fútbol Remake"
#   PREFIJO=pcf
#   STACK="TypeScript, monorepo npm workspaces"
#   REPO_CODIGO=/ruta/al/repo-de-codigo
#   # SOLO las áreas que YA tienen código. Un especialista sin territorio inventa
#   # trabajo hacia su especialidad. Las demás van a AREAS_LATENTES.
#   AREAS="core-domain:packages/core"
#   AREAS_LATENTES="frontend-ui data-pipeline backend-api devops-infra"
#   REGLA_DE_ORO="El núcleo no tiene dependencias y es determinista"
#   FF_TOOL="dependency-cruiser + tests de arquitectura"
#   COMANDO_FITNESS="npm test -- arquitectura"
#   COMANDO_VERIFICACION="npm run typecheck && npm test"
#   FUENTES_NORMATIVAS="docs/decision-stack.md"
#   FUENTES_CONSTRUCCION="docs/spec-implementacion.md, docs/formatos-datos.md"
#   TABLERO_DESC="CodeAgentSwarm, proyecto <nombre>"
#   CON_REVIEWER=0
#   MODELO_ESPECIALISTA=sonnet
#   MODELO_REVIEWER=sonnet
#
# Es idempotente sobre un destino que no exista. Si el destino ya existe, aborta:
# para actualizar un montaje existente se usa upgrade.sh, no esto.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TPL="$SKILL_DIR/templates"
VERSION="$(cat "$SKILL_DIR/VERSION")"

[ $# -eq 1 ] || { echo "Uso: $0 params.env" >&2; exit 2; }
[ -f "$1" ] || { echo "No existe el fichero de parámetros: $1" >&2; exit 2; }

# Los parámetros se LEEN, no se ejecutan. Hacer `source` de este fichero convertiría
# un nombre de proyecto con una comilla, o una ruta con espacios, en un fallo del
# script — o algo peor. Aquí se parte por el primer `=` y se quitan las comillas
# envolventes, sin evaluar nada.
while IFS= read -r _linea || [ -n "$_linea" ]; do
  case "$_linea" in ''|'#'*) continue ;; esac
  case "$_linea" in *=*) ;; *) continue ;; esac
  _clave="${_linea%%=*}"; _valor="${_linea#*=}"
  _clave="$(printf '%s' "$_clave" | tr -d '[:space:]')"
  case "$_clave" in [A-Za-z_]*) ;; *) continue ;; esac
  case "$_valor" in
    \"*\") _valor="${_valor#\"}"; _valor="${_valor%\"}" ;;
    \'*\') _valor="${_valor#\'}"; _valor="${_valor%\'}" ;;
  esac
  printf -v "$_clave" '%s' "$_valor"
done < "$1"
unset _linea _clave _valor

: "${DESTINO:?falta DESTINO}"; : "${PROYECTO:?falta PROYECTO}"; : "${PREFIJO:?falta PREFIJO}"
: "${AREAS:?falta AREAS}"
# Obligatorios: sin ellos el charter queda con huecos y el agente no puede operar.
: "${REPO_CODIGO:?falta REPO_CODIGO — el agente necesita saber dónde está el código}"
: "${REGLA_DE_ORO:?falta REGLA_DE_ORO — es el principio nº1 del arquitecto}"
: "${COMANDO_VERIFICACION:?falta COMANDO_VERIFICACION — el especialista no sabría verificar}"
: "${FUENTES_NORMATIVAS:?falta FUENTES_NORMATIVAS}"

STACK="${STACK:-}"; AREAS_LATENTES="${AREAS_LATENTES:-}"
FF_TOOL="${FF_TOOL:-pendiente de decidir}"
COMANDO_FITNESS="${COMANDO_FITNESS:-$COMANDO_VERIFICACION}"
FUENTES_CONSTRUCCION="${FUENTES_CONSTRUCCION:-$FUENTES_NORMATIVAS}"
TABLERO_DESC="${TABLERO_DESC:-sin tablero configurado}"; CON_REVIEWER="${CON_REVIEWER:-0}"
MODELO_ARQUITECTO="${MODELO_ARQUITECTO:-opus}"
MODELO_ESPECIALISTA="${MODELO_ESPECIALISTA:-sonnet}"; MODELO_REVIEWER="${MODELO_REVIEWER:-sonnet}"

[ -e "$DESTINO" ] && { echo "El destino ya existe: $DESTINO" >&2
                       echo "Para actualizar un montaje existente usa upgrade.sh" >&2; exit 1; }

# Sin identidad de git el commit final revienta y deja el montaje a medias, generado
# pero sin commitear, y sin poder re-ejecutar (el destino ya existiría). Se comprueba
# ahora, antes de crear un solo fichero.
_email="${GIT_EMAIL:-$(git config user.email 2>/dev/null || true)}"
_name="${GIT_NAME:-$(git config user.name 2>/dev/null || true)}"
if [ -z "$_email" ] || [ -z "$_name" ]; then
  echo "Falta la identidad de git." >&2
  echo "Configura user.email y user.name, o pásalos como GIT_EMAIL y GIT_NAME." >&2
  exit 2
fi

# ---- validación de AREAS: un especialista sin territorio no sirve para nada ----
for _spec in $AREAS; do
  case "$_spec" in
    *:*) ;;
    *) echo "AREAS mal formado: '$_spec' no tiene ':'. Formato: area:ruta[,ruta]" >&2; exit 2 ;;
  esac
  [ -n "${_spec#*:}" ] || { echo "AREAS: el área '${_spec%%:*}' no tiene rutas." >&2; exit 2; }
  [ -n "${_spec%%:*}" ] || { echo "AREAS: hay una ruta sin nombre de área." >&2; exit 2; }
done
unset _spec

FECHA="$(date +%Y-%m-%d)"
ARCH="$PREFIJO-architect"
KB_PATH="$DESTINO/agents/$ARCH/knowledge-base"
# Ruta RELATIVA al repo de agentes: es la que va en charters y guard, para que el
# montaje sobreviva a mover, renombrar o clonar el repo en otra máquina.
KB_REL="agents/$ARCH/knowledge-base/"

# Sustituye los tokens <TOKEN> de un fichero, in-place.
#
# Los valores viajan por el ENTORNO y el heredoc va entrecomillado (<<'PY'), así que
# ni bash ni Python los interpretan: un backslash en una ruta se queda como backslash,
# y un valor hostil no puede alterar la sintaxis del script. Interpolarlos dentro del
# source de Python corrompía charters en silencio y era un vector de ejecución.
sustituir() {
  local f="$1"
  AB_AREA="${2:-}" AB_AREA_DESC="${3:-}" AB_RUTAS_AREA="${4:-}" \
  AB_PROYECTO="$PROYECTO" AB_PREFIJO="$PREFIJO" AB_STACK="$STACK" \
  AB_KB_PATH="$KB_PATH" AB_KB_REL="$KB_REL" AB_REPO_CODIGO="$REPO_CODIGO" \
  AB_REGLA_DE_ORO="$REGLA_DE_ORO" AB_FF_TOOL="$FF_TOOL" \
  AB_COMANDO_FITNESS="$COMANDO_FITNESS" AB_COMANDO_VERIFICACION="$COMANDO_VERIFICACION" \
  AB_FUENTES_NORMATIVAS="$FUENTES_NORMATIVAS" AB_FUENTES_CONSTRUCCION="$FUENTES_CONSTRUCCION" \
  AB_TABLERO_DESC="$TABLERO_DESC" AB_AREAS_LATENTES="${AREAS_LATENTES:-ninguna}" \
  AB_MODELO_ARQUITECTO="$MODELO_ARQUITECTO" AB_MODELO_ESPECIALISTA="$MODELO_ESPECIALISTA" \
  AB_MODELO_REVIEWER="$MODELO_REVIEWER" AB_VERSION="$VERSION" AB_FECHA="$FECHA" \
  python3 - "$f" <<'PY'
import os, sys, pathlib
TOKENS = ("PROYECTO", "PREFIJO", "STACK", "KB_PATH", "KB_REL", "REPO_CODIGO",
          "REGLA_DE_ORO", "FF_TOOL", "COMANDO_FITNESS", "COMANDO_VERIFICACION",
          "FUENTES_NORMATIVAS", "FUENTES_CONSTRUCCION", "TABLERO_DESC",
          "AREAS_LATENTES", "MODELO_ARQUITECTO", "MODELO_ESPECIALISTA",
          "MODELO_REVIEWER", "VERSION", "FECHA", "AREA_DESC", "RUTAS_AREA", "AREA")
p = pathlib.Path(sys.argv[1])
t = p.read_text(encoding="utf-8")
for k in TOKENS:
    t = t.replace("<" + k + ">", os.environ.get("AB_" + k, ""))
p.write_text(t, encoding="utf-8")
PY
}

echo "Generando $DESTINO"
mkdir -p "$KB_PATH"/{contexts,adr} "$DESTINO/agents/$ARCH/scripts"

# --- charter y KB del arquitecto ---
cp "$TPL/charters/architect.md.tpl" "$DESTINO/agents/$ARCH/$ARCH.md"
for f in README system-map fitness-functions tech-debt scorecard BOOTSTRAP; do
  cp "$TPL/kb/$f.md.tpl" "$KB_PATH/$f.md"
done
cp "$TPL/kb/contexts/_TEMPLATE.md" "$KB_PATH/contexts/_TEMPLATE.md"
cp "$TPL/kb/adr/_TEMPLATE.md" "$KB_PATH/adr/_TEMPLATE.md"
cp "$TPL/scripts/write-guard.sh.tpl" "$DESTINO/agents/$ARCH/scripts/write-guard.sh"
chmod +x "$DESTINO/agents/$ARCH/scripts/write-guard.sh"

sustituir "$DESTINO/agents/$ARCH/$ARCH.md"
for f in "$KB_PATH"/*.md "$DESTINO/agents/$ARCH/scripts/write-guard.sh"; do sustituir "$f"; done

# --- especialistas, uno por área ---
declare -a AREAS_JSON=()
for spec in $AREAS; do
  area="${spec%%:*}"; rutas="${spec#*:}"
  dir="$DESTINO/agents/$PREFIJO-$area-dev"
  mkdir -p "$dir/notes"
  cp "$TPL/charters/specialist.md.tpl" "$dir/$PREFIJO-$area-dev.md"
  rutas_fmt=""
  for r in ${rutas//,/ }; do rutas_fmt="$rutas_fmt- \`$r\`"$'\n'; done
  sustituir "$dir/$PREFIJO-$area-dev.md" "$area" "$area" "$rutas_fmt"
  echo "  agents/$PREFIJO-$area-dev"
  AREAS_JSON+=("{\"area\":\"$area\",\"rutas\":\"$rutas\",\"agente\":\"$PREFIJO-$area-dev\"}")
done

# --- reviewer opcional ---
if [ "$CON_REVIEWER" = "1" ]; then
  mkdir -p "$DESTINO/agents/$PREFIJO-reviewer"
  cp "$TPL/charters/reviewer.md.tpl" "$DESTINO/agents/$PREFIJO-reviewer/$PREFIJO-reviewer.md"
  sustituir "$DESTINO/agents/$PREFIJO-reviewer/$PREFIJO-reviewer.md"
  echo "  agents/$PREFIJO-reviewer"
fi

# --- raíz del repo ---
cp "$TPL/repo/install.sh" "$DESTINO/install.sh"; chmod +x "$DESTINO/install.sh"
cp "$TPL/repo/orchestration.md.tpl" "$DESTINO/orchestration.md"
sustituir "$DESTINO/install.sh"; sustituir "$DESTINO/orchestration.md"

printf '%s\n' "node_modules/" ".DS_Store" "*.bak.*" > "$DESTINO/.gitignore"

latentes_json=""
for a in $AREAS_LATENTES; do latentes_json="$latentes_json\"$a\","; done
cat > "$DESTINO/.bootstrap-manifest.json" <<JSON
{
  "herramienta": "agent-bootstrap",
  "version": "$VERSION",
  "generado": "$FECHA",
  "proyecto": "$PROYECTO",
  "prefijo": "$PREFIJO",
  "repo_codigo": "$REPO_CODIGO",
  "areas_instanciadas": [$(IFS=,; echo "${AREAS_JSON[*]:-}")],
  "areas_latentes": [${latentes_json%,}],
  "reviewer": $([ "$CON_REVIEWER" = "1" ] && echo true || echo false),
  "tool_owned": [
    "install.sh",
    "agents/*/scripts/write-guard.sh",
    ".bootstrap-manifest.json"
  ],
  "_nota_propiedad": "check-arch y refresh son PROJECT-OWNED: codifican reglas de este proyecto. upgrade no los toca."
}
JSON

cat > "$DESTINO/README.md" <<MD
# Agentes de $PROYECTO

Capa de agentes persistentes. **Vive fuera del repo de código** para no contaminar el entregable
y sobrevivir a que el repo se mueva o se renombre.

Generado con \`agent-bootstrap\` v$VERSION el $FECHA.

## Instalación

\`\`\`bash
bash install.sh            # enlaza los agentes y cablea el hook
bash install.sh --dry-run  # ver qué haría, sin tocar nada
\`\`\`

Después, **recarga** (abre \`/hooks\` o reinicia) para que Claude los descubra.

Los agentes se instalan en el **workspace** (\`../.claude/agents/\`), no globalmente: solo aparecen
cuando trabajas en este proyecto.

Requisitos: este repo clonado **hermano** del repo de código · \`jq\` para que el hook se cablee
(sin él, \`install.sh\` avisa y no lo cablea; el guard, por diseño fail-safe, permitiría siempre).

## Los agentes

Ver [orchestration.md](orchestration.md) para los contratos y el orden canónico de una feature.

## La base de conocimiento

\`agents/$ARCH/knowledge-base/\` — la mantiene el arquitecto. **Es estado compartido**: \`git pull\`
antes de trabajar, \`git push\` después. Si no, diverge entre máquinas.

## Cómo invocar al arquitecto

\`\`\`
@$ARCH INIT
@$ARCH GATE: <el cambio o el plan>
@$ARCH CONSULT: <la duda>
@$ARCH RE-AUDIT
@$ARCH REFRESH
@$ARCH REDESIGN-CHECK
\`\`\`
MD

# --- verificación: cero placeholders residuales ---
echo
# Cero placeholders. Incluye <PENDIENTE...>, que la regex de tokens no capturaba.
resid="$(grep -rlE '<[A-Z_]+>|<PENDIENTE' "$DESTINO" 2>/dev/null | grep -v '_TEMPLATE' || true)"
if [ -n "$resid" ]; then
  echo "❌ Quedan placeholders sin sustituir:"; echo "$resid" | sed 's/^/   /'
  grep -rhoE '<[A-Z_]+>|<PENDIENTE[^>]*>' $resid 2>/dev/null | sort -u | sed 's/^/     /'
  exit 1
fi

# Un parámetro que llegó vacío deja un backtick vacío (``) donde debía ir un comando
# o una ruta. El agente no sabría qué ejecutar y el fallo pasaría inadvertido.
# Dos backticks seguidos que NO formen parte de una valla ``` de bloque de código.
vacios="$(grep -rlnE '(^|[^`])``([^`]|$)' "$DESTINO"/agents/*/*.md 2>/dev/null || true)"
if [ -n "$vacios" ]; then
  echo "❌ Hay parámetros vacíos (backtick sin contenido) en:"; echo "$vacios" | sed 's/^/   /'
  exit 1
fi

# Se usa la identidad YA validada al arrancar: volver a preguntarle a git aquí dentro
# devolvería vacío (repo nuevo, sin config local) y el commit reventaría dejando el
# montaje generado pero sin commitear, y sin poder re-ejecutar.
( cd "$DESTINO" && git init -q && git add -A \
  && git -c user.email="$_email" -c user.name="$_name" \
         commit -q -m "chore: bootstrap agent layer with agent-bootstrap v$VERSION" )

echo "✅ Generado sin placeholders residuales, con commit inicial."
echo
echo "Siguiente: sembrar la KB con el recon real y correr el BOOTSTRAP del arquitecto."
