# 5090 Node: JWT Secret Rotation + Runtime Secrets Hydration Runbook

Provenance: methodology proven on the DARKXSIDE node 2026-09-26/27 (see
`pmoves/chat-corpus/ITERATIONS.md` and PR #3204 thread). Tooling: #2956
`runtime_secrets_hydrate.py` + this runbook.

## Prerequisites

- SSH access to the 5090 node
- Docker running with the pmoves Supabase stack **up** (hydrate needs live
  containers to source real credentials from)
- Node has pulled latest main (gets `runtime_secrets_hydrate.py` + this doc)

## Phase 1: Hydrate runtime secrets from owning containers

The hydrate tool replaces placeholder values in `env.shared` with the real
credentials already baked into running containers. It is deliberately
**container-only** for Postgres/MinIO/Neo4j/ClickHouse — no random fallback —
so it cannot turn a placeholder into a wrong password.

```bash
cd /path/to/PMOVES.AI

# 1. Supabase stack must be running (hydrate reads container env)
docker compose up -d supabase-db supabase-kong supabase-gotrue supabase-postgrest

# 2. Generate the Supabase status snapshot
make supa-status

# 3. Preview what would be hydrated (no writes)
python pmoves/tools/runtime_secrets_hydrate.py --dry-run

# 4. Apply
python pmoves/tools/runtime_secrets_hydrate.py
```

This fills: `POSTGRES_PASSWORD`, `SUPABASE_DB_PASSWORD`, `SERVICE_PASSWORD_POSTGRES`,
`MINIO_ROOT_USER/PASSWORD`, `NEO4J_AUTH/PASSWORD`, `TENSORZERO_CLICKHOUSE_*`,
`PG_META_CRYPTO_KEY`, `LOGFLARE_*_ACCESS_TOKEN`, `MEILI_MASTER_KEY`,
`FIREFLY_APP_KEY`, `AGENT_ZERO_EVENTS_TOKEN`, `INVIDIOUS_COMPANION_KEY`,
`SUPABASE_SERVICE_KEY`, `SUPABASE_REALTIME_KEY`, `SUPABASE_REALTIME_SECRET`.

## Phase 2: Rotate the JWT secret + re-mint keys

> **Why**: the stock deployment ships demo-era keys (`iss=supabase-demo`) and a
> demo `SUPABASE_JWT_SECRET` that disagrees with the real `JWT_SECRET`. Every
> key PostgREST checks then fails with PGRST301 behind pmoves-ui 503.

```bash
# 5. Generate a new JWT secret (128 hex chars)
python3 -c "import secrets; print(secrets.token_hex(64))" > /tmp/new_jwt_secret

# 6. Mint anon + service_role HS256 tokens signed with the NEW secret
node -e "
const crypto=require('crypto');const fs=require('fs');
const s=fs.readFileSync('/tmp/new_jwt_secret','utf8').trim();
const b64u=x=>Buffer.from(x).toString('base64').replace(/=+$/,'').replace(/\+/g,'-').replace(/\//g,'_');
const now=Math.floor(Date.now()/1000);
const mk=r=>{const h=b64u(JSON.stringify({alg:'HS256',typ:'JWT'}));
const p=b64u(JSON.stringify({role:r,iss:'supabase-local',iat:now,exp:now+315360000}));
const sig=crypto.createHmac('sha256',s).update(h+'.'+p).digest('base64').replace(/=+$/,'').replace(/\+/g,'-').replace(/\//g,'_');
return h+'.'+p+'.'+sig};
fs.writeFileSync('/tmp/newkeys.txt',mk('anon')+'\n'+mk('service_role')+'\n');
"

# 7. Update env files (replace ALL key/secret variables)
NEW_SECRET=$(cat /tmp/new_jwt_secret)
NEW_ANON=$(head -1 /tmp/newkeys.txt)
NEW_SRK=$(tail -1 /tmp/newkeys.txt)

for f in env.shared env.shared.generated .env.generated env.tier-agent env.tier-media env.tier-worker env.tier-supabase env.tier-ui; do
  [ -f "$f" ] || continue
  sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$NEW_SECRET|" "$f"
  sed -i "s|^SUPABASE_JWT_SECRET=.*|SUPABASE_JWT_SECRET=$NEW_SECRET|" "$f"
  sed -i "s|^ANON_KEY=.*|ANON_KEY=$NEW_ANON|" "$f"
  sed -i "s|^SERVICE_ROLE_KEY=.*|SERVICE_ROLE_KEY=$NEW_SRK|" "$f"
  sed -i "s|^SUPABASE_ANON_KEY=.*|SUPABASE_ANON_KEY=$NEW_ANON|" "$f"
  sed -i "s|^SUPABASE_SERVICE_ROLE_KEY=.*|SUPABASE_SERVICE_ROLE_KEY=$NEW_SRK|" "$f"
  sed -i "s|^SUPABASE_SERVICE_KEY=.*|SUPABASE_SERVICE_KEY=$NEW_SRK|" "$f"
  echo "updated: $f"
done
```

## Phase 3: Recreate the JWT-consuming services

```bash
# 8. Load env and recreate
set -a; source env.shared; source env.tier-supabase; set +a
export SUPABASE_DB_USER=$(docker exec pmoves-supabase-db-1 printenv POSTGRES_USER)
export SUPABASE_DB_PASSWORD=$(docker exec pmoves-supabase-db-1 printenv POSTGRES_PASSWORD)
export DASHBOARD_PASSWORD=$(docker exec pmoves-supabase-kong-1 printenv SUPABASE_KONG_DASHBOARD_PASSWORD 2>/dev/null || echo 'changeme')

docker compose -p pmoves \
  -f docker-compose.yml -f docker-compose.comfyui.yml \
  -f docker-compose.ultimate-tts-studio.yml -f docker-compose.archon.submodule.yml \
  -f docker-compose.apps.yml \
  up -d --force-recreate --no-deps supabase-kong supabase-postgrest supabase-gotrue pmoves-ui

# 9. Verify
sleep 60
NEW_ANON=$(head -1 /tmp/newkeys.txt)
OLD_ANON=<old-anon-key>

echo -n "new key -> "
curl -s -o /dev/null -w '%{http_code}' -H "apikey: $NEW_ANON" -H "Authorization: Bearer $NEW_ANON" http://127.0.0.1:8000/rest/v1/
echo " (expect 200)"

echo -n "old key -> "
curl -s -o /dev/null -w '%{http_code}' -H "apikey: $OLD_ANON" -H "Authorization: Bearer $OLD_ANON" http://127.0.0.1:8000/rest/v1/
echo " (expect 401)"

echo -n "UI health -> "
curl -s http://127.0.0.1:<ui-port>/api/health | grep -o '"database":{"status":"[^"]*"}'
echo " (expect healthy)"
```

## Phase 4: Cleanup

```bash
# 10. Shred temp key files
shred -u /tmp/new_jwt_secret /tmp/newkeys.txt 2>/dev/null || rm -f /tmp/new_jwt_secret /tmp/newkeys.txt
```

## Acceptance criteria

| Check | Expected |
|---|---|
| New anon key → `GET /rest/v1/` | HTTP 200 |
| Old anon key → `GET /rest/v1/` | HTTP 401 |
| `POST /api/health` | `database: healthy` |
| All supabase containers | healthy |
| Hydrate dry-run | 0 placeholders remaining |

## Rollback

If anything breaks, the old env files are the rollback — restore from backup,
recreate, done. The old keys work again because the old JWT secret is still in
the env files (Kong renders from env at container start).
