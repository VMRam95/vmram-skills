---
name: vps-deploy
description: |
  Deploy projects to the Hetzner VPS (<YOUR_VPS_IP>). Standard procedure for Docker containers, Caddy reverse proxy, DNS, and HTTPS setup.
  Trigger phrases: "deploy vps", "deploy to vps", "migrate to vps", "desplegar en vps", "/vps-deploy"
---

# VPS Deploy - Project Deployment Guide

Standard procedure for deploying any project to the Hetzner VPS with Docker, Caddy reverse proxy, automatic HTTPS, and DNS configuration.

## VPS Details

| Property | Value |
|----------|-------|
| IP | <YOUR_VPS_IP> |
| SSH Host | `moltbot-vps` (configured in ~/.ssh/config) |
| SSH User | `claude` |
| SSH Key | `~/.ssh/id_ed25519_personal` |
| OS | Ubuntu 24.04 LTS |
| RAM | 4 GB (CX22) |
| Reverse Proxy | Caddy (systemd service) |
| DNS Provider | Porkbun (API keys configured on VPS) |
| Caddyfile | `/etc/caddy/Caddyfile` |
| Infrastructure Dir | `/opt/infrastructure/` |

## CRITICAL: SSH Rules

**Each Bash call is a SEPARATE shell session.** Always chain ssh-add with ssh:

```bash
# CORRECT
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "command"

# WRONG - key won't persist
ssh-add ~/.ssh/id_ed25519_personal  # Call 1
ssh moltbot-vps "command"            # Call 2 - FAILS
```

Failed SSH attempts (3x) trigger **fail2ban** IP ban.

## Arguments

```
/vps-deploy [command]
```

| Command | Description |
|---------|-------------|
| `guide` | Show full deployment guide (default) |
| `status` | Show VPS resource usage and running containers |
| `caddy` | Show current Caddyfile |
| `resources` | Show available RAM/CPU/disk |

## Deployment Steps

### Step 1: Prepare the Project

The project needs:
- A `Dockerfile` (or `docker-compose.yml`)
- Exposed port(s) mapped to `127.0.0.1` (localhost only, Caddy handles public access)

**Example docker-compose.yml:**
```yaml
services:
  my-app:
    build: .
    container_name: my-app
    restart: unless-stopped
    ports:
      - "127.0.0.1:PORT:PORT"
    environment:
      - NODE_ENV=production
    deploy:
      resources:
        limits:
          memory: 64M
```

### Step 2: Upload to VPS

```bash
# Create tarball (exclude unnecessary files)
cd /path/to/project
tar czf /tmp/my-app.tar.gz --exclude='node_modules' --exclude='dist' --exclude='.git' .

# Upload
ssh-add ~/.ssh/id_ed25519_personal && scp /tmp/my-app.tar.gz moltbot-vps:/tmp/my-app.tar.gz

# Extract on VPS
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "sudo mkdir -p /opt/infrastructure/my-app && cd /opt/infrastructure/my-app && sudo tar xzf /tmp/my-app.tar.gz"
```

### Step 3: Build and Start Containers

```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "cd /opt/infrastructure/my-app && sudo docker compose build --no-cache 2>&1 | tail -10"

ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "cd /opt/infrastructure/my-app && sudo docker compose up -d 2>&1"
```

### Step 4: Configure Caddy (Reverse Proxy + HTTPS)

Edit the Caddyfile on the VPS to add entries for the new domain.

**Standard domain (automatic HTTPS via HTTP challenge):**
```caddy
mydomain.com {
    reverse_proxy localhost:PORT
}
```

**WWW redirect:**
```caddy
www.mydomain.com {
    redir https://mydomain.com{uri} permanent
}
```

**Subdomain:**
```caddy
app.mydomain.com {
    reverse_proxy localhost:PORT
}
```

**Wildcard subdomains (requires DNS challenge - Porkbun):**
```caddy
*.mydomain.com {
    tls {
        dns porkbun {
            api_key {env.PORKBUN_API_KEY}
            api_secret_key {env.PORKBUN_API_SECRET}
        }
    }
    reverse_proxy localhost:PORT
}
```

**With Authelia forward-auth (protected routes):**
```caddy
mydomain.com {
    forward_auth localhost:9091 {
        uri /api/authz/forward-auth
        copy_headers Remote-User Remote-Groups Remote-Name Remote-Email
    }
    reverse_proxy localhost:PORT
}
```

**Apply changes:**
```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "sudo systemctl reload caddy"
```

### Step 5: Configure DNS (Porkbun)

Point the domain to the VPS IP:

| Type | Name | Value |
|------|------|-------|
| A | `@` (root) | <YOUR_VPS_IP> |
| A | `www` | <YOUR_VPS_IP> |
| A | `app` (subdomain) | <YOUR_VPS_IP> |
| A | `*` (wildcard) | <YOUR_VPS_IP> |

Caddy handles HTTPS certificates automatically once DNS propagates.

### Step 6: Verify

```bash
# Check container is running
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep my-app"

# Check health from VPS
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "curl -s http://localhost:PORT/health"

# Check public HTTPS
curl -s https://mydomain.com
```

## Existing Infrastructure

### Running Services (as of Feb 2026)

