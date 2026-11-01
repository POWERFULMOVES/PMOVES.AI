# Supabase Service-Key Rotation — Blast Radius & Refresh Runbook

**Context:** the 2026-10-21 service-role JWT expiry (see
[`CIPHER_TOKEN_STORE_RECOVERY_2026-10-22.md`](CIPHER_TOKEN_STORE_RECOVERY_2026-10-22.md))
exposed the full set of consumers of the forked supabase stack's derived
credentials. This is the map for (a) the refresh that already happened and
(b) the coming `SUPABASE_JWT_SECRET` rotation.

## Consumer classes

| Class | Breaks when | Signal |
|---|---|---|
| **Key-consumer** — authenticates to PostgREST with the service/anon JWT | key invalid (expired/rotated) | 401 PGRST303 / kong `Unauthorized` |
| **JWT-verifier** — validates user JWTs locally with `SUPABASE_JWT_SECRET` | secret rotates | stale user tokens fail until re-login |
| **Kong credential holder** — exact-string key-auth in the dbless config | key rotates (kong ignores JWT exp) | 401 no-PGRST-code |
| **URL-consumer** — points at a supabase endpoint | runtime/URL drift | connect timeout (dead `:54321` class) |

## Integration map (measured 2026-10-31, knuckles)

| Integration | Surface | Class | Refresh needed |
|---|---|---|---|
| cipher (Pmoves-cipher) | `auth.ts` per-agent token lookup | key + URL | **done** (recreated; fresh key verified 200) |
| **PMOVES-DoX** | `backend/app/database_supabase.py` direct client | key | submodule env + funnel refresh on its node |
| **PMOVES-BoTZ** (canonical) | compose `SUPABASE_SERVICE_KEY` passthrough + 21 swept NATS cred defaults | key | funnel + compose recreate; NATS sweep in [BoTZ #216](https://github.com/POWERFULMOVES/PMOVES-BoTZ/pull/216) |
| **PMOVES-ToKenism-Multi** | `docker-compose.docked.yml` key passthrough | key | docked overlay refresh |
| **PMOVES-A2UI** | `chit/secrets_manifest_v2.yaml` | key (funnel-declared) | local funnel run |
| **PMOVES-HiRAG** | `chit/secrets_manifest_v2.yaml` + gateway | key (funnel-declared) | local funnel run |
| **PMOVES-Jellyfin / AI-Media-Stack** | api-gateway `server.js`, audio-processor `main.py`, stack compose | key | stack env refresh + backfill re-run |
| **Pmoves-Health-wger** | none direct (own `WGER_API_TOKEN`) | — | no supabase-key action |
| Parent compose agents (agent-zero, archon, presign, tensorzero, minio…) | env chain carries the key | key (latent — no active PostgREST failures measured 2026-10-31) | recreate with `env -u SUPABASE_SERVICE_KEY …` after funnel |
| **PMOVES-supabase (the fork itself)** | kong creds, gotrue, realtime, postgrest | secret-holder | the gated supabase-recreate-from-main lane |

**Standing hazard (measured):** 22 running containers on knuckles carried the
expired JWT in env at audit time; only cipher + nats were fresh. Zero active
401s outside cipher — the exposure is latent, not burning, but every one of
them regresses the next time its service actually calls PostgREST.

## Refresh procedure (per node, post-rotation)

```bash
# 1. Funnel projection with the refreshed bundle (CI-bundle nodes: no export)
cd pmoves && bash scripts/chit_bundle_lock.sh .venv-pmoves/bin/python -c \
  "<secrets_sync generate --manifest … --cgp ~/.config/pmoves/chit/env.cgp.json --allow-missing --merge>"
# 2. env.shared JWT labels + SUPA_REST URLs refresh (see recovery doc)
# 3. Recreate each consumer — CRITICAL: unset session-exported shadows first
env -u SUPABASE_SERVICE_KEY -u SUPABASE_SERVICE_ROLE_KEY -u SERVICE_ROLE_KEY \
    -u SUPABASE_ANON_KEY -u ANON_KEY make -C pmoves up-<svc>
# 4. Kong credential: POST /admin/config (procedure in the recovery doc)
# 5. Verify per consumer: one authenticated /rest/v1 probe with the new key
```

## JWT-secret rotation (the larger lane, operator-gated)

`make -C pmoves secrets-rotate`-style rotation with `--keys JWT_SECRET`
auto-expands to re-derive all derived JWT keys (secrets_sync). Blast radius
beyond the key refresh above: every **JWT-verifier** (gateway/mcp-bridge
family validating user tokens with `SUPABASE_JWT_SECRET`), every in-flight
user JWT, kong's anon+service credentials, realtime/gotrue internal wiring,
and the fork's own config templates (`PMOVES-supabase/docker/volumes/api/`
kong entrypoint substitutes `$SUPABASE_*` at container start). Requires the
supabase stack recreate (gated) in the same window.

<!-- GRAPHITI_MARK: CRUSH-GLM52::SUPABASE-KEY-BLAST-RADIUS::2026-10-31 -->
