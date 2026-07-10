# Open Notebook → pmoves_auth JWT Integration Spec

> Architecture spec for replacing Open Notebook's bare-password `PasswordAuthMiddleware` with Supabase-JWT validation via a new `pmoves_auth` Python package in PMOVES-supabase. Closes the operator-visible auth gap: Open Notebook UI currently prompts for a password but expected a JWT against the PMOVES Supabase user pool. **Doc-only spec.** Runtime code lands in three follow-on PRs (one per phase) after §1 + §7 signoff per `AGNOTE4482_SIGNOFF_CHECKLIST.md` (Village Rule).

> **Status:** **DESIGN FINALIZED (2026-07-10).** All Open Items resolved (code-verified facts + operator decisions below); ready for Phase A implementation. Runtime code still lands in the three phase PRs. Finalization provenance: tandem review + verification pass (4090-CLAUDE), operator decisions (DARKXSIDE 2026-07-10).
>
> **Finalized decisions (see §Resolved Design Decisions for detail):**
> 1. **Studio access → gated behind Tailscale mesh.** JWT-minting (`supabase.pmoves.ai`) is not left on the public edge — reachable only from the tailnet. (Operator decision; privacy-mesh-only.)
> 2. **Sunset → 14-day dual, then JWT-only + remove password.** Spec default confirmed.
> 3. **Login UX → Studio copy-paste now; `pmoves auth login` CLI as a follow-up.** Ship JWT auth without blocking on the CLI.
> 4. **`OPEN_NOTEBOOK_API_TOKEN` → kept as a service-role credential.** The 3 machine callers stay token-based; only the human/UI path moves to user-JWT.

## Operator-visible symptom (the trigger)

DARKXSIDE on 2026-05-21:

> "i'm not able to login [to Open Notebook], it's asking for pass should be authed jwt"

Open Notebook's login currently expects a bearer token equal to the literal value of `OPEN_NOTEBOOK_PASSWORD` (a static env var). PMOVES has a Supabase user pool that issues JWTs; nothing wires the JWT into Open Notebook's auth middleware. The operator workflow expectation is:

```
sign in to Supabase → receive JWT → paste JWT into Open Notebook
                                  → Open Notebook validates JWT against Supabase issuer
                                  → access granted (user identity available to API)
```

Today, step 4 doesn't exist; Open Notebook only knows how to string-compare against `OPEN_NOTEBOOK_PASSWORD`.

## Scope

| In | Out |
|----|-----|
| `pmoves_auth` Python package surface (Phase A) | Existing `refresh-boot-jwt.sh` band-aid script (separate sunset path) |
| `SupabaseJWTMiddleware` design for Open Notebook (Phase B) | OAuth flow / browser-redirect login UX (Phase D, future) |
| Operator JWT-acquisition runbook (Phase C) | Per-user permission model inside Open Notebook (already absent; orthogonal) |
| Migration from password-only to dual-auth to JWT-only | RBAC/role mapping from Supabase claims to Open Notebook permissions (future) |
| Acceptance gates per phase | TensorZero / Esperanto auth (separate provider-credential system) |

## Architecture

### Current state (verified 2026-05-21)

```
                    ┌─────────────────────────────┐
                    │  Operator                   │
                    │  enters OPEN_NOTEBOOK_      │
                    │  PASSWORD as bearer token   │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
            ┌─────────────────────────────────────────┐
            │  Open Notebook API (FastAPI, :5055)     │
            │  PasswordAuthMiddleware                 │
            │  (PMOVES-Open-Notebook/api/auth.py:12)  │
            │                                         │
            │  if credentials != self.password:       │
            │      raise 401                          │
            │                                         │
            │  password = env OPEN_NOTEBOOK_PASSWORD  │
            │  (or OPEN_NOTEBOOK_API_TOKEN fallback)  │
            └─────────────────────────────────────────┘

PMOVES-supabase: has a user pool. Issues JWTs. NOT WIRED TO OPEN NOTEBOOK.
pmoves_auth Python package: DOES NOT EXIST (verified via Glob — only example/ files).
```

