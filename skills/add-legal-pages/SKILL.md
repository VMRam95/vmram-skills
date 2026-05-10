---
name: add-legal-pages
description: |
  Add GDPR-compliant legal pages (Privacy Policy, Terms of Service) and cookie consent system
  to any Next.js project with next-intl i18n and Tailwind CSS.
  Trigger phrases: "add legal pages", "privacy policy", "terms of service", "cookie consent", "GDPR", "legal section", "/add-legal-pages"
---

# Add Legal Pages & Cookie Consent

Adds a complete GDPR-compliant legal framework to a Next.js project:
- **Privacy Policy** page with 12 sections
- **Terms of Service** page with 10 sections
- **Cookie Consent** system (banner + preferences modal + analytics loader)
- **i18n translations** (English + Spanish)
- **Footer integration** with links to legal pages and cookie preferences

## Prerequisites

The target project MUST have:
- Next.js 14+ with App Router
- `next-intl` for i18n (with `[locale]` route segment)
- Tailwind CSS
- `framer-motion` (for cookie banner animations)

## Arguments

```
/add-legal-pages [project-path]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `project-path` | No | Path to the project. If omitted, uses current working directory |

## Examples

```bash
/add-legal-pages                                    # Current project
/add-legal-pages ~/projects/my-next-app             # Specific project
```

## Implementation

### Phase 1: Gather Project Information

Use `AskUserQuestion` to collect:

**Question 1: Contact Info**
- Contact email address (e.g., `info@example.com`)
- Company/developer name (e.g., "VMRam95")

**Question 2: Project Details**
- Project/app name (e.g., "Stick Crisis")
- Website hosting provider (default: Vercel)
- Database provider (default: Supabase)

**Question 3: Social Media** (optional)
- Instagram username (if applicable)
- Other social links

**Question 4: Legal Jurisdiction**
- Country for governing law (default: Spain)

### Phase 2: Detect Project Structure

Read the project to understand:

1. **i18n setup**: Check `src/i18n/` or `i18n/` for navigation config (Link component import path)
2. **Messages location**: Find `messages/en.json` and `messages/es.json` (or equivalent)
3. **Types file**: Find `src/types/index.ts` or equivalent
4. **Constants file**: Find `src/lib/constants.ts` or equivalent
5. **Layout file**: Find `src/app/[locale]/layout.tsx`
6. **Footer component**: Find footer for link integration
7. **UI components**: Check if `PixelButton`, `Modal`, or equivalent button/modal components exist
8. **Utility functions**: Check for `cn()` (clsx/twMerge) utility
9. **Design tokens**: Read existing Tailwind classes to match the project's design system

### Phase 3: Create Types

Add to the project's types file:

```typescript
// Cookie Consent Types
export type CookieCategory = "essential" | "analytics" | "marketing";

export interface CookiePreferences {
  essential: boolean;
  analytics: boolean;
  marketing: boolean;
}

export interface CookieConsentState {
  hasConsented: boolean;
  consentedAt: string | null;
  preferences: CookiePreferences;
}
```

### Phase 4: Add Constants

Add to the project's constants file:

```typescript
export const COOKIE_CONSENT_KEY = "{project-prefix}-cookie-consent";
export const COOKIE_CATEGORIES = ["essential", "analytics", "marketing"] as const;
```

Replace `{project-prefix}` with a short prefix derived from the project name (e.g., `sc` for Stick Crisis).

### Phase 5: Create Cookie Components

Create `src/components/cookie/` directory with these files:

#### 5.1 CookieConsentProvider.tsx

Context provider managing consent state:
- Reads/writes to `localStorage` using `COOKIE_CONSENT_KEY`
- Default preferences: `{ essential: true, analytics: false, marketing: false }`
- Shows banner after 500ms delay if no consent exists
- Methods: `acceptAll()`, `rejectAll()`, `savePreferences()`, `openPreferences()`, `closePreferences()`

```typescript
"use client";

