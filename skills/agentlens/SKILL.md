---
name: agentlens
description: |
  Navigate codebases using hierarchical documentation and generate code maps for context.
  Trigger phrases: "codebase map", "code structure", "navigate code", "/agentlens"
---

# AgentLens

This skill helps navigate large codebases by generating hierarchical documentation and code maps that provide context for AI agents.

## Arguments

```
/agentlens [command] [path]
```

| Argument | Description | Required |
|----------|-------------|----------|
| command | map, explore, summarize | No (default: map) |
| path | Directory or file to analyze | No (default: current dir) |

## Commands

### Map (Default)

Generate a hierarchical map of the codebase:

```bash
/agentlens map ./src
```

Output:
```
src/
├── components/     # React UI components
│   ├── ui/         # Reusable UI primitives (Button, Input, Modal)
│   ├── forms/      # Form components with validation
│   └── layout/     # Layout components (Header, Sidebar, Footer)
├── hooks/          # Custom React hooks
│   ├── useAuth.ts  # Authentication state management
│   └── useApi.ts   # API request handling with caching
├── services/       # Business logic and API clients
│   ├── api/        # REST API client modules
│   └── auth/       # Authentication service
├── utils/          # Utility functions
└── types/          # TypeScript type definitions
```

### Explore

Deep dive into a specific area:

```bash
/agentlens explore ./src/services/auth
```

Output:
```
Authentication Service Analysis
===============================

Files:
- auth.service.ts (main service, 245 lines)
- auth.types.ts (type definitions)
- auth.utils.ts (helper functions)

Key Functions:
- login(credentials): Promise<User>
- logout(): void
- refreshToken(): Promise<string>
- validateSession(): boolean

Dependencies:
- axios (HTTP client)
- jwt-decode (token parsing)
- @/hooks/useAuth (consumer)

Used By:
- LoginForm.tsx
- AuthProvider.tsx
- ProtectedRoute.tsx
```

### Summarize

Generate a high-level summary:

```bash
/agentlens summarize
```

Output:
```
Project Summary: my-app
=======================

Type: Next.js Application
Language: TypeScript (98%)
Size: 15,234 lines of code

Architecture:
- Frontend: React + Next.js
- State: React Context + hooks
- Styling: Tailwind CSS
- API: REST with axios

Key Directories:
- /src/app - Next.js app router pages
- /src/components - 47 React components
- /src/services - 8 service modules
- /src/hooks - 12 custom hooks

Entry Points:
- /src/app/layout.tsx - Root layout
- /src/app/page.tsx - Home page

Configuration:
- next.config.js
- tailwind.config.js
- tsconfig.json
```

## Implementation

### 1. Scan Directory Structure

```bash
find . -type f -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" | head -100
```

### 2. Analyze File Contents

For each key file:
- Extract exports (functions, classes, types)
- Identify imports and dependencies
- Count lines and complexity

### 3. Build Hierarchy

Create a tree structure with:
- Directory purposes
- File summaries
- Key function/class listings

### 4. Generate Documentation

Output as markdown or structured text that:
- Fits in context window
- Provides actionable navigation
- Highlights important patterns

## Best Practices

1. **Start broad**: Use `map` first to understand structure
2. **Drill down**: Use `explore` for specific areas
3. **Update regularly**: Re-run after major changes
4. **Share context**: Include output when asking for help

## Notes

- Ignores node_modules, .git, and common build directories
- Prioritizes source files over configuration
- Limits output to avoid context overflow
- Can be combined with grep/find for specific searches
