---
name: add-email-template
description: |
  Add a new email template to the email-service. Creates project if needed,
  generates professional HTML, inserts in Supabase DB, and creates migration file.
  Trigger phrases: "add email template", "create email template", "new template",
  "crear template", "añadir template", "/add-email-template"
---

# Add Email Template

Creates a new email template in the email-service. Handles everything: project creation (if needed), HTML generation, DB insertion via Supabase MCP, and migration file creation for reproducibility.

## Email Service Details

| Property | Value |
|----------|-------|
| Supabase Project ID | `vxirigqzqixsihyunazf` |
| DB Schema | `email_admin` |
| Production URL | `https://email-service-opal-seven.vercel.app` |
| Email-service repo | `~/Documentos/repositories/email-service` |
| Template engine | Handlebars |
| Template ID format | `category/slug` (e.g., `my-app/welcome`) |

## Arguments

```
/add-email-template [category/slug]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `category/slug` | No | If provided, pre-sets both values. Otherwise prompted |

## Examples

```bash
/add-email-template                                          # Interactive - asks everything
/add-email-template shopify-commission-engine/monthly-billing # Pre-sets category and slug
```

## Implementation

Follow these steps IN ORDER. Execute each step automatically using the tools indicated.

### Step 1: Gather template information

If `category/slug` was provided as argument, extract both values. Otherwise, use **AskUserQuestion** to collect all information:

**Question 1 - Template identity:**
- **Project slug** (category): kebab-case identifier for the project (e.g., `shopify-commission-engine`)
- **Project display name**: human-readable name (e.g., "Shopify Commission Engine") — only if project doesn't exist yet
- **Template slug**: kebab-case identifier for this template (e.g., `monthly-billing`)
- **Template display name**: human-readable (e.g., "Monthly Billing")

**Question 2 - Template content:**
- **Subject line**: with Handlebars variables (e.g., `"Invoice for {{storeName}} - {{period}}"`)
- **Variables**: comma-separated with required flag (e.g., `clientName (required), dashboardUrl (optional)`)
- **Description**: purpose of the email (e.g., "Monthly billing summary sent to clients")

**Question 3 - Email style:**
Options (single select):
- **Professional** (Recommended) — Clean corporate style, dark header, CTA button
- **Transactional** — Minimal, text-focused, no heavy branding
- **Marketing** — Colorful, multiple sections, hero image area
- **Custom HTML** — User provides their own HTML

### Step 2: Get admin user_id

Execute SQL via **Supabase MCP** (`project_id: vxirigqzqixsihyunazf`):

```sql
SELECT user_id, role FROM email_admin.admin_users WHERE is_active = true LIMIT 5;
```

- If multiple results -> use the first `super_admin`
- If zero results -> STOP and inform user they need an admin user in the email-service first

Store the selected `user_id` for all subsequent operations.

### Step 3: Check/create project

Check if the project already exists:

```sql
SELECT id, name, slug FROM email_admin.projects WHERE slug = '{{category}}';
```

- If exists -> use the existing `project_id`, skip creation
- If not exists -> create it:

```sql
INSERT INTO email_admin.projects (name, slug, description, is_active, created_by, updated_by)
VALUES ('{{project_name}}', '{{category}}', '{{description}}', true, '{{user_id}}', '{{user_id}}')
RETURNING id, name, slug;
```

Save the `project_id` for subsequent steps.

### Step 4: Check for existing template

```sql
SELECT id, name, slug, category FROM email_admin.templates
WHERE category = '{{category}}' AND slug = '{{slug}}';
```

- If exists -> ask user: **Update existing** or **Abort**?
- If not exists -> proceed to create

### Step 5: Generate email HTML

Generate professional, email-client-safe HTML based on the selected style and variables.

**IMPORTANT rules for email HTML:**
- Use `<table>` layout ONLY (no `<div>` for structure)
- ALL styles must be inline (`style="..."`)
- Use `cellpadding="0" cellspacing="0"` on all tables
- Max width 600px for the content area
- Use web-safe fonts: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- Use `{{variableName}}` for Handlebars variables
- Use `{{{variableName}}}` for variables containing HTML (triple braces = unescaped)
- Use `{{#if varName}}...{{/if}}` for conditional sections
- Available helpers: `{{year}}`, `{{date}}`, `{{uppercase text}}`, `{{lowercase text}}`

**Base HTML structure for Professional style:**

```html
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;padding:40px 20px">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden">

<!-- HEADER -->
<tr><td style="background-color:#18181b;padding:32px;text-align:center">
<h1 style="color:#ffffff;margin:0;font-size:24px">{{HEADER_TITLE}}</h1>
</td></tr>

<!-- BODY -->
<tr><td style="padding:32px">
<!-- Main content with variables here -->
<p style="color:#27272a;font-size:16px;line-height:1.6;margin:0 0 16px">{{GREETING}}</p>
<p style="color:#27272a;font-size:16px;line-height:1.6;margin:0 0 24px">{{BODY_TEXT}}</p>

<!-- Optional data table for structured info -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px;border:1px solid #e4e4e7;border-radius:6px;overflow:hidden">
<tr><td style="padding:12px 16px;background-color:#f4f4f5;border-bottom:1px solid #e4e4e7;font-weight:600;color:#27272a;font-size:14px">{{LABEL}}</td>
<td style="padding:12px 16px;border-bottom:1px solid #e4e4e7;color:#27272a;font-size:14px">{{VALUE}}</td></tr>
</table>

<!-- Optional CTA button -->
{{#if actionUrl}}
<table cellpadding="0" cellspacing="0" style="margin:0 auto">
<tr><td style="background-color:#18181b;border-radius:6px;padding:12px 24px">
<a href="{{actionUrl}}" style="color:#ffffff;text-decoration:none;font-size:16px;font-weight:600">{{actionText}}</a>
</td></tr></table>
{{/if}}
</td></tr>

<!-- FOOTER -->
<tr><td style="padding:24px 32px;background-color:#f4f4f5;text-align:center">
<p style="color:#71717a;font-size:13px;margin:0">&copy; {{year}} {{APP_NAME}}</p>
</td></tr>

</table>
</td></tr></table>
</body></html>
```

**Adapt the base HTML** to the specific template purpose:
- Replace placeholder sections with actual content using the provided variables
- Add/remove data table rows based on variables
- Include conditional sections (`{{#if}}`) for optional variables
- For Transactional style: remove the colored header, use simpler layout
- For Marketing style: add hero section, multiple content blocks, brand colors

**CRITICAL:** Escape single quotes in the HTML for SQL insertion: replace `'` with `''` inside the SQL string.

### Step 6: Insert template via Supabase MCP

Execute via **Supabase MCP** (`project_id: vxirigqzqixsihyunazf`):

```sql
INSERT INTO email_admin.templates (
  name, slug, subject, html, description, variables, category,
  project_id, is_active, owner_id, created_by, updated_by
) VALUES (
  '{{template_name}}',
  '{{slug}}',
  '{{subject}}',
  E'{{escaped_html}}',
  '{{description}}',
  '{{variables_jsonb}}'::jsonb,
  '{{category}}',
  '{{project_id}}',
  true,
  '{{user_id}}', '{{user_id}}', '{{user_id}}'
)
ON CONFLICT (category, slug) DO UPDATE SET
  name = EXCLUDED.name,
  html = EXCLUDED.html,
  subject = EXCLUDED.subject,
  variables = EXCLUDED.variables,
  description = EXCLUDED.description,
  updated_by = EXCLUDED.updated_by,
  updated_at = NOW()
RETURNING id, name, slug, category;
```

**Variables JSONB format:**
```json
[
  {"name": "clientName", "required": true},
  {"name": "storeName", "required": true},
  {"name": "dashboardUrl", "required": false}
]
```

### Step 7: Create migration file

Determine the next migration number by listing existing files in `~/Documentos/repositories/email-service/supabase/migrations/`.

Create file: `~/Documentos/repositories/email-service/supabase/migrations/{{NNN}}_{{category}}_{{slug}}_template.sql`

The migration file should contain:
1. Comment header explaining the template
2. The project INSERT (with `ON CONFLICT DO NOTHING`)
3. The template INSERT (with `ON CONFLICT DO UPDATE`)

Example:

```sql
-- Template: {{category}}/{{slug}}
-- Description: {{description}}

-- Ensure project exists
INSERT INTO email_admin.projects (name, slug, description, is_active)
VALUES ('{{project_name}}', '{{category}}', '{{project_description}}', true)
ON CONFLICT (slug) DO NOTHING;

-- Create/update template
INSERT INTO email_admin.templates (
  name, slug, subject, html, description, variables, category,
  project_id, is_active, owner_id, created_by, updated_by
)
SELECT
  '{{template_name}}',
  '{{slug}}',
  '{{subject}}',
  E'{{escaped_html}}',
  '{{description}}',
  '{{variables_jsonb}}'::jsonb,
  '{{category}}',
  p.id,
  true,
  u.user_id, u.user_id, u.user_id
FROM email_admin.projects p
CROSS JOIN (
  SELECT user_id FROM email_admin.admin_users
  WHERE role = 'super_admin' AND is_active = true
  ORDER BY created_at ASC LIMIT 1
) u
WHERE p.slug = '{{category}}'
ON CONFLICT (category, slug) DO UPDATE SET
  html = EXCLUDED.html,
  subject = EXCLUDED.subject,
  variables = EXCLUDED.variables,
  description = EXCLUDED.description,
  updated_at = NOW();
```

### Step 8: Update client email utility (if in a project context)

If running inside a project that already has an email utility module (e.g., `src/lib/email.ts`):

1. **Detect the email utility file** by searching for `EMAIL_SERVICE_URL`, `sendEmail`, or similar patterns
2. **Add a typed wrapper function** for the new template:

```typescript
export async function sendMonthlyBilling(
  email: string,
  data: { clientName: string; storeName: string; period: string; dashboardUrl?: string }
): Promise<boolean> {
  return sendEmail({
    template: "{{category}}/{{slug}}",
    to: email,
    data: { ...data, appName: "{{appName}}" },
  });
}
```

3. If no email utility exists, suggest running `/integrate-email-service` first

### Step 9: Show summary

Display to the user:

```markdown
## Template Created

| Property | Value |
|----------|-------|
| Template ID | `{{category}}/{{slug}}` |
| Name | {{template_name}} |
| Subject | {{subject}} |
| Variables | {{var1}}, {{var2}}, ... |
| Project | {{project_name}} ({{category}}) |
| Migration | `supabase/migrations/{{NNN}}_....sql` |

### Usage example:

```javascript
await fetch('https://email-service-opal-seven.vercel.app/api/send', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': process.env.EMAIL_SERVICE_API_KEY,
  },
  body: JSON.stringify({
    template: '{{category}}/{{slug}}',
    to: 'user@example.com',
    data: {
      {{var1}}: 'value1',
      {{var2}}: 'value2',
    }
  }),
});
```

### With typed wrapper (if email utility exists):

```typescript
import { sendMonthlyBilling } from "@/lib/email";

