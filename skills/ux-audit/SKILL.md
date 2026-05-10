---
name: ux-audit
description: |
  Perform automated UX audits evaluating user experience against proven design principles.
  Trigger phrases: "audit ux", "ux review", "user experience audit", "/ux-audit"
---

# UX Audit

This skill performs comprehensive UX audits evaluating user experience against proven design principles and usability heuristics.

## Arguments

```
/ux-audit [target] [--focus=<area>]
```

| Argument | Description | Required |
|----------|-------------|----------|
| target | Flow, feature, or page to audit | Yes |
| --focus | Specific area: onboarding, forms, navigation | No |

## Examples

```bash
/ux-audit ./src/pages/checkout      # Audit checkout flow
/ux-audit "user registration"       # Audit a user flow
/ux-audit ./src/app --focus=navigation
```

## UX Framework

### 3 Pillars of UX Decisions

1. **Scaffolding** - Automated rules for recurring decisions
2. **Decisioning** - Process methodology for new choices
3. **Crafting** - Execution checklists for quality delivery

### Information Weighting (Decision Process)

When making UX decisions, weight information in this order:
1. **Institutional knowledge** - Existing patterns, brand, constraints
2. **User familiarity** - Conventions, competitor patterns
3. **Research evidence** - Testing, analytics, studies

### Good UX Decisions Are...

**Contextually Appropriate** when they:
- Support the product's Jobs-to-be-Done (JTBD)
- Align with company macro bets (Velocity, Efficiency, Accuracy, Innovation)
- Respect operational constraints
- Balance user familiarity against differentiation needs

## Audit Sections

### 1. User Flow Analysis

| Check | Criteria | Status |
|-------|----------|--------|
| Task Completion | Can users complete primary tasks? | ⬜ |
| Step Count | Minimum necessary steps to goal | ⬜ |
| Cognitive Load | Information presented manageably | ⬜ |
| Error Recovery | Easy to fix mistakes | ⬜ |
| Progress Indication | Users know where they are in flow | ⬜ |

### 2. Onboarding (When Relevant)

| Check | Criteria | Status |
|-------|----------|--------|
| First-Run Experience | Clear initial guidance | ⬜ |
| Value Demonstration | Shows benefit quickly | ⬜ |
| Progressive Disclosure | Reveals complexity gradually | ⬜ |
| Skip Option | Can skip non-essential steps | ⬜ |
| Empty States | Helpful guidance when no data | ⬜ |

### 3. Feedback & Communication

| Check | Criteria | Status |
|-------|----------|--------|
| Action Confirmation | Success states are clear | ⬜ |
| Loading States | Users know system is working | ⬜ |
| Error Messages | Specific, actionable, friendly | ⬜ |
| Status Updates | Real-time feedback where needed | ⬜ |
| Undo Capability | Reversible actions where possible | ⬜ |

### 4. Navigation & Wayfinding

| Check | Criteria | Status |
|-------|----------|--------|
| Current Location | User always knows where they are | ⬜ |
| Navigation Clarity | Menu structure is logical | ⬜ |
| Back Navigation | Easy to return to previous state | ⬜ |
| Search Function | Can find content efficiently | ⬜ |
| Shortcuts | Power users have quick paths | ⬜ |

### 5. Content & Microcopy

| Check | Criteria | Status |
|-------|----------|--------|
| Clarity | Language is simple and direct | ⬜ |
| Consistency | Terminology is consistent | ⬜ |
| Tone | Matches brand voice | ⬜ |
| Actionability | CTAs are clear and specific | ⬜ |
| Help Text | Context-sensitive guidance | ⬜ |

### 6. Trust & Social Proof

| Check | Criteria | Status |
|-------|----------|--------|
| Credibility Signals | Trust indicators present | ⬜ |
| Security Indicators | Users feel safe | ⬜ |
| Testimonials/Reviews | Social proof where helpful | ⬜ |
| Transparency | Clear about data usage, pricing | ⬜ |

### 7. Accessibility & Inclusion

| Check | Criteria | Status |
|-------|----------|--------|
| Screen Reader | Content is accessible | ⬜ |
| Keyboard Navigation | Full keyboard operability | ⬜ |
| Color Independence | Not relying solely on color | ⬜ |
| Reading Level | Appropriate for audience | ⬜ |
| Internationalization | Ready for localization | ⬜ |

## Nielsen's 10 Heuristics Reference

1. **Visibility of system status**
2. **Match between system and real world**
3. **User control and freedom**
4. **Consistency and standards**
5. **Error prevention**
6. **Recognition rather than recall**
7. **Flexibility and efficiency of use**
8. **Aesthetic and minimalist design**
9. **Help users recognize, diagnose, recover from errors**
10. **Help and documentation**

## Output Format

```markdown
# UX Audit Report

**Feature:** User Registration Flow
**Date:** 2024-01-26
**Auditor:** Claude

## Executive Summary

The registration flow is functional but has friction points that may impact conversion. Key issues relate to form complexity and unclear error handling.

## Flow Analysis

**Steps to Complete:** 5 screens
**Estimated Time:** 3-4 minutes
**Drop-off Risk:** High on step 3 (payment)

## Findings by Severity

### Critical (Blocking)
1. **No error recovery on payment failure**
   - Users must restart entire flow
   - Impact: High abandonment risk
   - Recommendation: Allow retry without re-entering data

### Major (Significant Friction)
1. **Password requirements hidden**
   - Requirements only shown on error
   - Impact: User frustration, extra attempts
   - Recommendation: Show requirements proactively

### Minor (Polish)
1. **No progress indicator**
   - Users don't know how many steps remain
   - Impact: Uncertainty, potential abandonment
   - Recommendation: Add step indicator (e.g., "Step 2 of 4")

## Recommendations

### Quick Wins
- Add progress indicator
- Show password requirements upfront
- Add "show password" toggle

### Larger Improvements
- Implement payment retry without restart
- Add save-and-continue later
- Reduce to 3 steps via form consolidation

## Metrics to Track

- Registration completion rate
- Time to complete
- Drop-off by step
- Error rate by field
```

## Notes

- Focus on user goals, not just interface
- Consider the full user journey, not just screens
- Test with real users when possible
- Prioritize by impact on user success
