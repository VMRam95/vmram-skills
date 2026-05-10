---
name: web-search-plus
description: |
  Unified web search with intelligent auto-routing across multiple providers.
  Trigger phrases: "search", "web search", "buscar", "/web-search-plus"
---

# Web Search Plus

This skill provides unified web search with intelligent auto-routing to get the best results for different query types.

## Arguments

```
/web-search-plus <query> [--provider=<provider>]
```

| Argument | Description | Required |
|----------|-------------|----------|
| query | Search query | Yes |
| --provider | Force specific provider | No (auto-routes) |

## Examples

```bash
/web-search-plus "react 19 new features 2024"
/web-search-plus "best practices typescript" --provider=brave
/web-search-plus "next.js app router documentation"
```

## Auto-Routing Logic

The skill automatically selects the best provider based on query type:

| Query Type | Provider | Why |
|------------|----------|-----|
| Technical/Programming | Brave Search | Better for code and technical content |
| Documentation | WebFetch + Docs | Direct source is more accurate |
| Current Events | Web Search | Real-time information |
| Academic/Research | Web Search | Broader coverage |
| Local Business | Brave Local | Location-aware results |

## Implementation

### 1. Analyze Query

Detect query type:
- Contains code keywords → Technical
- Contains "docs", "documentation", "api" → Documentation
- Contains dates, "news", "latest" → Current Events
- Contains location → Local

### 2. Route to Provider

```
Technical Query → Brave Search API
Documentation → Direct WebFetch to docs site
General Query → WebSearch tool
Local Query → Brave Local Search
```

### 3. Execute Search

**Using WebSearch (default):**
```
WebSearch: "query here"
```

**Using Brave (MCP if available):**
```
mcp__brave-search__brave_web_search(query="...")
```

**Direct Documentation:**
```
WebFetch: https://docs.example.com/search?q=...
```

### 4. Process Results

1. Filter irrelevant results
2. Extract key information
3. Provide source links
4. Summarize findings

## Output Format

```markdown
# Search Results: "react 19 new features"

## Top Results

### 1. React 19 Release Notes
**Source:** [react.dev/blog/react-19](https://react.dev/blog/react-19)

Key features:
- Actions for handling async operations
- New use() hook for promises
- Server Components improvements
- Document metadata support

### 2. What's New in React 19
**Source:** [blog.example.com](https://blog.example.com/react-19)

Summary: React 19 introduces Actions, a new way to handle...

## Quick Answer

React 19's main new features are:
1. **Actions** - Simplified async state management
2. **use() hook** - Read promises in render
3. **Server Components** - Improved streaming
4. **Metadata** - Native title/meta tag support

---
*Sources: 5 results from Brave Search, fetched 2024-01-26*
```

## Provider Details

### Brave Search
- Best for: Technical queries, privacy-focused
- Features: No tracking, independent index
- Tool: `mcp__brave-search__brave_web_search`

### WebSearch (Claude)
- Best for: General queries, current events
- Features: Built-in, always available
- Tool: `WebSearch`

### WebFetch
- Best for: Known URLs, documentation
- Features: Full page content extraction
- Tool: `WebFetch`

## Tips

1. **Be specific** - Include version numbers, dates
2. **Use quotes** - For exact phrases
3. **Add context** - "typescript" vs "javascript typescript"
4. **Specify year** - "react hooks 2024" for current info

## Notes

- Always cite sources in responses
- Verify critical information from multiple sources
- Use WebFetch for following up on specific results
- Consider rate limits on external APIs
