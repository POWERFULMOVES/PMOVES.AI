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

## Node SSH Hardening (Cross-Platform)

PMOVES nodes (Windows, Linux, Jetson) all expose SSH for fleet management. Bring-up follows the same sequence on every platform; the silent-failure modes are platform-specific.

### Bring-Up Sequence (universal)

1. Verify `sshd` is installed and the service is running before injecting keys
2. Inject the agent's public key idempotently (see "Idempotent Key Injection" below)
3. Test key-only auth from a remote node **before** disabling password auth
4. Harden `sshd_config` (`PasswordAuthentication no`, `MaxAuthTries 3`, `PermitRootLogin prohibit-password`)
5. Restart sshd **from the local console, never over SSH** — `Restart-Service sshd` / `systemctl restart sshd` drops live sessions and you can lock yourself out if a key step silently failed

### Idempotent Key Injection

Dedup on the **base64 key body** (the middle field of `type body comment`), not the full line. Comments and key types vary between agents; the body is the stable identity. Example:

```powershell
$keyBody = ($PubKey -split '\s+')[1]
if ($existing -notmatch [regex]::Escape($keyBody)) { Add-Content -Path $authKeysPath -Value $PubKey }
```

This lets the same script re-apply any agent's pubkey safely. Per-comment dedup (the older pattern) appends duplicates when a key is re-applied with a different comment.

### Platform-Specific Silent-Failure Modes

| Platform | File | Required permissions | Silent-failure mode |
|----------|------|----------------------|---------------------|
| Windows (admin users) | `%ProgramData%\ssh\administrators_authorized_keys` | `icacls /inheritance:r` + grant only `Administrators:F` and `SYSTEM:F` | sshd ignores the file (no error logged) if any non-admin user has access |
| Windows (non-admin) | `%USERPROFILE%\.ssh\authorized_keys` | Owner = target user, no inherited perms | Same — sshd ignores the file silently |
| Linux / Jetson | `~/.ssh/authorized_keys` | `chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys` + owner = target user | `StrictModes yes` (default) refuses the key with `Authentication refused: bad ownership or modes` in sshd log |

The Windows ACL requirement is the most common silent failure: sshd does not write an error to its log when ACLs are wrong, it just behaves as if the key isn't there. Always verify with key-only auth from a remote node before disabling password auth.

### Anti-Patterns

| Pattern | Risk | Mitigation |
|---------|------|------------|
| Hardening sshd over an SSH session | Locks out the agent mid-restart if a key step failed | Run from local console or RustDesk |
| Dedup on the comment string instead of key body | Appends duplicate keys when re-applying with a new comment | Dedup on `($PubKey -split '\s+')[1]` (fixed in PR #1451) |
| `StrictModes no` as a permanent workaround on Linux | Hides ACL misconfig; key-auth works but breaks the next time `authorized_keys` is regenerated | Diagnose ownership/perms instead |
| Running `harden-ssh-windows.ps1` without first verifying both agent keys are present | Pre-flight refuses zero parseable `ssh-*` lines, but won't catch a malformed body | `Select-String -Pattern '^ssh-'` before hardening |

### Reference Scripts

| Script | Purpose | Idempotent? |
|--------|---------|-------------|
| `pmoves/scripts/claws/enable-ssh-windows.ps1` | Install OpenSSH, start sshd, inject pubkey, fix ACLs | Yes (since PR #1451) |
| `pmoves/scripts/claws/harden-ssh-windows.ps1` | Apply `sshd_config` hardening with pre-flight key check | Yes — pre-flight refuses if no keys present |

For Linux nodes, the equivalent steps live in the fleet enrollment skill (`fleet:enroll`) — the bring-up sequence is identical, only the file paths and permission commands differ per the table above.

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

## Agent Trail Signing (Split-Trust Model)

PMOVES uses a **split-trust trail signing** architecture for agent attribution and provenance:

### How It Works

1. **Local agent creates unsigned payload** — `sign_trail.py` loads agent identity (glyph, color, voice, resonance) from `agent_signatures.yaml` and builds a JSON payload with the session summary, phase, and timestamp.

2. **Payload is valid without signing** — The unsigned payload is written to `graphiti_signed_latest.json` (gitignored runtime artifact) and can be committed to trail docs (AGNOTE files). Unsigned payloads are fully auditable.

3. **Remote node attests provenance** — HMAC signing via `CHIT_PASSPHRASE` happens on the trusted GPU node (5090) where the passphrase lives. The `sign_cgp()` function from `chit_security.py` produces the HMAC-SHA256 signature.

### Why Split-Trust

| Property | Benefit |
|----------|---------|
| Any node can record work | Dev laptops, CI runners, and edge nodes create trail entries without secrets |
| Only trusted node attests | The HMAC passphrase never leaves the 5090 GPU node |
| Auditable even unsigned | Unsigned payloads contain full agent identity — `[warn] CHIT_PASSPHRASE not set` is expected in dev |
| Three-Body alignment | Maps to the Memory Body (Cipher + CHIT Lane) in the AGNOTE4482 collision-avoidance protocol |

### Trail Lifecycle

```
Agent creates payload → sign_trail.py → graphiti_signed_latest.json (local)
                      → AGNOTE claim register (committed)
                      → agent.graphiti.signed.v1 (NATS, if connected)
                      → 5090 remote signs HMAC (attestation)
```

### Key Files

| File | Purpose |
|------|---------|
| `pmoves/tools/sign_trail.py` | Trail signing CLI tool |
| `pmoves/config/agent_signatures.yaml` | Agent identity registry (11 agents + 3 node agents) |
| `pmoves/tools/chit_security.py` | `sign_cgp()` HMAC signing function |
| `pmoves/contracts/schemas/agent-graphiti/signature.v1.schema.json` | Payload validation schema |
| `pmoves/docs/logs/graphiti_signed_latest.json` | Runtime artifact (gitignored) |
| `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` | Canonical claim register + Agent ACK blocks |

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