import {
  createContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";
import { COOKIE_CONSENT_KEY } from "@/lib/constants";
import type { CookiePreferences, CookieConsentState } from "@/types";

export interface CookieConsentContextValue {
  hasConsented: boolean;
  preferences: CookiePreferences;
  showBanner: boolean;
  showPreferences: boolean;
  acceptAll: () => void;
  rejectAll: () => void;
  savePreferences: (prefs: CookiePreferences) => void;
  openPreferences: () => void;
  closePreferences: () => void;
}

const DEFAULT_PREFERENCES: CookiePreferences = {
  essential: true,
  analytics: false,
  marketing: false,
};

const DEFAULT_STATE: CookieConsentState = {
  hasConsented: false,
  consentedAt: null,
  preferences: DEFAULT_PREFERENCES,
};

export const CookieConsentContext = createContext<
  CookieConsentContextValue | undefined
>(undefined);

function readFromStorage(): CookieConsentState | null {
  try {
    const stored = localStorage.getItem(COOKIE_CONSENT_KEY);
    if (!stored) return null;
    return JSON.parse(stored) as CookieConsentState;
  } catch {
    return null;
  }
}

function writeToStorage(state: CookieConsentState): void {
  try {
    localStorage.setItem(COOKIE_CONSENT_KEY, JSON.stringify(state));
  } catch {
    // localStorage not available
  }
}

export function CookieConsentProvider({ children }: { children: ReactNode }) {
  const [consentState, setConsentState] =
    useState<CookieConsentState>(DEFAULT_STATE);
  const [showBanner, setShowBanner] = useState(false);
  const [showPreferences, setShowPreferences] = useState(false);

  useEffect(() => {
    const stored = readFromStorage();
    if (stored?.hasConsented) {
      setConsentState(stored);
    } else {
      const timer = setTimeout(() => setShowBanner(true), 500);
      return () => clearTimeout(timer);
    }
  }, []);

  const persistConsent = useCallback((preferences: CookiePreferences) => {
    const state: CookieConsentState = {
      hasConsented: true,
      consentedAt: new Date().toISOString(),
      preferences: { ...preferences, essential: true },
    };
    setConsentState(state);
    writeToStorage(state);
    setShowBanner(false);
    setShowPreferences(false);
  }, []);

  const acceptAll = useCallback(() => {
    persistConsent({ essential: true, analytics: true, marketing: true });
  }, [persistConsent]);

  const rejectAll = useCallback(() => {
    persistConsent(DEFAULT_PREFERENCES);
  }, [persistConsent]);

  const savePreferences = useCallback(
    (prefs: CookiePreferences) => {
      persistConsent(prefs);
    },
    [persistConsent]
  );

  const openPreferences = useCallback(() => setShowPreferences(true), []);
  const closePreferences = useCallback(() => setShowPreferences(false), []);

  return (
    <CookieConsentContext.Provider
      value={{
        hasConsented: consentState.hasConsented,
        preferences: consentState.preferences,
        showBanner,
        showPreferences,
        acceptAll,
        rejectAll,
        savePreferences,
        openPreferences,
        closePreferences,
      }}
    >
      {children}
    </CookieConsentContext.Provider>
  );
}
```

#### 5.2 CookieConsentBanner.tsx

Bottom-fixed banner with Framer Motion slide-up animation:
- Three buttons: "Essential Only" (ghost), "Customize" (secondary), "Accept All" (primary)
- Shield icon in accent color
- Uses project's button component (adapt to project)

```typescript
"use client";

import { useTranslations } from "next-intl";
import { motion, AnimatePresence } from "framer-motion";
import { useCookieConsent } from "@/hooks/useCookieConsent";

export function CookieConsentBanner() {
  const t = useTranslations("cookieConsent.banner");
  const { showBanner, acceptAll, rejectAll, openPreferences } =
    useCookieConsent();

  return (
    <AnimatePresence>
      {showBanner && (
        <motion.div
          initial={{ y: 100, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 100, opacity: 0 }}
          transition={{ type: "spring", damping: 25, stiffness: 300 }}
          className="fixed bottom-0 left-0 right-0 z-[60] bg-{card}/95 backdrop-blur-md border-t border-{border}"
        >
          <div className="container mx-auto px-4 py-4">
            <div className="flex flex-col md:flex-row items-start md:items-center gap-4">
              <div className="flex items-start gap-3 flex-1 min-w-0">
                <span className="text-{accent} mt-0.5 shrink-0">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                </span>
                <div>
                  <h3 className="font-heading text-sm text-{heading} tracking-wide">{t("title")}</h3>
                  <p className="text-{secondary} text-xs mt-0.5">{t("description")}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 w-full md:w-auto shrink-0">
                {/* Adapt buttons to project's button component */}
                <button onClick={rejectAll} className="flex-1 md:flex-none ...">{t("rejectAll")}</button>
                <button onClick={openPreferences} className="flex-1 md:flex-none ...">{t("customize")}</button>
                <button onClick={acceptAll} className="flex-1 md:flex-none ...">{t("acceptAll")}</button>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

**IMPORTANT**: Adapt the `{card}`, `{border}`, `{accent}`, `{heading}`, `{secondary}` placeholders to the project's actual Tailwind classes/design tokens. Use the project's existing button component if available.

#### 5.3 CookiePreferencesModal.tsx

Modal with toggle switches per cookie category:
- Uses project's modal component (or create one)
- Essential cookies always on + disabled toggle
- Local state synced with global preferences
- Badge system: "Always Active" (green) for essential, "Optional" for others

```typescript
"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { CookieToggle } from "./CookieToggle";
import { useCookieConsent } from "@/hooks/useCookieConsent";
import { COOKIE_CATEGORIES } from "@/lib/constants";
import type { CookieCategory, CookiePreferences } from "@/types";

export function CookiePreferencesModal() {
  const t = useTranslations("cookieConsent.preferences");
  const { showPreferences, closePreferences, preferences, savePreferences } =
    useCookieConsent();

  const [localPrefs, setLocalPrefs] = useState<CookiePreferences>(preferences);

  if (showPreferences && localPrefs !== preferences) {
    setLocalPrefs(preferences);
  }

  const handleToggle = (category: CookieCategory, checked: boolean) => {
    if (category === "essential") return;
    setLocalPrefs((prev) => ({ ...prev, [category]: checked }));
  };

  const handleSave = () => savePreferences(localPrefs);

  if (!showPreferences) return null;

  return (
    // Adapt modal wrapper to project's modal component
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-{card} border border-{border} rounded-lg p-6 max-w-md w-full mx-4">
        <h2 className="font-heading text-lg text-{heading} tracking-wide">{t("title")}</h2>
        <p className="text-{secondary} text-sm mb-6">{t("description")}</p>
        <div className="space-y-4">
          {COOKIE_CATEGORIES.map((category) => (
            <div key={category} className="flex items-center justify-between gap-4 p-3 rounded-lg bg-{surface} border border-{border}">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-heading text-sm text-{primary} tracking-wide">
                    {t(`categories.${category}.title`)}
                  </span>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${
                    category === "essential"
                      ? "text-green-400 border-green-400/30 bg-green-400/10"
                      : "text-gray-400 border-gray-400/30 bg-gray-400/10"
                  }`}>
                    {t(`categories.${category}.badge`)}
                  </span>
                </div>
                <p className="text-{muted} text-xs mt-1">{t(`categories.${category}.description`)}</p>
              </div>
              <CookieToggle
                checked={category === "essential" ? true : localPrefs[category]}
                onChange={(checked) => handleToggle(category, checked)}
                disabled={category === "essential"}
                label={t(`categories.${category}.title`)}
              />
            </div>
          ))}
        </div>
        <div className="flex items-center justify-end gap-2 mt-6 pt-4 border-t border-{border}">
          <button onClick={closePreferences}>{t("cancel")}</button>
          <button onClick={handleSave}>{t("save")}</button>
        </div>
      </div>
    </div>
  );
}
```

#### 5.4 CookieToggle.tsx

Accessible toggle switch:

```typescript
"use client";

