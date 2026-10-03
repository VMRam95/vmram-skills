// Keep browser launchers inside their already registered phase group.
import childProcess from 'node:child_process'
import { syncBuiltinESMExports } from 'node:module'

if (process.env.AGENT_WORK_JOB && process.env.AGENT_WORK_GENERATION) {
  const spawn = childProcess.spawn
  childProcess.spawn = function (command, args, options) {
    if (!Array.isArray(args)) {
      options = args
      args = []
    }
    return spawn(command, args, { ...options, detached: false })
  }
  syncBuiltinESMExports()
}
