---
name: ui-audit
description: |
  Perform automated UI audits evaluating interfaces against proven UX principles.
  Trigger phrases: "audit ui", "ui review", "check interface", "/ui-audit"
---

# UI Audit

This skill performs comprehensive UI audits evaluating interfaces against proven UX principles and design standards.

## Arguments

```
/ui-audit [target] [--section=<section>]
```

| Argument | Description | Required |
|----------|-------------|----------|
| target | File, component, or URL to audit | Yes |
| --section | Specific section to audit | No (audits all) |

## Examples

```bash
/ui-audit ./src/components/LoginForm.tsx
/ui-audit ./src/pages/Dashboard.tsx --section=accessibility
/ui-audit https://myapp.com/login
```

## Audit Framework

### Philosophy

**"Speed ≠ Recklessness"** - Designing quickly is not automatically reckless.

**Core Principle**: A design decision is "good" when it:
- Supports the product's Jobs-to-be-Done (JTBD)
- Aligns with company macro bets
- Respects constraints (time, tech, team)
- Balances user familiarity with differentiation

### Macro Bets Categories

| Category | Focus | Design Approach |
|----------|-------|-----------------|
| Velocity | Speed to market | Reuse patterns; cross-market metaphors |
| Efficiency | Waste reduction | Design systems; minimize WIP |
| Accuracy | Decision quality | Stronger research; instrumentation |
| Innovation | New potential | Novel patterns; cross-domain inspiration |

## Audit Sections

### 1. Visual Hierarchy (Always Include)

| Check | Criteria | Status |
|-------|----------|--------|
| Heading Distinction | Clear visual difference between H1-H6 | ⬜ |
| Primary Action Clarity | Main CTA stands out prominently | ⬜ |
| Grouping/Proximity | Related elements visually grouped | ⬜ |
| Reading Flow | Natural eye movement (F/Z pattern) | ⬜ |
| Type Scale | Consistent, purposeful size progression | ⬜ |
| Color Hierarchy | Color guides attention appropriately | ⬜ |
| Whitespace | Adequate breathing room between elements | ⬜ |
| Visual Weight Balance | Page doesn't feel lopsided | ⬜ |

### 2. Visual Style (Always Include)

| Check | Criteria | Status |
|-------|----------|--------|
| Spacing Consistency | Uses consistent spacing scale (4px/8px) | ⬜ |
| Color Palette | Adheres to defined color system | ⬜ |
| Elevation/Shadows | Consistent depth treatment | ⬜ |
| Typography System | Consistent font families and weights | ⬜ |
| Border/Radius | Consistent corner radius values | ⬜ |
| Icon Style | Icons match overall design language | ⬜ |
| Motion Principles | Animations feel cohesive | ⬜ |

### 3. Accessibility (Always Include)

| Check | Criteria | Status |
|-------|----------|--------|
| Keyboard Operability | All functions accessible via keyboard | ⬜ |
| Focus Visibility | Clear focus indicators on all interactive elements | ⬜ |
| Color Contrast | Minimum 4.5:1 for text, 3:1 for UI | ⬜ |
| Touch Targets | Minimum 44x44px for touch devices | ⬜ |
| Alt Text | Images have descriptive alt text | ⬜ |
| Semantic Markup | Proper HTML elements (button, nav, main) | ⬜ |
| Reduced Motion | Respects prefers-reduced-motion | ⬜ |

### 4. Navigation (When Relevant)

| Check | Criteria | Status |
|-------|----------|--------|
| Wayfinding | User always knows where they are | ⬜ |
| Breadcrumbs | Clear path back to previous levels | ⬜ |
| Menu Structure | Logical, scannable navigation | ⬜ |

### 5. Usability (When Relevant)

| Check | Criteria | Status |
|-------|----------|--------|
| Discoverability | Features are findable | ⬜ |
| Feedback | Actions provide clear feedback | ⬜ |
| Error Handling | Errors are clear and actionable | ⬜ |
| Cognitive Load | Not overwhelming users | ⬜ |

### 6. Forms (When Relevant)

| Check | Criteria | Status |
|-------|----------|--------|
| Labels | All inputs have visible labels | ⬜ |
| Validation | Clear, inline validation messages | ⬜ |
| Error Messaging | Specific, helpful error text | ⬜ |
| Autocomplete | Appropriate autocomplete attributes | ⬜ |

## Output Format

```markdown
# UI Audit Report

**Target:** LoginForm.tsx
**Date:** 2024-01-26
**Auditor:** Claude

## Summary

Overall Score: 7/10
- Visual Hierarchy: 8/10
- Visual Style: 7/10
- Accessibility: 6/10

## Findings

### Critical Issues
1. **Missing focus styles** (Accessibility)
   - Line 45: Button lacks :focus-visible style
   - Recommendation: Add `focus:ring-2 focus:ring-primary`

### Warnings
1. **Low contrast on placeholder** (Accessibility)
   - Line 23: Placeholder color #999 on #fff = 2.8:1
   - Recommendation: Use #767676 or darker

### Passes
- ✅ Clear heading hierarchy
- ✅ Primary CTA is prominent
- ✅ Consistent spacing

## Recommendations

1. Add focus-visible styles to all interactive elements
2. Increase placeholder contrast to 4.5:1
3. Add aria-describedby for error messages
```

## Notes

- Good design is **contextually appropriate**, not universally "correct"
- Consider the product's specific JTBD when evaluating
- Prioritize findings by impact on user experience
- Include specific line numbers and code suggestions
