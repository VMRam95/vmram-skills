# vmram-skills

A curated collection of [Claude Code](https://docs.claude.com/en/docs/claude-code) skills covering VPS/DevOps, document generation, frontend tooling, email/auth integration, code reviews, and more. Most skills also work with Codex (skills are interchangeable as long as their format is preserved).

41 skills, all production-tested.

## Quick install

One-liner (no clone needed):

```bash
# Install specific skills
curl -sL https://raw.githubusercontent.com/VMRam95/vmram-skills/main/install.sh | bash -s -- conventional-commits review-pr web-search-plus

# Install all 41
curl -sL https://raw.githubusercontent.com/VMRam95/vmram-skills/main/install.sh | bash -s -- --all

# Install into Codex instead of Claude
curl -sL https://raw.githubusercontent.com/VMRam95/vmram-skills/main/install.sh | bash -s -- --target codex conventional-commits
```

Or clone and copy manually:

```bash
git clone https://github.com/VMRam95/vmram-skills.git
cd vmram-skills
./install.sh conventional-commits review-pr      # one or many
./install.sh --all                                # everything
cp -r skills/<name> ~/.claude/skills/             # plain copy
```

After installing, restart your Claude Code / Codex session. The skill becomes available and can be invoked via its trigger phrases or `/<skill-name>`.

## Status legend

Use this when picking what to install:

| Badge | Meaning |
|-------|---------|
| 🟢 **standalone** | Pure instructions. Works for any user as soon as it's copied. |
| 🟡 **placeholders** | Works after replacing documented placeholders (`<YOUR_VPS_IP>`, `<YOUR_DOMAIN>`, etc.). |
| 🔵 **needs-deps** | Ships with scripts that require external packages (Python libs, Node modules, system binaries). |
| 🔴 **needs-infra** | Assumes the user runs specific self-hosted infrastructure (email-service, GoTrue, OpenClaw…). Useful as a reference even if you don't run that infra. |
| 🎮 **project-specific** | Tailored to the Stick Crisis Unity game; included for completeness. |

A skill can have multiple badges (e.g. `vps-deploy` is 🟡 + 🔴 — placeholders and assumes you have a VPS).

## Customization placeholders

Skills with the 🟡 badge use these placeholder tokens. Replace them after install (or before, if you fork):

| Placeholder | Used in | Replace with |
|-------------|---------|--------------|
| `<YOUR_VPS_IP>` | `moltbot-vps`, `vps-deploy`, `setup-dev-env` | Your VPS public IP |
| `<YOUR_DOMAIN>` | `setup-dev-env`, `vps-deploy`, `integrate-gotrue-auth` | Your wildcard / project domain |
| `moltbot-vps` (SSH alias) | All VPS skills | Your `~/.ssh/config` Host alias |
| `<YOUR_PERSONAL_EMAIL>` / `<YOUR_WORK_EMAIL>` | `create-project` | Git identities |
| `<TEMPLATES_DIR>` / `<PROJECTS_DIR>` | `create-project` | Where you keep templates / where new projects land |
| `<REFERENCE_PROJECT>` / `<REFERENCE_ADMIN_PROJECT>` | `add-analytics` | An existing Next.js project to copy patterns from |
| `<EMAIL_SERVICE_REPO>` | `add-email-template`, `integrate-email-service` | Your email-service backend repo |
| `<YOUR_BACKEND_REPO>` | `integrate-gotrue-auth` | A backend repo wiring JWT auth |
| `LINKEDIN_URL` env var | `doc-generator/scripts/generate-pdf.cjs` | Your LinkedIn URL |

## Catalog

### VPS / DevOps

| Skill | Status | What it does |
|-------|--------|--------------|
| [`burricalvo`](skills/burricalvo) | 🟡🔴 | Send messages to a remote AI agent (Burricalvo / OpenClaw) running on a VPS. |
| [`moltbot-vps`](skills/moltbot-vps) | 🟡🔴 | Manage an OpenClaw gateway on a Hetzner VPS — status, logs, recovery. |
| [`vps-deploy`](skills/vps-deploy) | 🟡🔴 | Deploy Docker containers + Caddy reverse proxy + HTTPS to a VPS. |
| [`setup-dev-env`](skills/setup-dev-env) | 🟡🔴 | Bootstrap a per-project dev env using PostgreSQL schema isolation + dedicated Docker containers. |

### Documents & Content

| Skill | Status | What it does |
|-------|--------|--------------|
| [`doc-generator`](skills/doc-generator) | 🔵 | Convert Markdown → HTML/PDF with predefined templates (corporate, tech, minimal, AWS, presupuesto). |
| [`gamma`](skills/gamma) | 🟢 | Generate AI-powered presentations and documents using Gamma. |
| [`excalidraw-flowchart`](skills/excalidraw-flowchart) | 🟢 | Create flowcharts/diagrams from text in Excalidraw format. |
| [`images-to-pdf`](skills/images-to-pdf) | 🔵 | Combine multiple images into a single PDF. |
| [`presupuesto`](skills/presupuesto) | 🟢 | Generate project budgets/quotes (fixed price, commission, dual-option) in Markdown. |
| [`remotion`](skills/remotion) | 🔵 | Create programmatic videos with Remotion (React-based video framework). |
| [`save-meeting`](skills/save-meeting) | 🟢 | Save and analyze meeting transcripts into project memory. |
| [`model-conversation-continuity`](skills/model-conversation-continuity) | 🟢 | Cross-model handoff files so another model can resume your work. |

### Frontend / UI

| Skill | Status | What it does |
|-------|--------|--------------|
| [`add-shadcn-component`](skills/add-shadcn-component) | 🟢 | Add a new shadcn/ui component to a project. |
| [`add-legal-pages`](skills/add-legal-pages) | 🟢 | Add GDPR-compliant Privacy Policy, ToS, cookie consent to a Next.js project. |
| [`add-analytics`](skills/add-analytics) | 🟡 | Supabase analytics + optional GA4 in a Next.js project (DB table, hook, API route). |
| [`ui-audit`](skills/ui-audit) | 🟢 | Automated UI audit against proven UX principles. |
| [`ux-audit`](skills/ux-audit) | 🟢 | Automated UX audit against proven design principles. |
| [`web-design-guidelines`](skills/web-design-guidelines) | 🟢 | Review UI code against Vercel-style Web Interface Guidelines. |

### Email / Auth

| Skill | Status | What it does |
|-------|--------|--------------|
| [`add-email-template`](skills/add-email-template) | 🔴 | Add a new email template to a self-hosted email-service. |
| [`integrate-email-service`](skills/integrate-email-service) | 🔴 | Wire any project to an email-service API (project, SMTP, API key, templates). |
| [`integrate-gotrue-auth`](skills/integrate-gotrue-auth) | 🔴 | Wire any project to a shared GoTrue auth instance — JWT middleware, frontend auth context. |

### Git / Code

| Skill | Status | What it does |
|-------|--------|--------------|
| [`conventional-commits`](skills/conventional-commits) | 🟢 | Format commit messages following the Conventional Commits spec. |
| [`review-pr`](skills/review-pr) | 🟢 | Exhaustive, opinionated PR review as a senior reviewer. |
| [`create-project`](skills/create-project) | 🟡 | Scaffold a new project from standardized templates (Next.js+Vercel, API+Railway/Docker, monorepo). |

### Search / Codebase intelligence

| Skill | Status | What it does |
|-------|--------|--------------|
| [`web-search-plus`](skills/web-search-plus) | 🟢 | Unified web search with intelligent auto-routing across providers. |
| [`deepwiki`](skills/deepwiki) | 🟢 | Query GitHub repository documentation via DeepWiki. |
| [`agentlens`](skills/agentlens) | 🟢 | Navigate codebases via hierarchical documentation; generate code maps. |
| [`claude-code-usage`](skills/claude-code-usage) | 🟢 | Check Claude Code OAuth usage limits and token consumption. |

### Image generation

| Skill | Status | What it does |
|-------|--------|--------------|
| [`imagegen`](skills/imagegen) | 🔵 | Generate or edit raster images via OpenAI image API (photos, sprites, mockups). |

### Skill / Plugin tooling

| Skill | Status | What it does |
|-------|--------|--------------|
| [`skill-creator`](skills/skill-creator) | 🔵 | Guide for creating effective skills (or updating existing ones). |
| [`skill-installer`](skills/skill-installer) | 🔵 | Install skills into `$CODEX_HOME/skills` from a curated list or GitHub repo path. |
| [`plugin-creator`](skills/plugin-creator) | 🔵 | Scaffold plugin directories with `.codex-plugin/plugin.json`. |
| [`openai-docs`](skills/openai-docs) | 🟢 | Up-to-date official OpenAI documentation lookup with citations. |
| [`agent-bootstrap`](skills/agent-bootstrap) | 🔵 | Bootstrap a project with its persistent agent team: an architect with a versioned knowledge base, area specialists, orchestration contracts and a write-guard hook. Generates a `<project>-agents` repo outside the code repo. |

### Unity / Stick Crisis (game project)

| Skill | Status | What it does |
|-------|--------|--------------|
| [`unity-mcp-skill`](skills/unity-mcp-skill) | 🔵 | Orchestrate Unity Editor via MCP — GameObjects, scripts, scenes, tests. |
| [`stick-crisis-add-skin`](skills/stick-crisis-add-skin) | 🎮 | Register a new character skin (SkinType + SkinConfig + AnimatorOverrideController). |
| [`stick-crisis-build`](skills/stick-crisis-build) | 🎮 | Compile C# with dotnet and refresh Unity assets after any code change. |
| [`stick-crisis-check-arch`](skills/stick-crisis-check-arch) | 🎮 | Validate DDD + Hexagonal placement before creating or modifying classes. |
| [`stick-crisis-deploy`](skills/stick-crisis-deploy) | 🎮 | Run the deploy workflow to itch.io via `distribute_itch.sh`. |
| [`stick-crisis-performance-optimizer`](skills/stick-crisis-performance-optimizer) | 🎮 | Audit and optimize Unity hot paths (Update/Coroutine, GC, frame-time). |

### Deploy

| Skill | Status | What it does |
|-------|--------|--------------|
| [`vercel`](skills/vercel) | 🟢 | Deploy and manage applications on the Vercel platform. |

## Prerequisites

Most skills (those marked 🟢) are pure instructions and need nothing extra. Skills marked 🔵 ship with scripts that need:

| Skill | What to install before use |
|-------|----------------------------|
| `doc-generator` | `python3`, Python packages used by `scripts/generate.py` (markdown, jinja2, weasyprint or wkhtmltopdf), and Node `puppeteer` + `pdf-lib` for `generate-pdf.cjs`. |
| `images-to-pdf` | `python3` with Pillow (`pip install Pillow`). |
| `imagegen` | `python3`, `OPENAI_API_KEY` env var, packages listed in `imagegen/scripts/image_gen.py`. |
| `remotion` | Node ≥ 18, `npm install remotion @remotion/cli` in your project. |
| `skill-creator`, `skill-installer`, `plugin-creator` | `python3` (the helper scripts use the standard library; no third-party deps). |
| `unity-mcp-skill` | Unity Editor + the MCP for Unity package. See `skills/unity-mcp-skill/references/`. |

Skills marked 🔴 assume you also run specific infrastructure: a self-hosted email-service, a shared GoTrue instance, or an OpenClaw VPS. They're still useful as templates if you want to set up similar infra; the SKILL.md spells out the contracts.

MCP servers some skills assume:

| Skill | MCP server |
|-------|-----------|
| `web-search-plus` | brave-search (or any web-search MCP) |
| `deepwiki` | DeepWiki MCP |
| `openai-docs` | OpenAI docs MCP |
| `add-analytics`, `integrate-email-service`, `add-email-template` | Supabase MCP |
| `plugin-creator` | filesystem MCP (optional) |

## Contributing

Pull requests are welcome. If you want to add a skill, follow the structure under `skills/<name>/SKILL.md` and run a quick check that no private data (IPs, emails, internal hostnames, secrets) is committed.

## License

MIT — see [LICENSE](LICENSE).
