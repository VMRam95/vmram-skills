#!/bin/bash
#
# add-area.sh — instancia un especialista de un área que estaba latente.
#
#   bash add-area.sh <repo-de-agentes> <area> <rutas> [--modelo sonnet] [--dry-run]
#
#   bash add-area.sh ~/proy/pcf-agents frontend-ui packages/ui
#
# `rutas` es el territorio del especialista, relativo al repo de código. Varias, con comas.
#
# LA COMPROBACIÓN QUE IMPORTA: se niega a instanciar un área cuyo territorio no existe
# todavía. Un especialista sin territorio no se queda quieto: empuja trabajo hacia su
# especialidad —un agente de UI sin UI inventará pantallas antes de que el manager
# funcione— y eso es exactamente lo que el catálogo de áreas latentes existe para evitar.
#
# Hereda del manifiesto los parámetros del montaje (regla de oro, comandos, fuentes), así
# que el charter nuevo sale idéntico en forma al de sus hermanos. En montajes generados con
# v1.0.0, que no los guardaba, los deduce del charter de otro especialista.
#
# [tool-owned]

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TPL="$SKILL_DIR/templates"
VERSION="$(cat "$SKILL_DIR/VERSION")"

DRY_RUN=0; MODELO=""
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --modelo) MODELO="$2"; shift 2 ;;
    --dry-run|-n) DRY_RUN=1; shift ;;
    -h|--help) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "Opción desconocida: $1" >&2; exit 2 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done

[ "${#ARGS[@]}" -eq 3 ] || { echo "Uso: $0 <repo-de-agentes> <area> <rutas> [--modelo m] [--dry-run]" >&2; exit 2; }
AGENTS_REPO="$(cd "${ARGS[0]}" && pwd)"; AREA="${ARGS[1]}"; RUTAS="${ARGS[2]}"

MANIFEST="$AGENTS_REPO/.bootstrap-manifest.json"
[ -f "$MANIFEST" ] || { echo "No hay .bootstrap-manifest.json en $AGENTS_REPO" >&2; exit 1; }

