# PMOVES.AI Migration Guide

This guide helps you migrate from legacy PMOVES.AI environments to the new 7-tier architecture.

## What Changed?

### Legacy Environment (Single File)
```
pmoves/.env.generated
```
- Single monolithic environment file
- All secrets mixed together
- Difficult to manage permissions
- Hard to identify which services need which variables

### New 7-Tier Architecture
```
pmoves/env.tier-data     # Database credentials
pmoves/env.tier-api      # Internal service URLs
pmoves/env.tier-llm      # LLM provider keys
pmoves/env.tier-media    # Media processing configs
pmoves/env.tier-agent    # Agent orchestration
pmoves/env.tier-worker   # Data processing workers
pmoves/env.tier-ui       # Frontend UI service URLs and client-side configs
```

**Benefits:**
- **Security:** LLM keys isolated to tier-llm only
- **Clarity:** Easy to see which variables belong to which tier
- **Flexibility:** Can share tier files selectively (e.g., tier-llm only with AI team)
- **Validation:** Tier-specific validation rules

## Migration Paths

### Path A: Fresh Start (Recommended)

Best for new deployments or when you can afford downtime.

```bash
# 1. Backup your current configuration
cd pmoves
../scripts/backup_for_fresh_start.sh

# 2. Stop all services
docker compose down

# 3. Migrate environment to tier layout
pmoves env migrate-to-tiers

# 4. Validate the migration
pmoves env validate

# 5. Start services
docker compose up -d

# 6. Verify services are healthy
pmoves env doctor
```

### Path B: Manual Migration

Best if you need fine-grained control over the migration.

```bash
# 1. Create backup
cp pmoves/.env.generated pmoves/.env.generated.backup

# 2. Create tier files manually
cat > pmoves/env.tier-data << 'EOF'
POSTGRES_PASSWORD=your_postgres_password
NEO4J_AUTH=neo4j/your_neo4j_password
MEILI_MASTER_KEY=your_meilisearch_master_key
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=your_minio_password
EOF

cat > pmoves/env.tier-llm << 'EOF'
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
EOF

# 3. Validate each tier
pmoves env validate --tier data
pmoves env validate --tier llm

# 4. Test services before removing legacy file
docker compose up -d
docker compose ps
```

### Path C: CHIT-Based Migration

Best if you're using CHIT for secret management.

```bash
# 1. Encode existing env to CHIT
pmoves secrets encode --env-file pmoves/.env.generated

# 2. Initialize tier files from CHIT
pmoves env init

# 3. Validate
pmoves env validate

# 4. Remove legacy file (after verification)
rm pmoves/.env.generated
```

## Variable Mapping

The following variables have been moved to specific tier files:

### From `.env.generated` to `env.tier-data`

```
POSTGRES_PASSWORD          → env.tier-data
POSTGRES_DB                → env.tier-data
POSTGRES_HOSTNAME          → env.tier-data
POSTGRES_PORT              → env.tier-data
NEO4J_AUTH                 → env.tier-data
MEILI_MASTER_KEY           → env.tier-data
MINIO_ROOT_USER            → env.tier-data
MINIO_ROOT_PASSWORD        → env.tier-data
SERVICE_PASSWORD_ADMIN     → env.tier-data
SERVICE_PASSWORD_POSTGRES  → env.tier-data
SERVICE_USER_ADMIN         → env.tier-data
CHIT_PASSPHRASE            → env.tier-data
```

### From `.env.generated` to `env.tier-api`

```
SUPABASE_JWT_SECRET        → env.tier-api
SUPABASE_SERVICE_ROLE_KEY  → env.tier-api
PRESIGN_SHARED_SECRET      → env.tier-api
GH_PAT_PUBLISH             → env.tier-api
GHCR_USERNAME              → env.tier-api
DOCKERHUB_PAT              → env.tier-api
DOCKERHUB_USERNAME         → env.tier-api
```

### From `.env.generated` to `env.tier-llm`

```
OPENAI_API_KEY             → env.tier-llm
OPENAI_API_BASE            → env.tier-llm
ANTHROPIC_API_KEY          → env.tier-llm
GEMINI_API_KEY             → env.tier-llm
GOOGLE_API_KEY             → env.tier-llm
GROQ_API_KEY               → env.tier-llm
MISTRAL_API_KEY            → env.tier-llm
COHERE_API_KEY             → env.tier-llm
DEEPSEEK_API_KEY           → env.tier-llm
TOGETHER_AI_API_KEY        → env.tier-llm
OPENROUTER_API_KEY         → env.tier-llm
PERPLEXITYAI_API_KEY       → env.tier-llm
XAI_API_KEY                → env.tier-llm
VOYAGE_API_KEY             → env.tier-llm
ELEVENLABS_API_KEY         → env.tier-llm
FIREWORKS_AI_API_KEY       → env.tier-llm
OLLAMA_BASE_URL            → env.tier-llm
TENSORZERO_API_KEY         → env.tier-llm
```

