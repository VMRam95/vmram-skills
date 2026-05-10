---
name: claude-code-usage
description: |
  Check Claude Code OAuth usage limits and token consumption.
  Trigger phrases: "usage", "limits", "tokens", "quota", "/claude-code-usage"
---

# Claude Code Usage

This skill checks your Claude Code OAuth usage limits and token consumption to help you manage your API usage effectively.

## Arguments

```
/claude-code-usage [period]
```

| Argument | Description | Required |
|----------|-------------|----------|
| period | Time period: today, week, month | No (default: today) |

## Usage

```bash
/claude-code-usage          # Check today's usage
/claude-code-usage today    # Check today's usage
/claude-code-usage week     # Check this week's usage
/claude-code-usage month    # Check this month's usage
```

## Implementation

### 1. Check Stats Cache

Read the stats cache file:

```bash
cat ~/.claude/stats-cache.json
```

This file contains:
- Token usage statistics
- Session information
- Model usage breakdown

### 2. Parse Usage Data

Extract relevant metrics:
- Total tokens used
- Input tokens
- Output tokens
- Number of requests
- Model breakdown (Sonnet, Opus, Haiku)

### 3. Calculate Limits

For OAuth users (Claude Max subscription):
- Check against daily/weekly limits
- Calculate remaining quota
- Estimate usage rate

### 4. Display Summary

Format output as:

```
Claude Code Usage Summary
========================

Period: Today (2024-01-26)

Tokens Used:
  - Input:  12,450 tokens
  - Output: 8,230 tokens
  - Total:  20,680 tokens

Requests: 45

Model Breakdown:
  - Sonnet:  35 requests (78%)
  - Opus:    8 requests (18%)
  - Haiku:   2 requests (4%)

Rate: ~1,722 tokens/hour
```

## Alternative: Direct API Check

If available, use Claude API to check account status:

```bash
# Check Anthropic account (if API key available)
curl -s https://api.anthropic.com/v1/usage \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01"
```

## Notes

- OAuth users have different limits than API key users
- Usage resets daily at midnight UTC
- Heavy Opus usage consumes quota faster
- Consider using Haiku for simple tasks to conserve quota
- Stats cache may have slight delay in updates
