---
name: add-shadcn-component
description: |
  Use this skill to add a new shadcn/ui component to a project.
  Trigger phrases: "add shadcn", "add component shadcn", "shadcn component", "/add-shadcn-component"
---

# Add shadcn/ui Component

This skill adds a new shadcn/ui component to a project's UI package.

## Arguments

```
/add-shadcn-component <component-name>
```

| Argument | Description | Required |
|----------|-------------|----------|
| component-name | Name of the shadcn component (e.g., dialog, tabs, accordion) | Yes |

## Examples

```bash
/add-shadcn-component dialog       # Add Dialog component
/add-shadcn-component accordion    # Add Accordion component
/add-shadcn-component tabs         # Add Tabs component
/add-shadcn-component dropdown-menu # Add DropdownMenu component
```

## Implementation

### 1. Detect Project Structure

Find the UI package location. Common patterns:
- `packages/ui/` (monorepo)
- `src/components/ui/` (standalone)
- Check for `components.json` in project root or ui package

### 2. Fetch Component Information

Get component code from shadcn documentation:
- URL: `https://ui.shadcn.com/docs/components/{component-name}`
- Extract the component source code
- Identify required Radix primitive dependency

### 3. Install Radix Dependency (if needed)

**Common Radix packages:**

| Component | Radix Package |
|-----------|---------------|
| accordion | @radix-ui/react-accordion |
| alert-dialog | @radix-ui/react-alert-dialog |
| avatar | @radix-ui/react-avatar |
| checkbox | @radix-ui/react-checkbox |
| collapsible | @radix-ui/react-collapsible |
| context-menu | @radix-ui/react-context-menu |
| dialog | @radix-ui/react-dialog |
| dropdown-menu | @radix-ui/react-dropdown-menu |
| hover-card | @radix-ui/react-hover-card |
| menubar | @radix-ui/react-menubar |
| navigation-menu | @radix-ui/react-navigation-menu |
| popover | @radix-ui/react-popover |
| progress | @radix-ui/react-progress |
| radio-group | @radix-ui/react-radio-group |
| scroll-area | @radix-ui/react-scroll-area |
| select | @radix-ui/react-select |
| separator | @radix-ui/react-separator |
| slider | @radix-ui/react-slider |
| switch | @radix-ui/react-switch |
| tabs | @radix-ui/react-tabs |
| toast | @radix-ui/react-toast |
| toggle | @radix-ui/react-toggle |
| toggle-group | @radix-ui/react-toggle-group |
| tooltip | @radix-ui/react-tooltip |

**Components without Radix dependency:**
- alert, badge, button, card, input, label, skeleton, textarea (HTML-based)

**Install command (monorepo):**
```bash
pnpm --filter <ui-package> add @radix-ui/react-<primitive>
```

**Install command (standalone):**
```bash
pnpm add @radix-ui/react-<primitive>
```

### 4. Create Component File

Create the component file in the appropriate location:
- Monorepo: `packages/ui/src/components/<component-name>.tsx`
- Standalone: `src/components/ui/<component-name>.tsx`

**Important adaptations:**
1. Update the `cn` utility import path:
   - shadcn default: `import { cn } from "@/lib/utils"`
   - Monorepo pattern: `import { cn } from "../lib/utils"`

2. Ensure all Tailwind classes use CSS variables (not hardcoded colors):
   - Use: `bg-primary`, `text-foreground`, `border-input`
   - Avoid: `bg-indigo-600`, `text-gray-900`, `border-gray-300`

### 5. Export Component

Add export to the package's index file:

```tsx
export {
  ComponentName,
  ComponentNameTrigger,  // If compound component
  ComponentNameContent,  // If compound component
  // ... other sub-components
} from "./components/<component-name>";
```

### 6. Verify

Run verification commands:
```bash
pnpm --filter <ui-package> typecheck
pnpm --filter <ui-package> lint
```

## Output

Report to user:
1. Component file created at: `<path>`
2. Radix dependency installed: `@radix-ui/react-<primitive>` (if applicable)
3. Export added to: `<index-file>`
4. Verification status: pass/fail

## Notes

- Always use CSS variable tokens for theming compatibility
- Test dark mode if the project supports it
- Generic/reusable components go in UI package
- Domain-specific components stay in app-level components
- If `components.json` exists, `pnpm ui:add <component>` may work directly
