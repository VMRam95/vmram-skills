---
name: doc-generator
description: Convertir Markdown a documentos HTML/PDF profesionales con templates predefinidos. Usar cuando el usuario quiera formatear documentacion tecnica, guias o presentaciones.
---

# Doc Generator

Convierte Markdown a documentos HTML profesionales listos para exportar a PDF.

## Templates Disponibles

| Template | Uso | Colores |
|----------|-----|---------|
| `aws` | Documentacion AWS/cloud | Naranja + gris oscuro |
| `corporate` | Documentos empresariales | Azul + gris |
| `minimal` | Limpio y simple | Negro + blanco |
| `tech` | Guias tecnicas | Verde + oscuro |
| `presupuesto` | Presupuestos profesionales | Navy + gold, portada, TOC auto |

## Uso Rapido

### 1. Generar documento

```bash
python3 ~/.claude/skills/doc-generator/scripts/generate.py \
  --input documento.md \
  --template corporate \
  --output /tmp/output.html
```

### 2. Abrir en navegador

```bash
open /tmp/output.html
```

El usuario puede guardar como PDF desde el navegador usando el boton "Guardar como PDF" o Ctrl+P / Cmd+P.

### 3. Limpiar

```bash
rm /tmp/output.html
```

## Generacion de PDF con Puppeteer (template presupuesto)

El template `presupuesto` tiene un script dedicado para generar PDFs con portada, footer personalizado y enlaces internos funcionales:

```bash
# 1. Generar HTML desde markdown
python3 ~/.claude/skills/doc-generator/scripts/generate.py \
  --input documento.md \
  --template presupuesto \
  --output output.html

# 2. Generar PDF con Puppeteer + pdf-lib
node ~/.claude/skills/doc-generator/scripts/generate-pdf.cjs \
  output.html output.pdf
```

### Como funciona generate-pdf.cjs

Usa una estrategia "replace page 0" para combinar portada sin footer + contenido con footer SIN romper enlaces internos:

1. **Pass 1 (full):** PDF completo con `displayHeaderFooter: true` (footer en todas las paginas, enlaces TOC funcionan)
2. **Pass 2 (cover):** Solo pagina 1 con `displayHeaderFooter: false` + margins 0 (portada limpia)
3. **Merge:** Reemplaza pagina 0 del PDF completo con la portada limpia via `fullDoc.removePage(0)` + `fullDoc.insertPage(0, newCover)`
4. **Post-process:** Anade anotaciones de enlace clickable (LinkedIn) en paginas 1+ via pdf-lib

### IMPORTANTE: No usar PDFDocument.create() + copyPages()

**NUNCA** crear un documento vacio y copiar paginas de dos PDFs separados. Esto rompe los enlaces internos porque `copyPages()` no copia el diccionario Names/Dests del documento. Siempre usar el enfoque "replace page 0" que preserva el documento original.

### Dependencias

- `puppeteer` (via `@modelcontextprotocol/server-puppeteer`)
- `pdf-lib` (npm global)

### Limitaciones conocidas de Puppeteer PDFs + pdf-lib

- `drawRectangle()` en paginas de Puppeteer **CORROMPE** los content streams (footer desaparece de TODAS las paginas)
- `displayHeaderFooter` de Puppeteer no permite excluir paginas individuales
- Links `<a href>` en `footerTemplate` de Puppeteer NO son clickables (hay que usar anotaciones pdf-lib)
- SVG en `footerTemplate` no renderiza, usar `<img src="data:image/png;base64,...">` en su lugar

## Flujo Completo (para el agente)

Cuando el usuario envie un markdown y pida formatearlo:

1. Guardar el markdown en `/tmp/doc-input.md`
2. Ejecutar el script con el template apropiado
3. Abrir el HTML resultante en el navegador
4. Informar al usuario que puede guardar como PDF
5. Limpiar archivos temporales cuando confirme

Para template `presupuesto`, usar siempre el flujo de PDF con `generate-pdf.cjs`.

## Features Soportados

- Headers (h1-h4)
- Tablas
- Bloques de codigo con syntax highlighting basico
- Listas (ordenadas y no ordenadas)
- Alertas/callouts (`> **AVISO:**` -> alert box)
- Texto en negrita/cursiva
- Links
- Saltos de pagina para impresion

## Personalizacion

Para crear un template nuevo, copiar uno existente en `~/.claude/skills/doc-generator/templates/` y modificar los estilos CSS.
