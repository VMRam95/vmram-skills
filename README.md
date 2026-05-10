# vmram-skills

A curated collection of [Claude Code](https://docs.claude.com/en/docs/claude-code) skills covering VPS/DevOps, document generation, frontend tooling, email/auth integration, code reviews, and more. Most skills also work with Codex (skills are interchangeable as long as their format is preserved).

40 skills, all production-tested.

## Install

Each skill lives in `skills/<name>/`. Install one or many:

```bash
# Clone the repo
git clone https://github.com/VMRam95/vmram-skills.git
cd vmram-skills

# Install a single skill
cp -r skills/conventional-commits ~/.claude/skills/

# Install several at once
for s in conventional-commits review-pr web-search-plus; do
  cp -r "skills/$s" ~/.claude/skills/
done

# Or install all of them
cp -r skills/* ~/.claude/skills/
```

For Codex users:

```bash
cp -r skills/<name> ~/.codex/skills/
```

After copying, restart your Claude Code / Codex session. The skill will appear in the available-skills list and can be invoked when its trigger phrases match (or via `/<skill-name>`).

## Customize before use

Skills that interact with infrastructure contain placeholder tokens you must replace before they work for you:

| Placeholder | Where | Replace with |
|-------------|-------|--------------|
| `<YOUR_VPS_IP>` | `moltbot-vps`, `vps-deploy`, `setup-dev-env` | Your VPS public IP |
| `<YOUR_DOMAIN>` | `setup-dev-env`, `vps-deploy`, `integrate-gotrue-auth` | Your wildcard domain |
| `moltbot-vps` (SSH alias) | All VPS skills | Your `~/.ssh/config` Host alias |
| `<YOUR_PERSONAL_EMAIL>` / `<YOUR_WORK_EMAIL>` | `create-project` | Git identities |
| `LINKEDIN_URL` env var | `doc-generator/scripts/generate-pdf.cjs` | Your LinkedIn URL |

## Catalog

### VPS / DevOps

| Skill | What it does |
|-------|--------------|
| [`burricalvo`](skills/burricalvo) | Send messages to a remote AI agent (Burricalvo / OpenClaw) running on a VPS. |
| [`moltbot-vps`](skills/moltbot-vps) | Manage an OpenClaw gateway running on a Hetzner VPS — status, logs, recovery. |
| [`vps-deploy`](skills/vps-deploy) | Standard procedure to deploy Docker containers + Caddy reverse proxy + HTTPS to a VPS. |
| [`setup-dev-env`](skills/setup-dev-env) | Bootstrap a dev environment per project using PostgreSQL schema isolation and dedicated Docker containers. |

### Documents & Content

| Skill | What it does |
|-------|--------------|
| [`doc-generator`](skills/doc-generator) | Convert Markdown to professional HTML/PDF with predefined templates (corporate, tech, minimal, AWS, presupuesto). |
| [`gamma`](skills/gamma) | Generate AI-powered presentations and documents using Gamma. |
| [`excalidraw-flowchart`](skills/excalidraw-flowchart) | Create flowcharts and diagrams from text descriptions in Excalidraw format. |
| [`images-to-pdf`](skills/images-to-pdf) | Combine multiple images (JPG, PNG, …) into a single PDF document. |
| [`presupuesto`](skills/presupuesto) | Generate professional project budgets/quotes (fixed price, commission, dual-option) in Markdown. |
| [`remotion`](skills/remotion) | Create programmatic videos with Remotion (React-based video framework). |
| [`save-meeting`](skills/save-meeting) | Save and analyze meeting transcripts into project memory — extracts decisions, action items, blockers. |
| [`model-conversation-continuity`](skills/model-conversation-continuity) | Cross-model handoff files so another model can resume your work without context loss. |

### Frontend / UI

| Skill | What it does |
|-------|--------------|
| [`add-shadcn-component`](skills/add-shadcn-component) | Add a new shadcn/ui component to a project. |
| [`add-legal-pages`](skills/add-legal-pages) | Add GDPR-compliant Privacy Policy, Terms of Service, and cookie consent to a Next.js project. |
| [`add-analytics`](skills/add-analytics) | Add Supabase analytics + optional GA4 to a Next.js project (DB table, hook, API route, GDPR-aware). |
| [`ui-audit`](skills/ui-audit) | Automated UI audit against proven UX principles. |
| [`ux-audit`](skills/ux-audit) | Automated UX audit against proven design principles. |
| [`web-design-guidelines`](skills/web-design-guidelines) | Review UI code for Web Interface Guidelines compliance (Vercel-style standards). |

### Email / Auth

| Skill | What it does |
|-------|--------------|
| [`add-email-template`](skills/add-email-template) | Add a new email template to a self-hosted email-service (HTML, Supabase row, migration). |
| [`integrate-email-service`](skills/integrate-email-service) | Integrate any project with an email-service API (project, SMTP, API key, templates, env vars). |
| [`integrate-gotrue-auth`](skills/integrate-gotrue-auth) | Integrate any project with a shared GoTrue auth instance — JWT middleware, frontend auth context, Docker. |

### Git / Code

| Skill | What it does |
|-------|--------------|
| [`conventional-commits`](skills/conventional-commits) | Format commit messages following the Conventional Commits spec. |
| [`review-pr`](skills/review-pr) | Exhaustive, opinionated PR review as a senior reviewer. |
| [`create-project`](skills/create-project) | Scaffold a new project from standardized templates (Next.js+Vercel, API+Railway/Docker, monorepo). |

### Search / Codebase intelligence

| Skill | What it does |
|-------|--------------|
| [`web-search-plus`](skills/web-search-plus) | Unified web search with intelligent auto-routing across providers. |
| [`deepwiki`](skills/deepwiki) | Query GitHub repository documentation via DeepWiki to understand external codebases. |
| [`agentlens`](skills/agentlens) | Navigate codebases using hierarchical documentation; generate code maps for context. |
| [`claude-code-usage`](skills/claude-code-usage) | Check Claude Code OAuth usage limits and token consumption. |

### Image generation

| Skill | What it does |
|-------|--------------|
| [`imagegen`](skills/imagegen) | Generate or edit raster images when bitmap output is needed (photos, sprites, mockups, transparent cutouts). |

### Skill / Plugin tooling

| Skill | What it does |
|-------|--------------|
| [`skill-creator`](skills/skill-creator) | Guide for creating effective skills (or updating existing ones). |
| [`skill-installer`](skills/skill-installer) | Install skills into `$CODEX_HOME/skills` from a curated list or a GitHub repo path. |
| [`plugin-creator`](skills/plugin-creator) | Scaffold plugin directories with `.codex-plugin/plugin.json` and baseline placeholders. |
| [`openai-docs`](skills/openai-docs) | Up-to-date official OpenAI documentation lookup with citations and model upgrade guidance. |

### Unity / Stick Crisis (game project)

| Skill | What it does |
|-------|--------------|
| [`unity-mcp-skill`](skills/unity-mcp-skill) | Orchestrate Unity Editor via MCP — GameObjects, scripts, scenes, tests, automation. |
| [`stick-crisis-add-skin`](skills/stick-crisis-add-skin) | Register a new character skin (SkinType + SkinConfig + AnimatorOverrideController). |
| [`stick-crisis-build`](skills/stick-crisis-build) | Compile C# with dotnet and refresh Unity assets after any code change. |
| [`stick-crisis-check-arch`](skills/stick-crisis-check-arch) | Validate DDD + Hexagonal placement rules before creating or modifying classes. |
| [`stick-crisis-deploy`](skills/stick-crisis-deploy) | Run the deploy workflow to itch.io via `distribute_itch.sh`. |
| [`stick-crisis-performance-optimizer`](skills/stick-crisis-performance-optimizer) | Audit and optimize Unity hot paths (Update/Coroutine, GC, frame-time, Debug logs). |

### Deploy

| Skill | What it does |
|-------|--------------|
| [`vercel`](skills/vercel) | Deploy and manage applications on the Vercel platform. |

## Contributing

Pull requests are welcome. If you want to add a skill, follow the structure under `skills/<name>/SKILL.md` and run a quick check that no private data (IPs, emails, internal hostnames, secrets) is committed.

## License

MIT — see [LICENSE](LICENSE).
