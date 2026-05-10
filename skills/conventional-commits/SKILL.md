---
name: conventional-commits
description: |
  Format commit messages following the Conventional Commits specification.
  Trigger phrases: "commit", "git commit", "conventional commit", "/conventional-commits"
---

# Conventional Commits

This skill formats commit messages using the Conventional Commits specification for automated changelog generation and semantic versioning.

## Arguments

```
/conventional-commits [type] [scope] [description]
```

| Argument | Description | Required |
|----------|-------------|----------|
| type | Commit type (feat, fix, docs, etc.) | No (interactive) |
| scope | Optional scope in parentheses | No |
| description | Short description | No (interactive) |

## Commit Types

### Required Types (SemVer)

| Type | Description | Version Impact |
|------|-------------|----------------|
| `feat` | New feature | MINOR |
| `fix` | Bug fix | PATCH |

### Additional Types

| Type | Use Case |
|------|----------|
| `docs` | Documentation only |
| `style` | Formatting (spaces, semicolons, no code change) |
| `refactor` | Refactoring without behavior change |
| `test` | Add/modify tests |
| `chore` | Maintenance tasks |
| `build` | Build system or external dependencies |
| `ci` | CI/CD configuration |
| `perf` | Performance improvements |

## Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

## Rules

1. **Imperative mood**: Use "add" not "added" or "adds"
2. **No capitalization**: Start with lowercase
3. **No period**: Don't end description with a period
4. **Max 72 characters**: Keep first line under 72 chars
5. **Scope optional**: But recommended for large projects

## Breaking Changes

Two ways to indicate breaking changes:

1. **Exclamation mark**: `feat!: remove deprecated API`
2. **Footer**: Add `BREAKING CHANGE: description` in footer

## Examples

```bash
# Simple feature
feat: add user authentication

# Feature with scope
feat(auth): add Google OAuth login

# Bug fix
fix(video): prevent race condition in room join

# Documentation
docs(api): update endpoint documentation

# Refactoring
refactor(hooks): simplify useAuth implementation

# Tests
test(components): add unit tests for StatusBadge

# Chore
chore(deps): update dependencies to latest versions

# Build
build(docker): optimize production image size

# CI
ci(github): add automated testing workflow

# Performance
perf(queries): optimize database queries with indexes

# Breaking change with !
feat!: remove legacy payment provider support

# Breaking change with footer
feat(api): change authentication flow

BREAKING CHANGE: JWT tokens now required for all endpoints
```

## Workflow

When user wants to commit:

1. **Check staged changes**: `git diff --staged`
2. **Analyze changes**: Determine appropriate type
3. **Suggest commit message**: Based on changes
4. **Format message**: Use heredoc for multi-line:

```bash
git commit -m "$(cat <<'EOF'
feat(scope): description

Body explaining what and why.
EOF
)"
```

## Attribution Rule

Do not add AI attribution trailers, co-author lines, or model/vendor references to commit messages unless the user explicitly requests them.
Forbidden examples: any co-author trailer, assistant/model signature, vendor name, or tool-brand reference added as commit metadata.
