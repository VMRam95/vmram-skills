---
name: deepwiki
description: |
  Query GitHub repository documentation via DeepWiki to understand external codebases.
  Trigger phrases: "deepwiki", "repo docs", "understand repo", "/deepwiki"
---

# DeepWiki

This skill queries GitHub repository documentation via DeepWiki to help understand external codebases without cloning them.

## Arguments

```
/deepwiki <repo> [query]
```

| Argument | Description | Required |
|----------|-------------|----------|
| repo | GitHub repo (owner/repo or full URL) | Yes |
| query | Specific question about the repo | No |

## Examples

```bash
/deepwiki vercel/next.js "how does routing work"
/deepwiki facebook/react "explain hooks implementation"
/deepwiki https://github.com/anthropics/claude-code
```

## Implementation

### 1. Construct DeepWiki URL

DeepWiki provides AI-generated documentation for GitHub repos:

```
https://deepwiki.com/{owner}/{repo}
```

### 2. Fetch Documentation

Use WebFetch to retrieve the documentation:

```bash
# Get overview
WebFetch https://deepwiki.com/vercel/next.js

# Get specific section
WebFetch https://deepwiki.com/vercel/next.js/routing
```

### 3. Query Processing

If user provides a query:
1. Fetch relevant documentation sections
2. Search for keywords in the content
3. Summarize findings related to the query

### 4. Output Format

```markdown
# Repository Documentation: vercel/next.js

## Overview
Next.js is a React framework for building full-stack web applications.

## Architecture
- `/app` - App Router (recommended)
- `/pages` - Pages Router (legacy)
- `/public` - Static assets
- `/api` - API routes

## Key Concepts

### Routing
Next.js uses file-system based routing...

### Data Fetching
Server Components can fetch data directly...

## Your Query: "how does routing work"

Next.js 13+ uses the App Router which is based on React Server Components.
Routes are defined by folders in the `/app` directory:

- `app/page.tsx` → `/`
- `app/about/page.tsx` → `/about`
- `app/blog/[slug]/page.tsx` → `/blog/:slug`

Dynamic segments use `[param]` syntax...
```

## Alternative: GitHub API

For repos not on DeepWiki, use GitHub API:

```bash
# Get README
gh api repos/{owner}/{repo}/readme -H "Accept: application/vnd.github.raw"

# Get file tree
gh api repos/{owner}/{repo}/git/trees/main?recursive=1

# Get specific file
gh api repos/{owner}/{repo}/contents/{path}
```

## Use Cases

1. **Understanding new libraries**
   ```
   /deepwiki shadcn/ui "how to customize themes"
   ```

2. **Learning framework internals**
   ```
   /deepwiki facebook/react "reconciliation algorithm"
   ```

3. **Finding patterns in popular repos**
   ```
   /deepwiki t3-oss/create-t3-app "project structure"
   ```

4. **Comparing implementations**
   ```
   /deepwiki tanstack/query "cache invalidation"
   ```

## Notes

- DeepWiki may not have documentation for all repos
- For private repos, use GitHub API with authentication
- Results are AI-generated summaries, verify with actual source
- Combine with `gh repo clone` for deeper investigation
