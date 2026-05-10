---
name: add-analytics
description: |
  Add custom Supabase analytics + optional GA4 to any Next.js project.
  Creates DB table, tracking library, API route, React hook, and integrates
  event tracking into existing components. GDPR-compliant via cookie consent.
  Trigger phrases: "add analytics", "analytics", "add tracking", "integrar analytics", "/add-analytics"
---

# Add Analytics

Adds a complete analytics system to any Next.js project:
- **Supabase custom analytics** — first-party data, full ownership
- **GA4 integration** — optional, bridges events via existing AnalyticsLoader
- **Cookie consent integration** — only tracks when user consents to analytics cookies
- **Event tracking** — page views, button clicks, form submissions, navigation, external links

## Reference Implementation

This skill is based on the analytics system built for `stick-crisis-landing`. Use these files as reference:

| File | Path |
|------|------|
| Analytics library | `~/Documentos/repositories/stick-crisis-landing/src/lib/analytics.ts` |
| useAnalytics hook | `~/Documentos/repositories/stick-crisis-landing/src/hooks/useAnalytics.ts` |
| AnalyticsTracker | `~/Documentos/repositories/stick-crisis-landing/src/components/analytics/AnalyticsTracker.tsx` |
| API route | `~/Documentos/repositories/stick-crisis-landing/src/app/api/analytics/event/route.ts` |
| Window types | `~/Documentos/repositories/stick-crisis-landing/src/types/window.d.ts` |

## Prerequisites

The target project MUST have:
- Next.js 14+ with App Router
- Supabase integration (client + server)
- Cookie consent system with analytics category (use `/add-legal-pages` first if missing)
- `useCookieConsent` hook returning `{ hasConsented, preferences }`

## Arguments

