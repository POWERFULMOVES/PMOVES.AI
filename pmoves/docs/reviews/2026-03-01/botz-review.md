# BoTZ Code Review — 2026-03-01

## Executive Summary

The Phase C P1 fixes are largely in place. The most critical prior finding — `if not JWT_SECRET: return True` — has been replaced with a fail-closed `raise HTTPException(status_code=500)` in `mcp_bridge/auth.py`. The gateway independently implements the same fail-closed logic and does so correctly. No `export` syntax appears in any active `.env*` templates. MCP Gateway POST endpoints (`/call`, `/mcp`, `/a2a/v1/tasks`) are JWT-gated.

**Two issues require resolution before shipping:**

1. A surviving fail-open bypass in `features/mcp_bridge/auth.py` lines 57-59 when `python-jose` is absent — this is the original P1 pattern, still present in a different branch of the same function.
2. Multiple GET endpoints on the MCP Gateway (`/servers`, `/tools`, `/.well-known/agent.json`, `/a2a/v1/tasks/<id>`) expose tool topology without authentication.

---

## Critical (P1)

### P1-A: Fail-open in `mcp_bridge/auth.py` — `HAS_JOSE` branch still returns `True`

**Confidence: 100**

**File:** `features/mcp_bridge/auth.py`, lines 57-59

```python
if not HAS_JOSE:
    # If python-jose is not installed, skip validation
    return True, None, "VALIDATION_UNAVAILABLE"
```

The `JWT_SECRET` branch (lines 61-65) was correctly fixed to raise HTTP 500, but the `HAS_JOSE` branch was not touched. When `python-jose` fails to import, every call to `validate_jwt_token()` returns `(True, None, "VALIDATION_UNAVAILABLE")` — any caller checking only the first tuple element grants full access.

**Compare to the correct pattern in `gateway.py` lines 281-284:**
```python
if not HAS_JOSE:
    self._send_json(500, {"error": "python-jose not installed"})
    logger.error("python-jose not installed — rejecting request (fail-closed)")
    return None
```

**Fix:**
```python
if not HAS_JOSE:
    raise HTTPException(
        status_code=500,
        detail="python-jose not installed — JWT validation unavailable"
    )
```

---

## Important (P2)

### P2-A: Unauthenticated GET endpoints leak tool topology

**Confidence: 95**

**File:** `features/gateway/python-gateway/gateway.py`, lines 486-514

| Endpoint | Data Exposed |
|---|---|
| `GET /servers` | Names, transports, descriptions of all upstream MCP servers |
| `GET /tools` | Every tool name, JSON schema, and server assignment |
| `GET /tools/<server>` | Per-server tool list |
| `GET /.well-known/agent.json` | Full A2A agent card with capabilities |
| `GET /a2a/v1/tasks/<id>` | Task state (asymmetric: POST is authed) |

**Fix:** Call `self._require_auth()` at the top of `do_GET()` for these paths.

### P2-B: NATS URL defaults missing credentials in `agent_sdk` submodules

**Confidence: 90**

Six locations default to `nats://localhost:4222` (no auth):
- `features/agent_sdk/pmoves_agent.py:82`
- `features/agent_sdk/core/events.py:35`
- `features/agent_sdk/subagents/researcher.py:56`
- `features/agent_sdk/subagents/media_processor.py:62`
- `features/n8n/monitor_agent.py:137`
- `features/agent_sdk/core/events.py:29` (docstring)

**Fix:** Change all to `"nats://nats:pmoves@nats:4222"`.

### P2-C: Two active Dockerfiles run as root

**Confidence: 85**

16 of 18 active `features/` Dockerfiles have `USER` directives. Two do not:
- `features/cipher/Dockerfile`
- `features/skills/Dockerfile`

**Fix:** Add `USER pmoves` with appropriate `chown`.

### P2-D: CHIT attestation uses SHA-256 hash-prefix instead of HMAC

**Confidence: 82**

**File:** `features/gateway/python-gateway/gateway.py`, lines 348-352

```python
"proof": hashlib.sha256(
    f"{SUPABASE_JWT_SECRET}:{endpoint}:{agent_id}:{ts}".encode()
).hexdigest()[:16],
```

`hashlib.sha256(secret || message)` is vulnerable to length-extension attacks. Truncating to 16 hex chars gives only 64 bits of entropy.

**Fix:** Use `hmac.new(secret, message, "sha256").hexdigest()`.

---

## Suggestions

- **`gateway.py` line 631** binds to `0.0.0.0` — prefer `127.0.0.1`
- **`features/vpn_mcp/vpn_mcp_server.py`** hardcodes `NATS_USER=pmoves` / `NATS_PASS=pmoves` separately — consolidate to `NATS_URL`
- **Stale fastapi pin** in `features/gateway/python-gateway/requirements.txt` (`fastapi==0.109.0`) — FastAPI not actually imported by gateway

---

## What's Good

- **JWT fail-closed (gateway)** — All three paths (no jose, no secret, bad token) correctly fail-closed
- **JWT fail-closed (mcp_bridge, JWT_SECRET path)** — `if not JWT_SECRET` branch now raises HTTP 500
- **No export syntax in env files** — `.env.example` and `core/example.env` use plain `KEY=VALUE`
- **NATS credentials in env templates** — `.env.example` uses authenticated URL
- **Docker hardening breadth** — 16 of 18 feature Dockerfiles have non-root `USER`
- **patterns.yaml self-protection** — In `readOnlyPaths`. `zeroAccessPaths` covers `.env*`, `*.pem`, `*.key`
- **CHIT CGP versioning** — Gateway uses canonical `"chit.cgp.v1.0"` format
- **python-jose pinned** — Both requirements files pin `python-jose[cryptography]==3.3.0`
- **No hardcoded secrets** — Only `CHANGE_ME_GENERATE_64_HEX_CHARS` placeholder found

---

## Phase C Fix Verification

- [ ] **JWT fail-open pattern fixed** — PARTIAL. `JWT_SECRET` branch fixed. `HAS_JOSE` branch (lines 57-59) still returns `True` (P1-A)
- [x] **Export syntax removed from env files** — CONFIRMED RESOLVED
- [ ] **MCP Gateway endpoints authenticated** — PARTIAL. POST protected. GET endpoints unprotected (P2-A)

---

## Dependabot Triage

| PR | Package | From -> To | Recommendation | Risk |
|----|---------|-----------|----------------|------|
| #66 | minimatch (npm group) | 3.1.2 -> 3.1.4 | **Merge** | Low — ReDoS fix in `**` pattern recursion. Archive/backup dirs only |
| #67 | lucide-react | 0.574.0 -> 0.575.0 | **Merge** | Low — New icons + ESM fix. No auth/network surface |
| #68 | fastapi | 0.129.0 -> 0.133.0 | **Merge with caution** | Medium — 0.132.0 adds `strict_content_type` checking (rejects requests without `Content-Type: application/json`). Verify internal MCP clients send proper headers. Also deprecates `ORJSONResponse`/`UJSONResponse` in 0.131.0 |
