# Handoff: restore GH_APP_SEC PEM on b850 (2026-11-19)

**To:** B850-CLAUDE (Knuckles) · **From:** CRUSH-SPARK (KIMI) · **Priority:** high — b850 is one of two bundle producers.

## What happened
`GH_APP_SEC` (GitHub App pmoves-ai / id 1041682 private key) was a **40-hex
string, not a PEM**, in env.shared + the CHIT bundle. The funnel propagated it
to the repo secret, breaking `create-github-app-token` fleet-wide ("A JSON web
token could not be decoded") — fork-sync failed daily 2026-11-09 → 11-19.

## Fixed everywhere EXCEPT b850
- GH repo secret `GH_APP_SEC` (PMOVES.AI): operator rotated the App key;
  spark pushed the new PEM (validated via `GET /app` JWT mint). fork-sync green.
- spark: env.shared, env.tier-agent, canonical CHIT bundle — PEM throughout
  (fresh spark-produced bundle `chit-bundle-spark-44594018771`).
- **b850: local env + any bundle it produces still carry the hex.** Its producer
  runs (`sync-secrets-local.yml` target=b850) re-export the corrupt value.

## The fix on b850 (same recipe spark used)
1. Operator provides the App PEM (`pmoves-ai.2026-11-19.private-key.pem`, also
   downloadable from GitHub App settings → generate new private key ONLY if
   a fresh rotation is wanted — re-generating invalidates the current key
   everywhere; prefer the existing file).
2. Write into `pmoves/env.shared` as a single `\n`-escaped line:
   `python3 -c "from pathlib import Path; pem=Path('<pem-path>').read_text().strip(); assert pem.startswith('-----BEGIN'); f=Path('pmoves/env.shared'); f.write_text('\n'.join(('GH_APP_SEC='+pem.replace(chr(10),'\\\\n')) if l.startswith('GH_APP_SEC=') else l for l in f.read_text().splitlines())+'\n')"`
3. **Validate before funneling** (do not push an unvalidated key):
   mint a JWT with the PEM and `GET https://api.github.com/app` — expect
   `{"name": "PMOVES.AI", "slug": "pmoves-ai"}`.
4. `env -u NATS_URL -u SUPABASE_SERVICE_ROLE_KEY -u SUPABASE_SERVICE_KEY make -C pmoves secrets-funnel`
   (CHIT_EXPORT_FORCE=1 if the CI-bundle guard trips, then re-pull).
5. Verify: next `sync-secrets-local.yml` b850 artifact carries the PEM
   (`chit-bundle-b850-<run>` → GH_APP_SEC point decodes to `-----BEGIN RSA`).

## Hazards (measured on spark this session)
- `gh secret set` via `with-env.sh` env indirection can silently push an EMPTY
  secret (loader precedence) — set from the file directly:
  `gh secret set GH_APP_SEC -R POWERFULMOVES/PMOVES.AI < app.pem`.
- A consumer-side `secrets-funnel-from-prod` against a stale b850 bundle will
  **regress a fixed node** to the hex — pull bundles produced AFTER step 4.
- fork-sync.yml now uses `client-id` (deprecation fix) once #3353 merges.
