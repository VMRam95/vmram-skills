---
name: integrate-gotrue-auth
description: |
  Integrate any project with the shared GoTrue auth instance with per-project roles.
  Backend JWT middleware, frontend login/auth context, Docker config, and VPS deployment.
  Trigger phrases: "integrate auth", "add gotrue", "setup authentication", "integrar autenticacion", "/integrate-gotrue-auth"
---

# Integrate GoTrue Authentication

Automates the full integration of any project with the shared GoTrue authentication instance running on the VPS. Adds backend JWT middleware with per-project role resolution, frontend GoTrueClient + AuthContext + LoginPage + ProtectedRoute, Docker/docker-compose configuration, and registers the project in the role management system.

## Architecture

All projects share a single GoTrue instance at `https://gotrue.<YOUR_DOMAIN>` (internal: `http://gotrue:9999`) on the `infrastructure_default` Docker network.

**Per-project roles structure in `app_metadata`:**
```json
{
  "roles": {
    "shopify-commission-engine": "SUPER_ADMIN",
    "vps-dashboard": "VIEWER",
    "new-project": "ADMIN"
  },
  "approved": true
}
```

**Role resolution fallback chain (backward compat):**
```
roles?.[projectId] || role || 'VIEWER'
```

## Arguments

```
/integrate-gotrue-auth [project-slug]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `project-slug` | No | Kebab-case project identifier (e.g., `my-cool-app`). Prompted if not provided |

## Examples

```bash
/integrate-gotrue-auth                    # Interactive - asks everything
/integrate-gotrue-auth my-new-project     # Pre-sets project slug
```

## Pre-requisites

- The target project must have a backend (Node.js/Express or similar) and a frontend (React/Vite or Next.js)
- The project is deployed (or will be deployed) on the VPS via Docker on the `infrastructure_default` network
- The shared GoTrue instance is running at `http://gotrue:9999`
- `GOTRUE_JWT_SECRET` is available (same value used by the GoTrue instance)

## Implementation

Follow these steps IN ORDER.

### Step 1: Gather project information

Use **AskUserQuestion** to collect:

**Question 1 - Project details:**
| Field | Example | Description |
|-------|---------|-------------|
| Project name | "My Cool App" | Human-readable name |
| Project slug | `my-cool-app` | Kebab-case, used as `PROJECT_ID` |
| Default route after login | `/dashboard` | Where to redirect after successful login |

**Question 2 - Tech stack detection:**

Auto-detect from the project's codebase:
- Backend language: JS or TS? (check for `tsconfig.json` in backend)
- Frontend framework: React+Vite or Next.js? (check for `vite.config` vs `next.config`)
- Package manager: npm, pnpm, or yarn? (check lock files)
- Has existing auth? (search for `authenticateToken`, `auth middleware`, `AuthContext`)

**Question 3 - Frontend style:**
| Option | Description |
|--------|-------------|
| `tailwind-zinc` | Dark theme with zinc palette (Recommended - matches existing projects) |
| `tailwind-custom` | Ask user for color palette |
| `shadcn` | Use shadcn/ui Card + Input + Button components |

### Step 2: Install dependencies

**Backend:**
```bash
# In the backend directory
npm install jsonwebtoken
# TypeScript projects also need:
npm install -D @types/jsonwebtoken
```

**Frontend:**
```bash
# In the frontend directory
npm install @supabase/gotrue-js
```

### Step 3: Backend - Add config variables

Add `gotrueJwtSecret` and `projectId` to the project's config file.

**For TypeScript projects** (e.g., `backend/src/config.ts`):
```typescript
export default {
  // ... existing config
  gotrueJwtSecret: process.env.GOTRUE_JWT_SECRET || '',
  projectId: process.env.PROJECT_ID || '{{project-slug}}',
};
```

**For JavaScript projects** (e.g., `backend/src/config/env.js`):
```javascript
module.exports = {
  // ... existing config
  gotrueJwtSecret: process.env.GOTRUE_JWT_SECRET,
  projectId: process.env.PROJECT_ID || '{{project-slug}}',
};
```

### Step 4: Backend - Create JWT auth middleware

Create the auth middleware file. Adapt the import style (ESM vs CJS) to match the project.

