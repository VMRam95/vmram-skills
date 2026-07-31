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
#   AREAS="core-domain:packages/core frontend-ui:packages/ui data-pipeline:packages/data"
#   AREAS_LATENTES="backend-api devops-infra"
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
# shellcheck disable=SC1090
source "$1"

: "${DESTINO:?falta DESTINO}"; : "${PROYECTO:?falta PROYECTO}"; : "${PREFIJO:?falta PREFIJO}"
: "${AREAS:?falta AREAS}"
STACK="${STACK:-}"; REPO_CODIGO="${REPO_CODIGO:-}"; AREAS_LATENTES="${AREAS_LATENTES:-}"
REGLA_DE_ORO="${REGLA_DE_ORO:-<PENDIENTE: definir la regla de oro>}"
FF_TOOL="${FF_TOOL:-}"; COMANDO_FITNESS="${COMANDO_FITNESS:-}"
COMANDO_VERIFICACION="${COMANDO_VERIFICACION:-}"
FUENTES_NORMATIVAS="${FUENTES_NORMATIVAS:-}"; FUENTES_CONSTRUCCION="${FUENTES_CONSTRUCCION:-}"
TABLERO_DESC="${TABLERO_DESC:-}"; CON_REVIEWER="${CON_REVIEWER:-0}"
MODELO_ESPECIALISTA="${MODELO_ESPECIALISTA:-sonnet}"; MODELO_REVIEWER="${MODELO_REVIEWER:-sonnet}"

[ -e "$DESTINO" ] && { echo "El destino ya existe: $DESTINO" >&2
                       echo "Para actualizar un montaje existente usa upgrade.sh" >&2; exit 1; }

FECHA="$(date +%Y-%m-%d)"
ARCH="$PREFIJO-architect"
KB_PATH="$DESTINO/agents/$ARCH/knowledge-base"

# Sustituye los tokens <TOKEN> de un fichero, in-place.
sustituir() {
  local f="$1" area="${2:-}" area_desc="${3:-}" rutas="${4:-}"
  python3 - "$f" <<PY
import sys, pathlib
p = pathlib.Path(sys.argv[1]); t = p.read_text(encoding="utf-8")
for k, v in {
    "<PROYECTO>": """$PROYECTO""", "<PREFIJO>": """$PREFIJO""", "<STACK>": """$STACK""",
    "<KB_PATH>": """$KB_PATH""", "<REGLA_DE_ORO>": """$REGLA_DE_ORO""",
    "<FF_TOOL>": """$FF_TOOL""", "<COMANDO_FITNESS>": """$COMANDO_FITNESS""",
    "<COMANDO_VERIFICACION>": """$COMANDO_VERIFICACION""",
    "<FUENTES_NORMATIVAS>": """$FUENTES_NORMATIVAS""",
    "<FUENTES_CONSTRUCCION>": """$FUENTES_CONSTRUCCION""",
    "<TABLERO_DESC>": """$TABLERO_DESC""", "<AREAS_LATENTES>": """${AREAS_LATENTES:-ninguna}""",
    "<MODELO_ESPECIALISTA>": """$MODELO_ESPECIALISTA""",
    "<MODELO_REVIEWER>": """$MODELO_REVIEWER""",
    "<VERSION>": """$VERSION""", "<FECHA>": """$FECHA""",
    "<AREA_DESC>": """$area_desc""", "<RUTAS_AREA>": """$rutas""", "<AREA>": """$area""",
}.items():
    t = t.replace(k, v)
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
  "areas_instanciadas": [$(IFS=,; echo "${AREAS_JSON[*]}")],
  "areas_latentes": [${latentes_json%,}],
  "reviewer": $([ "$CON_REVIEWER" = "1" ] && echo true || echo false),
  "tool_owned": [
    "install.sh",
    "agents/*/scripts/*",
    ".bootstrap-manifest.json"
  ]
}
JSON

cat > "$DESTINO/README.md" <<MD
# Agentes de $PROYECTO

Capa de agentes persistentes. **Vive fuera del repo de código** para no contaminar el entregable
y sobrevivir a que el repo se mueva o se renombre.

Generado con \`agent-bootstrap\` v$VERSION el $FECHA.

## Instalación

\`\`\`bash
bash install.sh            # enlaza los agentes en ~/.claude/agents/
bash install.sh --dry-run  # ver qué haría, sin tocar nada
\`\`\`

Después, **recarga** (abre \`/hooks\` o reinicia) para que Claude los descubra.

Requisitos: este repo clonado hermano del repo de código · \`jq\` si quieres que el write-guard
actúe (sin él permite siempre, por diseño fail-safe).

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
resid="$(grep -rlE '<[A-Z_]+>' "$DESTINO" 2>/dev/null | grep -v '_TEMPLATE' || true)"
if [ -n "$resid" ]; then
  echo "❌ Quedan placeholders sin sustituir:"; echo "$resid" | sed 's/^/   /'
  grep -rhoE '<[A-Z_]+>' $resid 2>/dev/null | sort -u | sed 's/^/     /'
  exit 1
fi

( cd "$DESTINO" && git init -q && git add -A \
  && git -c user.email="${GIT_EMAIL:-$(git config user.email)}" \
         -c user.name="${GIT_NAME:-$(git config user.name)}" \
         commit -q -m "chore: bootstrap agent layer with agent-bootstrap v$VERSION" )

echo "✅ Generado sin placeholders residuales, con commit inicial."
echo
echo "Siguiente: sembrar la KB con el recon real y correr el BOOTSTRAP del arquitecto."
