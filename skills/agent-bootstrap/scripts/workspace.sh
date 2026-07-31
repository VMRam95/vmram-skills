#!/bin/bash
#
# workspace.sh — crea la carpeta paraguas de un proyecto y coloca dentro sus repos.
#
#   bash workspace.sh workspace.env
#
# El workspace es una CARPETA, no un repo git: agrupa como hermanos el repo (o repos)
# de código, el repo de agentes y el de skills del proyecto, y aloja el `.claude/`
# desde el que se abren las sesiones.
#
#   <workspace>/
#   ├── .claude/                 settings.json + agents/  (los crea install.sh)
#   ├── .gitignore               ignora los repos hijos
#   ├── CLAUDE.md                normativa a nivel workspace
#   ├── README.md                qué es esto y cómo se usa
#   ├── docs/                    documentación cross-repo (si aplica)
#   ├── <prefijo>-agents/        capa de agentes  (la crea scaffold.sh)
#   ├── <prefijo>-skills/        skills propias del proyecto
#   └── <repo de código>/        movido o clonado aquí
#
# Fichero de parámetros:
#
#   WORKSPACE=/ruta/al/pcf7-workspace
#   PROYECTO="PC Fútbol Remake"
#   PREFIJO=pcf
#   MOVER="/ruta/al/repo-existente"      # opcional, repetible con espacios
#   CON_SKILLS=1                          # crear repo de skills del proyecto
#   CON_DOCS=1                            # crear docs/ cross-repo
#
# Idempotente sobre un workspace que no exista. Si ya existe, no lo destruye:
# añade lo que falte y avisa de lo que ya estaba.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(cat "$SKILL_DIR/VERSION")"