**TypeScript (ESM) - `backend/src/middleware/auth.ts`:**
```typescript
import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import config from '../config.js';

interface JwtPayload {
  sub: string;
  email: string;
  app_metadata?: {
    role?: string;
    roles?: Record<string, string>;
    approved?: boolean;
  };
}

declare global {
  namespace Express {
    interface Request {
      user?: {
        id: string;
        email: string;
        role: string;
        approved: boolean;
      };
    }
  }
}

export function authenticateToken(req: Request, res: Response, next: NextFunction): void {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) {
    res.status(401).json({ success: false, error: 'Authentication required' });
    return;
  }

  if (!config.gotrueJwtSecret) {
    console.error('[auth] GOTRUE_JWT_SECRET is not configured');
    res.status(500).json({ success: false, error: 'Authentication not configured' });
    return;
  }

  try {
    const decoded = jwt.verify(token, config.gotrueJwtSecret) as JwtPayload;

    const isApproved = decoded.app_metadata?.approved !== false;
    if (!isApproved) {
      res.status(403).json({ success: false, error: 'Account pending approval' });
      return;
    }

    req.user = {
      id: decoded.sub,
      email: decoded.email,
      role: decoded.app_metadata?.roles?.[config.projectId]
        || decoded.app_metadata?.role
        || 'VIEWER',
      approved: isApproved,
    };

    next();
  } catch {
    res.status(401).json({ success: false, error: 'Invalid or expired token' });
  }
}
```

**JavaScript (CJS) - `backend/src/middlewares/authMiddleware.js`:**
```javascript
const jwt = require('jsonwebtoken');
const config = require('../config/env');

function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) {
    return res.status(401).json({ error: 'Unauthorized', message: 'Authentication required' });
  }

  try {
    const decoded = jwt.verify(token, config.gotrueJwtSecret);

    const isApproved = decoded.app_metadata?.approved !== false;
    if (!isApproved) {
      return res.status(403).json({ error: 'AccountPendingApproval', message: 'Your account is pending administrator approval' });
    }

    req.user = {
      id: decoded.sub,
      email: decoded.email,
      role: decoded.app_metadata?.roles?.[config.projectId]
        || decoded.app_metadata?.role
        || 'VIEWER',
      approved: isApproved,
    };
    next();
  } catch (err) {
    return res.status(401).json({ error: 'Unauthorized', message: 'Invalid or expired token' });
  }
}

function authorizeRole(...roles) {
  return (req, res, next) => {
    if (!req.user || !roles.includes(req.user.role)) {
      return res.status(403).json({ error: 'Forbidden', message: 'Insufficient permissions' });
    }
    next();
  };
}

module.exports = { authenticateToken, authorizeRole };
```

### Step 5: Backend - Apply middleware to routes

In the main server file (e.g., `index.ts` or `app.js`), apply `authenticateToken` to all API routes **except health check**:

```typescript
import { authenticateToken } from './middleware/auth.js';

// Public routes (no auth)
app.use('/api/health', healthRoutes);

// Protected routes (auth required)
app.use('/api/system', authenticateToken, systemRoutes);
app.use('/api/data', authenticateToken, dataRoutes);
// ... apply to ALL other /api/* routes
```

### Step 6: Frontend - Create GoTrueClient

**`frontend/src/lib/auth.ts`:**
```typescript
import { GoTrueClient } from '@supabase/gotrue-js'

const GOTRUE_URL = import.meta.env.VITE_GOTRUE_URL || ''

export const gotrueClient = new GoTrueClient({
  url: GOTRUE_URL,
  storageKey: '{{project-slug}}-auth',
})
```

**For Next.js** use `process.env.NEXT_PUBLIC_GOTRUE_URL` instead of `import.meta.env.VITE_GOTRUE_URL`.

### Step 7: Frontend - Create AuthContext

**`frontend/src/contexts/AuthContext.tsx`:**
```tsx
import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import type { User, Session } from '@supabase/gotrue-js'
import { gotrueClient } from '@/lib/auth'

const PROJECT_ID = '{{project-slug}}'

interface AuthContextType {
  user: User | null
  session: Session | null
  isLoading: boolean
  isAuthenticated: boolean
  role: string
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    gotrueClient.getSession().then(({ data: { session: initialSession } }) => {
      setSession(initialSession)
      setUser(initialSession?.user ?? null)
      setIsLoading(false)
    })

    const { data: { subscription } } = gotrueClient.onAuthStateChange((_event, newSession) => {
      setSession(newSession)
      setUser(newSession?.user ?? null)
    })

    return () => { subscription.unsubscribe() }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const { error } = await gotrueClient.signInWithPassword({ email, password })
    if (error) throw error
  }, [])

  const logout = useCallback(async () => {
    await gotrueClient.signOut()
    setUser(null)
    setSession(null)
  }, [])

  const role = user?.app_metadata?.roles?.[PROJECT_ID]
    || user?.app_metadata?.role
    || 'VIEWER'

  return (
    <AuthContext.Provider value={{ user, session, isLoading, isAuthenticated: !!session, role, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) throw new Error('useAuth must be used within an AuthProvider')
  return context
}
```

