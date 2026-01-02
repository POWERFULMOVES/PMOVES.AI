# CodeRabbit Review Learnings: UI Error Handling (December 2025)

**Review Period:** December 18, 2025
**PRs Reviewed:** #325 (Error Infrastructure), #326 (Chat Error Handling), #327 (Accessibility)
**Reviewer:** CodeRabbit AI

## Executive Summary

This document captures key learnings from CodeRabbit's review of three UI error handling and accessibility PRs. The reviews identified patterns for security, privacy, UX, and code quality that should inform future UI development.

---

## Key Security Patterns

### 1. Never Trust Client-Provided User Identifiers
**Issue:** API endpoints accepting `ownerId` from query params or request body enables authentication bypass.

```typescript
// BAD - allows impersonation
const owner = bodyOwnerId ?? jwtOwner;

// GOOD - only use authenticated JWT
const owner = jwtOwner;
if (!owner) return NextResponse.json({ error: 'Authentication required' }, { status: 401 });
```

**Lesson:** User identity must always be derived from authenticated tokens, never from client-provided data.

### 2. JWT Base64url Decoding
**Issue:** JWT payloads use base64url encoding (with `-` and `_`), not standard base64.

```typescript
// CORRECT
const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
const json = JSON.parse(Buffer.from(base64, 'base64').toString('utf-8'));
```

---

## Privacy & Compliance

### 3. Avoid PII in Error Logging
- Remove `userId` fields from error context interfaces
- Use centralized `logError()` instead of raw `console.error`
- Never log full error objects that might contain user data

### 4. User-Facing Error Messages
- Never expose raw `error.message` to users
- Show generic messages with error digest/ID for support tracking

---

## Code Quality Patterns

### 5. DRY - Extract Shared Utilities
**Issue:** Duplicate `ownerFromJwt()` function in multiple routes.
**Fix:** Extract to `lib/jwtUtils.ts`

### 6. Consistent Error Response Shapes
```typescript
// Auth/validation failures
{ ok: false, error: string }

// Success with data
{ ok: true, data: ... }

// List endpoints
{ items: [...], error?: string }
```

### 7. HTTP Status Code Consistency
- 401 for authentication failures
- 400 for bad request data (malformed JSON, missing required fields)
- 500 for server errors

---

## Accessibility Patterns (WCAG 2.1)

### 8. Skip Links
```tsx
// layout.tsx - first focusable element
<a
  href="#main-content"
  className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-cata-cyan focus:text-void focus:rounded-md"
>
  Skip to main content
</a>

// DashboardShell - target with tabIndex
<main id="main-content" tabIndex={-1}>
```

### 9. ARIA Live Regions
- `aria-live="assertive"` for critical/root errors
- `aria-live="polite"` for component-level errors

### 10. Tailwind JIT Static Classes
```typescript
// BAD - dynamic interpolation
className={`border-cata-${color}/30`}

// GOOD - static lookup
const BORDER_CLASSES = { cyan: 'border-cata-cyan/30', ember: 'border-cata-ember/30' };
className={BORDER_CLASSES[color]}
```

---

## Checklist for Future UI PRs

### Security
- [ ] User identity derived only from JWT, never from request body/query
- [ ] Proper base64url decoding for JWT payloads
- [ ] No query parameter fallbacks that bypass authentication

### Privacy
- [ ] No PII in error logging interfaces
- [ ] Use `logError()` not raw `console.error`
- [ ] Generic user-facing error messages with digest IDs

### Code Quality
- [ ] Shared utilities extracted (no duplicate functions)
- [ ] Consistent error response shapes
- [ ] Consistent HTTP status codes (401 vs 400)
- [ ] Unused imports removed

### Accessibility
- [ ] Skip link as first focusable element
- [ ] Skip target has `tabIndex={-1}`
- [ ] Appropriate `aria-live` regions
- [ ] Tailwind classes statically analyzable

### Testing
- [ ] Run smoke tests for UI changes

---

## Action Items

1. **Security Critical:** Audit all API routes for client-provided identity bypass
2. **Code Quality:** Extract `ownerFromJwt` to shared `lib/jwtUtils.ts`
3. **Infrastructure:** Implement Sentry integration in `logError`

---

*Document Generated: December 18, 2025*
*PRs: #325, #326, #327*
