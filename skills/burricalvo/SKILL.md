---
name: burricalvo
description: |
  Communicate with Burricalvo, the AI agent running on the VPS.
  Trigger phrases: "burricalvo", "mensaje vps", "hablar con burricalvo", "/burricalvo"
---

# Burricalvo - Inter-Agent Communication

Communicate with Burricalvo, the AI agent running on the Hetzner VPS inside the OpenClaw container.

## Arguments

```
/burricalvo [command] [message]
```

| Command | Description |
|---------|-------------|
| `read` | Read unread messages from Burricalvo (default) |
| `send <message>` | Send a message to Burricalvo |
| `check` | Quick check for unread messages |

## Examples

```bash
/burricalvo                     # Read unread messages (default)
/burricalvo read                # Read messages from Burricalvo
/burricalvo send Hola!          # Send a message
/burricalvo check               # Quick unread check
```

## Communication Protocol

**Transport: SSH file-based mailbox**

Communication uses SSH to read/write markdown files inside the OpenClaw container on the VPS.

| File | Direction | Description |
|------|-----------|-------------|
| `/home/node/clawd/comms/to-local.md` | Burricalvo → Claudio Local | Messages FROM Burricalvo |
| `/home/node/clawd/comms/from-local.md` | Claudio Local → Burricalvo | Messages TO Burricalvo |

**SSH Host:** `moltbot-vps`
**SSH Key:** `~/.ssh/id_ed25519_personal`
**Container:** `moltbot-clawdbot-gateway-1`

## Implementation

### 1. Read (default)

Read messages from Burricalvo:
```bash
ssh-add ~/.ssh/id_ed25519_personal 2>/dev/null
ssh moltbot-vps "docker exec moltbot-clawdbot-gateway-1 cat /home/node/clawd/comms/to-local.md 2>/dev/null"
```

After reading, clear the mailbox:
```bash
ssh moltbot-vps "docker exec moltbot-clawdbot-gateway-1 bash -c '> /home/node/clawd/comms/to-local.md'"
```

### 2. Send

Send a message to Burricalvo. **Always use the Write tool** to create `/tmp/burricalvo-msg.md` first to avoid escaping issues:

```markdown
---
# Mensaje de Claudio Local
**De:** Claudio Local (Mac)
**Fecha:** 2026-02-25 10:00 UTC
---

Contenido del mensaje aqui.

— Claudio Local
```

Then send via SSH:
```bash
ssh-add ~/.ssh/id_ed25519_personal 2>/dev/null
cat /tmp/burricalvo-msg.md | ssh moltbot-vps "docker exec -i moltbot-clawdbot-gateway-1 bash -c 'cat >> /home/node/clawd/comms/from-local.md'"
```

**IMPORTANT:** Always use the Write tool to create `/tmp/burricalvo-msg.md` instead of heredoc in bash, to avoid escaping problems.

### 3. Check (quick read)

Same as read but don't clear the mailbox. Just check if there's content:
```bash
ssh moltbot-vps "docker exec moltbot-clawdbot-gateway-1 wc -l /home/node/clawd/comms/to-local.md 2>/dev/null"
```

## Notes

- SSH key must be added to agent before each operation (`ssh-add`)
- Messages are markdown files, appended to (not overwritten)
- Clear mailbox after reading to avoid re-reading old messages
- Burricalvo may take longer to respond since there's no instant webhook
- The local bridge (localhost:8877) and SSH tunnel have been DISABLED due to corporate security policy - do NOT attempt to restart them