Verified against:
- `PMOVES-Open-Notebook/api/auth.py:12-78` — `PasswordAuthMiddleware.dispatch()` string-compares bearer against env password
- `PMOVES-Open-Notebook/api/main.py:138-153` — middleware mounted with documented excluded paths
- `PMOVES-Open-Notebook/CLAUDE.md` § Authentication — *"Simple password middleware (insecure, dev-only). Production: Replace with OAuth/JWT"*
- `pmoves/docker-compose.open-notebook.yml:31-32` — env wiring requires either `OPEN_NOTEBOOK_PASSWORD` or `OPEN_NOTEBOOK_API_TOKEN`
- `[[project_pmoves_auth_gap]]` memory — `pmoves_auth` package needed, not yet built (memory is 64 days old; verified 2026-05-21 still absent)

### Target state (post-Phase-C)

```
                    ┌─────────────────────────────┐
                    │  Operator                   │
                    │  signs in to Supabase       │
                    │  (Studio UI or CLI)         │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
            ┌─────────────────────────────────────────┐
            │  Supabase /auth/v1/token endpoint       │
            │  issues JWT signed by SUPABASE_JWT_     │
            │  SECRET (HS256) with claims:            │
            │    sub: user_id                         │
            │    role: authenticated | admin          │
            │    exp: unix_ts                         │
            │    aud: authenticated                   │
            └──────────────┬──────────────────────────┘
                           │ Bearer <jwt>
                           ▼
            ┌─────────────────────────────────────────┐
            │  Open Notebook API (FastAPI, :5055)     │
            │  SupabaseJWTMiddleware                  │
            │                                         │
            │  user = pmoves_auth.verify_jwt(token)   │
            │  if not user: raise 401                 │
            │  request.state.user = user              │
            └──────────────┬──────────────────────────┘
                           │ (in-process import)
                           ▼
            ┌─────────────────────────────────────────┐
            │  pmoves_auth (Python pkg in supabase)   │
            │                                         │
            │  verify_jwt(token: str) -> User | None  │
            │    decodes JWT against SUPABASE_JWT_    │
            │    SECRET, validates exp/aud/iss        │
            │                                         │
            │  refresh_session(refresh_token: str)    │
            │  check_expiry(grace_days: int)          │
            │  rotate_keys() → publishes              │
            │    ops.auth.jwt.expiring.v1 on NATS     │
            └─────────────────────────────────────────┘
```

## Phase A — `pmoves_auth` Python package (PMOVES-supabase)

**Goal:** A reusable, importable Python package providing JWT lifecycle primitives that any PMOVES service can mount.

### Package surface

```python
# PMOVES-supabase/pmoves_auth/__init__.py — proposed (Phase A creates)
from .verify import verify_jwt, JWTValidationError
from .session import refresh_session, get_authenticated_client
from .expiry import check_expiry, ExpiryAlert
from .rotation import rotate_keys

__all__ = [
    "verify_jwt",
    "JWTValidationError",
    "refresh_session",
    "get_authenticated_client",
    "check_expiry",
    "ExpiryAlert",
    "rotate_keys",
]
```

### Core function — `verify_jwt`

