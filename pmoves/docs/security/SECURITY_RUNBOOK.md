# PMOVES.AI Security Runbook

**Version:** 1.0.0
**Last Updated:** 2026-02-07
**Purpose:** Operational procedures for security incident response and credential management

---

## Table of Contents

1. [Credential Management](#credential-management)
2. [Incident Response](#incident-response)
3. [Container Hardening](#container-hardening)
4. [Image Pinning](#image-pinning)
5. [Submodule Security](#submodule-security)
6. [Verification Procedures](#verification-procedures)

---

## Credential Management

### Generating New Supabase Credentials

**When:** Initial setup, credential rotation, suspected compromise

**Procedure:**
```bash
# Navigate to PMOVES.AI directory
cd /home/pmoves/PMOVES.AI

# Run the key generation script
bash pmoves/scripts/supabase/generate-keys.sh

# The script will:
# 1. Generate a cryptographically secure JWT_SECRET (256-bit base64)
# 2. Generate a secure database password
# 3. Generate properly signed JWT tokens for ANON_KEY and SERVICE_ROLE_KEY
```

**Applying Generated Credentials:**
1. Copy the `JWT_SECRET` value from script output
2. Replace `PLACEHOLDER_JWT_SECRET_HERE` in `pmoves/env.shared`
3. Copy the `DB_PASSWORD` value
4. Replace `PLACEHOLDER_DB_PASSWORD_HERE` in `pmoves/env.shared`

### Credential Rotation Schedule

| Credential Type | Rotation Frequency | Trigger |
|-----------------|-------------------|---------|
| JWT_SECRET | Quarterly (90 days) | Scheduled rotation |
| SUPABASE_DB_PASSWORD | Quarterly (90 days) | Scheduled rotation |
| SUPABASE_REALTIME_SECRET | Quarterly (90 days) | Scheduled rotation |
| API Keys (External) | Per provider policy | Provider requirement |
| After Incident | Immediate | Security breach |

### NEVER COMMIT These Values

- `JWT_SECRET` - The signing key for all JWT tokens
- `SUPABASE_DB_PASSWORD` - Database credentials
- `SUPABASE_REALTIME_SECRET` - Realtime signing key
- Any external API keys (OpenAI, Anthropic, etc.)

### SAFE TO COMMIT (Examples)

- `ANON_KEY` - This is a signed JWT, not a secret
- `SERVICE_ROLE_KEY` - This is a signed JWT (but treat with care)
- Placeholder values with `_HERE` suffix
- `.example` files with placeholder content

---

## Incident Response

### Scenario 1: Credentials Committed to Git

**Severity:** CRITICAL

**Immediate Actions:**
1. **DO NOT** push to remote if commit is local only
2. **DO NOT** force push to rewrite history (causes more issues)
3. Regenerate all exposed credentials
4. Create fix-forward commit with placeholder values

**Procedure:**
```bash
# 1. Identify the commit with credentials
git log --all --full-history -- "**/env.shared"

# 2. Generate new credentials
bash pmoves/scripts/supabase/generate-keys.sh

# 3. Replace actual values with placeholders in committed files
#    Use pmoves/env.shared.example as template

# 4. Create security fix commit
git add .
git commit -m "fix(security): Rotate credentials exposed in commit XYZ"

# 5. Document the incident in this runbook
```

**Follow-Up:**
- If pushed to GitHub, consider tokens compromised
- Rotate all Supabase credentials in production
- Review access logs for suspicious activity
- Update this runbook with lessons learned

### Scenario 2: Container Running as Root

**Severity:** HIGH

**Detection:**
```bash
# Check for containers running as root
docker ps --format "{{.Names}}: {{.Image}}" | \
  xargs -I {} sh -c 'docker inspect {} | grep "User" | grep -v "0" || echo {}'
```

**Remediation:**
1. Apply hardening template to service
2. For builds: Add `USER` instruction in Dockerfile
3. For third-party images: Use non-root variant if available
4. Rebuild and redeploy affected services

### Scenario 3: :latest Tag in Production

**Severity:** MEDIUM (but violates CIS Benchmark)

**Detection:**
```bash
# Check for floating tags
grep -r ":latest" pmoves/docker-compose*.yml
grep -r ":pmoves-latest" pmoves/docker-compose*.yml
```

**Remediation:**
1. Identify specific image SHA to pin
2. Update docker-compose.yml with SHA digest
3. Test with pinned image
4. Commit and redeploy

---

## Container Hardening

### Hardening Templates

PMOVES.AI uses two hardening templates in `docker-compose.yml`:

**x-hardening** (Stateless Services)
```yaml
x-hardening: &hardening
  cap_drop:
    - ALL
  cap_add:
    - NET_BIND_SERVICE
  read_only: true
  security_opt:
    - no-new-privileges:true
  tmpfs:
    - /tmp:noexec,nosuid,size=64m
    - /var/tmp:noexec,nosuid,size=64m
```

**x-hardening-rw** (Services with Filesystem Access)
```yaml
x-hardening-rw: &hardening-rw
  cap_drop:
    - ALL
  cap_add:
    - NET_BIND_SERVICE
    - CHOWN
    - SETGID
    - SETUID
  security_opt:
    - no-new-privileges:true
```

### Applying Hardening

To harden a new service:

1. Determine if service needs filesystem access
2. Add appropriate anchor after env tier anchor:
```yaml
your-service:
  <<: *id008           # env tier
  <<: *hardening       # OR *hardening-rw
  image: your-image
```

### Hardened Services (Current)

| Service | Template | Notes |
|---------|----------|-------|
| supabase-postgrest | x-hardening | Stateless API |
| supabase-gotrue | x-hardening-rw | Needs filesystem |
| supabase-storage | x-hardening-rw | Volume mounts |
| supabase-realtime | x-hardening-rw | Websocket state |
| supabase-kong | x-hardening-rw | Database config |
| supabase-studio | x-hardening-rw | UI state |
| agent-zero | x-hardening-rw | Agent state |
| archon | x-hardening-rw | Service state |
| tensorzero-gateway | x-hardening-rw | Config files |

---

## Image Pinning

### CIS Benchmark 1.1.0 Requirement

All container images MUST be pinned to specific SHA256 digests.

### Pinning Procedure

```bash
# 1. Pull the image you want to pin
docker pull <image>:<tag>

# 2. Get the digest
docker inspect <image>:<tag> | jq -r '.[0].RepoDigests[0]'

# 3. Update docker-compose.yml
# FROM:
image: ghcr.io/powerfulmoves/service:latest
# TO:
image: ghcr.io/powerfulmoves/service:tag@sha256:ABC123...

# 4. Verify the image still works
docker compose pull service
docker compose up -d service
```

### Currently Pinned Images

| Service | Image | Status |
|---------|-------|--------|
| supabase-db | supabase/postgres:17.6.1.079 | ✅ Pinned |
| supabase-gotrue | supabase/gotrue:v2.186.0 | ✅ Pinned |
| supabase-postgrest | postgrest/postgrest:v12.2.0 | ✅ Pinned |
| supabase-realtime | supabase/realtime:v2.30.26 | ✅ Pinned |
| supabase-storage | supabase/storage-api:v1.36.2 | ✅ Pinned |
| supabase-studio | supabase/studio:2026.02.04-sha-fba1944 | ✅ Pinned |
| supabase-kong | kong:3.7.1 | ✅ Pinned |
| tensorzero-gateway | tensorzero/gateway:2026.1.8 | ✅ Pinned |

### Needs Pinning (TODO)

| Service | Current Tag | Action Required |
|---------|-------------|-----------------|
| gpu-orchestrator | :latest | Pin to SHA |
| evo-controller | :latest | Pin to SHA |
| flute-gateway | :latest | Pin to SHA |
| session-context-worker | :latest | Pin to SHA |
| grayjay | :latest | Pin to SHA |

---

## Submodule Security

### Hardened Branch Verification

Each submodule should be on the `PMOVES.AI-Edition-Hardened` branch.

**Check:**
```bash
# Check all submodule branches
git submodule foreach 'git branch --show-current'
```

**Expected Output:**
All submodules should show `PMOVES.AI-Edition-Hardened` or `main` (if no hardened branch exists).

### Submodule Security Patterns

From PMOVES-supabase fork (reference implementation):

1. **Non-root user templates** - All services run as dedicated user
2. **Secret management utilities** - Scripts for credential rotation
3. **Database password rotation** - Automated password updates
4. **RLS policy patterns** - Row-Level Security for multi-tenant
5. **Edge Functions security** - Proper JWT validation

### Applying Security Patterns

When updating a submodule:

1. Check PMOVES-supabase for the pattern
2. Adapt pattern to submodule's requirements
3. Test in development environment first
4. Document any changes in submodule's README

---

## Verification Procedures

### Pre-Commit Security Checklist

Before committing changes:

```bash
# 1. Check for accidental credentials
git diff --cached | grep -i "secret\|password\|api_key\|jwt"

# 2. Verify .env files not committed
git diff --cached --name-only | grep -E "\.env$|env\." | grep -v example

# 3. Check for :latest tags
git diff --cached | grep ":latest"

# 4. Validate YAML syntax
docker-compose config > /dev/null

# 5. Run pre-commit hooks
./pmoves/.git/hooks/pre-commit
```

### Pre-Deployment Verification

Before deploying to production:

```bash
# 1. Verify all images are pinned
grep -r ":latest" pmoves/docker-compose*.yml | grep -v "#"

# 2. Verify hardening applied
grep -c "<<: \*hardening" pmoves/docker-compose.yml

# 3. Verify credentials in place
grep PLACEHOLDER pmoves/env.shared

# 4. Check service health
cd pmoves && make verify-all

# 5. Verify network isolation
docker network inspect pmoves_api
docker network inspect pmoves_data
```

### Post-Incident Verification

After security incident:

1. **Credential Rotation:** Confirm new values in place
2. **Access Logs:** Review for suspicious activity
3. **Container Status:** Verify all services running
4. **Health Checks:** All `/healthz` endpoints responding
5. **Monitoring:** No anomalies in Prometheus/Grafana

---

## Security Contacts

| Role | Contact |
|------|---------|
| Security Lead | TBD |
| Infrastructure Lead | TBD |
| On-Call | TBD |

---

## Related Documentation

- `.claude/context/tier-architecture.md` - Environment and network tier architecture
- `pmoves/docs/SUPABASE_UNIFIED_SETUP.md` - Supabase integration guide
- `pmoves/.gitignore` - Files that should never be committed
- `pmoves/scripts/supabase/generate-keys.sh` - Credential generation

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-02-07 | Initial security runbook created | Claude Code |
