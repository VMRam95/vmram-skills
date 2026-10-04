---
name: agent-watch
description: "Diagnosticar lentitud, CPU/RAM y capacidad para agentes de este Mac, o mantener su semáforo de la barra de menús. Usar con $agent-watch, «Mac lento» o «¿cabe otro agente?». No activar por rendimiento de una aplicación o servidor remoto sin indicios de un problema del Mac."
metadata:
  short-description: Rendimiento, recursos y capacidad del Mac
---

# Rendimiento y capacidad de agentes en el Mac

Mide el ordenador real. No uses el número de sesiones, el Kanban ni los límites
lógicos del equipo como sustituto de CPU y memoria.

## Ejecución

1. Ejecuta:

   ```bash
   python3 ~/.agents/skills/agent-watch/scripts/mac_agent_capacity.py
   ```

   Los clientes instalados enlazan a la misma fuente; no mantienen copias del medidor.
2. El consumo procede de los árboles de procesos reales. Consulta nombres de sesiones
   únicamente dentro de una revisión de coordinación autorizada; medir capacidad no
   autoriza sondear sesiones. El JSON incluye los jobs del gestor común y sus grupos
   registrados, incluso fuera de CodeAgentSwarm.
3. Presenta primero el veredicto y después una tabla por agente con nombre o
   cuadrante, tipo, RAM aproximada y CPU instantánea.

## Respuesta obligatoria

Incluye, sin relleno:

- CPU total, CPU libre y carga;
- presión de cola (`load_pressure`: normal / alta / saturación I/O) y hilos en
  espera ininterrumpida cuando la carga supere los núcleos;
- RAM total y RAM efectiva disponible según `memory_pressure`;
- consumo agregado de los agentes y sobrecoste de CodeAgentSwarm;
- qué agentes ocupan recursos;
- cuántos agentes adicionales caben con el margen configurado;
- una conclusión literal: **sí entra**, **no entra** o **medición inconclusa**, con el
  recurso limitante.

RSS es una aproximación y puede contar memoria compartida más de una vez; identifícalo
como tal. No expongas comandos completos ni variables de entorno: pueden contener
tokens. Para ajustar cargas especialmente pesadas, usa `--agent-budget-gb`,
`--reserve-gb`, `--agent-cpu-cores` y `--cpu-reserve-cores`.

## Semáforo en la barra de menús (tiempo real, sin terminal)

Desde el 2026-09-06 el veredicto de esta skill está siempre a la vista en la barra de
menús: `🟢 N` (caben N agentes más) o `🔴 0`. Lo pinta **SwiftBar**
(`~/Applications/SwiftBar.app`, cask de Homebrew instalado sin sudo) ejecutando cada
30 s el plugin `scripts/agent-watch.30s.py`, que reutiliza `mac_agent_capacity.py`.
El desplegable muestra carga, CPU libre, RAM efectiva, una línea por cuadrante y los
tres procesos que más CPU consumen (para ver al instante si es Defender o Unity).
Tarjeta Kanban: sandbox #4618. Captura de referencia:
`~/.codeagentswarm/sandbox/artifacts/agent-watch/semaforo-en-barra-de-menus.png`.

### Criterio del veredicto (vive en `mac_agent_capacity.py`, el plugin solo pinta)

- **Memoria:** `memory_pressure` (reserva 8 GB por defecto) y `swapout_delta > 0`
  → memoria a 0 aunque haya CPU libre.
- **CPU:** % ociosa real de `top` menos una reserva (2 núcleos por defecto).
- **Veto de I/O, basado en evidencia:** la carga media a 1 min en macOS cuenta
  hilos en cola, incluido trabajo en segundo plano QoS (Defender, Spotlight); el
  2026-09-29 se midió load1≈80 con CPU ~50 % ociosa y **0** hilos en espera
  ininterrumpida: una cola larga sola NO prueba incapacidad. El veredicto solo es
  rojo por I/O cuando `load1 > núcleos` **y** hay ≥2 hilos en estado `U` (`ps -axM`).
  `U` es espera ininterrumpida del kernel — indicador de contención de I/O, no
  prueba exclusiva de disco. Con cola alta sin esperas U el JSON
  informa `load_pressure: "alta"` (aviso en el desplegable) y no veta. Si `ps -axM`
  no responde, la medición es inconclusa y tampoco veta a ciegas.
- **Aviso nativo** (`osascript display notification`) solo al cambiar de estado
  verde↔rojo, nunca cada 30 s. Último estado en `~/.cache/agent-watch/state`.
- Si el script base revienta, la barra muestra `⚪️ ?` y el desplegable trae el error.

### Fuente única y piezas instaladas

La fuente versionada vive en `vmram-skills/skills/agent-work/scripts/`.
`agent-watch/scripts` enlaza a ese directorio: CLI y SwiftBar usan el mismo medidor
físico, registro de jobs y cálculo de crecimiento pendiente. Los enlaces de cada
cliente resuelven esa única fuente. No copiar scripts entre Codex y Claude.