```python
# PMOVES-supabase/pmoves_auth/verify.py — proposed
from dataclasses import dataclass
from typing import Optional, Literal

@dataclass(frozen=True)
class User:
    """Subject of a verified Supabase JWT. Immutable for downstream safety."""
    user_id:    str                                       # JWT `sub`
    email:      Optional[str]                             # JWT `email` (may be absent for service-role)
    role:       Literal["anon", "authenticated", "service_role"]  # JWT `role`
    aud:        str                                       # JWT `aud` (expected: "authenticated" for user, "service_role" for system)
    exp_unix:   int                                       # JWT `exp` (operator can warn if close)
    raw_claims: dict                                      # full claims dict for advanced consumers

class JWTValidationError(Exception):
    """Raised when JWT validation fails. Subclasses identify the failure mode."""

class JWTExpiredError(JWTValidationError): ...
class JWTSignatureError(JWTValidationError): ...
class JWTClaimError(JWTValidationError): ...    # missing required claim, bad aud/iss, etc.
class JWTMalformedError(JWTValidationError): ...

def verify_jwt(
    token: str,
    *,
    secret: Optional[str] = None,             # default: env SUPABASE_JWT_SECRET
    issuer: Optional[str] = None,             # default: env SUPABASE_URL (validated as iss claim)
    expected_audience: str = "authenticated", # most consumers want user-tier; service-role gets "service_role"
) -> User:
    """Verify a Supabase-issued JWT against the configured secret.

    Returns:
        User dataclass with subject identity + role + expiry on success.

    Raises:
        JWTExpiredError: token's `exp` is in the past
        JWTSignatureError: HMAC signature doesn't match secret
        JWTClaimError: missing required claim, wrong `aud`, wrong `iss`
        JWTMalformedError: token isn't a parseable JWT (bad encoding, wrong segments)
    """
```

### Why distinct exception subclasses

Open Notebook's `SupabaseJWTMiddleware` should distinguish:
- `JWTExpiredError` → return 401 with `WWW-Authenticate: Bearer error="invalid_token", error_description="token expired"` so frontend can trigger refresh
- `JWTSignatureError` → return 401 with no refresh hint (probably tampered or wrong issuer)
- `JWTClaimError` → return 403 (correct issuer but insufficient permissions)
- `JWTMalformedError` → return 400 (client bug, not auth failure)

Single `JWTValidationError` would force the middleware to message-match, replaying the same fragility we caught in PR #1569 (transport-error classification on string match).

### Other primitives

| Function | Signature | Purpose |
|----------|-----------|---------|
| `refresh_session(refresh_token: str) -> dict` | calls Supabase `/auth/v1/token?grant_type=refresh_token` | Replaces band-aid `refresh-boot-jwt.sh` with SDK-native flow |
| `get_authenticated_client(jwt: str) -> SupabaseClient` | returns a Supabase client with the JWT set as the auth header | For services that need to perform user-context queries downstream |
| `check_expiry(jwt: str, grace_days: int = 30) -> ExpiryAlert` | returns `ExpiryAlert(days_until_expiry, severity)` | Used by `make flight-check` preflight + NATS alerting |
| `rotate_keys() -> None` | full key-rotation flow with service-restart coordination | Operator action, NOT auto-triggered |

### NATS alerting

Per `[[project_pmoves_auth_gap]]`: publish `ops.auth.jwt.expiring.v1` when within 30 days of expiry. Phase A includes:

```python
# PMOVES-supabase/pmoves_auth/expiry.py — proposed
async def emit_expiry_alert(alert: ExpiryAlert, nats_url: str) -> None:
    """Publish ops.auth.jwt.expiring.v1 when expiry is within grace window.
    Payload: {jwt_kid, days_until_expiry, severity, alert_ts}"""
```

Subject must be registered in `pmoves/.claude/context/nats-subjects.md` before code lands.

### Acceptance gates (Phase A)

| Gate | Command | Expected |
|------|---------|----------|
| Unit tests pass | `pytest PMOVES-supabase/tests/test_pmoves_auth.py -v` | All tests pass; 100% branch coverage on `verify.py` |
| Exception specificity | `pytest -k "test_verify_jwt_expired or test_verify_jwt_bad_signature"` | Distinct exception subclasses for each failure mode (no string-matching) |
| NATS alert wiring | `pytest -k test_emit_expiry_alert` | Publishes to `ops.auth.jwt.expiring.v1` with correct payload shape |
| Importable | `python -c "from pmoves_auth import verify_jwt; print('ok')"` | exit 0 |
| Backwards compat | `bash PMOVES-supabase/scripts/refresh-boot-jwt.sh` | Still works (band-aid sunset is Phase C) |

## Phase B — `SupabaseJWTMiddleware` in Open Notebook fork

**Goal:** Replace `PasswordAuthMiddleware` with JWT-aware middleware that calls `pmoves_auth.verify_jwt()`.

### Files to modify