### From `.env.generated` to `env.tier-media`

```
JELLYFIN_API_KEY           → env.tier-media
JELLYFIN_USER_ID           → env.tier-media
JELLYFIN_URL               → env.tier-media
JELLYFIN_PUBLISHED_URL     → env.tier-media
INVIDIOUS_HMAC_KEY         → env.tier-media
INVIDIOUS_COMPANION_KEY    → env.tier-media
DISCORD_WEBHOOK_URL        → env.tier-media
DISCORD_USERNAME           → env.tier-media
DISCORD_AVATAR_URL         → env.tier-media
```

### From `.env.generated` to `env.tier-agent`

```
NATS_URL                   → env.tier-agent
SUPABASE_URL               → env.tier-agent
SUPABASE_ANON_KEY          → env.tier-agent
OPEN_NOTEBOOK_API_TOKEN    → env.tier-agent
OPEN_NOTEBOOK_API_URL      → env.tier-agent
OPEN_NOTEBOOK_PASSWORD     → env.tier-agent
TENSORZERO_URL             → env.tier-agent
HI_RAG_URL                 → env.tier-agent
AGENT_ZERO_URL             → env.tier-agent
DISCORD_WEBHOOK_URL        → env.tier-agent
TELEGRAM_BOT_TOKEN         → env.tier-agent
TAILSCALE_AUTHKEY          → env.tier-agent
CLAUDE_SESSION_CHANNEL_ID  → env.tier-agent
HOSTINGER_API_TOKEN        → env.tier-agent
HOSTINGER_SSH_PRIVATE_KEY  → env.tier-agent
HOSTINGER_SSH_HOST         → env.tier-agent
HOSTINGER_SSH_USER         → env.tier-agent
```

### From `.env.generated` to `env.tier-worker`

```
QDRANT_URL                 → env.tier-worker
MEILI_ADDR                 → env.tier-worker
TENSORZERO_URL             → env.tier-worker
SENTENCE_MODEL             → env.tier-worker
```

### From `.env.generated` to `env.tier-ui`

```
SUPABASE_URL               → env.tier-ui
SUPA_REST_URL              → env.tier-ui
SUPABASE_ANON_KEY          → env.tier-ui
AGENT_ZERO_URL             → env.tier-ui
ARCHON_URL                 → env.tier-ui
TENSORZERO_URL             → env.tier-ui
```

## Post-Migration Validation

### 1. Check Tier Files

```bash
# Verify all tier files exist
ls -la pmoves/env.tier-*

# Check each file has content
for tier in data api llm media agent worker ui; do
  echo "=== env.tier-$tier ==="
  cat pmoves/env.tier-$tier | head -5
  echo ""
done
```

### 2. Run Validation

```bash
# Validate all tiers
pmoves env validate

# Validate specific tiers
pmoves env validate --tier data
pmoves env validate --tier llm
```

### 3. Test Service Startup

```bash
# Start services
cd pmoves
docker compose up -d

# Check service status
docker compose ps

# Check for errors
docker compose logs --tail=50
```

### 4. Verify Service Health

```bash
# Run diagnostics
pmoves env doctor

# Check specific service health
curl http://localhost:8080/healthz  # Agent Zero
curl http://localhost:8091/healthz  # Archon
curl http://localhost:8086/healthz  # Hi-RAG v2
```

## Rollback Procedure

If you encounter issues after migration, you can roll back:

```bash
# 1. Stop services
cd pmoves
docker compose down

# 2. Restore from backup
cp pmoves/.env.generated.backup pmoves/.env.generated

# 3. Remove tier files
rm pmoves/env.tier-*

# 4. Restart services
docker compose up -d

# 5. Verify services
docker compose ps
```

## Troubleshooting

### Issue: Services Not Starting After Migration

**Symptoms:** Services fail to start with "missing environment variable" errors.

**Solution:**
```bash
# Check which variables are missing
pmoves env validate --tier all

# Compare with legacy file
diff pmoves/.env.generated.backup \
  <(cat pmoves/env.tier-* | grep -v "^#")

# Add missing variables to appropriate tier
```

### Issue: Validation Fails with "Placeholder Value"

**Symptoms:** Validation reports placeholder values like `changeme_*`.

**Solution:**
```bash
# Find placeholder values
grep -r "changeme\|placeholder\|your_.*_here" pmoves/env.tier-*

# Replace with actual values
# Edit each tier file and replace placeholders
```

### Issue: Docker Compose Can't Find Tier Files

