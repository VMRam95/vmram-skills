---
name: setup-dev-env
description: |
  Set up a dev environment for any project using PostgreSQL schema isolation and dedicated Docker containers.
  Creates schema=dev, dev containers, Caddy reverse proxy, and public URLs.
  Trigger phrases: "setup dev env", "dev environment", "entorno dev", "crear entorno dev", "/setup-dev-env"
---

# Setup Dev Environment

Creates a fully isolated dev environment for any project deployed on the VPS. Uses PostgreSQL schema separation (`public` for production, `dev` for development) and dedicated Docker containers with separate URLs.

## Architecture

```
Same PostgreSQL DB → 2 isolated schemas
                     ├── public (production)
                     └── dev (development)

Same VPS → 2 pairs of containers
           ├── backend      :PORT     → schema=public (prod)
           ├── frontend     :PORT+1
           ├── backend-dev  :PORT+2   → schema=dev
           └── frontend-dev :PORT+3
```

**Result:**
- Production: `https://PROJECT.<YOUR_DOMAIN>` + `https://api-PROJECT.<YOUR_DOMAIN>`
- Dev: `https://PROJECT-dev.<YOUR_DOMAIN>` + `https://api-PROJECT-dev.<YOUR_DOMAIN>`

## Arguments

```
/setup-dev-env [project-slug]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `project-slug` | No | Kebab-case project identifier. Prompted if not provided |

## Pre-requisites

- Project already deployed on VPS via `/vps-deploy`
- Project uses Prisma with PostgreSQL
- Docker containers running on `infrastructure_default` network
- Wildcard DNS `*.<YOUR_DOMAIN>` → <YOUR_VPS_IP> (already configured)

## Implementation

Follow these steps IN ORDER.

### Step 1: Gather project information

Use **AskUserQuestion** to collect (or auto-detect from codebase):

| Field | Example | Description |
|-------|---------|-------------|
| Project slug | `shopify-commission-engine` | Kebab-case project ID |
| VPS directory | `/opt/shopify-commission` | Where the project lives on VPS |
| Backend port (prod) | 4000 | Current production backend port |
| Frontend port (prod) | 4001 | Current production frontend port |
| Backend port (dev) | 4002 | Dev backend port (usually prod+2) |
| Frontend port (dev) | 4003 | Dev frontend port (usually prod+3) |
| Database name | `shopify_commission_engine` | PostgreSQL database name |

**Auto-detect from VPS:**
```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker ps --format '{{.Names}} {{.Ports}}' | grep PROJECT"
```

### Step 2: Create dev schema in PostgreSQL

```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker exec postgres psql -U postgres -d DATABASE_NAME -c 'CREATE SCHEMA IF NOT EXISTS dev;'"
```

### Step 3: Run Prisma migrations on dev schema

**CRITICAL: Run inside the backend container** (has correct Prisma version):

```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker exec BACKEND_CONTAINER sh -c '
  export DATABASE_URL=\$(echo \"\$DATABASE_URL\" | sed -E \"s/schema=[^&]*/schema=dev/\")
  npx prisma migrate deploy
'"
```

> **Never use `npx` from the VPS host** — it will download the latest Prisma version which may be incompatible with the project's `schema.prisma`.

**Verify tables were created:**
```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker exec postgres psql -U postgres -d DATABASE_NAME -c \"SELECT tablename FROM pg_tables WHERE schemaname = 'dev' ORDER BY tablename;\""
```

### Step 4: Add schema parsing to backend code

In the project's config file (e.g., `backend/src/config/env.js` or `backend/src/config.ts`):

```javascript
// Parse schema from DATABASE_URL
dbSchema: (() => {
  const url = process.env.DATABASE_URL || '';
  const match = url.match(/[?&]schema=([^&]+)/);
  return match ? match[1] : 'public';
})(),
```

**Safety check (add after config validation):**
```javascript
if (config.nodeEnv !== 'production' && config.dbSchema === 'public') {
  console.warn('WARNING: Non-production environment using PUBLIC schema!');
  console.warn('   This could affect production data. Use ?schema=dev in DATABASE_URL');
}
console.log(`Database schema: ${config.dbSchema}`);
```

**Startup banner (add to server startup):**
```javascript
logger.info(`DB Schema: ${config.dbSchema}`);
```

### Step 5: Create `.env.dev` on VPS

Copy the production `.env` and modify these values:

```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "cp /opt/PROJECT_DIR/.env /opt/PROJECT_DIR/.env.dev"
```

Then edit `.env.dev` to change:

| Variable | Production value | Dev value |
|----------|-----------------|-----------|
| `DATABASE_URL` | `?schema=public&...` | `?schema=dev&...` |
| `PAYMENT_MODE` | `LIVE` or `TEST` | `MOCK` |
| `CORS_ORIGIN` | `https://PROJECT.<YOUR_DOMAIN>` | `https://PROJECT-dev.<YOUR_DOMAIN>` |
| `API_URL` | `https://api-PROJECT.<YOUR_DOMAIN>` | `https://api-PROJECT-dev.<YOUR_DOMAIN>` |
| `FRONTEND_URL` | `https://PROJECT.<YOUR_DOMAIN>` | `https://PROJECT-dev.<YOUR_DOMAIN>` |
| `LOG_LEVEL` | `info` | `debug` |
| `ENABLE_CLIENT_NOTIFICATIONS` | `true` | `false` |
| `ENABLE_ADMIN_NOTIFICATIONS` | `true` | `false` |

**Keep the same values for:** Stripe/Shopify test keys, GoTrue secrets, JWT secrets, email service keys.

**Sed command to automate the key changes:**
```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "cd /opt/PROJECT_DIR && sed -i \
  -e 's/schema=public/schema=dev/' \
  -e 's/PAYMENT_MODE=.*$/PAYMENT_MODE=\"MOCK\"/' \
  -e 's|CORS_ORIGIN=.*$|CORS_ORIGIN=\"https://PROJECT-dev.<YOUR_DOMAIN>\"|' \
  -e 's|API_URL=.*$|API_URL=\"https://api-PROJECT-dev.<YOUR_DOMAIN>\"|' \
  -e 's|FRONTEND_URL=.*$|FRONTEND_URL=\"https://PROJECT-dev.<YOUR_DOMAIN>\"|' \
  -e 's/LOG_LEVEL=.*$/LOG_LEVEL=\"debug\"/' \
  -e 's/ENABLE_CLIENT_NOTIFICATIONS=.*$/ENABLE_CLIENT_NOTIFICATIONS=false/' \
  -e 's/ENABLE_ADMIN_NOTIFICATIONS=.*$/ENABLE_ADMIN_NOTIFICATIONS=false/' \
  .env.dev"
```

### Step 6: Add dev services to docker-compose.yml

Add these services to the project's `docker-compose.yml` on the VPS:

```yaml
  # ============================================
  # Backend DEV (schema=dev)
  # ============================================
  backend-dev:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: PROJECT-backend-dev
    restart: unless-stopped
    ports:
      - "127.0.0.1:BACK_DEV_PORT:INTERNAL_PORT"
    env_file: .env.dev
    environment:
      NODE_ENV: production
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.25'
        reservations:
          memory: 128M
    healthcheck:
      test: ["CMD", "node", "-e", "require('http').get('http://localhost:INTERNAL_PORT/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 60s
    volumes:
      - avatar-uploads-dev:/app/uploads    # If project uses uploads
    networks:
      - infrastructure_default
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # ============================================
  # Frontend DEV
  # ============================================
  frontend-dev:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        NEXT_PUBLIC_API_URL: https://api-PROJECT-dev.<YOUR_DOMAIN>
        NEXT_PUBLIC_GOTRUE_URL: https://gotrue.<YOUR_DOMAIN>
        NEXT_PUBLIC_APP_NAME: "Project Name [DEV]"
        NEXT_PUBLIC_APP_DESCRIPTION: "DEV - Project description"
    container_name: PROJECT-frontend-dev
    restart: unless-stopped
    ports:
      - "127.0.0.1:FRONT_DEV_PORT:INTERNAL_PORT"
    environment:
      NODE_ENV: production
      PORT: INTERNAL_PORT
    deploy:
      resources:
        limits:
          memory: 128M
          cpus: '0.15'
        reservations:
          memory: 64M
    healthcheck:
      test: ["CMD", "node", "-e", "require('http').get('http://localhost:INTERNAL_PORT/login', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 40s
    networks:
      - infrastructure_default
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    depends_on:
      backend-dev:
        condition: service_healthy
```

> **Don't forget:** Add `avatar-uploads-dev:` (or similar) to the `volumes:` section if the project uses file uploads.

**For Vite frontends** (not Next.js), replace `NEXT_PUBLIC_*` with `VITE_*` build args.

### Step 7: Configure Caddy reverse proxy

Append to `/etc/caddy/Caddyfile`:

```caddy
# PROJECT - DEV Frontend
PROJECT-dev.<YOUR_DOMAIN> {
    reverse_proxy localhost:FRONT_DEV_PORT {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
    }
    log {
        output file /var/log/caddy/PROJECT-frontend-dev.log {
            roll_size 10mb
            roll_keep 5
            roll_keep_for 720h
        }
        format json
        level INFO
    }
}

# PROJECT - DEV Backend API
api-PROJECT-dev.<YOUR_DOMAIN> {
    reverse_proxy localhost:BACK_DEV_PORT {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
    }
    log {
        output file /var/log/caddy/PROJECT-backend-dev.log {
            roll_size 10mb
            roll_keep 5
            roll_keep_for 720h
        }
        format json
        level INFO
    }
}
```

**Validate and reload:**
```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy"
```

### Step 8: DNS (usually nothing to do)

The wildcard `*.<YOUR_DOMAIN>` already resolves to the VPS. Verify:

```bash
dig +short PROJECT-dev.<YOUR_DOMAIN> A
dig +short api-PROJECT-dev.<YOUR_DOMAIN> A
```

Both should return `<YOUR_VPS_IP>`.

**IMPORTANT:** Use single-level subdomains only. Wildcards don't cover nested subdomains:
- `PROJECT-dev.<YOUR_DOMAIN>` — works with wildcard
- `dev.PROJECT.<YOUR_DOMAIN>` — does NOT work with wildcard

### Step 9: Build and deploy

```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "cd /opt/PROJECT_DIR && docker compose up -d --build backend-dev frontend-dev"
```

### Step 10: Update .env.example in the repo

Update the project's `.env.example` to default to `?schema=dev`:

```env
# Development uses 'dev' schema (default for local):
DATABASE_URL="postgresql://user:pass@localhost:5432/mydb?schema=dev"
# Production uses 'public' schema:
# DATABASE_URL="postgresql://user:pass@host:5432/mydb?schema=public"
```

### Step 11: Add setup script to the repo (optional)

Create `backend/scripts/setup-dev-env.sh`:

```bash
#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

[ -f "$BACKEND_DIR/.env" ] && { set -a; source "$BACKEND_DIR/.env"; set +a; }
[ -z "${DATABASE_URL:-}" ] && echo "ERROR: DATABASE_URL not set" && exit 1

# psql doesn't understand ?schema= — strip all query params
PSQL_URL=$(echo "$DATABASE_URL" | sed -E 's/\?.*$//')
psql "$PSQL_URL" -c "CREATE SCHEMA IF NOT EXISTS dev;"

# Replace schema value for Prisma (preserves other params like connection_limit)
if echo "$DATABASE_URL" | grep -q 'schema='; then
  export DATABASE_URL=$(echo "$DATABASE_URL" | sed -E 's/schema=[^&]*/schema=dev/')
else
  if echo "$DATABASE_URL" | grep -q '?'; then
    export DATABASE_URL="${DATABASE_URL}&schema=dev"
  else
    export DATABASE_URL="${DATABASE_URL}?schema=dev"
  fi
fi

cd "$BACKEND_DIR"
npx prisma migrate deploy
npx prisma generate
echo "Dev environment ready!"
```

Add to `package.json`:
```json
"db:setup-dev": "bash scripts/setup-dev-env.sh"
```

### Step 12: Update docker-compose.local.yml in the repo

Add equivalent dev services for local development using ports +2/+3 from production:

```yaml
  backend-dev:
    # Same as VPS version but with:
    ports:
      - "BACK_DEV_PORT:INTERNAL_PORT"    # No 127.0.0.1 binding for local
    environment:
      PAYMENT_MODE: MOCK
      CORS_ORIGIN: "http://localhost:FRONT_DEV_PORT"
      API_URL: "http://localhost:BACK_DEV_PORT"
      FRONTEND_URL: "http://localhost:FRONT_DEV_PORT"
      LOG_LEVEL: debug

  frontend-dev:
    build:
      args:
        NEXT_PUBLIC_API_URL: "http://localhost:BACK_DEV_PORT"
        NEXT_PUBLIC_APP_NAME: "Project Name [DEV]"
    ports:
      - "FRONT_DEV_PORT:INTERNAL_PORT"
    depends_on:
      backend-dev:
        condition: service_healthy
```

## Verification

Run all these checks after deployment:

```bash
# 1. Containers running and healthy
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'PROJECT'"

# 2. Dev backend uses schema=dev
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker logs PROJECT-backend-dev 2>&1 | grep -i schema"
# Expected: "Database schema: dev"

# 3. Prod backend still uses schema=public
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker logs PROJECT-backend 2>&1 | grep -i schema"
# Expected: "Database schema: public"

# 4. Dev API health
curl -s https://api-PROJECT-dev.<YOUR_DOMAIN>/health
# Expected: paymentMode: "MOCK"

# 5. Dev frontend accessible
curl -s -o /dev/null -w '%{http_code}' https://PROJECT-dev.<YOUR_DOMAIN>/login
# Expected: 200

# 6. Production NOT affected
curl -s https://api-PROJECT.<YOUR_DOMAIN>/health
# Expected: same as before, paymentMode: "LIVE" or "TEST"

# 7. Data isolation — dev data doesn't appear in prod
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker exec postgres psql -U postgres -d DATABASE_NAME -c \"SELECT count(*) FROM dev.\\\"Client\\\";\"  "
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker exec postgres psql -U postgres -d DATABASE_NAME -c \"SELECT count(*) FROM public.\\\"Client\\\";\""
```

## Assigned Ports Reference

| Project | Prod Back | Prod Front | Dev Back | Dev Front |
|---------|-----------|------------|----------|-----------|
| shopify-commission | 4000 | 4001 | 4002 | 4003 |
| vetcraft | — | 3000/7000 | — | — |
| vps-dashboard | 3002 | — | — | — |
| (next project) | X | X+1 | X+2 | X+3 |

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `relation "X" does not exist` | Dev schema has no tables | Run migrations inside backend container (Step 3) |
| `npx` downloads Prisma 7.x | Running from VPS host instead of container | Always use `docker exec CONTAINER` for Prisma commands |
| Phantom database `mydb&connection_limit=5` | `sed` mangled the DATABASE_URL query params | Use `sed -E 's/schema=[^&]*/schema=dev/'` — only replace the schema value, don't touch `?` or other params |
| Wildcard DNS doesn't resolve `dev.project.X` | Wildcards only cover 1 subdomain level | Use `project-dev.X` instead of `dev.project.X` |
| Frontend shows wrong API URL | Build args not updated for dev frontend | Rebuild with correct `NEXT_PUBLIC_API_URL` or `VITE_API_URL` |
| Dev container uses public schema | `.env.dev` not created or `env_file` not set in docker-compose | Verify `.env.dev` has `?schema=dev` and service uses `env_file: .env.dev` |

## Reference Implementation

**shopify-commission-engine** is the reference project:
- VPS dir: `/opt/shopify-commission/`
- Ports: 4000/4001 (prod), 4002/4003 (dev)
- URLs: `shopify.<YOUR_DOMAIN>` (prod), `shopify-dev.<YOUR_DOMAIN>` (dev)
- `.env.dev` at `/opt/shopify-commission/.env.dev`
- Local: `docker-compose.local.yml` with dev services

## Notes

- Dev containers use ~half the resources of prod (256MB/128MB vs 512MB/256MB)
- `PAYMENT_MODE=MOCK` in dev prevents real Stripe charges
- Notifications disabled in dev to avoid sending test emails
- `LOG_LEVEL=debug` in dev for more verbose logging
- Same GoTrue instance for both environments — auth works the same way
- The `[DEV]` suffix in `APP_NAME` makes it visually obvious which environment you're in
