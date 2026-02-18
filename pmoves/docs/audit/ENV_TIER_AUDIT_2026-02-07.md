# Environment Tier Audit - 2026-02-07

## Summary

| File | Empty Variables | Placeholder Variables | Status |
|------|-----------------|----------------------|--------|
| env.tier-api | 1 | 1 | 🟡 Minor issues |
| env.tier-data | 3 | 1 | 🔴 Credentials needed |
| env.tier-llm | 3 | 0 | 🟢 OK (optional keys) |
| env.tier-media | 0 | 2 | 🟡 Placeholder defaults |
| env.tier-ui | 0 | 0 | 🟢 Good |
| env.tier-worker | 1 | 1 | 🟡 Minor issues |

## Detailed Findings

### env.tier-api
**Empty Variables:**
- `SUPABASE_SERVICE_ROLE_KEY=` - Required for Supabase access

**Placeholders:**
- `PGRST_DB_URI=postgres://pmoves:changeme@postgres:5432/pmoves` - Default password

**Recommendation:** Set SUPABASE_SERVICE_ROLE_KEY from env.tier-supabase

### env.tier-data
**Empty Variables:**
- `SERVICE_PASSWORD_ADMIN=` - Neo4j admin password
- `SERVICE_PASSWORD_POSTGRES=` - PostgreSQL password
- `SERVICE_USER_ADMIN=` - Admin username

**Placeholders:**
- `NEO4J_PASSWORD=changeme` - Default Neo4j password

**Recommendation:** Generate secure passwords for data services

### env.tier-llm
**Empty Variables (Optional):**
- `OLLAMA_API_KEY=` - Ollama local (no key needed)
- `VOYAGE_API_KEY=` - Optional embedding provider
- `MOONSHOT_API_KEY=` - Optional LLM provider

**Status:** All empty keys are for optional providers

### env.tier-media
**Placeholders (Default Values):**
- `PGRST_DB_URI=${PGRST_DB_URI:-postgres://pmoves:${POSTGRES_PASSWORD:-your_secure_password_here}@postgres:5432/pmoves}`
- `POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-your_secure_password_here}`

**Status:** Uses defaults from env.tier-supabase

### env.tier-ui
**Status:** No empty or placeholder variables ✅

### env.tier-worker
**Empty Variables:**
- `OPEN_NOTEBOOK_API_TOKEN=` - Optional authentication

**Placeholders:**
- `SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_here` - Needs actual value

**Recommendation:** Set SUPABASE_SERVICE_ROLE_KEY from env.tier-supabase

## Priority Actions

1. **High Priority:**
   - Set SUPABASE_SERVICE_ROLE_KEY in env.tier-api and env.tier-worker
   - Generate secure passwords for env.tier-data

2. **Medium Priority:**
   - Update PGRST_DB_URI to use env.tier-supabase credentials
   - Verify Neo4j authentication

3. **Low Priority:**
   - Configure optional LLM provider keys if needed