**Symptoms:** Docker Compose errors about missing env files.

**Solution:**
```bash
# Check file paths
ls -la pmoves/env.tier-*

# Verify docker-compose.yml references
grep "env_file" pmoves/docker-compose.yml

# Ensure paths are relative to docker-compose.yml location
```

### Issue: CHIT Decode Fails

**Symptoms:** `pmoves secrets decode` fails with parsing errors.

**Solution:**
```bash
# Check CGP file format
cat pmoves/pmoves/data/chit/env.cgp.json | python3 -m json.tool

# Verify version
grep '"version"' pmoves/pmoves/data/chit/env.cgp.json

# Re-encode from source if needed
pmoves secrets encode --env-file pmoves/env.shared
```

## Advanced: Custom Tier Configuration

If you need to customize tier assignments:

```bash
# Edit the tier mapping
vim pmoves/chit/secrets_manifest_v2.yaml

# Regenerate CHIT with new mapping
python3 pmoves/tools/generate_chit_v2.py

# Re-encode secrets
pmoves secrets encode

# Re-initialize tier files
pmoves env init --force
```

## Next Steps

After successful migration:

1. **Remove legacy files** (after verification):
   ```bash
   rm pmoves/.env.generated
   rm pmoves/.env.generated.backup.*
   ```

2. **Update CI/CD pipelines** to use tier files:
   ```yaml
   # GitHub Actions example
   - name: Validate environment
     run: pmoves env validate --json
   ```

3. **Document custom configurations** for your team:
   ```markdown
   # Our Environment Configuration
   - Tier files stored in: `/path/to/pmoves/env.tier-*`
   - LLM keys: Contact AI team for tier-llm access
   - Database credentials: Contact DevOps for tier-data access
   ```

4. **Set up rotation schedule** for sensitive credentials:
   ```bash
   # Rotate database passwords quarterly
   # Rotate API keys monthly
   # Use CHIT for secure distribution
   ```

## Security Hardening (v1.5 → v2.0)

### Breaking Change: RLS Policy Authentication

**Affected Tables:**
- `public.detections`, `public.segments`, `public.emotions` (media analysis)
- `public.anchors`, `public.constellations`, `public.shape_points`, `public.shape_index` (geometry bus)

**What Changed:**
- **Before:** Policies allowed anonymous access (`TO anon`) with a fallback to `namespace = 'pmoves'`
- **After:** Policies require authentication (`TO authenticated`) with NO fallback

**Impact:**
- Services without JWT authentication will receive permission denied errors
- The `'pmoves'` namespace fallback has been removed for strict tenant isolation
- All database access must now provide:
  1. Valid JWT token via `Authorization: Bearer <token>` header
  2. Tenant context via `SET LOCAL app.current_tenant = 'tenant_name'`

**Migration Steps:**

1. **Update your application to include JWT tokens:**
   ```bash
   # Get JWT from Supabase
   SUPABASE_ANON_KEY="your-anon-key"
   JWT_TOKEN=$(curl -s -X POST \
     "https://your-project.supabase.co/auth/v1/token?grant_type=password" \
     -H "apikey: $SUPABASE_ANON_KEY" \
     -d '{"email":"user@example.com","password":"password"}' | jq -r '.access_token')

   # Include in API requests
   curl -H "Authorization: Bearer $JWT_TOKEN" \
     http://localhost:3000/rest/v1/detections
   ```

2. **Set tenant context for multi-tenant deployments:**
   ```sql
   -- In your application or migration script
   SET LOCAL app.current_tenant = 'your_tenant_name';

   -- Now queries will only return data for this tenant
   SELECT * FROM detections;
   ```

3. **Verify RLS policies are active:**
   ```sql
   -- Check current policies
   SELECT schemaname, tablename, policyname, roles
   FROM pg_policies
   WHERE schemaname = 'public'
     AND tablename IN ('detections', 'segments', 'emotions', 'anchors', 'constellations');
   ```

**Rollback (if needed):**
```sql
-- To temporarily allow anon access (NOT RECOMMENDED for production)
ALTER POLICY detections_tenant_isolation ON public.detections
  TO anon
  USING (namespace = current_setting('app.current_tenant', true) OR namespace = 'pmoves')
  WITH CHECK (namespace = current_setting('app.current_tenant', true) OR namespace = 'pmoves');
```

**See Also:**
- Row Level Security documentation: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- Supabase RLS guide: https://supabase.com/docs/guides/auth/row-level-security

## Additional Resources

- **Environment Setup:** `ENVIRONMENT_SETUP.md`
- **CHIT Documentation:** `.claude/context/chit-geometry-bus.md`
- **Services Catalog:** `.claude/context/services-catalog.md`
- **CLI Reference:** Run `pmoves --help`
