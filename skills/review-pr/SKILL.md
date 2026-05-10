---
name: review-pr
description: |
  Performs an exhaustive, opinionated PR review as a senior reviewer.
  Trigger phrases: "review pr", "revisa la pr", "review PR #N", "/review-pr"
---

# PR Review — Strict Code Reviewer

Performs an exhaustive, opinionated review of a Pull Request. Acts as a senior reviewer who blocks merge until all issues are resolved.

## Trigger

User says: "review pr", "revisa la pr", "review PR #N", "/review-pr"

## Arguments

- PR number or branch name (optional — auto-detects current branch if omitted)
- Repository path (optional — defaults to cwd)

## Review Protocol

### Phase 1: Context Gathering

1. Identify the PR branch and base branch
2. Get full diff: `git diff <base>...<branch> --stat` + per-file diffs
3. Read the PR description (if on GitHub, use `gh pr view`)
4. Identify the Jira ticket from PR title/body/branch name
5. Count: files changed, lines added/removed, commits

### Phase 2: Per-File Analysis

For EACH changed file, check:

#### Code Quality
- [ ] No dead code, commented-out code, or TODOs without ticket
- [ ] No hardcoded secrets, credentials, or tokens
- [ ] No debug logs (console.log, System.out.println, print())
- [ ] Consistent naming conventions with the rest of the codebase
- [ ] No duplicated logic that should be extracted

#### Architecture & Patterns
- [ ] Follows existing patterns in the codebase (don't reinvent)
- [ ] No unnecessary abstractions or over-engineering
- [ ] Proper separation of concerns
- [ ] No circular dependencies introduced

#### Security
- [ ] No SQL injection, XSS, or command injection vectors
- [ ] Secrets not committed (check .env, credentials, API keys)
- [ ] Proper input validation at boundaries

#### YAML/OpenAPI Specific (if swagger/openapi files)
- [ ] Valid OpenAPI spec (run linter if available)
- [ ] All $ref references resolve
- [ ] Consistent naming (camelCase for schemas, snake_case for query params)
- [ ] operationId unique and follows naming convention
- [ ] All endpoints have proper response codes (2XX + at least one 4XX)
- [ ] Pagination pattern consistent (x-spring-paginated or Page wrappers)
- [ ] Security scheme applied

#### Config Files (.yaml, .xml, .json, .properties)
- [ ] No environment-specific values hardcoded (should be in config profiles)
- [ ] No sensitive data
- [ ] Consistent formatting with existing files

#### Pre-commit / CI Config
- [ ] Hook doesn't break existing workflows
- [ ] Hook runs against ALL affected files (not just new ones)
- [ ] Dependencies documented (what needs to be installed)
- [ ] Hook tested against the full repo, not just the changed files

### Phase 3: Cross-File Consistency

- [ ] Changes are coherent across files (no orphaned references)
- [ ] If schema changed, all consumers updated
- [ ] If config changed, documentation updated if needed
- [ ] Version numbers consistent where applicable

### Phase 4: Commit Hygiene

- [ ] Conventional Commits format on all commit messages
- [ ] Each commit is atomic (one logical change per commit)
- [ ] No merge commits (clean history)
- [ ] No giant commits mixing unrelated changes
- [ ] Commit messages accurately describe the change

### Phase 5: PR Quality

- [ ] PR title follows conventions
- [ ] PR description explains WHAT and WHY (not just HOW)
- [ ] Jira ticket linked
- [ ] No files included that shouldn't be (build artifacts, .DS_Store, etc.)
- [ ] Diff is minimal — no unnecessary formatting changes or whitespace

### Phase 6: Impact Assessment

- [ ] Does this change break any existing functionality?
- [ ] Does this change affect other teams/services?
- [ ] Are there migration steps needed?
- [ ] Run relevant validation tools (linters, tests, codegen)

## Output Format

Report must follow this exact structure:

```
## PR Review: <title>

### Summary
- Files: N changed (N+ / N-)
- Commits: N
- Scope: <brief description>

### Blockers (must fix before merge)
| # | File | Line | Issue |
|---|------|------|-------|
| 1 | ... | ... | ... |

### Warnings (should fix, not blocking)
| # | File | Issue |
|---|------|-------|
| 1 | ... | ... |

### Nits (optional improvements)
| # | File | Issue |
|---|------|-------|
| 1 | ... | ... |

### Positive
- What's good about this PR

### Verdict
APPROVE / REQUEST CHANGES / COMMENT
```

## Rules

1. **Be specific**: Always reference file:line when pointing out issues
2. **Be actionable**: Every issue must have a clear fix
3. **Prioritize**: Blockers > Warnings > Nits. Don't bury critical issues in a wall of nits
4. **Test claims**: If you say "this breaks X", verify it. Run the tool, check the ref, read the file
5. **No false positives**: Don't flag something unless you're sure it's wrong
6. **Acknowledge good work**: Always include a Positive section
7. **Context matters**: A placeholder hello-world file has different standards than production code