| File | Change |
|------|--------|
| `PMOVES-Open-Notebook/api/auth.py` | Add `SupabaseJWTMiddleware` class alongside (not replacing) `PasswordAuthMiddleware` |
| `PMOVES-Open-Notebook/api/main.py:140-153` | Switch to `SupabaseJWTMiddleware` based on env flag `OPEN_NOTEBOOK_AUTH_MODE` |
| `PMOVES-Open-Notebook/pyproject.toml` | Add `pmoves_auth` to dependencies (path or git ref to PMOVES-supabase) |
| `pmoves/docker-compose.open-notebook.yml:27-32` | Add `OPEN_NOTEBOOK_AUTH_MODE`, `SUPABASE_JWT_SECRET`, `SUPABASE_URL` env passthrough |

### Dual-auth migration window

A hard flip from password-only to JWT-only breaks every existing operator session and forces a clean-room cutover. Cleaner: **dual-auth mode** for 1-2 weeks, then sunset.

```python
# PMOVES-Open-Notebook/api/auth.py — proposed addition
class SupabaseJWTMiddleware(BaseHTTPMiddleware):
    """JWT-aware auth. Mode determined by OPEN_NOTEBOOK_AUTH_MODE env var:
        "jwt"      → JWT-only. Password rejected.
        "dual"     → JWT preferred; falls back to password if JWT validation fails.
        "password" → password-only (legacy). JWT never validated. (deprecated)
    """
    def __init__(self, app, excluded_paths=None):
        super().__init__(app)
        self.mode = os.getenv("OPEN_NOTEBOOK_AUTH_MODE", "dual").lower()
        if self.mode not in ("jwt", "dual", "password"):
            raise ValueError(f"OPEN_NOTEBOOK_AUTH_MODE must be jwt|dual|password, got {self.mode!r}")
        # ... (excluded paths same as PasswordAuthMiddleware)

    async def dispatch(self, request, call_next):
        # ... (excluded-path + OPTIONS handling identical to PasswordAuthMiddleware)
        token = self._extract_bearer(request)
        if not token:
            return self._unauth("Missing authorization header")

        if self.mode in ("jwt", "dual"):
            try:
                user = pmoves_auth.verify_jwt(token)
                request.state.user = user
                return await call_next(request)
            except JWTExpiredError:
                return self._unauth("token expired", refresh_hint=True)
            except JWTValidationError:
                if self.mode == "jwt":
                    return self._unauth("invalid token")
                # dual: fall through to password check

        if self.mode in ("dual", "password"):
            password = get_secret_from_env("OPEN_NOTEBOOK_PASSWORD")
            if password and token == password:
                request.state.user = None  # password-auth has no identity
                return await call_next(request)

        return self._unauth("invalid credentials")
```

### `request.state.user` contract

After Phase B lands, downstream routers can opt-in to user identity:

```python
# Example: routers using identity to scope queries
@router.get("/notebooks")
async def list_notebooks(request: Request):
    user = getattr(request.state, "user", None)
    if user is None:
        # password-auth (dual mode): unscoped fallback (legacy behavior)
        return await notebooks_service.list_all()
    # jwt-auth: scope to user
    return await notebooks_service.list_for_user(user.user_id)
```

Routers MUST NOT crash if `request.state.user` is `None` — that's the password-auth fallback state during the dual-auth window.

### Acceptance gates (Phase B)

| Gate | Command | Expected |
|------|---------|----------|
| Middleware unit tests | `pytest PMOVES-Open-Notebook/tests/test_supabase_jwt_middleware.py` | All 3 modes (jwt/dual/password) tested + all 4 `JWTValidationError` subclass branches |
| Dual-auth integration | Operator with old password works; operator with new JWT works; both in same compose-up | Both auth paths succeed; `request.state.user` set only on JWT path |
| JWT-only mode | Set `OPEN_NOTEBOOK_AUTH_MODE=jwt`, password is rejected | 401 with `error_description="invalid token"` |
| Refresh hint | Send expired JWT, check response header | `WWW-Authenticate: Bearer error="invalid_token", error_description="token expired"` |
| 401-CORS preserved | Send bad JWT from frontend origin | Response includes CORS headers (existing `custom_http_exception_handler` covers this) |

