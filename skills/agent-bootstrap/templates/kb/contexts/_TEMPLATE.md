---
module: <nombre>
path: <ruta>
files: <N>
pattern: <patrón arquitectónico>
health: 🟢
updated: <YYYY-MM-DD>
provisional: true
---

## Responsabilidad

Qué hace y, sobre todo, **qué NO le corresponde hacer**.

## Dominio

Conceptos y entidades que le pertenecen.

## Interfaz

Qué expone al resto y qué consume.

## Dependencias

**Entrantes**: quién le llama.
**Salientes**: a quién llama. **Marca las ilegales.**

## Violaciones de fitness functions

Cada una con su ubicación `fichero:línea`. Sin "etc.".

## Deuda

Referencias a `TD-NNN`. No re-describir la deuda aquí.