await sendMonthlyBilling("user@example.com", {
  clientName: "Acme Corp",
  storeName: "acme-store",
  period: "January 2026",
});
```

### With attachment (PDF):

```javascript
body: JSON.stringify({
  template: '{{category}}/{{slug}}',
  to: 'user@example.com',
  data: { ... },
  attachments: [{
    filename: 'document.pdf',
    content: '<base64-encoded-pdf>',
    contentType: 'application/pdf'
  }]
})
```
```

## Error Handling

- **No admin users found:** Inform user to create an admin in the email-service admin panel first
- **Project slug conflict:** Use existing project, inform user
- **Template already exists:** Ask user whether to update or abort
- **Supabase MCP not available:** Inform user to configure Supabase MCP server
- **HTML too large:** Warn if HTML exceeds 50KB (email clients may clip)

## Notes

- The `category` field MUST match the project `slug` exactly — this routes emails to the correct SMTP config
- Templates use Handlebars: `{{var}}` for escaped, `{{{var}}}` for raw HTML
- Built-in helpers: `{{year}}`, `{{date}}`, `{{uppercase x}}`, `{{lowercase x}}`
- The `ON CONFLICT (category, slug)` ensures idempotent execution
- Migration files allow reproducing templates across environments
- Subject line also supports Handlebars variables
- Attachments are a separate feature of `/api/send`, not part of the template itself
- **The email service API is stack-agnostic** — any language/framework can consume templates via HTTP POST
