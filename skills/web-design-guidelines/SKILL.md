---
name: web-design-guidelines
description: |
  Review UI code for Web Interface Guidelines compliance (Vercel standards).
  Trigger phrases: "design guidelines", "web guidelines", "vercel standards", "/web-design-guidelines"
---

# Web Design Guidelines

This skill reviews UI code for compliance with Web Interface Guidelines, ensuring high-quality, accessible, and performant web interfaces.

## Arguments

```
/web-design-guidelines <files> [--section=<section>]
```

| Argument | Description | Required |
|----------|-------------|----------|
| files | Files or patterns to audit | Yes |
| --section | Specific guideline section | No |

## Examples

```bash
/web-design-guidelines ./src/components/*.tsx
/web-design-guidelines ./src/app/page.tsx --section=accessibility
/web-design-guidelines ./src/components/Button.tsx
```

## Guidelines Source

Guidelines are based on Vercel's Web Interface Guidelines:
https://github.com/vercel-labs/web-interface-guidelines

## Audit Process

### 1. Fetch Guidelines

Always check for latest guidelines:
```
WebFetch: https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md
```

### 2. Read Target Files

Analyze the specified files for guideline compliance.

### 3. Apply Rules

Check each file against all applicable guidelines.

### 4. Output Findings

Report in `file:line` format with specific recommendations.

## Guideline Categories

### 1. Accessibility

| Rule | Description |
|------|-------------|
| A1 | All interactive elements must be keyboard accessible |
| A2 | Focus states must be visible |
| A3 | Color contrast must meet WCAG 2.1 AA (4.5:1 text, 3:1 UI) |
| A4 | Touch targets must be at least 44x44px |
| A5 | Images must have alt text |
| A6 | Forms must have associated labels |
| A7 | ARIA attributes must be valid |

### 2. Performance

| Rule | Description |
|------|-------------|
| P1 | Images must use next/image or optimized loading |
| P2 | Fonts should use font-display: swap |
| P3 | Third-party scripts should be loaded async/defer |
| P4 | CSS should avoid expensive selectors |
| P5 | Animations should use transform/opacity |

### 3. Responsiveness

| Rule | Description |
|------|-------------|
| R1 | Layouts must work from 320px to 2560px+ |
| R2 | Touch and mouse interactions both supported |
| R3 | Text must be readable without zooming |
| R4 | No horizontal scroll on mobile |

### 4. Semantics

| Rule | Description |
|------|-------------|
| S1 | Use semantic HTML elements (nav, main, article) |
| S2 | Heading hierarchy must be logical (h1 → h2 → h3) |
| S3 | Lists should use ul/ol elements |
| S4 | Buttons vs links used appropriately |

### 5. Forms

| Rule | Description |
|------|-------------|
| F1 | Inputs must have visible labels |
| F2 | Error messages must be specific and actionable |
| F3 | Required fields must be indicated |
| F4 | Autocomplete attributes should be set |
| F5 | Form submission must handle loading/error states |

### 6. Visual Design

| Rule | Description |
|------|-------------|
| V1 | Consistent spacing scale (4px/8px base) |
| V2 | Typography scale is coherent |
| V3 | Color palette is consistent |
| V4 | Icons are consistent style |
| V5 | Dark mode support (if applicable) |

## Output Format

```markdown
# Web Design Guidelines Audit

**Files:** src/components/LoginForm.tsx
**Date:** 2024-01-26
**Guidelines Version:** 1.0

## Summary

- Total Rules Checked: 25
- Passed: 20
- Failed: 3
- Warnings: 2

## Findings

### Failed

#### A2: Focus states must be visible
**File:** src/components/LoginForm.tsx:45
**Issue:** Button lacks focus-visible styles
**Code:**
```tsx
<button className="bg-blue-500 text-white">
```
**Fix:**
```tsx
<button className="bg-blue-500 text-white focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2">
```

#### A3: Color contrast insufficient
**File:** src/components/LoginForm.tsx:23
**Issue:** Placeholder text #999 on #fff = 2.8:1 (needs 4.5:1)
**Fix:** Use #767676 or darker for placeholder

#### F4: Missing autocomplete attribute
**File:** src/components/LoginForm.tsx:30
**Issue:** Email input missing autocomplete
**Code:**
```tsx
<input type="email" name="email" />
```
**Fix:**
```tsx
<input type="email" name="email" autocomplete="email" />
```

### Warnings

#### P5: Animation not using transform
**File:** src/components/LoginForm.tsx:67
**Issue:** Animating `left` property instead of `transform`
**Recommendation:** Use `transform: translateX()` for smoother animation

### Passed

- ✅ A1: Keyboard accessibility
- ✅ A5: Alt text present
- ✅ S1: Semantic HTML used
- ✅ R1: Responsive layout
- ... (18 more)

## Recommendations

1. Add focus-visible styles to all interactive elements
2. Increase placeholder contrast
3. Add autocomplete attributes to form inputs
4. Consider using CSS transforms for animations
```

## Automated Checks

The following can be automatically detected:

| Check | Method |
|-------|--------|
| Missing alt text | Search for `<img` without alt |
| Focus styles | Search for :focus/:focus-visible |
| Color contrast | Parse color values |
| Touch target size | Check width/height/padding |
| Semantic elements | Check for div-soup |
| Form labels | Match inputs to labels |
| Heading order | Parse h1-h6 hierarchy |

## Integration

### With ESLint

```json
{
  "extends": [
    "plugin:jsx-a11y/recommended"
  ]
}
```

### With Lighthouse

```bash
npx lighthouse https://mysite.com --only-categories=accessibility,best-practices
```

## Notes

- Guidelines should be applied contextually
- Some rules may not apply to all components
- Prioritize fixes by user impact
- Consider automated tooling for CI/CD integration
