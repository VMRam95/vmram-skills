---
name: moltbot-vps
description: |
  Manage the OpenClaw gateway running on Hetzner VPS (<YOUR_VPS_IP>).
  Trigger phrases: "vps", "openclaw vps", "check vps", "vps status", "vps logs", "/moltbot-vps"
---

# OpenClaw VPS Management

This skill manages the OpenClaw gateway deployed on the Hetzner VPS via Docker.

**Note:** Rebranded from MoltBot to OpenClaw. Docker compose dir still uses old name `/opt/moltbot/`.

## Connection Details

| Property | Value |
|----------|-------|
| Host | `moltbot-vps` (<YOUR_VPS_IP>) |
| User | claude (NOT root - root login is disabled) |
| SSH Key | `~/.ssh/id_ed25519_personal` |
| Docker Dir | `/opt/moltbot` |
| CLI | `openclaw` (run via `node /app/openclaw.mjs`) |
| Config | `/home/node/.openclaw/` |
| Media | `/home/node/.openclaw/media/inbound/` |
| Comms | `/home/node/clawd/comms/` (inter-agent mailbox) |

## CRITICAL: SSH Key Loading Rules

**Each Bash tool call is a SEPARATE shell session** - the ssh-agent state does NOT persist between calls.

**YOU MUST chain the key loading with ALL ssh commands using `&&` in a SINGLE Bash call:**

```bash
# CORRECT - single Bash call with &&
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "command"

# WRONG - separate Bash calls (key won't persist)
ssh-add ~/.ssh/id_ed25519_personal  # Call 1
ssh moltbot-vps "command"            # Call 2 - WILL FAIL
```

**Why this matters:**
- Failed SSH attempts (3x) trigger fail2ban and block your IP
- If blocked, need VPS console to unban: `fail2ban-client set sshd unbanip <your-ip>`
- There is NO way to persist the key between Bash calls

## Arguments

```
/moltbot-vps [command] [options]
```

| Command | Description |
|---------|-------------|
| `status` | Check container and gateway status (default) |
| `logs` | View gateway logs (last 100 lines) |
| `logs -f` | Follow logs in real-time |
| `restart` | Restart the gateway container |
| `exec <cmd>` | Execute command inside container |
| `config` | Show current gateway config |
| `diagnose` | Full diagnostic when VPS seems down or unresponsive |
| `recover` | Attempt automatic recovery of crashed services |

## Examples

```bash
/moltbot-vps                    # Check status
/moltbot-vps status             # Check status
/moltbot-vps logs               # View last 100 log lines
/moltbot-vps logs -f            # Follow logs
/moltbot-vps restart            # Restart gateway
/moltbot-vps exec openclaw channels status --probe
/moltbot-vps config             # Show config
/moltbot-vps diagnose           # Full diagnostic when VPS seems down
/moltbot-vps recover            # Attempt automatic recovery
```

## Implementation

**IMPORTANT: All commands below MUST be run in a SINGLE Bash call with `&&` chaining.**

### 1. Status (default)

```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'NAMES|clawdbot' && docker exec moltbot-clawdbot-gateway-1 node /app/openclaw.mjs channels status --probe"
```

### 2. Logs

**Last 100 lines:**
```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker logs moltbot-clawdbot-gateway-1 --tail 100"
```

**Follow logs:**
```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh -t moltbot-vps "docker logs moltbot-clawdbot-gateway-1 --tail 50 -f"
```

### 3. Restart

```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "cd /opt/moltbot && docker compose down && docker compose up -d clawdbot-gateway && docker ps | grep clawdbot"
```

### 4. Exec

```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker exec moltbot-clawdbot-gateway-1 node /app/openclaw.mjs <command>"
```

### 5. Config

```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker exec moltbot-clawdbot-gateway-1 cat /home/node/.openclaw/openclaw.json" | jq .
```

### 6. Diagnose

Run this when the VPS seems down or Burricalvo is not responding. Execute steps sequentially and stop early if a clear diagnosis is found.

**Step 1: Ping check**
```bash
ping -c 3 -W 5 <YOUR_VPS_IP>
```
- If fails → Server is completely down. Check Hetzner dashboard for outages.

**Step 2: Port checks (run in parallel)**
```bash
nc -z -w 5 <YOUR_VPS_IP> 22 2>&1; echo "SSH: $?"
nc -z -w 5 <YOUR_VPS_IP> 443 2>&1; echo "HTTPS: $?"
nc -z -w 5 <YOUR_VPS_IP> 80 2>&1; echo "HTTP: $?"
```

**Step 3: HTTP health checks (run in parallel)**
```bash
curl -sL -o /dev/null -w "burricalvo: HTTP %{http_code} (%{time_total}s)\n" --connect-timeout 10 --max-time 15 https://burricalvo.moltbot.com/
curl -sL -o /dev/null -w "gateway: HTTP %{http_code} (%{time_total}s)\n" --connect-timeout 10 --max-time 15 https://gateway.moltbot.com/
curl -sL -o /dev/null -w "dashboard: HTTP %{http_code} (%{time_total}s)\n" --connect-timeout 10 --max-time 15 https://dashboard.moltbot.com/
```
- If all return OpenClaw landing page HTML → Backend services are down but Caddy is alive.