[ $# -eq 1 ] || { echo "Uso: $0 workspace.env" >&2; exit 2; }
[ -f "$1" ] || { echo "No existe el fichero de parámetros: $1" >&2; exit 2; }

# Los parámetros se LEEN, no se ejecutan (ver la misma nota en scaffold.sh).
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

: "${WORKSPACE:?falta WORKSPACE}"; : "${PROYECTO:?falta PROYECTO}"; : "${PREFIJO:?falta PREFIJO}"
MOVER="${MOVER:-}"; CON_SKILLS="${CON_SKILLS:-1}"; CON_DOCS="${CON_DOCS:-0}"

_email="${GIT_EMAIL:-$(git config user.email 2>/dev/null || true)}"
_name="${GIT_NAME:-$(git config user.name 2>/dev/null || true)}"
if [ -z "$_email" ] || [ -z "$_name" ]; then
  echo "Falta la identidad de git. Configúrala o pasa GIT_EMAIL y GIT_NAME." >&2; exit 2
fi

FECHA="$(date +%Y-%m-%d)"
NOMBRE_WS="$(basename "$WORKSPACE")"

echo "Workspace: $WORKSPACE"
mkdir -p "$WORKSPACE"

# --- 1. Mover los repos indicados -----------------------------------------------
repos_dentro=""
for origen in $MOVER; do
  [ -n "$origen" ] || continue
  if [ ! -d "$origen" ]; then
    echo "  ⚠  no existe, me lo salto: $origen" >&2; continue
  fi
  nombre="$(basename "$origen")"
  destino="$WORKSPACE/$nombre"
  if [ -e "$destino" ]; then
    echo "  ✓ ya estaba dentro: $nombre"
  else
    # Comprobación de seguridad: no mover un repo con trabajo sin guardar.
    if [ -d "$origen/.git" ] && [ -n "$(git -C "$origen" status --porcelain 2>/dev/null)" ]; then
      echo "  ✗ $nombre tiene cambios sin commitear. No lo muevo." >&2
      echo "    Commitea o guarda el trabajo y vuelve a lanzarlo." >&2
      exit 1
    fi
    mv "$origen" "$destino"
    echo "  → movido: $nombre"
  fi
  repos_dentro="$repos_dentro $nombre"
done

# --- 2. Repo de skills del proyecto ---------------------------------------------
if [ "$CON_SKILLS" = "1" ]; then
  SK="$WORKSPACE/$PREFIJO-skills"
  if [ -e "$SK" ]; then
    echo "  ✓ ya estaba: $PREFIJO-skills"
  else
    mkdir -p "$SK/skills"
    cat > "$SK/README.md" <<MD
# Skills de $PROYECTO

Skills **propias de este proyecto**. Lo reutilizable entre proyectos vive en el repo
personal de skills, no aquí.

Cada skill es una carpeta con su \`SKILL.md\`. \`install.sh\` las enlaza en el
\`.claude/skills/\` del workspace, así que solo están disponibles cuando trabajas aquí.

\`\`\`bash
bash install.sh            # enlaza todas
bash install.sh --dry-run  # ver qué haría
\`\`\`

## Catálogo

_(vacío: todavía no hay skills propias)_

Candidatas cuando surjan: importar o validar datos maestros, recalibrar valores del
simulador, generar contenido, y cualquier procedimiento que repitas más de dos veces.
MD
    cat > "$SK/install.sh" <<'MD'
#!/bin/bash
# Enlaza las skills de este repo en el .claude/skills/ del workspace.
# Idempotente. El workspace es el directorio padre de este repo.
set -uo pipefail
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$(cd "$REPO/.." && pwd)/.claude/skills"
[ "$DRY" -eq 0 ] && mkdir -p "$DEST"
n=0
for s in "$REPO"/skills/*/; do
  [ -d "$s" ] || continue
  nombre="$(basename "$s")"
  if [ "$DRY" -eq 1 ]; then echo "→ $nombre (se enlazaría)"; else
    ln -sfn "$s" "$DEST/$nombre" && echo "→ $nombre"; fi
  n=$((n+1))
done
[ "$n" -eq 0 ] && echo "(todavía no hay skills en este repo)"
exit 0
MD
    chmod +x "$SK/install.sh"
    printf '%s\n' ".DS_Store" > "$SK/.gitignore"
    ( cd "$SK" && git init -q && git add -A \
      && git -c user.email="$_email" -c user.name="$_name" \
             commit -q -m "chore: scaffold project skills repo" )
    echo "  → creado: $PREFIJO-skills"
  fi
fi

# --- 3. docs/ cross-repo ---------------------------------------------------------
if [ "$CON_DOCS" = "1" ] && [ ! -d "$WORKSPACE/docs" ]; then
  mkdir -p "$WORKSPACE/docs"
  cat > "$WORKSPACE/docs/README.md" <<MD
# Documentación cross-repo de $PROYECTO

Lo que no pertenece a un repo concreto: visión, decisiones que cruzan repos, índices.
La documentación **de un repo** vive en ese repo. La **base de conocimiento del
arquitecto** vive en \`$PREFIJO-agents\`, no aquí.
MD
  echo "  → creado: docs/"
fi

# --- 4. Ficheros del workspace ---------------------------------------------------
if [ ! -f "$WORKSPACE/.gitignore" ]; then
  cat > "$WORKSPACE/.gitignore" <<MD
# Los repos hijos son independientes, no submódulos
$PREFIJO-*/
.DS_Store
.claude/settings.local.json
MD
  echo "  → creado: .gitignore"
fi

if [ ! -f "$WORKSPACE/CLAUDE.md" ]; then
  cat > "$WORKSPACE/CLAUDE.md" <<MD
# $PROYECTO — workspace

Esta carpeta agrupa como hermanos todos los repos del proyecto. **No es un repo git**:
cada hijo tiene su propia historia e independencia.

## Abre las sesiones DESDE AQUÍ

No desde dentro de un repo hijo. Claude Code lee \`.claude/\` del directorio donde
arranca la sesión, así que solo abriendo aquí se cargan los agentes del proyecto y el
hook que los limita.

## Qué hay

| Carpeta | Qué es | Estado |
|---|---|---|
| \`$PREFIJO-agents/\` | Los agentes y la base de conocimiento del arquitecto | ⏳ **sin montar todavía** — se crea con \`agent-bootstrap\` en modo INIT |
| \`$PREFIJO-skills/\` | Skills propias del proyecto | ✅ creado, catálogo vacío |
$(for r in $repos_dentro; do echo "| \`$r/\` | Código | ✅ |"; done)

## Los agentes

Contratos y orden de trabajo: [\`$PREFIJO-agents/orchestration.md\`]($PREFIJO-agents/orchestration.md).

Lo que decide el arquitecto se registra en su base de conocimiento; lo que se hace, en
el tablero de tareas. No se duplica entre ambos.

## Instalación

Mientras \`$PREFIJO-agents/\` no exista, aquí no hay agentes cargados: móntalo primero con
\`agent-bootstrap\` en modo INIT.

Una vez montado —o al clonar el workspace en otra máquina:

\`\`\`bash
bash $PREFIJO-agents/install.sh
bash $PREFIJO-skills/install.sh
\`\`\`

Después recarga (\`/hooks\` o reiniciar) para que Claude descubra agentes y skills.
MD
  echo "  → creado: CLAUDE.md"
fi

if [ ! -f "$WORKSPACE/README.md" ]; then
  cat > "$WORKSPACE/README.md" <<MD
# $NOMBRE_WS

Workspace de **$PROYECTO**. Carpeta paraguas con todos los repos del proyecto como
hermanos, más su capa de agentes.

Generado con \`agent-bootstrap\` v$VERSION el $FECHA.

Instrucciones para trabajar aquí: [CLAUDE.md](CLAUDE.md).
MD
  echo "  → creado: README.md"
fi

mkdir -p "$WORKSPACE/.claude"

echo
echo "✅ Workspace listo."
echo
echo "Siguiente: montar la capa de agentes dentro."
echo "  DESTINO debe ser $WORKSPACE/$PREFIJO-agents"
