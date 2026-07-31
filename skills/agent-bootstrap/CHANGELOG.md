# Changelog — agent-bootstrap

Versionado semántico de la **metodología**. Un cambio mayor implica que los proyectos ya
inicializados necesitan revisión manual al hacer `upgrade`.

## 1.0.0 — 2026-07-31

Primera versión. Fusiona el handoff del arquitecto persistente v3 (probado en stick-crisis,
tmf-agents y vetimoly-agents) con dos aportaciones nuevas:

- **Roles fijos + áreas de catálogo.** Separa el rol (arquitecto, especialista, reviewer) del área
  (core-domain, frontend-ui, backend-api, data-pipeline, devops-infra). Resuelve el problema de
  instanciar un especialista sin territorio en proyectos que no tienen esa capa, sin perder la
  portabilidad hacia los que sí.
- **Mecanismo anti-divergencia.** `VERSION` + manifest por proyecto + clasificación tool-owned /
  project-owned, que permite propagar mejoras de la metodología sin pisar la base de conocimiento
  de ningún proyecto.
