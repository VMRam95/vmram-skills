---
name: vercel
description: |
  Deploy and manage applications on Vercel platform.
  Trigger phrases: "deploy vercel", "vercel", "deploy to vercel", "/vercel"
---

# Vercel

This skill helps deploy and manage applications on the Vercel platform.

## Arguments

```
/vercel <command> [options]
```

| Command | Description |
|---------|-------------|
| deploy | Deploy current project |
| list | List deployments |
| env | Manage environment variables |
| logs | View deployment logs |
| domains | Manage custom domains |
| status | Check deployment status |

## Examples

```bash
/vercel deploy                    # Deploy to preview
/vercel deploy --prod             # Deploy to production
/vercel env pull                  # Pull env vars locally
/vercel logs https://my-app.vercel.app
```

## Commands

### Deploy

```bash
# Preview deployment
vercel

# Production deployment
vercel --prod

# Deploy specific directory
vercel ./dist

# Deploy with build command override
vercel --build-command "npm run build:prod"
```

### Environment Variables

```bash
# List all env vars
vercel env ls

# Add env var (interactive)
vercel env add

# Add env var (non-interactive)
echo "value" | vercel env add VARIABLE_NAME production

# Pull env vars to .env.local
vercel env pull

# Remove env var
vercel env rm VARIABLE_NAME production
```

### Domains

```bash
# List domains
vercel domains ls

# Add domain
vercel domains add mydomain.com

# Remove domain
vercel domains rm mydomain.com
```

### Logs

```bash
# View recent logs
vercel logs

# View logs for specific deployment
vercel logs https://my-deployment-url.vercel.app

# Follow logs in real-time
vercel logs --follow
```

### Project Management

```bash
# Link to existing project
vercel link

# Unlink project
vercel unlink

# List projects
vercel projects ls

# Remove project
vercel projects rm my-project
```

## Framework-Specific Configuration

### Next.js

```json
// vercel.json (usually not needed)
{
  "framework": "nextjs"
}
```

### Vite/React

```json
// vercel.json
{
  "framework": "vite",
  "buildCommand": "vite build",
  "outputDirectory": "dist"
}
```

### Static Site

```json
// vercel.json
{
  "buildCommand": "npm run build",
  "outputDirectory": "public"
}
```

## Environment Configuration

### Environment Types

| Type | Description |
|------|-------------|
| Production | Live site (main branch) |
| Preview | PR/branch deployments |
| Development | Local development |

### Example Setup

```bash
# Production only
vercel env add DATABASE_URL production

# All environments
vercel env add API_KEY production preview development
```

## Deployment Workflow

### 1. Initial Setup

```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Link project
vercel link
```

### 2. Deploy Preview

```bash
# Creates unique preview URL
vercel
```

### 3. Promote to Production

```bash
# Deploy directly to production
vercel --prod

# Or promote existing preview
vercel promote <deployment-url>
```

## Vercel.json Reference

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "nextjs",
  "regions": ["iad1"],
  "headers": [
    {
      "source": "/api/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "no-store" }
      ]
    }
  ],
  "redirects": [
    { "source": "/old", "destination": "/new", "permanent": true }
  ],
  "rewrites": [
    { "source": "/api/:path*", "destination": "https://api.example.com/:path*" }
  ]
}
```

## Troubleshooting

### Build Failures

```bash
# Check build logs
vercel logs --follow

# Run build locally
vercel build

# Check Node.js version
# Add to package.json:
{
  "engines": { "node": "18.x" }
}
```

### Environment Issues

```bash
# Verify env vars are set
vercel env ls

# Check var is accessible in build
# Add to next.config.js:
console.log('ENV:', process.env.MY_VAR)
```

### Domain Issues

```bash
# Check DNS propagation
dig mydomain.com

# Verify domain ownership
vercel domains inspect mydomain.com
```

## Custom Domain Setup Checklist

When adding a custom domain to a Vercel project, follow this complete checklist.
This prevents the recurring issue of SSL warnings and stale env vars.

### Step 1: Add domains to Vercel

```bash
# Add root domain
vercel domains add mydomain.com

# Add www subdomain
vercel domains add www.mydomain.com
```

### Step 2: Tell user to configure DNS (their responsibility)

Provide the DNS records they need to add at their registrar:

| Type | Host | Value |
|------|------|-------|
| **A** | `@` (root) | `76.76.21.21` |
| **CNAME** | `www` | `cname.vercel-dns.com` |

### Step 3: Wait for SSL certificates

Vercel auto-issues Let's Encrypt certs. Verify both exist:

```bash
# Check certs were issued
vercel certs ls

# Verify cert covers the right domain
echo | openssl s_client -servername mydomain.com -connect mydomain.com:443 2>/dev/null | openssl x509 -noout -subject -ext subjectAltName
echo | openssl s_client -servername www.mydomain.com -connect www.mydomain.com:443 2>/dev/null | openssl x509 -noout -subject -ext subjectAltName
```

### Step 4: Update NEXT_PUBLIC_APP_URL (CRITICAL - commonly forgotten!)

This is the #1 issue that gets missed. The env var still points to the old `.vercel.app` domain.

```bash
# Check current value
vercel env pull /tmp/.env.check --environment production && grep APP_URL /tmp/.env.check

# Remove old value
vercel env rm NEXT_PUBLIC_APP_URL production -y

# Set new value (use printf to avoid trailing newline)
printf '%s' 'https://mydomain.com' | vercel env add NEXT_PUBLIC_APP_URL production
```

**Why this matters:** `NEXT_PUBLIC_APP_URL` is used for:
- SEO meta tags (og:url, canonical)
- metadataBase in Next.js layout
- Email links (unsubscribe URLs, etc.)

### Step 5: Check other env vars that reference the old domain

```bash
vercel env pull /tmp/.env.prod --environment production
grep -i "vercel.app" /tmp/.env.prod
```

Update any that still reference the `.vercel.app` URL.

### Step 6: Add www → root redirect in vercel.json

Prevents duplicate content and ensures a canonical domain:

```json
{
  "redirects": [
    {
      "source": "/:path*",
      "has": [{ "type": "host", "value": "www.mydomain.com" }],
      "destination": "https://mydomain.com/:path*",
      "permanent": true
    }
  ]
}
```

If vercel.json already exists, merge the redirect into the existing `redirects` array.

### Step 7: Update local .env.production

Sync the local file to match Vercel:

```
NEXT_PUBLIC_APP_URL=https://mydomain.com
```

### Step 8: Redeploy to production

```bash
vercel --prod
```

### Step 9: Verify everything works

```bash
# SSL on both domains
curl -sI https://mydomain.com | head -5
curl -sI https://www.mydomain.com | head -5

# www redirects to root (should be 308)
curl -sI https://www.mydomain.com/some-path | grep location

# HTTP redirects to HTTPS (should be 308)
curl -sI http://mydomain.com | grep -i location

# Meta tags use new domain
curl -s https://mydomain.com | grep -o 'content="https://[^"]*"' | head -5

# Download/action URLs are correct
curl -s https://mydomain.com | grep -o 'href="[^"]*"' | grep -i download | head -5
```

## Notes

- Vercel CLI requires authentication (`vercel login`)
- Preview deployments are created automatically for PRs
- Production deployments require explicit `--prod` flag
- Environment variables are encrypted at rest
- Logs are retained for 1 hour (free) to 3 days (Pro)