```
/add-analytics [project-path]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `project-path` | No | Path to the project. If omitted, uses current working directory |

## Implementation

### Phase 1: Gather Project Information

Use `AskUserQuestion` to collect:

**Question 1 — Events to track (multiSelect):**
- Page views (automatic on route change)
- Button clicks (CTA buttons, download links)
- Form submissions (newsletter, contact, feedback)
- Navigation clicks (header/footer links)
- Language switcher usage
- External link clicks (social media, etc.)

**Question 2 — GA4:**
- Do you have a GA4 Measurement ID? (Yes + provide ID / No, skip GA4 / No, help me create one)

**Question 3 — Supabase details:**
- Supabase project ID (for migration)
- Schema name (default: detect from project's Supabase client config)

### Phase 2: Detect Project Structure

Read the project to understand:

1. **Supabase client**: Find server client file (e.g., `src/lib/supabase/server.ts`) — note the import path and schema
2. **Cookie consent**: Find `useCookieConsent` hook — note the import path
3. **Layout file**: Find `src/app/[locale]/layout.tsx` or `src/app/layout.tsx`
4. **Existing AnalyticsLoader**: Check if `AnalyticsLoader` component exists (from `/add-legal-pages`)
5. **Components to track**: Identify all components from Question 1 that need event tracking
6. **i18n**: Check if project uses `next-intl` (for locale tracking)
7. **Constants file**: Find where constants are defined (for storage keys)
8. **Middleware**: Verify `/api` routes are excluded from i18n middleware

### Phase 3: Create Supabase Migration

Apply migration via Supabase MCP (`mcp__supabase__apply_migration`):

```sql
CREATE TABLE {schema}.analytics_events (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  event_name VARCHAR(100) NOT NULL,
  event_category VARCHAR(50) NOT NULL,
  session_id VARCHAR(64) NOT NULL,
  visitor_id VARCHAR(64),
  page_path VARCHAR(500) NOT NULL,
  page_title VARCHAR(200),
  referrer VARCHAR(1000),
  utm_source VARCHAR(200),
  utm_medium VARCHAR(200),
  utm_campaign VARCHAR(200),
  device_type VARCHAR(20),
  browser VARCHAR(50),
  os VARCHAR(50),
  screen_width SMALLINT,
  screen_height SMALLINT,
  locale VARCHAR(10),
  properties JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Indexes
CREATE INDEX idx_analytics_events_created_at ON {schema}.analytics_events (created_at DESC);
CREATE INDEX idx_analytics_events_event_name ON {schema}.analytics_events (event_name);
CREATE INDEX idx_analytics_events_event_category ON {schema}.analytics_events (event_category);
CREATE INDEX idx_analytics_events_page_path ON {schema}.analytics_events (page_path);
CREATE INDEX idx_analytics_events_session_id ON {schema}.analytics_events (session_id);
CREATE INDEX idx_analytics_events_visitor_id ON {schema}.analytics_events (visitor_id);
CREATE INDEX idx_analytics_events_name_created ON {schema}.analytics_events (event_name, created_at DESC);

-- RLS
ALTER TABLE {schema}.analytics_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anonymous event inserts"
  ON {schema}.analytics_events FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "Deny public reads"
  ON {schema}.analytics_events FOR SELECT TO anon USING (false);
```

Replace `{schema}` with the project's Supabase schema.

### Phase 4: Create Analytics Library

Read the reference file `~/Documentos/repositories/stick-crisis-landing/src/lib/analytics.ts` and adapt it to the target project:

Create `src/lib/analytics.ts` with:

- **Session ID**: `crypto.randomUUID()` stored in `sessionStorage` (key: `{prefix}-session-id`)
- **Visitor ID**: `crypto.randomUUID()` stored in `localStorage` (key: `{prefix}-visitor-id`)
- **Event delivery**: `navigator.sendBeacon()` with `fetch` fallback, posts to `/api/analytics/event`
- **Device detection**: Lightweight UA parsing for browser/OS, screen dimensions
- **UTM parsing**: Reads `utm_source`, `utm_medium`, `utm_campaign` from URL params
- **GA4 bridge**: If `window.gtag` exists, also fires event via `gtag('event', ...)`

**Public API** — create helper functions based on the events selected in Phase 1:

```typescript
export function setLocale(locale: string): void
export function trackEvent(name: string, category: EventCategory, properties?: Record<string, unknown>): void
export function trackPageView(): void
// Add per selected events:
export function trackDownloadClick(location: string): void
export function trackFormSubmit(formName: string): void
export function trackNavClick(target: string): void
export function trackLanguageSwitch(from: string, to: string): void
export function trackExternalLink(url: string, label: string): void
// ... etc based on user's selections
```

### Phase 5: Create Window Types

Create `src/types/window.d.ts`:

```typescript
interface Window {
  gtag?: (...args: unknown[]) => void;
  dataLayer?: unknown[];
}
```

### Phase 6: Create useAnalytics Hook

Read the reference file `~/Documentos/repositories/stick-crisis-landing/src/hooks/useAnalytics.ts` and adapt:

Create `src/hooks/useAnalytics.ts`:

- Imports `useCookieConsent` from the project's hook path
- `isEnabled = hasConsented && preferences.analytics`
- Auto-tracks page views on `usePathname()` changes (only when enabled)
- Sets locale from `useLocale()` if project uses `next-intl`
- Returns memoized tracking functions that no-op when disabled

### Phase 7: Create AnalyticsTracker Component

Create `src/components/analytics/AnalyticsTracker.tsx`:

```typescript
"use client";

import { useAnalytics } from "@/hooks/useAnalytics";

export function AnalyticsTracker() {
  useAnalytics();
  return null;
}
```

### Phase 8: Create API Route

Read the reference file `~/Documentos/repositories/stick-crisis-landing/src/app/api/analytics/event/route.ts` and adapt:

Create `src/app/api/analytics/event/route.ts`:

- **Rate limiting**: 30 events/min/IP using in-memory Map
- **Validation**: Whitelist of allowed event names and categories
- **Sanitization**: Truncate all string fields to max lengths
- **Storage**: Insert into `analytics_events` via Supabase service role client
- **Error handling**: Never expose internal errors, return generic messages

Define `ALLOWED_EVENT_NAMES` based on the events selected in Phase 1.

### Phase 9: Integrate into Layout

Add `<AnalyticsTracker />` to the locale layout (or root layout), inside `CookieConsentProvider`:

```tsx
import { AnalyticsTracker } from "@/components/analytics/AnalyticsTracker";

// Inside layout, alongside AnalyticsLoader:
<AnalyticsLoader />
<AnalyticsTracker />
```

### Phase 10: Add Event Tracking to Components

For each component/interaction selected in Phase 1:

1. Import `useAnalytics` hook
2. Destructure the relevant tracking function
3. Add `onClick` handler or call after successful action

**Pattern for click tracking (buttons, links):**
```tsx
const { trackDownloadClick } = useAnalytics();
<a href={url} onClick={() => trackDownloadClick("hero")}>
```

**Pattern for form submission tracking:**
```tsx
const { trackFormSubmit } = useAnalytics();
// After successful submission:
showToast("Success!");
trackFormSubmit("newsletter");
```

**Pattern for navigation tracking:**
```tsx
const { trackNavClick } = useAnalytics();
<Link href="/about" onClick={() => trackNavClick("/about")}>
```

### Phase 11: Update .env.example

Add if GA4 is enabled:
```env
# Google Analytics (optional)
NEXT_PUBLIC_GA_MEASUREMENT_ID=G-XXXXXXXXXX
```

### Phase 12: Verify

1. Run `npm run build` — no errors
2. Accept analytics cookies in the app
3. Navigate pages → check Supabase `analytics_events` table for `page_view` events
4. Click tracked buttons → verify events appear with correct `event_name` and `properties`
5. Reject cookies → verify NO events are sent (check browser Network tab)
6. If GA4 enabled → check Google Analytics Real-Time report

## Event Taxonomy

Standard event names (adapt per project):

| event_name | event_category | When fired | properties |
|---|---|---|---|
| `page_view` | `pageview` | Every route change | `{}` |
| `download_click` | `conversion` | CTA/download button click | `{ "location": "hero" }` |
| `form_submit` | `conversion` | Successful form submission | `{ "form": "newsletter" }` |
| `nav_click` | `navigation` | Navigation link click | `{ "target": "/about" }` |
| `language_switch` | `engagement` | Language changed | `{ "from": "en", "to": "es" }` |
| `external_link` | `engagement` | External link clicked | `{ "target_url": "...", "link_label": "..." }` |

## Privacy

- No PII stored (no IPs, no emails)
- Only tracks with cookie consent (`preferences.analytics === true`)
- Session ID is ephemeral (sessionStorage — dies with tab)
- Visitor ID is anonymous UUID (localStorage — persistent but not PII)
- GA4 uses `anonymize_ip: true`
- RLS prevents public reads of analytics data

## Notes

- The analytics library is pure TypeScript — no React dependency, can be used in API routes too
- `navigator.sendBeacon()` ensures events survive page navigation/unload
- Rate limiting prevents abuse but allows normal browsing (30 events/min is generous)
- Ad blockers may block GA4 but not first-party Supabase analytics (same-origin requests)
- For admin dashboard visualization, see the stick-crisis-admin implementation at `~/Documentos/repositories/stick-crisis-admin/src/app/analytics/`
