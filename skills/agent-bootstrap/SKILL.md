---
name: agent-bootstrap
description: >
  Inicializa un proyecto (nuevo o existente) con su equipo de agentes persistentes: un arquitecto
  con base de conocimiento versionada, especialistas por área, la orquestación entre ellos y la
  integración con el tablero de tareas. Genera un repo `<proyecto>-agents` fuera del repo de código.
  Úsala cuando quieras: montar la capa de agentes de un proyecto desde cero · añadir un área nueva
  a un proyecto ya inicializado (`add-area`) · propagar mejoras de la metodología a un proyecto ya
  montado (`upgrade`) · o auditar si la capa de agentes de un proyecto sigue coherente (`status`).
  Trigger phrases: "monta los agentes de este proyecto", "inicializa el proyecto con agentes",
  "agent bootstrap", "añade un agente de <área>", "actualiza la metodología de agentes",
  "/agent-bootstrap".
---

# agent-bootstrap — inicializador portable de proyectos agénticos

Monta, en cualquier proyecto, la misma arquitectura agéntica: **un arquitecto que decide y no
codifica**, **especialistas que implementan dentro de su área**, y una **base de conocimiento
versionada** que sobrevive meses. El objetivo no es sólo montar agentes: es que **todos tus
proyectos compartan la misma forma**, para que lo que aprendes en uno sirva en los demás.

Base metodológica: `references/HANDOFF-arquitecto-v3.md` (probado en real en tres proyectos).
Léelo cuando necesites el detalle de una fase; esta skill es el playbook operativo.

---

## Modos

Declara el modo en la primera línea al invocar la skill.

| Modo | Cuándo | Qué hace |
|---|---|---|
| **INIT** (por defecto) | Proyecto sin capa de agentes | Entrevista → recon → genera `<proyecto>-agents` con charters y KB sembrada → bootstrap del arquitecto |
| **ADD-AREA** ⚠️ | El proyecto desarrolla un área que estaba latente | Instancia el especialista desde el template y lo registra. **Sin procedimiento detallado todavía** (v1.1) |
| **UPGRADE** | Has mejorado la metodología y quieres propagarla | Compara el manifest del proyecto con `VERSION`, diffea **solo lo tool-owned** y aplica con confirmación |
| **STATUS** ⚠️ | Duda de si la capa sigue coherente | Verifica symlinks, hook, manifest y cobertura de la KB. **Sin procedimiento detallado todavía** (v1.1) |

---

## Principio estructural (no negociable)

**La KB y los charters viven FUERA del repo de código.** Nunca contaminan el entregable y
sobreviven a que el repo se mueva o se renombre. El hogar es un repo dedicado
`<proyecto>-agents`, clonado hermano del repo de código, versionado desde el minuto uno.

```
<proyecto>-agents/
├── README.md                      # onboarding: layout, requisitos, cómo invocar
├── install.sh                     # [tool-owned] symlinks + hook; idempotente
├── .bootstrap-manifest.json       # [tool-owned] versión, parámetros, áreas latentes
├── orchestration.md               # [mixto] quién invoca a quién y con qué contratos
└── agents/
    ├── <p>-architect/             # ÚNICO agente con knowledge-base
    │   ├── <p>-architect.md
    │   ├── knowledge-base/
    │   │   ├── README.md  system-map.md  fitness-functions.md
    │   │   ├── tech-debt.md  scorecard.md  BOOTSTRAP.md
    │   │   ├── contexts/  (_TEMPLATE.md + una ficha por módulo)
    │   │   └── adr/       (_TEMPLATE.md + ADR-NNN-*.md)
    │   └── scripts/       (write-guard.sh; check-arch lo escribe el proyecto)
    ├── <p>-<area>-dev/            # especialistas: charter + notes/, SIN KB propia
    └── <p>-reviewer/              # opcional
```

---

## Topología: roles fijos, áreas instanciadas

Esto es lo que hace la herramienta portable sin volverse rígida. **Separa el rol del área.**

**Roles** — idénticos en todos los proyectos:

