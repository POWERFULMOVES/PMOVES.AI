# pmoves-auth-phase-a-5090

Implement **Phase A** of the Open Notebook JWT-auth design: the reusable **`pmoves_auth`
Python package** in the `PMOVES-supabase` submodule. This is the foundation any PMOVES
service mounts to validate Supabase-issued JWTs — Open Notebook (Phase B) is the first
consumer. The design is **FINALIZED** (all open items resolved); this brief hands the
implementation to KiloCode GLM on the 5090.

## Lane

pmoves_auth-PhaseA · KiloCode GLM (5090) · submodule `PMOVES-supabase` · branch `feat/pmoves-auth-phase-a`

Three-Body: **Claude (4090) analyzed + finalized the design → KiloCode GLM (5090) implements →
`chit:sign-trail` closes the loop.** Source of truth = `pmoves/docs/integrations/OPEN_NOTEBOOK_JWT_AUTH.md`
§"Phase A" (package surface, function signatures, exception taxonomy, acceptance gates). Do NOT
redesign — implement the spec as written; flag any spec gap back to 4090-CLAUDE rather than improvising.

## Arguments

- `submodule` (string, required): `PMOVES-supabase` — package lands at `PMOVES-supabase/pmoves_auth/`.
- `nats_url` (string, optional): bus URL for the expiry-alert publisher, default the fleet leaf (`nats://nats:4222`); do NOT hardcode an IP — use the env/service name.
- `grace_days` (int, optional): expiry-alert window for `check_expiry`, default `30` (per spec §198, §203).

## Implementation

Build `PMOVES-supabase/pmoves_auth/` exactly to spec §113–222. Files + responsibilities:

### 1. Package surface (`pmoves_auth/__init__.py`)
Export per spec §119–135: `verify_jwt`, `JWTValidationError`, `refresh_session`,
`get_authenticated_client`, `check_expiry`, `ExpiryAlert`, `rotate_keys`. Nothing more in `__all__`.

### 2. `verify.py` — the core validator (spec §137–190)
- `verify_jwt(token, *, secret=None, issuer=None, expected_audience="authenticated") -> User`.
  Defaults: `secret` ← env `SUPABASE_JWT_SECRET`, `issuer` ← env `SUPABASE_URL`. HS256.
- Immutable frozen `User` dataclass: `user_id` (`sub`), `email`, `role` (Literal
  `anon|authenticated|service_role`), `aud`, `exp_unix`, `raw_claims`.
- **Distinct exception subclasses** (spec §154–160, §182–190) — NON-NEGOTIABLE, no string-matching:
  `JWTExpiredError`, `JWTSignatureError`, `JWTClaimError`, `JWTMalformedError`, all under
  `JWTValidationError`. These map to distinct HTTP responses in Phase B, so the boundaries must be crisp.
- Validate `exp`, `aud`, `iss`. Use `pyjwt` (already a Supabase-stack dep — confirm, don't add a second JWT lib).

### 3. `session.py` (spec §196–197)
- `refresh_session(refresh_token) -> dict` → Supabase `/auth/v1/token?grant_type=refresh_token`
  (the SDK-native replacement for the `refresh-boot-jwt.sh` band-aid — do NOT delete that script; its
  sunset is Phase C).
- `get_authenticated_client(jwt) -> SupabaseClient` with the JWT set as the auth header.

### 4. `expiry.py` (spec §198, §201–210)
- `check_expiry(jwt, grace_days=30) -> ExpiryAlert(days_until_expiry, severity)`.
- `async emit_expiry_alert(alert, nats_url)` → publish **`ops.auth.jwt.expiring.v1`**, payload
  `{jwt_kid, days_until_expiry, severity, alert_ts}`. **Register the subject in
  `pmoves/.claude/context/nats-subjects.md` BEFORE the code lands** (spec §212) — that registration is a gate.

### 5. `rotation.py` (spec §199)
- `rotate_keys() -> None` — full key-rotation flow, operator-invoked (NOT auto-triggered).

### 6. Tests (`PMOVES-supabase/tests/test_pmoves_auth.py`)
- Cover all 4 `JWTValidationError` branches independently; **100% branch coverage on `verify.py`**.
- `test_emit_expiry_alert` asserts the exact `ops.auth.jwt.expiring.v1` payload shape.

## Acceptance gates (from spec §214–222 — all must pass)

| Gate | Command | Expected |
|------|---------|----------|
| Unit tests | `pytest PMOVES-supabase/tests/test_pmoves_auth.py -v` | pass; 100% branch coverage on `verify.py` |
| Exception specificity | `pytest -k "test_verify_jwt_expired or test_verify_jwt_bad_signature"` | distinct subclasses, no string-matching |
| NATS alert wiring | `pytest -k test_emit_expiry_alert` | publishes `ops.auth.jwt.expiring.v1`, correct payload |
| Importable | `python -c "from pmoves_auth import verify_jwt; print('ok')"` | exit 0 |
| Backwards compat | `bash PMOVES-supabase/scripts/refresh-boot-jwt.sh` | still works (sunset is Phase C) |
| Subject registered | grep `ops.auth.jwt.expiring.v1` in `.claude/context/nats-subjects.md` | present |

## Related

- **Finalized design (source of truth):** `pmoves/docs/integrations/OPEN_NOTEBOOK_JWT_AUTH.md` (PR #2028)
- **Phase B (next, blocks on this):** `SupabaseJWTMiddleware` + dual-auth in `PMOVES-Open-Notebook/api/` — Phase A pin must merge before Phase B pin (spec §357).
- **Companion:** notebooklm-agent parked (PR #2025); Open Notebook is the sovereign notebook lane.

## Notes

- **Naming:** `snake_case` for Python + module symbols; this is a library, not an agent-facing id.
- **Secret is `SUPABASE_JWT_SECRET=${JWT_SECRET}`** — the GoTrue HS256 signing secret, verified distinct from `SUPABASE_ANON_KEY` (`env.shared.example:137,144`). Do NOT import the anon key.
- **Phase-B forward-compat:** the finalized terminal-auth state accepts a service-role `OPEN_NOTEBOOK_API_TOKEN` (decoupled from the human password) alongside user JWTs. `verify_jwt` must correctly surface `role="service_role"` in the `User` so Phase B's middleware can branch on it — do not collapse roles.
- **Do not** hardcode fleet IPs or Studio URLs in the package; Studio (`supabase.pmoves.ai`) is Tailscale-gated and injected via env.
- Close the loop with `chit:sign-trail` on the branch; open the Phase A PR with the pydantic/naming provenance and tag Z890-CLAUDE (submodule pin sequencing) + 4090-CLAUDE (design intersection).