interface CookieToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label: string;
}

export function CookieToggle({ checked, onChange, disabled = false, label }: CookieToggleProps) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => !disabled && onChange(!checked)}
      disabled={disabled}
      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 transition-colors duration-200 ${
        checked ? "bg-green-500 border-green-500" : "bg-gray-700 border-gray-600"
      } ${disabled ? "opacity-60 cursor-not-allowed" : ""}`}
    >
      <span className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg transform transition-transform duration-200 ${
        checked ? "translate-x-5" : "translate-x-0"
      }`} />
    </button>
  );
}
```

#### 5.5 AnalyticsLoader.tsx

Conditional Google Analytics loader:

```typescript
"use client";

import Script from "next/script";
import { useCookieConsent } from "@/hooks/useCookieConsent";

const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;

export function AnalyticsLoader() {
  const { preferences, hasConsented } = useCookieConsent();

  if (!hasConsented || !preferences.analytics) return null;
  if (!GA_MEASUREMENT_ID) return null;

  return (
    <>
      <Script
        src={`https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`}
        strategy="afterInteractive"
      />
      <Script id="google-analytics" strategy="afterInteractive">
        {`
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', '${GA_MEASUREMENT_ID}', { anonymize_ip: true });
        `}
      </Script>
    </>
  );
}
```

#### 5.6 index.ts (barrel export)

```typescript
export { CookieConsentProvider } from "./CookieConsentProvider";
export { CookieConsentBanner } from "./CookieConsentBanner";
export { CookiePreferencesModal } from "./CookiePreferencesModal";
export { CookieToggle } from "./CookieToggle";
export { AnalyticsLoader } from "./AnalyticsLoader";
```

### Phase 6: Create Cookie Hook

Create `src/hooks/useCookieConsent.ts`:

```typescript
"use client";