| Service | Port | Domain | RAM |
|---------|------|--------|-----|
| Authelia | 9091 | auth.<YOUR_DOMAIN> | ~38 MB |
| OpenClaw Gateway | 3001 | - (internal) | ~700 MB |
| VPS Dashboard | 3002 | dashboard.<YOUR_DOMAIN> | ~21 MB |
| VetCraft Landing | 3000 | <YOUR_DOMAIN> | ~33 MB |
| VetCraft Web | 7000 | admin.<YOUR_DOMAIN>, *.<YOUR_DOMAIN> | ~51 MB |
| Shopify Commission Backend | 4000 | api-shopify.<YOUR_DOMAIN> | ~49 MB |
| Shopify Commission Frontend | 4001 | shopify.<YOUR_DOMAIN> | ~33 MB |
| Shopify Commission Backend DEV | 4002 | api-shopify-dev.<YOUR_DOMAIN> | ~49 MB |
| Shopify Commission Frontend DEV | 4003 | shopify-dev.<YOUR_DOMAIN> | ~33 MB |
| PostgreSQL 17 | 5432 | - (internal) | ~50 MB |
| PgBouncer | 6432 | - (internal) | ~5 MB |
| GoTrue | 9999 | gotrue.<YOUR_DOMAIN> | ~15 MB |

> **Dev environments:** Use `/setup-dev-env` skill to create isolated dev environments with schema separation and dedicated containers/URLs.

### Docker Networks

| Network | Services |
|---------|----------|
| `infrastructure_default` | PostgreSQL, PgBouncer, GoTrue, VPS Dashboard, Authelia |
| `moltbot_default` | OpenClaw Gateway |
| `vetcraft_default` | VetCraft Landing, VetCraft Web |

**Cross-network communication:** Use Docker bridge gateway IP `172.17.0.1` + host-mapped port.

### Directory Structure

```
/opt/infrastructure/          # Main infrastructure dir
  ├── docker-compose.yml      # PostgreSQL + PgBouncer + GoTrue + Authelia
  ├── .env                    # Shared env vars (POSTGRES_PASSWORD, etc.)
  ├── vps-dashboard/          # Dashboard app
  ├── backups/                # PostgreSQL backups
  └── authelia/               # Authelia config
/opt/moltbot/                 # OpenClaw gateway
/opt/vetcraft/                # VetCraft app (<YOUR_DOMAIN>)
```

## Real Migration Example: <YOUR_DOMAIN>

### What was deployed:

1. **2 Docker containers** via docker-compose:
   - `vetcraft-landing-1` (port 3000) - Landing page
   - `vetcraft-web-1` (port 7000) - Admin + tenant subdomains

2. **Caddy entries:**
   - `<YOUR_DOMAIN>` → localhost:3000
   - `www.<YOUR_DOMAIN>` → redirect to <YOUR_DOMAIN>
   - `admin.<YOUR_DOMAIN>` → localhost:7000
   - `*.<YOUR_DOMAIN>` → localhost:7000 (wildcard with Porkbun DNS challenge)

3. **DNS (Porkbun):**
   - A record: <YOUR_DOMAIN> → <YOUR_VPS_IP>
   - A record: *.<YOUR_DOMAIN> → <YOUR_VPS_IP>

4. **Resources:** ~84 MB RAM additional

## Updating a Deployed Project

```bash
# Build tarball locally
cd /path/to/project
tar czf /tmp/my-app.tar.gz --exclude='node_modules' --exclude='dist' --exclude='.git' .

# Upload + extract + rebuild + restart (single pipeline)
ssh-add ~/.ssh/id_ed25519_personal && \
  scp /tmp/my-app.tar.gz moltbot-vps:/tmp/my-app.tar.gz && \
  ssh moltbot-vps "cd /opt/infrastructure/my-app && sudo tar xzf /tmp/my-app.tar.gz && sudo docker compose build --no-cache 2>&1 | tail -5 && sudo docker compose up -d 2>&1"
```

## Environment Variables

If the project needs shared env vars (like POSTGRES_PASSWORD):

```bash
# Symlink from main infrastructure .env
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "cd /opt/infrastructure/my-app && sudo ln -sf /opt/infrastructure/.env .env"
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Container can't reach PostgreSQL | Use `infrastructure_default` network or bridge IP `172.17.0.1:5432` |
| HTTPS not working | Wait for DNS propagation, check `sudo caddy validate --config /etc/caddy/Caddyfile` |
| Port conflict | Check `docker ps` for used ports, pick an unused one |
| Build fails on VPS | Check `docker compose build` output, often missing files in tarball |
| Caddy reload fails | Validate config first: `sudo caddy validate --config /etc/caddy/Caddyfile` |
| fail2ban blocked IP | VPS console: `sudo fail2ban-client set sshd unbanip YOUR_IP` |

## Implementation (for /vps-deploy commands)

### Status

```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "echo '=== Containers ===' && docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' && echo && echo '=== Resources ===' && free -h | head -2 && echo && df -h / | tail -1"
```

### Caddy

```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "cat /etc/caddy/Caddyfile"
```

### Resources

```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "echo '=== Memory ===' && free -h && echo && echo '=== Disk ===' && df -h / && echo && echo '=== CPU ===' && nproc && echo 'cores'"
```