## Phase C — Operator runbook + password sunset

**Goal:** Document the JWT-acquisition flow + transition from dual-auth to JWT-only.

### Operator JWT acquisition

```
1. Open Supabase Studio: https://supabase.pmoves.local
2. Sign in with operator credentials (DARKXSIDE / others)
3. Settings → API → "anon" or "service_role" key
   (For Open Notebook UI, use the user-scoped JWT from `/auth/v1/token?grant_type=password`
   not the long-lived anon key, so requests are scoped to user identity.)
4. Copy the JWT
5. Open Notebook UI login: paste JWT as the password value
6. Tokens last ~1h by default; UI should auto-refresh via `pmoves_auth.refresh_session`
   if a refresh_token is held client-side
```

### Compose env diff (after Phase B lands)

```diff
# pmoves/docker-compose.open-notebook.yml
 environment:
   OPEN_NOTEBOOK_PASSWORD: ${OPEN_NOTEBOOK_PASSWORD:-${OPEN_NOTEBOOK_API_TOKEN:?Set OPEN_NOTEBOOK_PASSWORD or OPEN_NOTEBOOK_API_TOKEN}}
   OPEN_NOTEBOOK_API_TOKEN: ${OPEN_NOTEBOOK_API_TOKEN:-${OPEN_NOTEBOOK_PASSWORD:?Set OPEN_NOTEBOOK_API_TOKEN or OPEN_NOTEBOOK_PASSWORD}}
+  OPEN_NOTEBOOK_AUTH_MODE: ${OPEN_NOTEBOOK_AUTH_MODE:-dual}
+  SUPABASE_URL: ${SUPABASE_URL:?Set SUPABASE_URL for JWT validation}
+  SUPABASE_JWT_SECRET: ${SUPABASE_JWT_SECRET:?Set SUPABASE_JWT_SECRET for JWT validation}
```

### Sunset timeline

| When | Action | Outcome |
|------|--------|---------|
| Phase B merge + 0 days | Default `OPEN_NOTEBOOK_AUTH_MODE=dual` | Existing password sessions keep working; JWT sessions start working |
| Phase B merge + 14 days | Operator-led: flip env to `OPEN_NOTEBOOK_AUTH_MODE=jwt` on each node | JWT-only; password rejected |
| Phase B merge + 30 days | Remove `PasswordAuthMiddleware` class + `OPEN_NOTEBOOK_PASSWORD` env requirement | Code cleanup; doc updates |
| Phase B merge + 30 days | Sunset `refresh-boot-jwt.sh` band-aid | Replaced by `pmoves_auth.refresh_session()` SDK call |

## Cross-Node Reviewers

This spec lands on `main` after signoff. Code PRs (Phase A in PMOVES-supabase, Phase B in PMOVES-Open-Notebook fork) open with these reviewers tagged:

| Reviewer | Concern | Specifics |
|----------|---------|-----------|
| **4090-CLAUDE** | Supabase + JWT intersection | ✅ **RESOLVED (2026-07-10).** `SUPABASE_JWT_SECRET=${JWT_SECRET}` is the correct GoTrue HS256 signing secret, distinct from `SUPABASE_ANON_KEY` (`env.shared.example:137,144`). Operator-facing Studio is `https://supabase.pmoves.ai` (KVM4-2 Kong `:8000`, per `.claude/context/self-hosted-defaults.md:41,51`), **not** `supabase.pmoves.local` — spec corrected below. |
| **Z890-CLAUDE (submodule sync)** | Phase A lands in PMOVES-supabase submodule; Phase B lands in PMOVES-Open-Notebook submodule | Submodule pin promotion sequencing — Phase A pin must merge before Phase B pin |
| **MissingLinc** (when minted) | Auth audit / forensic data analysis | The token-vs-JWT cutover surfaces credential-leak risk if old `OPEN_NOTEBOOK_PASSWORD` env values are checked into env.tier-* files; MissingLinc should sweep for residual password values after Phase C |
| **DARKXSIDE** | Operator UX + sunset timeline | ✅ **RESOLVED (2026-07-10).** (a) 14-day dual-auth window **accepted** → then JWT-only + remove password. (b) **Studio copy-paste now**, `pmoves auth login` CLI as a follow-up (not a Phase-C blocker). (c) `OPEN_NOTEBOOK_AUTH_MODE=password` **removed** in Phase C cleanup (not retained as permanent fallback). |

