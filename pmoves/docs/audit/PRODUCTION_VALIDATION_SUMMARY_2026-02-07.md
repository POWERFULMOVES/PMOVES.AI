# Production Validation Summary - 2026-02-07

## Audit Scope
- Environment configuration files (env.shared, env.tier-*)
- Docker Compose service definitions
- Database migration files
- Service health and dependency configuration

## Critical Findings

### 🔴 Critical Security Issues (Blocking Production)

1. **All LLM Provider API Keys Empty**
   - ANTHROPIC_API_KEY=
   - OPENAI_API_KEY=
   - GROQ_API_KEY=
   - GEMINI_API_KEY=
   - COHERE_API_KEY=
   - DEEPSEEK_API_KEY=
   - **Impact:** Agent services cannot make LLM calls

2. **CHIT Security Disabled**
   - CHIT_PASSPHRASE=
   - CHIT_REQUIRE_SIGNATURE=false
   - CHIT_DECRYPT_ANCHORS=false
   - **Impact:** Geometry encryption disabled, no signature verification

3. **Supabase Using Example Credentials**
   - PGRST_JWT_SECRET=super-secret-jwt-token-with-at-least-32-characters-long
   - **Impact:** JWT tokens predictable, security risk

4. **Missing MinIO Secret Key**
   - MINIO_SECRET_KEY= (empty in env.shared)
   - **Impact:** S3-compatible storage cannot authenticate

### 🟡 Configuration Issues (17 services affected)

5. **NATS Authorization Missing**
   - 17 services use `NATS_URL=${NATS_URL:-nats://nats:4222}` (no credentials)
   - Should use `nats://nats:pmoves@nats:4222` from env.tier-agent
   - **Affected Services:**
     - Line 725: tensorzero-gateway
     - Line 876: hi-rag-gateway-v1
     - Line 927: hi-rag-gateway-v1-gpu
     - Line 1266: agent-zero (environment override)
     - Line 1294: deepresearch
     - Line 1331: supaserch
     - Line 1365: supabase-studio
     - Line 1386: supabase-storage
     - Line 1403: supabase-realtime
     - Line 1420: supabase-gotrue
     - Line 1556: channel-monitor
     - Line 1601: extract-worker
     - Line 1654: session-context-worker
     - Line 1676: notebook-sync
     - Line 1779: langextract
     - Line 1858: pdf-ingest

6. **channel-monitor PostgreSQL Connection**
   - Uses host.docker.internal:65432 (external)
   - Should use supabase-db:5432 (internal)

### 🟠 Service Startup Issues

7. **ultimate-tts-studio** - Missing `gradio[mcp]` dependency
8. **comfy-watcher** - Missing MINIO_ACCESS_KEY/MINIO_SECRET_KEY
9. **retrieval-eval** - Missing /app/server.py entrypoint
10. **model-registry** - Healthcheck failing (needs investigation)

## Fixes Applied Today

✅ **Database Schema Files Restored**
- Restored 00_pmoves_schema.sql through 15_user_personalization.sql from git history
- Creates pmoves_core schema with agent, session, message, memory, event_log tables

✅ **NATS Healthcheck Added**
- Added healthcheck to NATS service in docker-compose.yml
- Prevents dependency failures when NATS is starting

✅ **Archon NATS Authorization Fixed**
- Removed hardcoded NATS_URL from archon environment section
- Now uses credentials from env.tier-agent

## Environment File Status

| File | Empty Variables | Placeholders | Status |
|------|-----------------|--------------|--------|
| env.shared | ~40 | 5+ | ⚠️ Needs LLM keys |
| env.tier-agent | 0 | 0 | ✅ Good |
| env.tier-supabase | 2 | 0 | 🟡 Minor |
| env.tier-api | TBD | TBD | ❌ Not audited |
| env.tier-data | TBD | TBD | ❌ Not audited |
| env.tier-llm | TBD | TBD | ❌ Not audited |
| env.tier-media | TBD | TBD | ❌ Not audited |
| env.tier-worker | TBD | TBD | ❌ Not audited |

## Next Steps for Production

1. **Immediate (Security):**
   - Generate CHIT_PASSPHRASE
   - Enable CHIT security (signatures, decryption)
   - Rotate Supabase JWT secrets
   - Configure at least one LLM provider API key

2. **High Priority (Services):**
   - Fix 16 remaining NATS_URL configurations
   - Fix channel-monitor PostgreSQL URL
   - Configure MinIO credentials

3. **Medium Priority (Optional Services):**
   - Fix ultimate-tts-studio dependency
   - Fix comfy-watcher credentials
   - Investigate retrieval-eval and model-registry

4. **Validation:**
   - Run full environment audit on all tier files
   - Complete production bring-up checklist
   - Run integration smoke tests

## Documents Created

1. **PRODUCTION_VALIDATION_CHECKLIST.md** - Step-by-step bring-up guide
2. **PRODUCTION_READINESS_REPORT_2026-02-07.md** - Detailed findings
3. **PRODUCTION_VALIDATION_SUMMARY_2026-02-07.md** - This document

## Recommended Commands

```bash
# View all services with NATS auth issue
grep -n "NATS_URL=\${NATS_URL:-nats://nats:4222}" docker-compose.yml

# Find empty env vars
grep -E "=$" env.shared | grep -v "^#" | wc -l

# Generate secure JWT secret
openssl rand -base64 32

# Generate CHIT passphrase
openssl rand -base64 32 | tr -d '/+=' | head -c 32
```

---

**Status:** ⚠️ **NOT READY FOR PRODUCTION**
**Blockers:** LLM API keys, CHIT security, Supabase credentials, 16 NATS auth fixes
**Estimated Time to Ready:** 2-4 hours (assuming API keys available)
