---
name: integrate-email-service
description: |
  Integrate any project with the email-service API. Creates project, SMTP config,
  API key, templates, and env vars automatically via Supabase MCP.
  Trigger phrases: "integrate email", "email service", "setup email", "integrar email", "/integrate-email-service"
---

# Integrate Email Service

Automates the full integration of any project with the email-service API. Supports two modes:

- **Client-only integration** (most common): Generate email utility code + env vars for a project that will consume the email API. No Supabase MCP needed.
- **Full admin setup**: Create project, SMTP config, API key, and templates in the email-service database. Requires Supabase MCP or direct DB access.

## Email Service Details

| Property | Value |
|----------|-------|
| Production URL | `https://email-service-opal-seven.vercel.app` |
| Supabase Project ID | `vxirigqzqixsihyunazf` |
| DB Schema | `email_admin` |
| API Key Format | `es-{32 hex chars}` |
| Encryption | AES-256-CBC |
| Email-service repo | `<EMAIL_SERVICE_REPO>` |

## API Reference

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/send` | POST | `X-API-Key` header | Send email (template or custom HTML) |
| `/api/templates` | GET | None | List available templates |
| `/api/health` | GET | None | Health check |

### Send with template

```json
POST /api/send
{
  "template": "my-project/welcome",
  "to": "user@example.com",
  "data": { "name": "John", "appName": "MyApp" }
}
```

### Send with custom HTML

```json
POST /api/send
{
  "to": "user@example.com",
  "subject": "Hello!",
  "html": "<h1>Content</h1>"
}
```

### Send with attachments

```json
POST /api/send
{
  "template": "my-project/invoice",
  "to": "user@example.com",
  "data": { ... },
  "attachments": [{
    "filename": "invoice.pdf",
    "content": "<base64-encoded>",
    "contentType": "application/pdf"
  }]
}
```

## Arguments

```
/integrate-email-service [project-slug]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `project-slug` | No | If provided, used as slug. Otherwise prompted |

## Examples

```bash
/integrate-email-service                    # Interactive - asks everything
/integrate-email-service customer-portal    # Pre-sets slug, asks the rest
```

## Implementation

Follow these steps IN ORDER. Execute each step automatically using the tools indicated.

### Step 1: Determine integration mode

Use **AskUserQuestion** to ask:

> How do you want to integrate the email service?
>
> **A) Client-only integration** (Recommended for most projects)
> Your project already has a project + API key in the email-service, or someone will set them up separately. I'll generate the email utility code and configure env vars.
>
> **B) Full admin setup**
> Create a new project, SMTP config, API key, and templates from scratch. Requires Supabase MCP access to the email-service database.

- If **A** → go to **Step 2A**
- If **B** → go to **Step 2B**

---

## Path A: Client-Only Integration

### Step 2A: Gather project information

Use **AskUserQuestion** to collect:

**Question 1 - Project details:**
- **Project slug** (used as template namespace, e.g., `my-project`)
- **App display name** (used in templates, e.g., "My Project")
- **API key** — if they already have one. If not, tell them to ask an admin or run `/integrate-email-service` with full setup mode

**Question 2 - Templates to use:**
Which email templates does the project need? (multiSelect)
- Welcome email
- Email verification
- Password reset
- Contact form confirmation
- Contact form admin notification
- Newsletter welcome
- Custom notification
- Other (describe)

