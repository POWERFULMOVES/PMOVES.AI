# Security Patterns Reference

Cross-cutting security reference for all PMOVES.AI agents and developers.

## Authentication Patterns

### Fail-Closed Principle

All authentication MUST fail closed. If the auth secret is missing, the service MUST return HTTP 500, never allow anonymous access.

**Correct:**
```python
if not JWT_SECRET:
    raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
```

**WRONG (fail-open anti-pattern):**
```python
if not JWT_SECRET:
    return True  # DANGER: allows anonymous access
```

### JWT-Only Identity

User identity MUST come from JWT claims only, never from request body or query parameters:
- Decode JWT from `Authorization: Bearer <token>` header
- Use proper base64url decoding (`-` to `+`, `_` to `/`)
- No query parameter fallbacks that bypass authentication

### Known Anti-Patterns

| Pattern | Risk | Found In |
|---------|------|----------|
| `if not JWT_SECRET: return True` | Fail-open auth bypass | BoTZ auth.py:59 |
| `if not self.password: return await call_next(request)` | Fail-open middleware | Open-Notebook auth.py:29 |
| `RLS USING (true) WITH CHECK (true)` | No access control | Supabase migrations |
| `verify_token()` returning anonymous on missing secret | Anonymous fallback | Multiple services |

## Secrets Management

### Variable Patterns

| Syntax | Meaning | Use When |
|--------|---------|----------|
| `${VAR:?message}` | Error with message if unset | Required secrets (API keys, JWT secrets) |
| `${VAR:-default}` | Use default if unset | Operational defaults (URLs, ports) |
| `KEY=value` | Plain assignment | Docker `env_file` format (no `export`) |

**IMPORTANT:** `export VAR=value` syntax is incompatible with Docker `env_file` — use plain `KEY=VALUE`.

### CHIT Manifest as Source of Truth

`pmoves/chit/secrets_manifest_v2.yaml` is the canonical definition of all credentials:
- Defines source (CGP, static, env), targets (tier files, GitHub secrets, Docker secrets)
- Run `make -C pmoves secrets-funnel` to regenerate tier env files
- Never edit `env.tier-*` files directly — they're auto-generated

### Credential Rotation

Default credentials that MUST be changed for production:

| Credential | Default | Service |
|------------|---------|---------|
| MinIO root password | `minioadmin` | MinIO |
| SurrealDB user/pass | `root/root` | Open Notebook |
| ClickHouse user/pass | `tensorzero/tensorzero` | TensorZero |
| Neo4j password | `neo4j` | Knowledge Graph |
| Meilisearch master key | varies | Full-text search |

## NATS Authentication

**All NATS URLs MUST include credentials:**
```
nats://nats:pmoves@nats:4222
```

**NOT:** `nats://nats:4222` (unauthenticated)

This applies to:
- `env.shared` and all tier env files
- CHIT secrets manifest static entries
- Service-level `.env` files
- Docker compose environment blocks

## Docker Hardening

### Tier+Hardening YAML Anchors

PMOVES uses combined anchors in docker-compose files:
- `*tier-agent-hardened-ro` — env_file + cap_drop ALL + read_only + tmpfs
- `*tier-worker-hardened` — env_file + cap_drop ALL + cap_add specific

### Required Hardening

| Control | Stateless Services | Stateful Services |
|---------|-------------------|-------------------|
| `cap_drop: [ALL]` | Required | Required |
| `read_only: true` | Required | Not applicable |
| `tmpfs: [/tmp, /var/run]` | Required with read_only | Optional |
| `USER` directive | Required | Required |
| Image SHA pins | Recommended | Recommended |

### Health Checks

All services MUST expose `/healthz` returning JSON:
```json
{"status": "healthy", "version": "1.0.0", "uptime_seconds": 3600}
```

Docker HEALTHCHECK must reference port 8222 for NATS (`/varz`).

## Input Validation

### Path Validation

Use allowlist regex for user-controlled paths:
```python
import re
SAFE_PATH = re.compile(r'^[a-zA-Z0-9_\-/.]+$')
if not SAFE_PATH.match(user_path):
    raise ValueError("Invalid path characters")
```

### Database Queries

- **Neo4j:** Use parameterized queries, never f-string label construction
- **Supabase:** Use PostgREST or parameterized SQL, never string interpolation
- **Meilisearch:** API handles escaping; validate search terms for length

### URL Scheme Validation

For user-provided URLs (especially in `img.src`):
```python
ALLOWED_SCHEMES = {'http', 'https', 'data'}
parsed = urllib.parse.urlparse(url)
if parsed.scheme not in ALLOWED_SCHEMES:
    raise ValueError(f"Disallowed URL scheme: {parsed.scheme}")
```

## P2 Submodule Issue Tracker

See `pmoves/docs/security/P2_SUBMODULE_TRACKER.md` for the complete tracker of open P2 issues requiring submodule PRs.

| Submodule | Open P2 Count |
|-----------|---------------|
| BoTZ | 2 |
| Open-Notebook | 3 |
| PMOVES.YT | 2 |
| DoX | 1 |
| Pipecat | 2 |
| A2UI | 2 |
| tensorzero | 2 |
| HiRAG | 1 |
