# CodeRabbit Review Learnings: UI Error Handling & Security (December 2025)

**Review Period:** December 18, 2025
**PRs Reviewed:** #325 (Error Infrastructure), #326 (Chat Error Handling), #327 (Accessibility), #329 (Security), #330 (JWT Utils), #331 (Loki Logging)
**Security Commits:** 8f2f555c (IDOR Fix), 1401ef70 (JWT Utils), b187b2b9 (Loki Logging)
**Reviewer:** CodeRabbit AI

## Executive Summary

This document captures key learnings from CodeRabbit's review of UI error handling, security, and accessibility PRs. The reviews identified patterns for security, privacy, UX, and code quality that should inform future UI development.

---

## Key Security Patterns

### 1. Never Trust Client-Provided User Identifiers
**Issue:** API endpoints accepting `ownerId` from query params or request body enables authentication bypass (IDOR - Insecure Direct Object Reference).

**Affected Routes (Fixed in PR #329):**
- `api/uploads/presign` - Removed `body.ownerId` fallback
- `api/uploads/persist` - Removed `body.ownerId` fallback
- `api/chat/send` - Removed `body.ownerId` fallback
- `api/chat/messages` - Removed `searchParams.get('ownerId')` fallback

```typescript
// CRITICAL VULNERABILITY - allows impersonation
const bodyOwnerId = await req.json().then(b => b.ownerId);
const owner = bodyOwnerId ?? jwtOwner; // ❌ Attacker controls bodyOwnerId

// SECURE - only use authenticated JWT
const { ownerId } = ownerFromJwt();
if (!ownerId) {
  return NextResponse.json(
    { error: 'Authentication required' },
    { status: 401 }
  );
}
```

**Impact:** Attackers could access or modify any user's resources by sending arbitrary `ownerId` values in requests, bypassing authentication entirely.

**Lesson:** User identity must always be derived from authenticated tokens (JWT, session cookies), never from client-provided data (request body, query params, headers).

### 2. JWT Base64url Decoding (RFC 4648)
**Issue:** JWT payloads use base64url encoding (with `-` and `_`), not standard base64 (`+` and `/`).

**Why this matters:** Standard `Buffer.from(payload, 'base64')` silently fails or corrupts data when JWT uses base64url encoding. This can work in some environments but fail in others depending on the JWT issuer.

```typescript
// WRONG - fails on base64url encoded JWTs
const json = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf-8'));

// CORRECT - RFC 4648 base64url to base64 conversion
let payload = parts[1];
payload = payload.replace(/-/g, '+').replace(/_/g, '/');

// Add padding if needed (base64 requires length % 4 == 0)
const padding = payload.length % 4;
if (padding) {
  payload += '='.repeat(4 - padding);
}

const json = JSON.parse(Buffer.from(payload, 'base64').toString('utf-8'));
```

**Lesson:** Always convert base64url to base64 before decoding JWTs. This is the standard per RFC 4648 Section 5.

**Reference:** PR #330 - Extracted to `lib/jwtUtils.ts`

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

### 5. DRY - Extract Shared Utilities with Context
**Issue:** Duplicate `ownerFromJwt()` function in multiple routes (chat/send, chat/messages).
**Fix:** Extract to `lib/jwtUtils.ts` with component parameter for error context.

```typescript
// lib/jwtUtils.ts
export function ownerFromJwt(component?: string): OwnerResult {
  try {
    // ... JWT parsing logic with proper base64url handling
  } catch (e) {
    logError('JWT parsing failed', e, 'error', {
      component: component || 'jwtUtils'
    });
    return { ownerId: null, error: 'Failed to parse JWT' };
  }
}

// Usage in routes
const { ownerId } = ownerFromJwt('chat/messages');
const { ownerId } = ownerFromJwt('chat/send');
```

**Lesson:** When extracting shared utilities, include contextual parameters (like component name) to maintain debugging traceability across different callers.

**Reference:** PR #330

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

## Observability Patterns

### 11. Structured Logging for Loki Integration
**Pattern:** Environment-aware structured logging for observability stack.

```typescript
// StructuredLogEntry interface
interface StructuredLogEntry {
  timestamp: string;
  level: ErrorSeverity;
  message: string;
  error?: { name: string; message: string; stack?: string };
  component?: string;
  action?: string;
  context?: Record<string, unknown>;
}

// Environment-aware emission
function emitStructuredLog(entry: StructuredLogEntry): void {
  if (process.env.NODE_ENV === 'production') {
    // JSON to stdout - Promtail picks up docker logs
    console.log(JSON.stringify(entry));
  } else {
    // Colorized console for development
    const levelColors = { debug: '\x1b[90m', info: '\x1b[36m', warning: '\x1b[33m', error: '\x1b[31m', critical: '\x1b[35m' };
    console.log(`${levelColors[entry.level]}[${entry.level.toUpperCase()}]\x1b[0m ${entry.message}`, entry);
  }
}
```

**Lesson:** Leverage existing Loki/Promtail infrastructure. Production logs as JSON to stdout, Promtail scrapes docker container logs and sends to Loki. Development gets readable colorized output.

**Reference:** PR #331 - `lib/errorUtils.ts`

### 12. Post-Refactoring Cleanup
**Pattern:** After extracting shared utilities, remove orphaned imports and dead code.

**Example:** After extracting `ownerFromJwt()` to `lib/jwtUtils.ts`, routes that previously had inline JWT parsing using `getBootJwt()` no longer need that import:

```typescript
// Before refactoring
import { getBootJwt } from '@/lib/supabaseClient';

function ownerFromJwt(): OwnerResult {
  const token = getBootJwt();
  // ... parsing logic
}

// After refactoring - remove unused import
// import { getBootJwt } from '@/lib/supabaseClient'; // DELETE THIS
import { ownerFromJwt } from '@/lib/jwtUtils';
```

**Lesson:** Code review should catch unused imports after utility extraction. Tools like ESLint with `no-unused-vars` can automate this.

---

## Checklist for Future UI PRs

### Security
- [ ] User identity derived only from JWT, never from request body/query
- [ ] Proper base64url decoding for JWT payloads (RFC 4648: `-`→`+`, `_`→`/`, padding)
- [ ] No query parameter fallbacks that bypass authentication
- [ ] All 4 vulnerable routes audited: uploads/presign, uploads/persist, chat/send, chat/messages

### Privacy
- [ ] No PII in error logging interfaces
- [ ] Use `logError()` not raw `console.error`
- [ ] Generic user-facing error messages with digest IDs

### Code Quality
- [ ] Shared utilities extracted (no duplicate functions)
- [ ] Shared utilities include component context for error tracing
- [ ] Consistent error response shapes
- [ ] Consistent HTTP status codes (401 vs 400)
- [ ] Unused imports removed after refactoring (run ESLint)

### Accessibility
- [ ] Skip link as first focusable element
- [ ] Skip target has `tabIndex={-1}`
- [ ] Appropriate `aria-live` regions
- [ ] Tailwind classes statically analyzable

### Observability
- [ ] Structured logging uses StructuredLogEntry interface
- [ ] Production logs emit JSON to stdout for Promtail ingestion
- [ ] Development logs use colorized console output
- [ ] Error logs include component and action context
- [ ] Leverage existing Loki/Promtail stack (no new infrastructure)

### Testing
- [ ] Run smoke tests for UI changes

---

## Action Items

1. ✅ **Security Critical (COMPLETED):** Audited all API routes for client-provided identity bypass (PR #329, commit 8f2f555c)
2. ✅ **Code Quality (COMPLETED):** Extracted `ownerFromJwt` to shared `lib/jwtUtils.ts` (PR #330, commit 1401ef70)
3. ✅ **Infrastructure (COMPLETED):** Wired logError to Loki/Promtail with structured JSON logging (PR #331, commit b187b2b9)
4. **Testing:** Verify Loki ingestion of UI error logs in Grafana dashboard
5. **Documentation:** Update API route security guidelines with IDOR examples

---

*Document Generated: December 18, 2025*
*PRs: #325, #326, #327, #329, #330, #331*