| Pieza | Ruta | Papel |
|---|---|---|
| Medidor común | `~/.agents/skills/agent-watch/scripts/mac_agent_capacity.py` | CPU/RAM reales y grupos exactos registrados |
| Plugin | `~/.swiftbar/agent-watch.30s.py` | Enlace del semáforo de SwiftBar al plugin común |
| Compatibilidad | `~/.claude/skills/agent-watch/scripts/` y `~/.codex/skills/agent-watch/scripts/` | Enlaces a los scripts comunes; las piezas auxiliares previas se conservan |
| Arranque al login | `~/Library/LaunchAgents/com.victormanuel.swiftbar.plist` | Configuración existente, conservada |
| Posición del icono | `defaults com.ameba.SwiftBar "NSStatusItem Preferred Position <ruta real del plugin>" = 100` | Conserva la ubicación fuera del notch |
| Estado | `~/.cache/agent-watch/state` | Último semáforo; aviso nativo solo al cambiar |

El desplegable añade jobs activos/en cola y crecimiento aún no realizado. RAM/CPU
ya observadas en sus procesos se contabilizan en la muestra física; solo se resta
la reserva de crecimiento pendiente para evitar contar lo mismo dos veces. El
semáforo expresa capacidad adicional medida, no garantiza 15 stacks simultáneos.
Una reserva antigua o un journal inválido se informa; nunca autoriza matar o limpiar.

### Cómo meter cambios

1. Edita la fuente versionada de `agent-work/scripts/` y ejecuta sus regresiones
   necesarias. Los enlaces existentes distribuyen el mismo cambio a los clientes.
2. Ejecuta `~/.agents/skills/agent-watch/scripts/agent-watch.30s.py`: la primera línea
   es el semáforo, `---` separa el menú y `|` introduce atributos de SwiftBar.
3. Refresca el plugin existente con `open "swiftbar://refreshplugin?name=agent-watch"`
   y verifica su item real. No abras otra instancia de SwiftBar.
4. Cambiar el intervalo exige renombrar el plugin y actualizar su enlace y la clave
   de posición con la ruta real nueva. Los umbrales permanecen en el medidor común
   y en el `argparse.Namespace` del plugin: 4 GB/agente, 8 GB de reserva, 1,5 núcleos
   por agente y 2 de reserva, ajustables con la CLI.
5. Conserva backup y hashes al migrar archivos instalados. No reemplaces un enlace
   o fichero que haya cambiado entre inspección y aplicación.

### Refrescar al instante con un atajo (Raycast)

- SwiftBar acepta `open "swiftbar://refreshplugin?name=agent-watch"` (nombre SIN
  intervalo ni extensión; con `agent-watch.30s.py` no hace nada; `refreshallplugins`
  también vale). El icono se actualiza en ~3 s.
- Script command de Raycast en `raycast/refrescar-semaforo.sh` (modo `silent`): dispara
  ese refresh y muestra en el HUD el veredicto (`🟢 1 SÍ entran 1 agentes`). Registro,
  que Raycast no deja automatizar: Raycast › Settings › Extensions › Script Commands ›
  Add Directory → `~/.claude/skills/agent-watch/raycast`; luego asignar hotkey al
  comando "Refrescar semáforo de agentes". Ejecuta el plugin una vez más por pulsación
  (0,65 s CPU), coste despreciable.

### Si no se ve el icono

- ¿SwiftBar vivo? `pgrep -x SwiftBar`; si no, `open -a ~/Applications/SwiftBar.app`.
- ¿Existe el item pero no se ve? `osascript -e 'tell application "System Events" to
  tell process "SwiftBar" to get {position, size} of menu bar item 1 of menu bar 1'`.
  Si la x está entre ~670 y ~840 pt está **bajo el notch** del MacBook 14" (los items
  nuevos entran por la izquierda, justo ahí). Arreglo sin arrastrar: la clave
  `NSStatusItem Preferred Position` de la tabla y reiniciar SwiftBar
  (`pkill -x SwiftBar; open -a ~/Applications/SwiftBar.app`). **Solo funciona con la
  ruta real del plugin; con la ruta del symlink no.** 100 = pegado al bloque del sistema.
- Abrir el desplegable por script (`click menu bar item`) no es fiable; la captura del
  desplegable se hace a mano.

### Seguridad corporativa (valorado el 2026-09-06)

- **Zscaler: indiferente.** Es un proxy de red; SwiftBar no abre sockets (verificado con
  `lsof`), tiene desactivadas las actualizaciones automáticas
  (`SUEnableAutomaticChecks=0`) y el plugin no toca red (solo `ps`, `top`, `sysctl`,
  `memory_pressure`, `osascript`).
- **EDR (Defender, BeyondTrust, DLP, Intune, Jamf):** riesgo bajo. Lo único que un
  analista vería es el LaunchAgent (persistencia benigna: `open -a` de una app
  notarizada, Developer ID de Ameba Labs, aceptada por Gatekeeper). Si se quiere cero
  huella: borrar el plist y activar "Launch at Login" en las preferencias de SwiftBar.
- El plugin lee el entorno de procesos con `ps eww` cada 30 s (ya lo hacía la skill bajo
  demanda) y solo extrae las tres claves `CODEAGENTSWARM_*`. Nada sale de la máquina.
- Coste medido: SwiftBar ~65 MB RSS; cada muestra ~0,65 s de CPU y 2 s de reloj.