| Rol | Mandato | Escribe sólo en | Límites duros |
|---|---|---|---|
| `architect` | Decide vía ADRs, emite veredictos, detecta deriva, mantiene la KB. Dueño de **todas las costuras entre áreas** | `knowledge-base/**` | NO escribe código de producción · NO comandos que muten estado · NO opina de estilo |
| `<area>-dev` | Implementa siguiendo el diseño. Ante duda de diseño o cambio estructural, **para y escala** | Las rutas de SU área + `notes/` | NO toca la KB (leerla sí, y es obligatorio antes de implementar) · NO cruza fronteras de área sin GATE |
| `reviewer` | Revisa diffs de forma independiente: cumplimiento, no diseño | — | NO escribe código · NO duplica al arquitecto |

**Áreas** — se instancian según lo que el proyecto *tiene*:

| Área | Se instancia cuando existe… |
|---|---|
| `core-domain` | un dominio o lógica de negocio aislable |
| `frontend-ui` | una interfaz de usuario |
| `backend-api` | un servidor o API |
| `data-pipeline` | datos maestros, validadores, importadores |
| `devops-infra` | despliegue no trivial, CI/CD, contenedores |

Las áreas que el proyecto no tiene quedan **latentes** en el manifest y se activan con `ADD-AREA`
cuando aparezcan. Un proyecto con las cuatro capas clásicas instancia arquitecto + backend +
frontend + devops; uno de navegador puro instancia arquitecto + core + ui + data. **La coherencia
entre proyectos está en los roles y los contratos, no en clonar la misma lista de áreas.**

> ⚠️ **No instancies un área vacía.** Un especialista sin territorio inventa trabajo hacia su
> especialidad: un backend-dev en un proyecto sin servidor empujará hacia servidores y APIs contra
> las decisiones del proyecto.

**Una sola KB, la del arquitecto.** Si cada área acumula su propia verdad, nadie es dueño de la
costura y el diseño deriva. Los especialistas tienen `notes/` con runbooks operativos de su área
— eso es *cómo se opera*, no *autoridad de diseño*.

---

## Modo INIT — el proceso

### Fase 1 · Recon (antes de preguntar nada)

Inventaría el repo en **solo lectura** y prepara propuestas, no conclusiones:

- Stack y build (`package.json`, `pom.xml`, `pyproject.toml`, lockfiles)
- Layout mono o multi-repo (workspaces, repos hermanos con prefijo común)
- Módulos candidatos a contexto, con LOC por zona
- Herramienta de fitness functions candidata: TS → dependency-cruiser + ESLint · Java → ArchUnit ·
  Python → import-linter
- Documentación existente, que es la **semilla de la KB**: `docs/`, `README`, `CLAUDE.md`, `AGENTS.md`
- **Candidata a regla de oro**: reglas ya declaradas como no negociables en esos documentos
- **Qué áreas existen de verdad**: ¿hay servidor? ¿hay UI? ¿hay pipeline de datos? ¿hay despliegue?

### Fase 2 · Entrevista

**Pregunta 0 — el perfil del proyecto.** Derívalo del recon (líneas de código reales, módulos con
contenido, número de repos, tamaño del equipo) y proponlo:

| Perfil | Cuándo | Qué se monta |
|---|---|---|
| **S** | un repo, un módulo con código real, una persona | Arquitecto + **un** especialista. Sin reviewer. Fitness sí (baratas y valiosas desde el día uno). Scorecard y AUDIT-REPORT opcionales. Hook opcional |
| **M** | varios módulos con código, un equipo pequeño | Todo lo anterior + un especialista por área real + scorecard |
| **L** | multi-repo o equipo | Todo + reviewer + fan-out de auditoría + AUDIT-REPORT |

Esto es la regla de oro nº 9 con mecanismo. Sin ella, "proporcionalidad" es una convención más, y
las convenciones sin mecanismo decaen. **Montar la maquinaria completa sobre un repo de trescientas
líneas no protege nada: solo añade ceremonia.**

Después, las ocho decisiones, con `AskUserQuestion`, cada una con el default que sugiere el recon.
**No las asumas: cambian el diseño del agente.**