### Step 8: Frontend - Create LoginPage

Create `frontend/src/components/auth/LoginPage.tsx`. Adapt styling to match the project.

**Default (tailwind-zinc):**
```tsx
import { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('{{default-route}}', { replace: true })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Login failed'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 px-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center space-y-2">
          <h1 className="text-xl font-semibold text-zinc-100">{{Project Name}}</h1>
          <p className="text-sm text-zinc-500">Sign in to access the dashboard</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-md bg-red-950/50 border border-red-900/50 px-3 py-2 text-sm text-red-400">
              {error}
            </div>
          )}
          <div className="space-y-1.5">
            <label htmlFor="email" className="text-sm font-medium text-zinc-400">Email</label>
            <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email"
              className="w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
              placeholder="admin@example.com" />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="password" className="text-sm font-medium text-zinc-400">Password</label>
            <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password"
              className="w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
              placeholder="Enter your password" />
          </div>
          <button type="submit" disabled={loading}
            className="w-full rounded-md bg-zinc-100 px-3 py-2 text-sm font-medium text-zinc-900 hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2">
            {loading ? (<><Loader2 className="h-4 w-4 animate-spin" />Signing in...</>) : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
```

**Note:** If the project uses `lucide-react`, use `Loader2` for the spinner. If not, install it or use a simple CSS spinner.

### Step 9: Frontend - Create ProtectedRoute

**`frontend/src/components/auth/ProtectedRoute.tsx`:**
```tsx
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-950">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-700 border-t-zinc-400" />
      </div>
    )
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}
```

### Step 10: Frontend - Inject auth token in API client

Find the project's API client (e.g., `lib/api.ts`) and add token injection:

```typescript
import { gotrueClient } from './auth'

// Inside the request method, before making the fetch:
const { data: { session } } = await gotrueClient.getSession()
if (session?.access_token) {
  headers["Authorization"] = `Bearer ${session.access_token}`
}
```

### Step 11: Frontend - Wrap app with AuthProvider

In the root component (e.g., `App.tsx`):

1. Wrap the entire app with `<AuthProvider>`
2. Add `/login` route pointing to `<LoginPage />`
3. Wrap protected routes with `<ProtectedRoute>`

```tsx
import { AuthProvider } from '@/contexts/AuthContext'
import { LoginPage } from '@/components/auth/LoginPage'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            {/* All protected routes here */}
            <Route path="*" element={<Navigate to="{{default-route}}" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
```

### Step 12: Docker configuration

**12a. Dockerfile - Add `VITE_GOTRUE_URL` build arg:**

In the frontend build stage of the Dockerfile, add:
```dockerfile
ARG VITE_GOTRUE_URL
ENV VITE_GOTRUE_URL=$VITE_GOTRUE_URL
```

This is needed because Vite bakes env vars at compile time.

For **Next.js**, use `NEXT_PUBLIC_GOTRUE_URL` instead.

**12b. docker-compose.yml - Add environment variables:**

```yaml
services:
  {{project-slug}}:
    build:
      context: .
      args:
        VITE_GOTRUE_URL: ${VITE_GOTRUE_URL:-https://gotrue.<YOUR_DOMAIN>}
    environment:
      - GOTRUE_URL=http://gotrue:9999
      - GOTRUE_JWT_SECRET=${GOTRUE_JWT_SECRET}
      - PROJECT_ID={{project-slug}}
    networks:
      - infrastructure_default

networks:
  infrastructure_default:
    external: true
```

### Step 13: Register project in role management system

Add the new project to the `KNOWN_PROJECTS` array in **shopify-commission-engine**:

File: `<YOUR_BACKEND_REPO>/backend/src/routes/users.js`

