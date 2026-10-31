# Cipher Token-Store Recovery — 2026-10-22

**Incident:** cipher per-agent memory writes failed with HTTP 503 from
2026-10-21T04:04:38Z (knuckles). Root cause: the shared `SUPABASE_SERVICE_KEY`
is a Supabase CLI-minted service_role JWT with a **365-day lifetime**, minted
2025-10-21T04:03:43Z, expiring exactly one year later. The first token-lookup
401 hit **55 seconds** after expiry. Cipher's `auth.ts` classifies a failed
service-key lookup as `unavailable` ("couldn't check the token, not that the
token was refused") and the MCP surface returns 503 — so every per-agent
`cipher_<uuid>` write failed while the bootstrap-token path (no Supabase
lookup) kept working, splitting the fleet's cipher behavior by token class.

**Resolution PRs:**
- [#3410](https://github.com/POWERFULMOVES/PMOVES.AI/pull/3410) — funnel
  refreshes expired self-generated Supabase JWTs (rolling 10-year mint, one
  token per role; live/opaque values untouched).
- [#3434](https://github.com/POWERFULMOVES/PMOVES.AI/pull/3434) —
  `SUPABASE_SERVICE_KEY` joins the refresh map: the label `auth.ts` reads
  FIRST (`SUPABASE_SERVICE_KEY ?? SERVICE_ROLE_KEY`) and which the manifest
  projects separately from `SUPABASE_SERVICE_ROLE_KEY`. Measured after #3410
  alone: ROLE_KEY +3650d while SERVICE_KEY kept the corpse at −10d.

## The fix chain (each layer was its own discovery)

1. **Funnel fan-out from the CI bundle.** A CI-bundle node cannot run
   `make secrets-funnel` end-to-end: `chit-export` fail-closed refuses to
   overwrite a CI-pulled bundle (prod-only keys would drop; the 2026-09-03
   TensorZero crash-loop lesson). Road: run `tools/secrets_sync.py generate
   --manifest … --cgp ~/.config/pmoves/chit/env.cgp.json --allow-missing
   --merge` directly — projection without export, prod keys preserved.
2. **env.shared is a projection source too.** env.shared itself carried the
   expired JWTs under three labels AND the dead CLI-topology URLs
   (`host.docker.internal:54321` — nothing has listened there since the CLI
   stack retired). Both refreshed; INTERNAL now points at the in-network
   kong route (`http://supabase-kong:8000/rest/v1`).
3. **Session-exported variables shadow every env_file.** The recreated cipher
   still carried the old key because `crush-env.sh` had exported
   `SUPABASE_SERVICE_KEY` into the agent session, and compose gives the
   process environment precedence over env files — the same mechanism as the
   2026-09-03 `NATS_PASSWORD` register lesson. Road:
   `env -u SUPABASE_SERVICE_KEY … make up-cipher-nobuild`.
4. **Kong is the last key-holder.** With the key fresh, kong answered
   `401 Unauthorized` (no PGRST code = kong, not PostgREST): the dbless
   key-auth credential is an exact-string match on the key as it was at
   container start. `kong reload` does NOT re-read the declarative file.

## Procedure: rotating the kong dbless credential (no container recreate)

```bash
# 1. Patch the credential inside the container's declarative file
#    (/usr/local/kong/kong.yml — service_role consumer keyauth_credentials).
#    NOTE: kong requires UNIQUE key values — one entry per key, not two.
docker cp pmoves-supabase-kong-1:/usr/local/kong/kong.yml /tmp/kong.yml
#    edit service_role credentials to the new JWT, dedupe, then:
# 2. Apply atomically via the admin API (dbless; 'kong reload' won't do it)
python3 -c 'import urllib.request; r=urllib.request.Request("http://127.0.0.1:8001/config?check_hash=1",data=open("/tmp/kong.yml","rb").read(),method="POST",headers={"Content-Type":"application/yaml"}); print(urllib.request.urlopen(r,timeout=10).status)'
#    expect 201
```

Pitfalls measured live: POSTing duplicate key values → 400 uniqueness
violation; direct PostgREST (`supabase-postgrest:3000`) does not serve the
`/rest/v1` prefix — that is kong's route (`supabase-kong:8000/rest/v1`).

## Durability gaps (open)

| Gap | Why it matters | Road |
|---|---|---|
| Kong container env still holds the old keys | A container restart re-runs the entrypoint, which regenerates creds from env → regression | The gated supabase-recreate-from-main reconciliation (steward's narrowed re-claim; dry-run proof first) |
| `.generated/kong.yml` seeder source still stale | Next seeder run re-plants the expired credential | Refresh seeder input from the funnel output |
| Live PostgREST runs on the CLI default placeholder JWT secret | Every JWT in the chain is signed with a public default | Rotate `SUPABASE_JWT_SECRET` fleet-wide (funnel `--keys JWT_SECRET` expands to all derived keys) — operator lane |
| 1-year JWTs from the CLI era persist in CHIT lineage | #3410 refreshes at projection time, but the source values remain | Age out with the next bundle generation |

## Provenance

- Discovery + node restore: `CRUSH-GLM52 (Knuckles)`, session 2026-10-22.
- CHIT trail HMACs: `IDabaXm7…` (diagnosis), `1hST2XdD…` (restore).
- Cipher memory: incident `d6ajP3ZA2dyv`, resolution `rNelbxS0b3id`.
- Register: lane `fix/secrets-expired-jwt-refresh` (CLAIM+RELEASE, PR #3411).

<!-- GRAPHITI_MARK: CRUSH-GLM52::CIPHER-TOKEN-STORE-RECOVERY::2026-10-22 -->