## Resolved Design Decisions (finalized 2026-07-10)

Every pre-code Open Item is now closed — by verified code facts (tandem verification pass, cited) or operator decision (DARKXSIDE). Order preserved from the original Open Items list.

1. **`OPEN_NOTEBOOK_API_TOKEN` semantic → KEEP as a service-role credential.** *(Operator decision.)* Verified: exactly **3 machine callers** send it as a static bearer today — `pmoves/services/notebook-sync/sync.py:529`, `pmoves/services/deepresearch/worker.py:541`, `pmoves/services/showtime-api/notebook_client.py:31`. Machine-to-machine stays token-based (or a long-lived service-role JWT); only the human/UI path moves to user-JWT. Phase B must **not** break these — they keep the token path (see #6). Deprecating the human `password` (Phase C) does **not** remove `OPEN_NOTEBOOK_API_TOKEN`.
2. **JWT refresh-token storage → HTTP-only cookie (recommended default; Phase B impl lane owns final call).** Verified: the frontend today stores the *password itself* as `token` in `localStorage` via Zustand `persist` (`PMOVES-Open-Notebook/frontend/src/lib/stores/auth-store.ts:94,212-216`) with **zero refresh-token infrastructure** — so Phase B builds this from scratch and is unconstrained by legacy. Given the existing localStorage-XSS exposure, prefer a same-origin HTTP-only cookie for the refresh token; keep the short-lived access token in-memory.
3. **Supabase Studio access → GATE BEHIND TAILSCALE MESH.** *(Operator decision — this was the open security risk.)* Verified: `supabase.pmoves.ai` is currently a **public Cloudflare-DNS subdomain** with no gating in front of Studio (`.claude/context/self-hosted-defaults.md:20,26,41`), i.e. whoever reaches it can attempt sign-in and, with Studio access, mint JWTs for any user. Resolution: JWT-minting endpoint is reachable **only from the tailnet** (privacy-mesh-only), closing the weak point without new SSO infra. Implementation = Tailscale-serve / ACL restriction on the Studio route (mesh-gateway lane). MissingLinc still sweeps for residual `OPEN_NOTEBOOK_PASSWORD` values post-Phase-C.
4. **CHIT integration → UNCHANGED (no CHIT).** Confirmed still correct: `PMOVES-Open-Notebook/CLAUDE.md` § CHIT = "No CHIT integration (by design)"; JWT identity does not trigger it.
5. **i18n on JWT error messages → REQUIRED in Phase B.** Verified: `getApiErrorMessage()` (`PMOVES-Open-Notebook/frontend/src/lib/utils/error-handler.ts:59-77`) has an `ERROR_MAP` with password-era keys but **no** entries for `"token expired"` / `"invalid token"` (falls through to raw untranslated string). Phase B adds i18n keys `apiErrors.tokenExpired` / `apiErrors.invalidToken` alongside the middleware.
6. **Service-to-service auth → dual-auth bridge is MANDATORY, service token retained.** *(Code-verified, non-negotiable default.)* The 3 callers in #1 have no JWT/refresh logic; a hard flip to `OPEN_NOTEBOOK_AUTH_MODE=jwt` would break all three (`verify_jwt()` → `JWTMalformedError` on a static string). `OPEN_NOTEBOOK_AUTH_MODE=dual` (default) is the only safe migration state; the service-role token path stays open past the human-password sunset. Migrating the 3 callers to rotating service-role JWTs is explicitly **out of scope** for this finalization (future, if desired).

### Implementation-ready follow-ups (verified, separable from the auth phases)

These are code-fact tech-debt items surfaced by the tandem review — fixable unilaterally, no further design input:
- **Topology de-duplication (P1).** `open-notebook` (`pmoves/docker-compose.open-notebook.yml:14-69`) and `open-notebook-ext` (`pmoves/docker-compose.external.yml:119-148`) are **literal duplicates** colliding on host ports `8503`/`5055`; SurrealDB (`open-notebook-surrealdb-ext`) is defined only in `external.yml`, so `make up-open-notebook` alone can't reach it. Pick one canonical compose owner (recommend `docker-compose.open-notebook.yml` — it's what the Make target + docs point at) and either co-locate SurrealDB there or make the target depend on it; retire the `-ext` duplicate.
- **Healthcheck wiring (P0-ops).** The fork exposes `/healthz` (`PMOVES-Open-Notebook/api/main.py:298`, auth-excluded), but **neither** compose service wires a Docker `healthcheck:` — add one so `depends_on: service_healthy` and `docker compose ps` work.

