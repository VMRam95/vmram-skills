---
name: create-project
description: |
  Use this skill to create a new project from standardized templates.
  Trigger phrases: "create project", "new project", "scaffold project", "/create-project"
---

# Create Project

This skill creates a new project from standardized templates with proper configuration.

## Arguments

```
/create-project [project-name]
```

| Argument | Description | Required |
|----------|-------------|----------|
| project-name | Name of the new project (kebab-case) | Optional (will prompt if not provided) |

## Examples

```bash
/create-project my-awesome-app    # Create new project with name
/create-project                   # Interactive mode (prompts for all options)
```

## Implementation

### 1. Gather Project Information

Use `AskUserQuestion` to gather the following information:

**Question 1: Project Name** (if not provided as argument)
- Validate: kebab-case, no spaces, lowercase

**Question 2: Project Type**
| Option | Description |
|--------|-------------|
| `nextjs` | Next.js 15 monolithic application (Recommended) |
| `api` | Backend API service |
| `monorepo` | Turborepo with shared packages |

**Question 3: Deploy Platform**
| Option | Description |
|--------|-------------|
| `vercel` | Vercel (serverless, edge) - Recommended for Next.js |
| `railway` | Railway (containers, databases) |
| `docker` | Docker generic (self-hosted, AWS, GCP) |

**Question 4: Git Identity**
| Option | Description |
|--------|-------------|
| `personal` | <YOUR_PERSONAL_EMAIL> (github-personal SSH) |
| `work` | <YOUR_WORK_EMAIL> (github.com SSH) |

**Question 5: Additional Options** (multiSelect)
| Option | Description |
|--------|-------------|
| Supabase | Include Supabase client setup |
| shadcn/ui | Pre-install shadcn/ui components |
| Vitest | Include testing setup |

### 2. Determine Template Path

Templates are located in the shared-config repository:
```
~/Documentos/repositories/shared-config/templates/
├── nextjs-vercel/     # Next.js + Vercel template ✅
├── api-railway/       # API + Railway template ✅
├── api-docker/        # API + Docker template ✅
└── monorepo-vercel/   # Monorepo + Vercel template ✅
```

**Current available templates:**
- `nextjs-vercel` ✅
- `api-railway` ✅
- `api-docker` ✅
- `monorepo-vercel` ✅

**Template selection logic:**
```
if type == "nextjs" && platform == "vercel":
    template = "nextjs-vercel"
elif type == "api" && platform == "railway":
    template = "api-railway"
elif type == "api" && platform == "docker":
    template = "api-docker"
elif type == "monorepo" && platform == "vercel":
    template = "monorepo-vercel"
else:
    inform user template not available yet
    suggest using available templates as base
```

### 3. Create Project Directory

**Default location:** `~/Documentos/repositories/{project-name}/`

```bash
mkdir -p ~/Documentos/repositories/{project-name}
cp -r {template-path}/* ~/Documentos/repositories/{project-name}/
cp -r {template-path}/.* ~/Documentos/repositories/{project-name}/ 2>/dev/null || true
```

### 4. Replace Placeholders

Replace these placeholders in all files:

| Placeholder | Replace With |
|-------------|--------------|
| `{{PROJECT_NAME}}` | project-name |
| `{{PROJECT_DESCRIPTION}}` | "A new {type} project" or user-provided |
| `{{REPO_URL}}` | GitHub URL based on git identity |

**Files to process (Next.js):**
- `package.json`
- `CLAUDE.md`
- `README.md`
- `src/app/layout.tsx`
- `src/app/page.tsx`

**Files to process (API):**
- `package.json`
- `CLAUDE.md`
- `README.md`
- `src/index.ts`
- `tests/health.test.ts`

```bash
find . -type f \( -name "*.json" -o -name "*.md" -o -name "*.tsx" -o -name "*.ts" \) \
  -exec sed -i '' 's/{{PROJECT_NAME}}/{project-name}/g' {} \;
```

### 5. Configure Git

**Initialize git with correct identity:**

```bash
cd ~/Documentos/repositories/{project-name}
git init

# Set identity based on selection
if identity == "personal":
    git config user.email "<YOUR_PERSONAL_EMAIL>"
    git config user.name "<YOUR_NAME>"
    # Remote will use github-personal SSH host
else:
    git config user.email "<YOUR_WORK_EMAIL>"
    git config user.name "<YOUR_FULL_NAME>"
    # Remote will use github.com SSH host
```

### 6. Install Dependencies

```bash
cd ~/Documentos/repositories/{project-name}
pnpm install
```

### 7. Run Initial Setup (Optional)

If shadcn/ui option selected:
```bash
npx shadcn@latest add button card input
```

### 8. Create Initial Commit

```bash
git add -A
git commit -m "feat: initial project setup from template

Created from {template-name} template v1.2.0
"
```

### 9. Verification

Run checks to ensure project is properly set up:
```bash
pnpm typecheck
pnpm lint
pnpm build
```

## Output

Report to user:
1. Project created at: `~/Documentos/repositories/{project-name}/`
2. Template used: `{template-name}`
3. Git configured with: `{email}`
4. Dependencies installed: ✅/❌
5. Verification: pass/fail
6. Next steps:
   - `cd ~/Documentos/repositories/{project-name}`
   - `pnpm dev`
   - Create GitHub repository: `gh repo create {project-name} --private --source=. --push`

## Notes

- Always use the `github-personal` SSH alias for personal projects
- Default location is `~/Documentos/repositories/`
- Templates extend `@shared/config` for consistent configuration
- CLAUDE.md is automatically customized with project name
- Initial commit follows conventional commits format and must not include AI attribution trailers