1. **Mandato del arquitecto** — default: steward de diseño + GATE estructural, sin revisión de
   cumplimiento por PR.
2. **Alcance y profundidad** — ¿todo a fondo, o núcleo a fondo y periféricos "aware"? Enumera los
   módulos detectados y pide clasificarlos.
3. **Hogar de la KB** — default: repo dedicado `<proyecto>-agents` hermano. Pregunta el nombre y si
   se crea remoto (verifica antes `gh auth status` y **usa la cuenta correcta**).
4. **Topología** — presenta el catálogo de áreas con las detectadas premarcadas.
5. **Fuentes de "cómo se construye aquí"** — lista los documentos y skills detectados y pide
   confirmar el **orden de autoridad**.
6. **Testing** — ¿el arquitecto lidera el testing o sólo es consciente de su estado?
7. **Tablero** — dónde vive la gestión del trabajo (ver más abajo).
8. **Extras** — modelo del arquitecto (default: razonamiento alto), y si se instala el write-guard
   (default: sí).

### Fase 3 · Scaffold

`scripts/scaffold.sh` crea el árbol, sustituye los tokens y hace `git init`. Es determinista y
verificable: **su criterio de éxito es cero placeholders `<TOKEN>` residuales**.

Después materializas los charters con el contenido real del recon. Al copiar desde informes que
hayan viajado por canales que escapan HTML, **des-escapa** `&gt;`, `&lt;` y `&amp;` o el frontmatter
YAML del charter se rompe.

### Fase 4 · Siembra de la KB

Las fichas **nunca nacen vacías**. Una por módulo, sembrada del recon. Si el proyecto tiene
documentación previa, la KB la **referencia y transforma**, no la duplica ni la muda: esos
documentos siguen siendo la autoridad de dominio.

Mapea **todos** los módulos en el `system-map`, aunque sea como fila "aware" (tooling, mirrors),
o tu propio check de completitud los marcará como no mapeados — y hará bien.

Marca `provisional` las fichas sembradas de hechos verificados pero sin barrido exhaustivo.

### Fase 5 · Fitness functions con baseline medido

Reglas objetivas que **fallan en build o test**, no convenciones en un documento. Convención:
listan violaciones, salida vacía es OK, `exit != 0` en CI.

**En un proyecto con historia, empieza NO bloqueante** — arrancar todo bloqueante rompe el CI el
día uno. En un proyecto nuevo es al revés: **nacen bloqueantes con baseline cero**, que es el mejor
momento posible.

Tres trampas al medir el baseline:

1. **Falso verde** — una regla que apunta a un paquete inexistente "pasa vacía". Verifica que cada
   regla evalúa sujetos reales: número de sujetos > 0.
2. **Clasifica por la frontera efectiva**, no por un ancestro.
3. **Camina la indirección** — herencia transitiva, imports con alias. Un grep ingenuo se los pierde.
   Si conviven dos mecanismos para el mismo invariante, detecta el patrón de cada uno.

### Fase 6 · Bootstrap y verificación

El arquitecto, ya descubrible, ingiere su KB, la **valida por muestreo (≥5 hechos contra el código
real)**, hace un dry-run de un veredicto y escribe `BOOTSTRAP.md`. Si fallan dos o más muestras,
**para**: la KB está envenenada y todas las decisiones que salgan de ella lo estarán.

Después: `install.sh`, hook, recordar el reload, commit inicial.

---

## Integración con el tablero de tareas

**Lo duradero vive en git** (spec, ADRs, KB — el *porqué*). **Lo efímero vive en el tablero**
(órdenes y ejecución — el *qué* y *quién*). Nunca dupliques entre ambos.

| Artefacto | Vive en | El tablero… |
|---|---|---|
| ADRs, deuda técnica, fitness functions, fichas | KB | Las **referencia** por identificador, no las re-describe |
| Estado del trabajo, quién hace qué | Tablero | La KB no sabe qué está en curso |

