# Changelog — agent-bootstrap

Versionado semántico de la **metodología**. Un cambio mayor implica que los proyectos ya
inicializados necesitan revisión manual al hacer `upgrade`.

## 1.1.0 — 2026-08-04

Cierra los tres huecos que quedaban declarados en la v1.0.0, más dos fallos encontrados al
revisarla. Todo salió de montar un proyecto real con ella.

**`ADD-AREA` y `STATUS` dejan de ser una descripción y pasan a ser scripts.**

- `scripts/add-area.sh` instancia un especialista de un área latente, hereda los parámetros del
  montaje y lo mueve de latente a instanciada en el manifest. **Se niega si el territorio no
  existe**, que es lo que da sentido al catálogo de áreas latentes: un especialista sin territorio
  empuja trabajo hacia su especialidad.
- `scripts/status.sh` audita entorno, charters, enlaces, hook, base de conocimiento y áreas.
  `exit 1` si hay algo roto, así que sirve en CI. Probado contra un montaje sano y contra uno roto
  a propósito: caza el frontmatter mal colocado, los agentes sin enlazar, el guard sin cablear y la
  KB sin sembrar.

**El fallo que motivó todo esto: una skill instalada que se queda vieja en silencio.**

- `install.sh` del repo gana `--link`, que enlaza en vez de copiar. Una copia es una foto: editas
  el repo y la instalada no cambia, y **su propio `VERSION` sigue diciendo el número viejo**, así
  que es indistinguible de una al día. Esta herramienta pasó semanas generando charters con un
  defecto ya corregido upstream por exactamente eso.
- `status.sh` lo detecta como primer bloque de su auditoría.

**Dos bugs de bulto encontrados de camino:**

- `install.sh` copiaba con `cp -R src dest/` sobre un destino existente, lo que **anida la skill
  dentro de sí misma** (`skills/foo/foo`) y la rompe en silencio. Ahora limpia el destino antes,
  guardando copia de seguridad, con nombres que no colisionan aunque se instale dos veces en el
  mismo segundo.
- El manifest se escribía con un heredoc, así que **una regla de oro con comillas dobles producía
  un JSON inválido** y dejaba el montaje con un manifiesto que ni `status` ni `upgrade` podrían
  leer. Ahora se serializa con `json.dumps`.

**El manifest guarda los parámetros del montaje** (`parametros`): regla de oro, comandos, fuentes y
modelos. Sin ellos, `add-area` tendría que volver a preguntarlos o inventárselos, y el especialista
nuevo nacería con un charter distinto del de sus hermanos. Los montajes de 1.0.0 siguen funcionando:
`add-area` deduce lo que falta del charter de otro especialista y avisa de que lo ha hecho.

## 1.0.0 — 2026-07-31

Primera versión. Fusiona el handoff del arquitecto persistente v3 —cuya metodología está probada
en **stick-crisis**, un arquitecto backend Java/Spring y **tmf-agents**— con dos aportaciones
nuevas.

> Nota de alcance: `vetimoly-agents` **no** implementa esta metodología (no tiene arquitecto ni base
> de conocimiento: es un agente de dominio con skills). Comparte solo el patrón de repo hermano con
> `install.sh`. La herramienta, hoy, no cubre esa familia de proyectos.

- **Roles fijos + áreas de catálogo.** Separa el rol (arquitecto, especialista, reviewer) del área
  (core-domain, frontend-ui, backend-api, data-pipeline, devops-infra). Resuelve el problema de
  instanciar un especialista sin territorio en proyectos que no tienen esa capa, sin perder la
  portabilidad hacia los que sí.
- **Mecanismo anti-divergencia.** `VERSION` + manifest por proyecto + clasificación tool-owned /
  project-owned, que permite propagar mejoras de la metodología sin pisar la base de conocimiento
  de ningún proyecto.

### Revisada antes del primer uso

Auditada de forma adversarial antes de estrenarse. Se corrigieron: el frontmatter de los charters
quedaba detrás de comentarios HTML (habría impedido registrar los agentes); se horneaban rutas
absolutas de máquina en charters y hook (contradiciendo el principio de que el montaje sobreviva a
mover el repo); `install.sh` instalaba en ámbito de usuario y no cableaba el hook pese a prometerlo;
el especialista recibía una orden imposible de ejecutar (invocar al arquitecto, cosa que los agentes
no pueden hacer entre sí); y el criterio de "cero placeholders" era gameable por el propio
scaffolder.

### Limitaciones conocidas de esta versión

- **No reproduce un montaje multi-repo.** La fase de auditoría en paralelo con manifiesto de
  cobertura y el `system-map` cross-repo del handoff no están implementadas. Hoy la herramienta no
  podría regenerar un `tmf-agents`.
- **`refresh.sh` y los esqueletos de `check-arch` no existen** todavía.
- **`ADD-AREA` y `STATUS` están descritos pero sin procedimiento detallado.**
- **Los charters se tratan como project-owned de facto.** En cuanto se llenan de contenido real, un
  diff por secciones deja de ser viable. `upgrade` no intenta sincronizarlos: para eso está el
  changelog.
- **No cubre agentes de dominio no-código** (del estilo de `vetimoly-agents`).
- **El perfil S/M/L es guía de la entrevista, no un parámetro.** `scaffold.sh` genera siempre el
  mismo conjunto de ficheros; la proporcionalidad la aplica quien conduce el montaje, no el script.
- **Los parámetros obligatorios bloquean un greenfield puro.** Un proyecto sin documentos
  normativos ni comando de verificación no puede scaffoldearse sin inventarse valores. Es
  deliberado —un charter con huecos no sirve— pero es un montaje legítimo que hoy se rechaza.
- **`AREAS` no valida su formato.** `core-domain:` (sin rutas) genera un especialista sin
  territorio y pasa todas las comprobaciones.