## Cross-Links

- **Issue:** to-be-filed after spec signoff
- **Signoff:** [`AGNOTE4482_SIGNOFF_CHECKLIST.md`](../AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md) §1 (architecture), §7 (when persona-binding intersects)
- **Upstream auth file:** `PMOVES-Open-Notebook/api/auth.py:12-78` (PasswordAuthMiddleware) — what gets replaced
- **Upstream mount point:** `PMOVES-Open-Notebook/api/main.py:138-153` — where middleware is added
- **Compose wiring:** `pmoves/docker-compose.open-notebook.yml:27-45` — env passthrough
- **Submodule home (Phase A):** `PMOVES-supabase/` (new `pmoves_auth/` package)
- **Submodule home (Phase B):** `PMOVES-Open-Notebook/api/` (new `SupabaseJWTMiddleware` + dual-auth toggle)
- **Memory:** `[[project_pmoves_auth_gap]]` — originating gap analysis (64 days old; verified still gap 2026-05-21)
- **Upstream CLAUDE.md:** `PMOVES-Open-Notebook/CLAUDE.md` § Authentication — *"Production: Replace with OAuth/JWT"*

## Emperor-CHIT-Humility Disclosure

**Have (verified in this session, off `origin/main@7119ca8f`):**
- `PMOVES-Open-Notebook/api/auth.py:12-78` — `PasswordAuthMiddleware` does straight string-compare bearer-vs-env
- `PMOVES-Open-Notebook/api/main.py:138-153` — middleware mount + excluded-paths list verified
- `pmoves/docker-compose.open-notebook.yml:31-32` — env wiring confirmed (no JWT vars present)
- `PMOVES-Open-Notebook/CLAUDE.md` § Authentication — upstream itself flags password-middleware as dev-only
- `PMOVES-supabase/**/pmoves_auth*` — glob returns zero matches (package does not exist)
- `[[project_pmoves_auth_gap]]` memory — describes the same gap, 64 days old

**Resolved at finalization (2026-07-10) — see §Resolved Design Decisions:**
- Supabase Studio URL confirmed `https://supabase.pmoves.ai` (was assumed `.local`); **decision: gate behind Tailscale mesh** (closes the public-edge weak point).
- Phase B refresh-token storage → HTTP-only cookie recommended; verified no legacy refresh infra to constrain it.
- Service-to-service auth → 3 callers enumerated + verified; **service-role token retained, dual-auth bridge mandatory**.

**Still deferred (by design, not blocking):**
- Migrating the 3 machine callers from static token → rotating service-role JWT (future, optional).
- MissingLinc residual-`OPEN_NOTEBOOK_PASSWORD` sweep runs post-Phase-C.

<!-- GRAPHITI_MARK: Z890→5090-CLAUDE::OPEN-NOTEBOOK-JWT-AUTH-SPEC::2026-05-21 -->
<!-- GRAPHITI_MARK: 4090-CLAUDE::OPEN-NOTEBOOK-JWT-AUTH-DESIGN-FINALIZED::2026-07-10 -->