**Si el proyecto usa CodeAgentSwarm** (default cuando está disponible): sus estados ya implementan
las dos puertas humanas — `complete_task` lleva a *in_testing* y **sólo el humano** cierra. No
construyas un sistema de estados encima.

**Si no**, degrada a ficheros Markdown versionados en el repo de agentes, **uno por tarjeta** —
nunca un tablero único mutable, que garantiza conflictos entre agentes concurrentes.

**Formato de tarjeta, en ambos casos.** Los subagentes arrancan **sin tu contexto**: la tarjeta
es el brief y tiene que bastar en frío.

- **Contexto** — por qué existe, con enlace a la fuente
- **Qué hacer** — alcance concreto y decisiones ya tomadas que **no** debe reabrir
- **Criterios de aceptación** — verificables uno a uno, máquina-comprobables donde se pueda
- **Ficheros** — la zona que puede tocar. **Es un contrato**: dos tareas con ficheros solapados no
  pueden estar en curso a la vez. Los barrel files quedan exentos: su conflicto es trivial y
  someterlos a exclusión serializaría el proyecto entero
- **Fuera de alcance** — obligatorio en toda tarea no trivial. Es la defensa estructural contra el
  scope creep, que es el fallo típico de los agentes

**Trazabilidad a git**: rama `t-<id>-<slug>`, footer `Task: #<id>` en los commits, y el número de
PR anotado de vuelta. Así, meses después, `git blame` → commit → tarea → ADR responde "por qué
existe este código" en cuatro saltos.

---

## Contratos entre agentes

Definidos en `orchestration.md` del proyecto, con el mismo formato en todos:

```
CONSULT(pregunta, contexto)  → recomendación primero + 2-3 alternativas descartadas con motivo
GATE(diff | plan)            → VERDICT: APPROVE | APPROVE-WITH-CONDITIONS | REWORK | ESCALATE
                               + FINDINGS con severidad S1..S4 + CONDITIONS + KB IMPACT
```

**Orden canónico de una feature**: se plantea → arquitecto CONSULT si hay duda de encaje →
especialista implementa → si el diff es estructural, arquitecto GATE antes de integrar → reviewer
si existe → **decide el humano**. Lo no estructural (CRUD que respeta el patrón, textos, tests)
fluye sin GATE.

**Los subagentes no se invocan entre sí**: todos los contratos pasan por el hilo principal, que es
donde además supervisa el humano.

---

## Concurrencia entre agentes

- Cada especialista con sus **rutas declaradas** en el charter.
- **Un agente, un worktree.** Nunca cambies de rama en un working tree que otro agente está usando.
- **Commitea sólo tus ficheros** (`git add <rutas>`, jamás `-A`): otro agente puede estar
  escribiendo al lado.
- Nunca `rebase` de una rama compartida. Para mover commits, `git worktree`.

---

## El hook write-guard

Refuerza a nivel de harness el límite "el arquitecto sólo escribe en su KB". Los hooks
`PreToolUse` se disparan dentro de subagentes y el payload incluye el tipo de agente.

**Dos ámbitos distintos, y es deliberado.** Los **agentes** se enlazan en el workspace
(`../.claude/agents/`), para que solo aparezcan en este proyecto. El **hook**, en cambio, va al
`settings.json` **de usuario** — porque Claude Code no lee settings de directorios padre: solo de la
raíz del repo de la sesión, del ámbito de usuario y de la política gestionada. Un hook en el
workspace **no se cargaría nunca**. Que sea de usuario es inofensivo: el guard filtra por tipo de
agente y es fail-safe, así que solo actúa sobre el arquitecto de este proyecto. Es la vía que
prescribe el handoff: hook global con filtro en el script.

`install.sh` lo cablea con la ruta absoluta de cada máquina, con copia de seguridad y merge no
destructivo, y **avisa si el merge falla** en vez de dar éxito por supuesto.

**Diséñalo fail-safe**: bloquea **sólo** si el agente coincide **y** la ruta está fuera de la KB.

