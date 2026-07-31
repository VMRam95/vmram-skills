<!-- tool-owned: contratos, orden canónico, concurrencia -->
<!-- project-owned: la tabla de agentes y sus rutas -->
# Orquestación de agentes — <PROYECTO>

## Los agentes

| Agente | Rol | Territorio | Tiene KB |
|---|---|---|---|
| `<PREFIJO>-architect` | Decide, no codifica | Todas las costuras | Sí, la única |
| _(especialistas)_ | Implementan | Sus rutas | No, sólo `notes/` |

**Áreas latentes** — no instanciadas porque el proyecto aún no las tiene. Se activan con
`agent-bootstrap` en modo ADD-AREA: <AREAS_LATENTES>

## Contratos

```
CONSULT(pregunta, contexto)
  → recomendación PRIMERO + 2-3 alternativas descartadas con motivo
  → si sienta precedente, ADR en Proposed

GATE(diff | plan)
  → VERDICT: APPROVE | APPROVE-WITH-CONDITIONS | REWORK | ESCALATE
  → SUMMARY · FINDINGS [severidad fichero:línea] · CONDITIONS · KB IMPACT
```

Severidades: `S1` bloquea · `S2` condición · `S3` deuda · `S4` sugerencia.

## Orden canónico de una feature

```
se plantea
  → arquitecto CONSULT          (sólo si hay duda de encaje)
  → especialista implementa
  → arquitecto GATE             (sólo si el diff es estructural)
  → reviewer                    (si existe)
  → decide el humano
```

Lo **no estructural** —funcionalidad que respeta el patrón, textos, tests, refactor interno—
fluye sin GATE. Meter todo por GATE convierte al arquitecto en un cuello de botella y deja de
mirar lo que importa.

**Los subagentes no se invocan entre sí.** Todos los contratos pasan por el hilo principal, que es
donde además supervisa el humano.

## Tablero

<TABLERO_DESC>

**Trazabilidad**: rama `t-<id>-<slug>` · footer `Task: #<id>` en los commits · número de PR
anotado de vuelta en la tarea.

**La tarjeta es el brief.** Los subagentes arrancan sin contexto: contexto, qué hacer, criterios de
aceptación verificables, ficheros (zona de exclusión) y **fuera de alcance** explícito.

## Concurrencia

- **Dos tareas con ficheros solapados no pueden estar en curso a la vez.** Los barrel files
  quedan exentos: su conflicto es trivial y someterlos a exclusión serializaría el proyecto.
- Un agente, un worktree. Nunca cambies de rama en un working tree que otro esté usando.
- `git add <rutas>`, jamás `-A`.
- Nunca `rebase` de rama compartida.