```javascript
const KNOWN_PROJECTS = [
  { id: 'shopify-commission-engine', name: 'Shopify Commission Engine' },
  { id: 'vps-dashboard', name: 'VPS Dashboard' },
  { id: '{{project-slug}}', name: '{{Project Name}}' },  // <-- Add this
];
```

This makes the project appear in the role management UI of shopify-commission-engine, where admins can assign per-project roles.

### Step 14: VPS deployment

**14a. Add GOTRUE_JWT_SECRET to the project's .env on the VPS:**

```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "grep -q GOTRUE_JWT_SECRET /opt/{{project-slug}}/.env && echo 'Already set' || echo 'GOTRUE_JWT_SECRET=<value>' >> /opt/{{project-slug}}/.env"
```

The JWT secret value must match the one used by GoTrue. Check:
```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "grep GOTRUE_JWT_SECRET /opt/infrastructure/.env"
```

**14b. Rebuild and deploy:**

```bash
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "cd /opt/{{project-slug}} && git pull && docker compose up -d --build"
```

### Step 15: Assign initial roles via migration

After deployment, assign roles for existing GoTrue users to the new project. This can be done from the shopify-commission-engine admin UI (`/users` page) or via the GoTrue Admin API:

```bash
# Via the VPS - set a user's role for the new project
ssh-add ~/.ssh/id_ed25519_personal && ssh moltbot-vps "docker exec shopify-commission-backend node -e \"
const axios = require('axios');
const jwt = require('jsonwebtoken');
const SECRET = process.env.GOTRUE_JWT_SECRET || require('fs').readFileSync('/dev/stdin','utf8').trim();
const token = jwt.sign({role:'service_role',iss:'supabase'}, SECRET, {expiresIn:'1h'});
// Replace USER_ID and ROLE
axios.get('http://gotrue:9999/admin/users', {headers:{Authorization:'Bearer '+token}})
  .then(r => console.log(r.data.users.map(u => u.email + ' -> ' + JSON.stringify(u.app_metadata?.roles))))
  .catch(e => console.error(e.message));
\""
```

Or simply use the **shopify-commission-engine UI** at `/users` where SUPER_ADMIN users can assign roles per project.

## Verification Checklist

After completing all steps, verify:

1. **Backend rejects unauthenticated requests:** `curl http://localhost:PORT/api/some-endpoint` returns 401
2. **Frontend shows login page:** Opening the app redirects to `/login`
3. **Login works:** Enter valid credentials, redirected to default route
4. **API calls include token:** Check network tab, `Authorization: Bearer ...` header present
5. **Role is resolved correctly:** Check `req.user.role` in backend logs matches the user's role for this project
6. **Role management UI:** New project appears in shopify-commission-engine `/users` page
7. **Logout works:** Click logout, session cleared, redirected to `/login`

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `GOTRUE_JWT_SECRET is not configured` | Add `GOTRUE_JWT_SECRET` to `.env` and `docker-compose.yml` |
| `Invalid or expired token` | Verify JWT secret matches GoTrue's secret |
| Frontend login fails with network error | Check `VITE_GOTRUE_URL` is set correctly as Docker build arg |
| User has no role for project | Default is `VIEWER`. Assign via shopify-commission-engine `/users` page |
| `@supabase/gotrue-js` types missing | Ensure `@supabase/gotrue-js` version >= 2.x |
| Docker build doesn't pick up VITE_GOTRUE_URL | Must be an `ARG` in the frontend build stage, not just runtime `ENV` |

## Reference implementations

| Project | Backend Auth | Frontend Auth |
|---------|-------------|---------------|
| shopify-commission-engine | `backend/src/middlewares/authMiddleware.js` (CJS) | `frontend/src/contexts/AuthContext.tsx` |
| vps-dashboard | `backend/src/middleware/auth.ts` (ESM/TS) | `frontend/src/contexts/AuthContext.tsx` |

## Notes

- All projects share ONE GoTrue instance; roles are scoped per project via `app_metadata.roles`
- The `storageKey` in `GoTrueClient` should be unique per project to avoid session conflicts across projects on the same domain
- The backward-compat fallback `|| app_metadata?.role` handles users not yet migrated to the per-project structure
- Never expose `GOTRUE_JWT_SECRET` on the frontend; only `VITE_GOTRUE_URL` (the public GoTrue URL) goes to the client
- The `approved !== false` check allows existing users without the `approved` field to pass (they default to approved)
