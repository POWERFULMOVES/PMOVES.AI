# Firefly III External Stack – Bootstrap Checklist

_Last updated: 2025-10-20_

This note captures the fast path to get the Firefly III finance stack online inside the `pmoves` external integrations workspace, align it with Geometry Bus (CHIT) consumers, and surface an API token for downstream automation.

## 1. Compose + environment requirements
- The shared external compose (`pmoves/docker-compose.external.yml`) now pins Firefly III to the published `ghcr.io/cataclysm-studios-inc/pmoves-firefly-iii:pmoves-latest` image, binds to `FIREFLY_PORT` (compose default `8080`, but we set `FIREFLY_PORT=8082` in `env.shared` to avoid Agent Zero on 8080), and mounts a named volume `firefly-storage` so the SQLite database persists across restarts.
- New environment knobs:
  - `FIREFLY_APP_KEY` → Laravel encryption key. Defaults to `SomeRandomStringOf32CharsExactly` for local smoke tests; override with a generated key before pushing to shared stacks.
  - `FIREFLY_APP_ENV`, `FIREFLY_SITE_OWNER`, `FIREFLY_TZ`, `FIREFLY_TRUSTED_PROXIES` → quality-of-life defaults that keep HTTP + logging sane behind pmoves’ reverse proxies.
  - `FIREFLY_DB_CONNECTION`/`FIREFLY_DB_DATABASE` → default to SQLite in the mounted storage directory. Swap to Postgres when we point at managed infra.
- To override any value, drop it in `pmoves/.env.local` (checked-in template) or export it inline before running `make`.

## 2. Bring the container up (or recycle it)
```bash
# optional: avoid 8080 conflicts, pick an open host port
export FIREFLY_PORT=8082

# start or recreate just Firefly
make -C pmoves up-external-firefly
```
- Healthy startup log ends with Laravel migrations finishing and HTTP 302 when curling `/`.
- The first boot seeds an empty SQLite db under the `firefly-storage` volume.

## 3. Generate + store the encryption key
- Quick local default (already wired): leave `FIREFLY_APP_KEY` unset to fall back to `SomeRandomStringOf32CharsExactly`.
- Recommended for anything beyond smoke testing:
  ```bash
  # Generate a fresh base64 key and append it to pmoves/.env.local
  docker exec pmoves-firefly php -r 'echo "FIREFLY_APP_KEY=base64:".base64_encode(random_bytes(32)).PHP_EOL;'
  ```
  - Copy the line into `pmoves/.env.local`, replace the existing value, then recycle the container:
    ```bash
    make -C pmoves up-external-firefly
    ```

## 4. Create the first admin + login
- Visit `http://localhost:${FIREFLY_PORT:-8082}` and walk through the onboarding wizard to register the initial admin (email + password).
- Use a temporary password during setup, then rotate it immediately from the Profile menu to keep the shell history clean.

## 5. Produce API tokens for Geometry Bus + n8n flows
Two supported paths once you have an admin session:

- **CLI (fastest, scriptable)**
  ```bash
  docker exec pmoves-firefly php artisan firefly-iii:generate-access-token \
    --email ops@pmoves.ai \
    --description 'pmoves-geometry-bus' \
    --permissions read,write
  ```
  - The command prints the token once; capture it immediately.
  - Record the value in `pmoves/.env.local` as `FIREFLY_ACCESS_TOKEN=…` (consumed by n8n sync + CHIT adapters).

- **UI (if you prefer manual)**  
  Profile → Options → API → “Create new token”, give it a descriptive label (`pmoves-cgp`), select scopes, copy the token, and store it in `pmoves/.env.local`.

After updating the env file, restart dependent services so they pick up the credential:
```bash
make -C pmoves up-n8n
make -C pmoves up-external-firefly
```

## 6. Wire into CHIT + downstream integrations
- Populate `FIREFLY_ACCESS_TOKEN` and point the Geometry Bus ingest workflows (`finance.transactions.ingested.v1`) to Firefly’s REST API at `http://pmoves-firefly:8080/api/v1`.
- Confirm the n8n “finance-cgp” webhook flow dispatches envelopes to CHIT once the token is active (see `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` for evidence logging templates).
- Update Supabase seeds / migrations to include Firefly account metadata if we promote this dataset beyond local smoke tests.

## 7. Troubleshooting checklist
- **HTTP 500 / blank page** → verify `FIREFLY_APP_KEY` is 32 chars or a `base64:` string and recycle the container.
- **401 from n8n sync** → confirm `FIREFLY_ACCESS_TOKEN` in `.env.local` matches the freshly generated token, then rerun `make -C pmoves up-n8n`.
- **Port collision** → override `FIREFLY_PORT` before calling `make` (see step 2).
- **Lost data after restart** → ensure `firefly-storage` volume exists (`docker volume inspect pmoves_firefly-storage`). Recreate if needed.

Once these items are green, capture the success logs + token inventory in `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` so the roadmap checkpoints stay accurate.