**Question 3 - Integration pattern:**
- **Fire-and-forget** (non-critical emails, errors logged but don't block) — recommended for most cases
- **Await response** (email delivery is critical to the operation)
- **Mixed** (some critical, some not)

### Step 3A: Detect project stack

Analyze the current working directory to detect:
- **Language**: TypeScript / JavaScript / Python / Go / etc.
- **Framework**: Next.js / Express / Fastify / Django / etc.
- **Server-side env prefix**: `NEXT_PUBLIC_` / `VITE_` / none
- **Existing patterns**: Look for existing fetch wrappers, API clients, env var patterns

### Step 4A: Generate email utility module

Based on the detected stack, generate a reusable email utility module. The module MUST follow the **vetcraft pattern** (proven in production):

#### TypeScript/Next.js pattern (reference implementation):

Create file at the appropriate location (e.g., `src/lib/email.ts`, `lib/email.ts`, `utils/email.ts`):

```typescript
/**
 * Email service client.
 * Uses the shared email-service API for template-based email delivery.
 */

const EMAIL_SERVICE_URL = process.env["EMAIL_SERVICE_URL"];
const EMAIL_SERVICE_API_KEY = process.env["EMAIL_SERVICE_API_KEY"];

interface EmailPayload {
  template: string;
  to: string;
  data: Record<string, string | number>;
}

interface CustomEmailPayload {
  to: string;
  subject: string;
  html: string;
}

type SendPayload = EmailPayload | CustomEmailPayload;

/**
 * Send an email via the email service API.
 * Returns true on success, false on failure. Never throws.
 */
export async function sendEmail(payload: SendPayload): Promise<boolean> {
  if (!EMAIL_SERVICE_URL || !EMAIL_SERVICE_API_KEY) {
    console.warn("[Email] Email service not configured, skipping");
    return false;
  }

  try {
    const res = await fetch(`${EMAIL_SERVICE_URL}/api/send`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": EMAIL_SERVICE_API_KEY,
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const label = "template" in payload ? payload.template : payload.subject;
      console.error(`[Email] Failed to send "${label}": ${res.status}`);
      return false;
    }
    return true;
  } catch (error) {
    console.error("[Email] Error sending email:", error);
    return false;
  }
}
```

Then generate **typed wrapper functions** for each selected template:

```typescript
// --- Typed wrappers for each template ---

export async function sendWelcomeEmail(
  email: string,
  name: string
): Promise<boolean> {
  return sendEmail({
    template: "{{slug}}/welcome",
    to: email,
    data: { name, appName: "{{appName}}" },
  });
}

export async function sendVerificationEmail(
  email: string,
  verificationLink: string
): Promise<boolean> {
  return sendEmail({
    template: "{{slug}}/email-verification",
    to: email,
    data: { verificationLink, appName: "{{appName}}" },
  });
}

// ... etc. for each selected template
```

**Key design decisions to follow:**
1. `sendEmail()` NEVER throws — returns boolean
2. Graceful degradation: if env vars missing, logs warning and returns false
3. Each template gets a typed wrapper function with explicit parameters
4. Template IDs use format: `{project-slug}/{template-slug}`
5. Server-side only — API key must NOT be exposed to the client

#### Python pattern:

```python
import os
import logging
import httpx

EMAIL_SERVICE_URL = os.getenv("EMAIL_SERVICE_URL")
EMAIL_SERVICE_API_KEY = os.getenv("EMAIL_SERVICE_API_KEY")

logger = logging.getLogger(__name__)

async def send_email(*, template: str, to: str, data: dict) -> bool:
    if not EMAIL_SERVICE_URL or not EMAIL_SERVICE_API_KEY:
        logger.warning("Email service not configured, skipping")
        return False
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{EMAIL_SERVICE_URL}/api/send",
                json={"template": template, "to": to, "data": data},
                headers={"X-API-Key": EMAIL_SERVICE_API_KEY},
            )
            if res.status_code != 200:
                logger.error(f"Failed to send {template}: {res.status_code}")
                return False
            return True
    except Exception as e:
        logger.error(f"Error sending {template}: {e}")
        return False
```

#### Go pattern:

```go
package email

import (
    "bytes"
    "encoding/json"
    "fmt"
    "log"
    "net/http"
    "os"
)

var (
    serviceURL = os.Getenv("EMAIL_SERVICE_URL")
    apiKey     = os.Getenv("EMAIL_SERVICE_API_KEY")
)

type Payload struct {
    Template string            `json:"template"`
    To       string            `json:"to"`
    Data     map[string]string `json:"data"`
}

func Send(p Payload) bool {
    if serviceURL == "" || apiKey == "" {
        log.Println("[Email] Service not configured, skipping")
        return false
    }
    body, _ := json.Marshal(p)
    req, _ := http.NewRequest("POST", serviceURL+"/api/send", bytes.NewReader(body))
    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("X-API-Key", apiKey)
    resp, err := http.DefaultClient.Do(req)
    if err != nil {
        log.Printf("[Email] Error sending %s: %v\n", p.Template, err)
        return false
    }
    defer resp.Body.Close()
    if resp.StatusCode != 200 {
        log.Printf("[Email] Failed %s: %d\n", p.Template, resp.StatusCode)
        return false
    }
    return true
}
```

### Step 5A: Add environment variables

Detect which env file exists in the **current working directory**:

1. Check for `.env.local`, `.env`, `.env.development` (in that order)
2. If none exists, create `.env.local`
3. Append (do NOT overwrite existing content):

```env
# Email Service
EMAIL_SERVICE_URL=https://email-service-opal-seven.vercel.app
EMAIL_SERVICE_API_KEY={{api_key_or_placeholder}}
```

**Rules for env var naming:**
- Server-side only (recommended): `EMAIL_SERVICE_URL`, `EMAIL_SERVICE_API_KEY`
- If the project ONLY runs server-side (API server, CLI tool): use plain names
- If Next.js and URL is needed client-side: `NEXT_PUBLIC_EMAIL_SERVICE_URL` for the URL only
- **NEVER** expose the API key to the client: always `EMAIL_SERVICE_API_KEY` (no public prefix)

### Step 6A: Show summary and usage examples

Display:

```markdown
## Integration Complete

**Email utility:** `src/lib/email.ts` (or wherever created)
**Env vars added to:** `.env.local`

### Usage — Fire-and-forget (non-critical):

import { sendWelcomeEmail } from "@/lib/email";

// Won't throw, won't block — logs errors silently
void sendWelcomeEmail("user@example.com", "John");

### Usage — Await response (critical):

import { sendVerificationEmail } from "@/lib/email";

const sent = await sendVerificationEmail(email, link);
if (!sent) {
  // Handle failure (retry, show error, etc.)
}

### Usage — Custom HTML (no template):

import { sendEmail } from "@/lib/email";

await sendEmail({
  to: "user@example.com",
  subject: "Custom subject",
  html: "<h1>Hello</h1><p>Custom content</p>",
});

### Available templates:

| Template ID | Variables |
|-------------|-----------|
| {{slug}}/welcome | name, appName |
| ... | ... |
```

**Done.** Path A ends here.

---

## Path B: Full Admin Setup

### Step 2B: Gather project information

Use **AskUserQuestion** to collect:

**Question 1 - Project details:**
- Project name (e.g., "Customer Portal")
- Project slug (e.g., `customer-portal`) — if not passed as argument
- Short description

**Question 2 - SMTP configuration:**
- SMTP host (e.g., `smtp.sendgrid.net`, `mail.example.com`)
- SMTP port (`587` for STARTTLS, `465` for SSL)
- SMTP secure (`true` for 465, `false` for 587)
- SMTP user (email or username)
- SMTP password
- From email (sender address)
- From name (display name)
- Reply-to email (optional)

**Question 3 - Templates to create (multiSelect):**
- Welcome email
- Password reset
- Email verification
- Generic notification
- Custom template (user defines details)

The email-service production URL is already known: `https://email-service-opal-seven.vercel.app` — do NOT ask the user for it.

### Step 3B: Get admin user_id

Execute SQL via **Supabase MCP** (`project_id: vxirigqzqixsihyunazf`):

```sql
SELECT user_id, role FROM email_admin.admin_users WHERE is_active = true LIMIT 5;
```

- If multiple results -> ask user which to use
- If zero results -> STOP and inform the user they must first create an admin user in the email-service admin panel

Store the selected `user_id` for all subsequent operations.

### Step 4B: Check for existing project

```sql
SELECT id, name, slug FROM email_admin.projects WHERE slug = '{{slug}}';
```

- If exists -> ask user: reuse existing or abort?
- If not exists -> proceed to create

### Step 5B: Create the project

```sql
INSERT INTO email_admin.projects (name, slug, description, is_active, created_by, updated_by)
VALUES ('{{name}}', '{{slug}}', '{{description}}', true, '{{user_id}}', '{{user_id}}')
RETURNING id, name, slug;
```

Save the returned `project_id` for subsequent steps.

### Step 6B: Generate API Key

```sql
INSERT INTO email_admin.api_keys (user_id, api_key, name, is_active)
VALUES (
  '{{user_id}}',
  'es-' || encode(gen_random_bytes(16), 'hex'),
  '{{project_name}} - Production',
  true
)
RETURNING id, api_key, name;
```

**IMPORTANT:** Save the returned `api_key` value — it will be added to the target project's env vars.

### Step 7B: Encrypt SMTP password and create config

**7a. Read encryption key from email-service .env:**

Use the **Read** tool to read `<EMAIL_SERVICE_REPO>/.env` and extract the `GMAIL_ENCRYPTION_KEY` value.

**7b. Encrypt password via Bash + Node.js:**

```bash
node -e "
const crypto = require('crypto');
const key = Buffer.from('{{GMAIL_ENCRYPTION_KEY}}', 'hex');
const iv = crypto.randomBytes(16);
const cipher = crypto.createCipheriv('aes-256-cbc', key, iv);
let enc = cipher.update('{{SMTP_PASSWORD}}', 'utf8', 'hex');
enc += cipher.final('hex');
console.log(iv.toString('hex') + ':' + enc);
"
```

Save the output as `encrypted_password`.

**7c. Insert SMTP config:**

```sql
INSERT INTO email_admin.project_smtp_configs (
  project_id, project_name, smtp_host, smtp_port, smtp_secure,
  smtp_user, smtp_password_encrypted, from_email, from_name,
  reply_to_email, is_active, is_verified, created_by, updated_by
) VALUES (
  '{{project_id}}', '{{slug}}', '{{smtp_host}}', {{smtp_port}}, {{smtp_secure}},
  '{{smtp_user}}', '{{encrypted_password}}', '{{from_email}}', '{{from_name}}',
  {{reply_to_or_null}}, true, false, '{{user_id}}', '{{user_id}}'
) RETURNING id, project_name, smtp_host;
```

### Step 8B: Create templates

For each selected template, execute the corresponding INSERT. The `category` field MUST match the project `slug`.

#### Template: Welcome Email

```sql
INSERT INTO email_admin.templates (
  name, slug, subject, html, description, variables, category,
  project_id, is_active, owner_id, created_by, updated_by
) VALUES (
  'Welcome Email',
  'welcome',
  'Welcome to {{appName}}, {{name}}!',
  E'<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,''Segoe UI'',Roboto,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;padding:40px 20px">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden">
<tr><td style="background-color:#18181b;padding:32px;text-align:center">
<h1 style="color:#ffffff;margin:0;font-size:24px">Welcome!</h1>
</td></tr>
<tr><td style="padding:32px">
<p style="color:#27272a;font-size:16px;line-height:1.6;margin:0 0 16px">Hi <strong>{{name}}</strong>,</p>
<p style="color:#27272a;font-size:16px;line-height:1.6;margin:0 0 24px">Thanks for joining <strong>{{appName}}</strong>. We''re glad to have you on board.</p>
{{#if actionUrl}}
<table cellpadding="0" cellspacing="0" style="margin:0 auto">
<tr><td style="background-color:#18181b;border-radius:6px;padding:12px 24px">
<a href="{{actionUrl}}" style="color:#ffffff;text-decoration:none;font-size:16px;font-weight:600">{{actionText}}</a>
</td></tr></table>
{{/if}}
</td></tr>
<tr><td style="padding:24px 32px;background-color:#f4f4f5;text-align:center">
<p style="color:#71717a;font-size:13px;margin:0">&copy; {{year}} {{appName}}</p>
</td></tr>
</table>
</td></tr></table>
</body></html>',
  'Welcome email sent to new users after registration',
  ''[{"name":"name","required":true},{"name":"appName","required":true},{"name":"actionUrl","required":false},{"name":"actionText","required":false}]'',
  '{{slug}}',
  '{{project_id}}',
  true,
  '{{user_id}}', '{{user_id}}', '{{user_id}}'
) RETURNING id, name, slug;
```

#### Template: Password Reset

```sql
INSERT INTO email_admin.templates (
  name, slug, subject, html, description, variables, category,
  project_id, is_active, owner_id, created_by, updated_by
) VALUES (
  'Password Reset',
  'reset-password',
  'Reset your password - {{appName}}',
  E'<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,''Segoe UI'',Roboto,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;padding:40px 20px">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden">
<tr><td style="background-color:#18181b;padding:32px;text-align:center">
<h1 style="color:#ffffff;margin:0;font-size:24px">Password Reset</h1>
</td></tr>
<tr><td style="padding:32px">
<p style="color:#27272a;font-size:16px;line-height:1.6;margin:0 0 16px">Hi <strong>{{name}}</strong>,</p>
<p style="color:#27272a;font-size:16px;line-height:1.6;margin:0 0 24px">We received a request to reset your password. Click the button below to set a new one.</p>
<table cellpadding="0" cellspacing="0" style="margin:0 auto">
<tr><td style="background-color:#18181b;border-radius:6px;padding:12px 24px">
<a href="{{resetLink}}" style="color:#ffffff;text-decoration:none;font-size:16px;font-weight:600">Reset Password</a>
</td></tr></table>
<p style="color:#71717a;font-size:14px;line-height:1.6;margin:24px 0 0">This link expires in <strong>{{expirationTime}}</strong>. If you didn''t request this, you can safely ignore this email.</p>
</td></tr>
<tr><td style="padding:24px 32px;background-color:#f4f4f5;text-align:center">
<p style="color:#71717a;font-size:13px;margin:0">&copy; {{year}} {{appName}}</p>
</td></tr>
</table>
</td></tr></table>
</body></html>',
  'Password reset email with secure link and expiration',
  ''[{"name":"name","required":true},{"name":"resetLink","required":true},{"name":"expirationTime","required":true},{"name":"appName","required":true}]'',
  '{{slug}}',
  '{{project_id}}',
  true,
  '{{user_id}}', '{{user_id}}', '{{user_id}}'
) RETURNING id, name, slug;
```

#### Template: Email Verification

```sql
INSERT INTO email_admin.templates (
  name, slug, subject, html, description, variables, category,
  project_id, is_active, owner_id, created_by, updated_by
) VALUES (
  'Email Verification',
  'verify-email',
  'Verify your email - {{appName}}',
  E'<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,''Segoe UI'',Roboto,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;padding:40px 20px">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden">
<tr><td style="background-color:#18181b;padding:32px;text-align:center">
<h1 style="color:#ffffff;margin:0;font-size:24px">Verify Your Email</h1>
</td></tr>
<tr><td style="padding:32px">
<p style="color:#27272a;font-size:16px;line-height:1.6;margin:0 0 16px">Hi <strong>{{name}}</strong>,</p>
<p style="color:#27272a;font-size:16px;line-height:1.6;margin:0 0 24px">Please verify your email address by clicking the button below.</p>
<table cellpadding="0" cellspacing="0" style="margin:0 auto">
<tr><td style="background-color:#18181b;border-radius:6px;padding:12px 24px">
<a href="{{verificationLink}}" style="color:#ffffff;text-decoration:none;font-size:16px;font-weight:600">Verify Email</a>
</td></tr></table>
<p style="color:#71717a;font-size:14px;line-height:1.6;margin:24px 0 0">If you didn''t create an account, you can safely ignore this email.</p>
</td></tr>
<tr><td style="padding:24px 32px;background-color:#f4f4f5;text-align:center">
<p style="color:#71717a;font-size:13px;margin:0">&copy; {{year}} {{appName}}</p>
</td></tr>
</table>
</td></tr></table>
</body></html>',
  'Email verification with confirmation link',
  ''[{"name":"name","required":true},{"name":"verificationLink","required":true},{"name":"appName","required":true}]'',
  '{{slug}}',
  '{{project_id}}',
  true,
  '{{user_id}}', '{{user_id}}', '{{user_id}}'
) RETURNING id, name, slug;
```

#### Template: Generic Notification

```sql
INSERT INTO email_admin.templates (
  name, slug, subject, html, description, variables, category,
  project_id, is_active, owner_id, created_by, updated_by
) VALUES (
  'Notification',
  'notification',
  '{{title}}',
  E'<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,''Segoe UI'',Roboto,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;padding:40px 20px">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden">
<tr><td style="background-color:#18181b;padding:32px;text-align:center">
<h1 style="color:#ffffff;margin:0;font-size:24px">{{title}}</h1>
</td></tr>
<tr><td style="padding:32px">
<p style="color:#27272a;font-size:16px;line-height:1.6;margin:0 0 24px">{{{message}}}</p>
{{#if actionUrl}}
<table cellpadding="0" cellspacing="0" style="margin:0 auto">
<tr><td style="background-color:#18181b;border-radius:6px;padding:12px 24px">
<a href="{{actionUrl}}" style="color:#ffffff;text-decoration:none;font-size:16px;font-weight:600">{{actionText}}</a>
</td></tr></table>
{{/if}}
</td></tr>
<tr><td style="padding:24px 32px;background-color:#f4f4f5;text-align:center">
<p style="color:#71717a;font-size:13px;margin:0">&copy; {{year}} {{appName}}</p>
</td></tr>
</table>
</td></tr></table>
</body></html>',
  'Generic notification email with optional action button. Message supports HTML via triple braces.',
  ''[{"name":"title","required":true},{"name":"message","required":true},{"name":"appName","required":true},{"name":"actionUrl","required":false},{"name":"actionText","required":false}]'',
  '{{slug}}',
  '{{project_id}}',
  true,
  '{{user_id}}', '{{user_id}}', '{{user_id}}'
) RETURNING id, name, slug;
```

#### Template: Custom

If the user selected "Custom template", ask them for:
- Template name and slug
- Subject line (with Handlebars variables)
- HTML content (or generate a basic one from a text description)
- Variables list
- Description

Then build the INSERT following the same pattern as above.

### Step 9B: Generate client code + env vars

After all admin setup is complete, **automatically run Path A Steps 4A-6A** to generate the email utility module, env vars, and usage examples in the target project. Use the API key generated in Step 6B.

### Step 10B: Show full summary

Display:

```markdown
## Integration Complete

**Project:** {{name}} ({{slug}})
**API Key:** es-xxxxxxxxxxxxxxxxxxxxxxxxxxxx
**SMTP:** {{smtp_host}}:{{smtp_port}} ({{from_email}})
**Templates created:** welcome, reset-password, verify-email, notification
**Email utility:** src/lib/email.ts
**Env file updated:** .env.local

### Available templates:

| Template ID | Variables |
|-------------|-----------|
| {{slug}}/welcome | name, appName, actionUrl?, actionText? |
| {{slug}}/reset-password | name, resetLink, expirationTime, appName |
| {{slug}}/verify-email | name, verificationLink, appName |
| {{slug}}/notification | title, message, appName, actionUrl?, actionText? |
```

---

## Error Handling

- **No admin users found:** Inform user to create an admin in the email-service first
- **Project slug already exists:** Ask if they want to reuse or abort
- **SMTP config already exists for slug:** Ask if they want to update or skip
- **Encryption key not found:** Inform user that `GMAIL_ENCRYPTION_KEY` must be set in email-service .env
- **Supabase MCP not available:** Inform user to configure the Supabase MCP server (only for Path B)

## Notes

- The `category` field in templates MUST match the project `slug` exactly — this is how the email-service routes emails to the correct SMTP config
- SMTP passwords are encrypted with AES-256-CBC before storage; the encryption key is read from the email-service .env file
- The email-service sends emails with this priority: Project SMTP > API key owner config > System default
- API keys are validated on every `/api/send` request via the `X-API-Key` header
- Templates use Handlebars syntax: `{{variable}}` for escaped output, `{{{variable}}}` for raw HTML
- Built-in Handlebars helpers: `{{year}}`, `{{date}}`, `{{uppercase text}}`, `{{lowercase text}}`
- **The email service is stack-agnostic** — any project that can make HTTP POST requests can use it. No Supabase, Vercel, or specific framework required on the client side.