**Step 4: SSH attempt**
```bash
ssh-add ~/.ssh/id_ed25519_personal 2>/dev/null && ssh -o ConnectTimeout=15 -o ServerAliveInterval=5 moltbot-vps "echo SSH_OK"
```
- If "Connection timed out during banner exchange" → Server overloaded or sshd stuck. Go to **Recovery via VNC**.
- If "Permission denied" → fail2ban may have blocked IP. Try VNC to unban.
- If SSH_OK → Continue to Step 5.

**Step 5: System health (only if SSH works)**
```bash
ssh-add ~/.ssh/id_ed25519_personal 2>/dev/null && ssh moltbot-vps "
echo '=== MEMORY ===' && free -h &&
echo '=== SWAP ===' && swapon --show &&
echo '=== TOP PROCESSES ===' && ps aux --sort=-%mem | head -10 &&
echo '=== DOCKER ===' && docker ps -a --format 'table {{.Names}}\t{{.Status}}' | grep -E 'NAMES|clawdbot|openclaw' &&
echo '=== RECENT OOM KILLS ===' && dmesg | grep -i 'out of memory' | tail -5 &&
echo '=== GATEWAY LOGS ===' && docker logs moltbot-clawdbot-gateway-1 --tail 20 2>&1
"
```

**Step 6: Present diagnosis summary** with:
- Server status (up/down)
- SSH access (ok/timeout/blocked)
- Web services (ok/down/degraded)
- Memory status (ok/high/OOM detected)
- Gateway container (running/stopped/restarting)
- Recommended action

### 7. Recover

Attempt automatic recovery based on the diagnosis.

**If SSH works → restart gateway:**
```bash
ssh-add ~/.ssh/id_ed25519_personal 2>/dev/null && ssh moltbot-vps "cd /opt/moltbot && docker compose up -d clawdbot-gateway && sleep 5 && docker ps | grep clawdbot && docker logs moltbot-clawdbot-gateway-1 --tail 10 2>&1"
```

**If SSH does NOT work → instruct user for Hetzner VNC Console:**

Tell the user:
1. Go to **console.hetzner.cloud** → select the server → **Console (VNC)**
2. Login as `root` (password: check Hetzner "Reset Root Password" or use stored password)
3. Run these commands:
```bash
# Check what's consuming resources
top -bn1 | head -15

# Kill any runaway processes if needed
# (look for processes using >50% memory)

# Restart sshd so we can connect remotely
systemctl restart sshd
```
4. Once sshd is restarted, run `/moltbot-vps recover` again with SSH access.

**After recovery → verify services:**
```bash
ssh-add ~/.ssh/id_ed25519_personal 2>/dev/null && ssh moltbot-vps "
docker ps | grep clawdbot &&
echo '---' &&
curl -s -o /dev/null -w 'Gateway HTTP: %{http_code}\n' http://localhost:3001 &&
docker logs moltbot-clawdbot-gateway-1 --tail 5 2>&1 | grep -i 'listening\|ready\|initialized'
"
```

## Common Failure Patterns

| Symptom | Cause | Fix |
|---------|-------|-----|
| SSH timeout + ping OK | OOM killed sshd or server overloaded | Hetzner VNC → `systemctl restart sshd` |
| All domains show OpenClaw landing page | Backend containers down, Caddy fallback | `docker compose up -d clawdbot-gateway` |
| OOM kill in dmesg/console | Large audio transcription, memory spike | Docker auto-restarts; if not → manual restart |
| SSH "Permission denied" after attempts | fail2ban IP block | VNC → `fail2ban-client set sshd unbanip <IP>` |
| Gateway crash loop | Config error or dependency issue | Check logs → fix config → restart |
| WhatsApp "Connection Closed" in logs | Gateway restart needed after OOM | Usually self-recovers; if not → restart |
| Swap 100% used | Memory pressure, slow recovery | Wait or reboot: `reboot` from VNC |

## Systemd Service

The VPS has a systemd service for auto-start on boot:

```bash
# Check service status
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "systemctl status moltbot"

# Enable/disable auto-start
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "systemctl enable moltbot"
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "systemctl disable moltbot"
```

## Known Issues

- **WhatsApp Desktop audio**: Audio sent from WhatsApp Desktop/Mac app returns 0 bytes (Baileys library bug). Audio from mobile works fine.
- **Doctor warning**: State dir migration skipped message is expected (old `.clawdbot` → new `.openclaw`)

## Paths Reference

| Path | Description |
|------|-------------|
| `/opt/moltbot/` | Docker compose directory (legacy name) |
| `/opt/moltbot/.env` | Environment variables |
| `/home/node/.openclaw/` | Config directory (inside container) |
| `/home/node/.openclaw/openclaw.json` | Gateway config |
| `/home/node/.openclaw/credentials/` | Auth credentials |
| `/home/node/.openclaw/media/inbound/` | Received media files |
| `/home/node/clawd/comms/` | Inter-agent mailbox |
| `/home/node/clawd/comms/to-local.md` | Messages TO local agent |
| `/home/node/clawd/comms/from-local.md` | Messages FROM local agent |

## Container Details

- **Container name**: `moltbot-clawdbot-gateway-1`
- **User inside container**: `node` (UID 1000)
- **Container can SSH to host**: via `172.18.0.1` (Docker gateway)

## Inter-Agent Communication

To communicate with Claudio (the agent on the VPS):

**Read messages from VPS agent:**
```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker exec moltbot-clawdbot-gateway-1 cat /home/node/clawd/comms/from-local.md"
```

**Send message to VPS agent:**
```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker exec moltbot-clawdbot-gateway-1 bash -c 'echo \"Your message here\" >> /home/node/clawd/comms/to-local.md'"
```