campo() { python3 -c "
import json
d=json.load(open('$MANIFEST'))
v=d
for k in '$1'.split('.'):
    v = v.get(k, '') if isinstance(v, dict) else ''
print(v if isinstance(v,str) else '')" 2>/dev/null; }

PROYECTO="$(campo proyecto)"; PREFIJO="$(campo prefijo)"; REPO_CODIGO="$(campo repo_codigo)"
AGENTE="$PREFIJO-$AREA-dev"
KB_PATH="$AGENTS_REPO/agents/$PREFIJO-architect/knowledge-base"

# --- el área tiene que estar latente, y no instanciada ya ---
python3 - "$MANIFEST" "$AREA" <<'PY' || exit 1
import json, sys
d = json.load(open(sys.argv[1])); area = sys.argv[2]
if any(a.get('area') == area for a in d.get('areas_instanciadas', [])):
    print(f"El área '{area}' ya está instanciada. Para cambiar sus rutas, edita su charter.", file=sys.stderr)
    sys.exit(1)
lat = d.get('areas_latentes', [])
if area not in lat:
    print(f"El área '{area}' no está en las latentes del manifiesto: {', '.join(lat) or 'ninguna'}.", file=sys.stderr)
    print("Si de verdad es un área nueva del catálogo, añádela primero a areas_latentes.", file=sys.stderr)
    sys.exit(1)
PY

# --- el territorio tiene que existir: no se instancia un área vacía ---
faltan=""
IFS=',' read -ra _rutas <<< "$RUTAS"
for r in "${_rutas[@]}"; do
  r="$(echo "$r" | xargs)"
  [ -d "$REPO_CODIGO/$r" ] || faltan="$faltan $r"
done
if [ -n "$faltan" ]; then
  echo "❌ Estas rutas no existen en $REPO_CODIGO:$faltan" >&2
  echo >&2
  echo "   Un especialista sin territorio empuja trabajo hacia su especialidad." >&2
  echo "   Crea primero el código del área; el agente viene después, no antes." >&2
  exit 1
fi

# --- parámetros heredados del montaje (o deducidos, si el manifiesto es v1.0.0) ---
STACK="$(campo parametros.stack)"
REGLA_DE_ORO="$(campo parametros.regla_de_oro)"
COMANDO_VERIFICACION="$(campo parametros.comando_verificacion)"
FUENTES_CONSTRUCCION="$(campo parametros.fuentes_construccion)"
MODELO_ESPECIALISTA="${MODELO:-$(campo parametros.modelo_especialista)}"

hermano="$(find "$AGENTS_REPO/agents" -maxdepth 2 -name "$PREFIJO-*-dev.md" | head -1)"
deducir() {  # $1 = etiqueta a buscar en el charter hermano, $2 = fallback
  [ -n "$hermano" ] && grep -m1 "$1" "$hermano" 2>/dev/null | sed "s/.*$1[[:space:]]*//" | head -1 || echo "$2"
}
if [ -z "$COMANDO_VERIFICACION" ] && [ -n "$hermano" ]; then
  COMANDO_VERIFICACION="$(grep -m1 'La verificación pasa:' "$hermano" | sed 's/.*La verificación pasa:[[:space:]]*//')"
  echo "   (manifiesto sin parámetros: comando de verificación deducido del charter de $(basename "$hermano"))"
fi
[ -n "$MODELO_ESPECIALISTA" ] || MODELO_ESPECIALISTA="sonnet"

DIR="$AGENTS_REPO/agents/$AGENTE"
[ -e "$DIR" ] && { echo "Ya existe $DIR" >&2; exit 1; }

echo "Instanciando $AGENTE"
echo "  área:    $AREA"
echo "  rutas:   $RUTAS"
echo "  modelo:  $MODELO_ESPECIALISTA"
[ "$DRY_RUN" -eq 1 ] && { echo "(dry-run: no se escribe nada)"; exit 0; }

mkdir -p "$DIR/notes"
cp "$TPL/charters/specialist.md.tpl" "$DIR/$AGENTE.md"

rutas_fmt=""
for r in "${_rutas[@]}"; do rutas_fmt="$rutas_fmt- \`$(echo "$r" | xargs)\`"$'\n'; done

AB_AREA="$AREA" AB_AREA_DESC="$AREA" AB_RUTAS_AREA="$rutas_fmt" \
AB_PROYECTO="$PROYECTO" AB_PREFIJO="$PREFIJO" AB_STACK="$STACK" \
AB_KB_PATH="$KB_PATH" AB_KB_REL="agents/$PREFIJO-architect/knowledge-base" \
AB_REPO_CODIGO="$REPO_CODIGO" AB_REGLA_DE_ORO="$REGLA_DE_ORO" \
AB_COMANDO_VERIFICACION="$COMANDO_VERIFICACION" \
AB_FUENTES_CONSTRUCCION="$FUENTES_CONSTRUCCION" \
AB_FUENTES_NORMATIVAS="$(campo parametros.fuentes_normativas)" \
AB_COMANDO_FITNESS="$(campo parametros.comando_fitness)" \
AB_FF_TOOL="$(campo parametros.ff_tool)" \
AB_TABLERO_DESC="$(campo parametros.tablero_desc)" \
AB_AREAS_LATENTES="" AB_MODELO_ARQUITECTO="" \
AB_MODELO_ESPECIALISTA="$MODELO_ESPECIALISTA" AB_MODELO_REVIEWER="" \
AB_VERSION="$VERSION" AB_FECHA="$(date +%Y-%m-%d)" \
python3 - "$DIR/$AGENTE.md" <<'PY'
import os, sys, pathlib
TOKENS = ("PROYECTO", "PREFIJO", "STACK", "KB_PATH", "KB_REL", "REPO_CODIGO",
          "REGLA_DE_ORO", "FF_TOOL", "COMANDO_FITNESS", "COMANDO_VERIFICACION",
          "FUENTES_NORMATIVAS", "FUENTES_CONSTRUCCION", "TABLERO_DESC",
          "AREAS_LATENTES", "MODELO_ARQUITECTO", "MODELO_ESPECIALISTA",
          "MODELO_REVIEWER", "VERSION", "FECHA", "AREA_DESC", "RUTAS_AREA", "AREA")
p = pathlib.Path(sys.argv[1]); t = p.read_text(encoding="utf-8")
for k in TOKENS:
    t = t.replace("<" + k + ">", os.environ.get("AB_" + k, ""))
p.write_text(t, encoding="utf-8")
PY

# El frontmatter tiene que abrir en la línea 1 o Claude Code no reconoce el agente.
[ "$(head -1 "$DIR/$AGENTE.md")" = "---" ] || {
  echo "❌ El charter generado no abre con '---' en la línea 1: no sería descubrible." >&2
  echo "   Revisa templates/charters/specialist.md.tpl" >&2; exit 1; }

# --- registrar en el manifiesto: sale de latentes, entra en instanciadas ---
python3 - "$MANIFEST" "$AREA" "$RUTAS" "$AGENTE" <<'PY'
import json, sys
ruta, area, rutas, agente = sys.argv[1:5]
d = json.load(open(ruta))
d.setdefault('areas_instanciadas', []).append({"area": area, "rutas": rutas, "agente": agente})
d['areas_latentes'] = [a for a in d.get('areas_latentes', []) if a != area]
open(ruta, 'w', encoding='utf-8').write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
PY

echo
echo "✅ $AGENTE instanciado y registrado."
echo
echo "Queda por hacer, y no lo hace este script:"
echo "  1. bash install.sh   (con CLAUDE_HOME si los agentes viven en el workspace)"
echo "  2. RECARGAR la sesión: hasta entonces el agente no es descubrible"
echo "  3. Pedir al arquitecto un REFRESH: tiene que onboardar el módulo nuevo en su"
echo "     system-map y darle ficha de contexto, o nacerá sin gobierno"
echo "  4. Revisar el charter: sus 'gotchas' son project-owned y salen vacíos"