import { useContext } from "react";
import { CookieConsentContext } from "@/components/cookie/CookieConsentProvider";

export function useCookieConsent() {
  const context = useContext(CookieConsentContext);
  if (!context) {
    throw new Error("useCookieConsent must be used within a CookieConsentProvider");
  }
  return context;
}
```

### Phase 7: Create Privacy Policy Page

Create `src/app/[locale]/privacy/page.tsx`:

- 12 sections as cards: overview, dataController, dataCollected, purpose, legalBasis, storage, thirdParties, rights, retention, children, changes, contact
- Special rendering for thirdParties (bulleted list of services), rights (bulleted list of GDPR rights), and contact (email link + social links)
- Header with back-to-home link, title, subtitle, lastUpdated
- **Customize content** based on collected project info (email, developer name, DB provider, hosting, jurisdiction)

### Phase 8: Create Terms of Service Page

Create `src/app/[locale]/terms/page.tsx`:

- 10 sections as cards: acceptance, intellectualProperty, useOfWebsite, gameDistribution, newsletter, limitationOfLiability, disclaimer, governingLaw, changes, contact
- Same card layout as privacy page
- **Customize content** based on collected project info

### Phase 9: Add i18n Translations

Add to `messages/en.json` and `messages/es.json`:

**Keys to add:**
- `privacy.*` — Title, subtitle, lastUpdated, backToHome, and all 12 sections with title + content
- `terms.*` — Title, subtitle, lastUpdated, backToHome, and all 10 sections with title + content
- `cookieConsent.banner.*` — title, description, acceptAll, rejectAll, customize
- `cookieConsent.preferences.*` — title, description, save, cancel, categories (essential/analytics/marketing with title/description/badge)
- `cookieConsent.footer.manageCookies`
- `footer.privacyPolicy`, `footer.termsOfService`

**IMPORTANT**: Customize ALL legal text content based on the project info gathered in Phase 1:
- Replace developer/company name
- Replace contact email
- Replace database provider name
- Replace hosting provider name
- Replace game/product distribution method
- Replace jurisdiction/governing law country
- Replace social media handles

### Phase 10: Integrate into Layout

Wrap the layout's children with `CookieConsentProvider` and add the banner/modal/analytics components:

```tsx
// src/app/[locale]/layout.tsx
import { CookieConsentProvider, CookieConsentBanner, CookiePreferencesModal, AnalyticsLoader } from "@/components/cookie";

// Inside the layout return:
<CookieConsentProvider>
  {/* ... existing providers ... */}
  <Header />
  <main>{children}</main>
  <Footer />
  {/* ... existing components ... */}
  <CookieConsentBanner />
  <CookiePreferencesModal />
  <AnalyticsLoader />
</CookieConsentProvider>
```

### Phase 11: Add Footer Links

Add to the project's footer component:

```tsx
import { Link } from "@/i18n/navigation";  // or project's link component
import { useCookieConsent } from "@/hooks/useCookieConsent";

// Inside footer:
const { openPreferences } = useCookieConsent();

<Link href="/privacy">{t("footer.privacyPolicy")}</Link>
<Link href="/terms">{t("footer.termsOfService")}</Link>
<button onClick={openPreferences}>{t("cookieConsent.footer.manageCookies")}</button>
```

### Phase 12: Add Environment Variable

If analytics is desired, remind the user to add to `.env.local`:

```env
NEXT_PUBLIC_GA_MEASUREMENT_ID=G-XXXXXXXXXX
```

### Phase 13: Verify

1. Run `npm run build` — no errors
2. Check both locale routes work: `/en/privacy`, `/es/privacy`, `/en/terms`, `/es/terms`
3. Cookie banner appears on first visit
4. "Accept All" / "Essential Only" / "Customize" all work
5. Preferences persist across page reloads (check localStorage)
6. "Manage Cookies" in footer reopens preferences modal
7. Analytics scripts only load when analytics consent is given

## Customization Notes

- **Design System**: All components use placeholder Tailwind classes (`{card}`, `{border}`, `{accent}`, etc.) — replace with the project's actual design tokens
- **Button Component**: Adapt to use the project's existing button component instead of raw `<button>` tags
- **Modal Component**: If the project has an existing modal, use it for CookiePreferencesModal
- **Additional Cookie Categories**: Add more categories to `COOKIE_CATEGORIES` constant and corresponding i18n keys as needed
- **Third-Party Services**: Update the privacy policy's thirdParties section to list the actual services used by the project
- **GDPR Rights**: The rights section covers standard GDPR rights — adjust for other jurisdictions if needed (CCPA, LGPD, etc.)
