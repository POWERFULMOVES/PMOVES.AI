# UI Development Patterns

**Reference documentation for PMOVES.AI UI development patterns.**

Based on learnings from PRs #325, #326, #327 (December 2025).
See `.claude/learnings/ui-error-handling-review-2025.md` for complete review analysis.

---

## Error Handling Patterns

### Error Boundary Architecture (PR #325)

```
RootErrorBoundary (layout.tsx)
└── ErrorBoundary (per-page/component)
    └── Component with try/catch
```

**Key Files:**
- `pmoves/ui/components/ErrorBoundary.tsx` - Reusable error boundary
- `pmoves/ui/lib/errorUtils.ts` - `logError()`, `logForDebugging()` utilities

### Error Logging Functions

```typescript
// Production errors - centralized, Sentry-ready
logError(error: Error, context?: ErrorContext): void

// Development debugging - console only, stripped in prod
logForDebugging(message: string, data?: unknown): void
```

### API Error Response Shapes

```typescript
// Auth/validation failures
{ ok: false, error: string }

// Success with data
{ ok: true, data: T }

// List endpoints
{ items: T[], error?: string }
```

### HTTP Status Code Rules

| Code | Use For |
|------|---------|
| 401 | Authentication failures (missing/invalid JWT) |
| 400 | Bad request data (malformed JSON, missing fields) |
| 500 | Server errors (database, external service) |

---

## Authentication Patterns (PR #326)

### JWT Owner Extraction

```typescript
// CORRECT - Always from authenticated token
function ownerFromJwt(req: NextRequest): { owner: string | null; error: string | null } {
  const authHeader = req.headers.get('authorization');
  if (!authHeader?.startsWith('Bearer ')) {
    return { owner: null, error: 'Missing authorization header' };
  }
  const token = authHeader.slice(7);
  const [, payload] = token.split('.');
  // base64url decoding (JWT uses - and _ instead of + and /)
  const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
  const json = JSON.parse(Buffer.from(base64, 'base64').toString('utf-8'));
  return { owner: json.sub || json.user_id, error: null };
}
```

### Security Anti-Patterns

```typescript
// BAD - allows client to impersonate any user
const owner = bodyOwnerId ?? jwtOwner;

// BAD - query param fallback bypasses auth
const owner = searchParams.get('ownerId') || jwtOwner;

// GOOD - only trust authenticated token
const { owner, error } = ownerFromJwt(request);
if (!owner) {
  return NextResponse.json({ ok: false, error }, { status: 401 });
}
```

---

## Accessibility Patterns (PR #327)

### Skip Link Implementation (WCAG 2.1 SC 2.4.1)

**In layout.tsx (first focusable element):**
```tsx
<a
  href="#main-content"
  className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-cata-cyan focus:text-void focus:rounded-md focus:font-medium focus:outline-2 focus:outline-offset-2 focus:outline-void"
>
  Skip to main content
</a>
```

**In main content container:**
```tsx
<main id="main-content" tabIndex={-1} className="relative">
  {children}
</main>
```

**Why `tabIndex={-1}`:** Allows programmatic focus via skip link without adding to tab order. Required for proper skip link behavior in all browsers.

### ARIA Live Regions

```tsx
// Critical/root-level errors - interrupts screen reader
<div role="alert" aria-live="assertive">
  {rootError.message}
</div>

// Component-level errors - polite announcement
<div role="alert" aria-live="polite">
  {componentError}
</div>
```

### Tailwind JIT Static Classes

```typescript
// BAD - dynamic interpolation breaks JIT compilation
className={`border-cata-${color}/30`}

// GOOD - static lookup preserves JIT analysis
const BORDER_CLASSES: Record<string, string> = {
  cyan: 'border-cata-cyan/30',
  ember: 'border-cata-ember/30',
  violet: 'border-cata-violet/30',
};
className={BORDER_CLASSES[color]}
```

---

## File Organization

### UI Library Structure

```
pmoves/ui/
├── app/                    # Next.js App Router pages
│   ├── api/               # API routes
│   │   └── chat/
│   │       ├── messages/route.ts
│   │       └── send/route.ts
│   ├── dashboard/         # Dashboard pages
│   └── layout.tsx         # Root layout with skip link
├── components/            # Reusable components
│   ├── ErrorBoundary.tsx
│   └── DashboardNavigation.tsx
└── lib/                   # Shared utilities
    ├── errorUtils.ts      # Error logging
    └── jwtUtils.ts        # JWT handling (TODO: extract)
```

---

## Action Items (From Review)

| Item | Priority | Status |
|------|----------|--------|
| Extract `ownerFromJwt` to `lib/jwtUtils.ts` | Medium | TODO |
| Implement Sentry in `logError` | Medium | TODO |
| Audit all API routes for auth bypass | High | TODO |

---

*Last Updated: December 18, 2025*