**Calcula la ruta de la KB en tiempo de ejecución**, desde la ubicación del propio script — ni la
hornea al generar el proyecto, ni la compara por sufijo. Horneada, deja de proteger en cuanto mueves
el repo. Por sufijo, se elude construyendo una ruta que lo contenga. Calculada en runtime y comparada
por prefijo absoluto **normalizado** (resolviendo `..` incluso cuando el directorio aún no existe),
sobrevive a mover el repo y no se puede rodear.
Cualquier otro caso —otro agente, JSON inválido, falta `jq`— **permite**. Así es imposible
sobre-bloquear. Pruébalo con payloads simulados antes de confiar en él.

> No hay forma declarativa de acotar un hook a un subagente: la vía real es un hook **global** con
> **filtro por tipo de agente en el script**. Un `hooks:` en el frontmatter del agente es plausible
> y **falso** — contrasta siempre los mecanismos con la documentación, no con la intuición.

---

## Reglas de oro

1. La KB describe la **realidad**. Si contradice al código, **gana el código** y se actualiza la KB.
   Lo aspiracional va a un ADR en estado `Proposed`.
2. El arquitecto **nunca** escribe código de producción.
3. Charter y KB **fuera** del repo de código, versionados.
4. **Sólo el humano** mueve un ADR de `Proposed` a `Accepted`.
5. Fan-out con **manifiesto de cobertura**: `ficheros_encontrados == ficheros_cubiertos`. Nada de
   huecos silenciosos.
6. **Bootstrap obligatorio** antes de operar: si la KB no supera el muestreo, no es fiable.
7. **Enforcement antes que disciplina**: la convención sin mecanismo que la fuerce decae.
8. La KB es **estado compartido**: `pull` antes, `push` después.
9. **Proporcionalidad**: óptimo no es máximo. Calibra al tamaño real del proyecto.

---

## Verificación antes de dar por bueno un montaje

- [ ] Las ocho decisiones de la entrevista, cerradas con el humano
- [ ] KB en su hogar versionado, agentes descubribles
- [ ] Charter completo: modos, límites, principios, formatos
- [ ] Una ficha por módulo, con las cuentas cuadrando y **cero placeholders**
- [ ] Fitness functions con **baseline medido** y calibradas bloqueante/aviso
- [ ] ADRs iniciales sembrados; deuda técnica; scorecard
- [ ] **Bootstrap ejecutado y validado**; `BOOTSTRAP.md` escrito
- [ ] Hook instalado y **probado fail-safe**
- [ ] `install.sh` idempotente verificado

---

## Ficheros de la skill

| Ruta | Qué es |
|---|---|
| `VERSION` | Semver de la metodología. Lo consulta `upgrade` |
| `templates/charters/` | Esqueletos de charter: arquitecto, especialista, reviewer |
| `templates/kb/` | Esqueleto de la base de conocimiento |
| `templates/repo/` | `install.sh` y `orchestration.md`. El README y el manifest los genera `scaffold.sh` |
| `templates/scripts/` | write-guard. `refresh.sh` y los esqueletos de `check-arch` están **pendientes** (v1.1) |
| `scripts/scaffold.sh` | Genera el repo de agentes y sustituye tokens |
| `scripts/upgrade.sh` | Propaga mejoras respetando lo project-owned |
| `references/HANDOFF-arquitecto-v3.md` | La metodología completa |

**Propiedad de los ficheros** — lo que hace posible actualizar sin pisar:

- **tool-owned** — `upgrade` los actualiza mostrando el diff: `install.sh` y `write-guard.sh`.
- **project-owned** — `upgrade` **nunca** los toca: toda la KB, los ADRs, los principios rectores,
  la regla de oro, y también `check-arch` y `refresh`, que codifican reglas **de ese proyecto**.
- **Los charters, en la práctica, son project-owned.** Los marcadores `<!-- tool-owned -->` que
  llevan dentro sirven para orientar a quien los edite a mano, pero `upgrade` **no los sincroniza**:
  en cuanto se llenan de contenido real, un diff por secciones deja de ser viable. Cuando cambie la
  metodología, lo que se propaga es el **CHANGELOG**, y la revisión es manual.
