#!/bin/bash
#
# upgrade.sh — propaga mejoras de la metodología a un proyecto ya inicializado.
#
#   bash upgrade.sh /ruta/al/<proyecto>-agents            # muestra el diff, no aplica
#   bash upgrade.sh /ruta/al/<proyecto>-agents --aplicar  # aplica lo tool-owned
#
# REGLA INVIOLABLE: sólo toca ficheros tool-owned. La base de conocimiento, los ADRs,
# los principios rectores y la regla de oro son project-owned y NUNCA se tocan.
#
# Ante la duda, no aplica: prefiere dejar un proyecto desactualizado a pisar su KB.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_SKILL="$(cat "$SKILL_DIR/VERSION")"

[ $# -ge 1 ] || { echo "Uso: $0 <ruta-al-repo-de-agentes> [--aplicar]" >&2; exit 2; }
DESTINO="$1"; APLICAR=0
[ "${2:-}" = "--aplicar" ] && APLICAR=1

MANIFEST="$DESTINO/.bootstrap-manifest.json"
[ -f "$MANIFEST" ] || { echo "No es un montaje de agent-bootstrap: falta .bootstrap-manifest.json" >&2; exit 1; }

command -v jq >/dev/null 2>&1 || { echo "Hace falta 'jq'" >&2; exit 1; }

VERSION_PROY="$(jq -r '.version' "$MANIFEST")"
PREFIJO="$(jq -r '.prefijo' "$MANIFEST")"
PROYECTO="$(jq -r '.proyecto' "$MANIFEST")"
KB_PATH="$DESTINO/agents/$PREFIJO-architect/knowledge-base"

# Los templates llevan tokens <TOKEN>. Al propagarlos hay que re-sustituirlos con los
# parámetros que este proyecto ya tiene en su manifest, o el fichero queda inservible.
sustituir_tokens() {
  local f="$1"
  sed -i.tmp \
    -e "s|<PREFIJO>|$PREFIJO|g" \
    -e "s|<PROYECTO>|$PROYECTO|g" \
    -e "s|<KB_PATH>|$KB_PATH|g" \
    -e "s|<VERSION>|$VERSION_SKILL|g" "$f"
  rm -f "$f.tmp"
}

echo "Proyecto:    $(jq -r '.proyecto' "$MANIFEST")"
echo "Su versión:  $VERSION_PROY"
echo "Skill:       $VERSION_SKILL"
echo

if [ "$VERSION_PROY" = "$VERSION_SKILL" ]; then
  echo "✅ Ya está al día. Nada que propagar."
  exit 0
fi

mayor_skill="${VERSION_SKILL%%.*}"; mayor_proy="${VERSION_PROY%%.*}"
if [ "$mayor_skill" != "$mayor_proy" ]; then
  echo "⚠️  Cambio de versión MAYOR ($VERSION_PROY → $VERSION_SKILL)."
  echo "   Implica revisión manual: puede haber cambios que no se propagan solos."
  echo "   Revisa el CHANGELOG antes de continuar."
  echo
fi

# --- ficheros tool-owned que sí se propagan ---
# Nota: los charters son MIXTOS. No se sobrescriben automáticamente: sólo se avisa
# de que su parte estructural ha cambiado, y el humano decide.
declare -a CAMBIOS=()

comparar() {
  local origen="$1" destino="$2" etiqueta="$3"
  [ -f "$origen" ] || return 0
  if [ ! -f "$destino" ]; then
    echo "  ＋ $etiqueta (nuevo)"; CAMBIOS+=("$origen|$destino"); return 0
  fi
  if ! diff -q "$origen" "$destino" >/dev/null 2>&1; then
    echo "  ~ $etiqueta"; CAMBIOS+=("$origen|$destino")
  fi
}

echo "Ficheros tool-owned con cambios:"
comparar "$SKILL_DIR/templates/repo/install.sh" "$DESTINO/install.sh" "install.sh"

# El write-guard lleva tokens sustituidos: se compara ignorando las líneas parametrizadas.
GUARD_DEST="$DESTINO/agents/$PREFIJO-architect/scripts/write-guard.sh"
if [ -f "$GUARD_DEST" ]; then
  tmp_a="$(mktemp)"; tmp_b="$(mktemp)"
  grep -vE '^(AGENTE_PROTEGIDO|KB_PATH)=' "$SKILL_DIR/templates/scripts/write-guard.sh.tpl" > "$tmp_a"
  grep -vE '^(AGENTE_PROTEGIDO|KB_PATH)=' "$GUARD_DEST" > "$tmp_b"
  diff -q "$tmp_a" "$tmp_b" >/dev/null 2>&1 || { echo "  ~ write-guard.sh (conserva sus parámetros)"; CAMBIOS+=("GUARD|$GUARD_DEST"); }
  rm -f "$tmp_a" "$tmp_b"
fi

if [ ${#CAMBIOS[@]} -eq 0 ]; then
  echo "  (ninguno)"
else
  echo
  echo "Ficheros PROJECT-OWNED que NO se tocan bajo ningún concepto:"
  echo "  · toda la base de conocimiento (fichas, ADRs, deuda, scorecard, baseline)"
  echo "  · la regla de oro y los principios rectores del charter"
  echo "  · las rutas de área y los comandos de verificación de los especialistas"
fi

echo
if [ "$APLICAR" -eq 0 ]; then
  echo "Esto ha sido una vista previa. Para aplicar: $0 $DESTINO --aplicar"
  exit 0
fi

for c in "${CAMBIOS[@]:-}"; do
  [ -n "$c" ] || continue
  origen="${c%%|*}"; destino="${c#*|}"
  cp "$destino" "$destino.bak.$(date +%Y%m%d%H%M%S)"
  if [ "$origen" = "GUARD" ]; then
    # Regenera el guard conservando sus dos parámetros
    ag="$(grep -E '^AGENTE_PROTEGIDO=' "$destino")"; kb="$(grep -E '^KB_PATH=' "$destino")"
    sed -e "s|^AGENTE_PROTEGIDO=.*|$ag|" -e "s|^KB_PATH=.*|$kb|" \
        "$SKILL_DIR/templates/scripts/write-guard.sh.tpl" > "$destino"
    chmod +x "$destino"
  else
    cp "$origen" "$destino"
    sustituir_tokens "$destino"
  fi
  echo "  actualizado: $destino"
done

# Verificación: si quedó algún token sin sustituir, el fichero está roto. Restaura y aborta.
roto=0
for c in "${CAMBIOS[@]:-}"; do
  [ -n "$c" ] || continue
  destino="${c#*|}"
  if grep -qE '<[A-Z_]+>' "$destino" 2>/dev/null; then
    echo "❌ $destino quedó con tokens sin sustituir:" >&2
    grep -oE '<[A-Z_]+>' "$destino" | sort -u | sed 's/^/     /' >&2
    ultima_copia="$(ls -t "$destino".bak.* 2>/dev/null | head -1)"
    [ -n "$ultima_copia" ] && cp "$ultima_copia" "$destino" && echo "   restaurado desde $ultima_copia" >&2
    roto=1
  fi
done
[ "$roto" -eq 0 ] || { echo >&2; echo "Propagación abortada. El proyecto queda como estaba." >&2; exit 1; }

jq --arg v "$VERSION_SKILL" --arg f "$(date +%Y-%m-%d)" \
   '.version = $v | .actualizado = $f' "$MANIFEST" > "$MANIFEST.tmp" && mv "$MANIFEST.tmp" "$MANIFEST"

echo
echo "✅ Propagado a v$VERSION_SKILL. Copias de seguridad junto a cada fichero."
echo "   Revisa el diff antes de commitear, y recarga si cambió el hook."
