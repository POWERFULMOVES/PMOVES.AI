# Environment Policy (Single‑File Mode)

- Source of truth: `pmoves/env.shared` (+ generated `env.shared.generated`).
- Default mode is single‑file: Make, Compose and the UI read only these files.
- Legacy `.env.local` layering is disabled unless you export `SINGLE_ENV_MODE=0`.
- Service‑specific variables and examples live in each service’s docs under `pmoves/docs/services/<service>/README.md` (or the service directory README).
- Integration‑specific additions (previously `env.*.additions`) are now documented where they are used; the root working directory should not accumulate service overrides.

## Jellyfin host folders
- List host or network paths in `pmoves/jellyfin.hosts`, one per line:
  - `/mnt/c/Media:WindowsMedia:ro`
  - `//NAS/Share/Movies:NASMovies:rw`
- Generate override: `make -C pmoves jellyfin-hosts-generate`.
- Start single instance: `make -C pmoves up-jellyfin-single` (port 8096).

## Quick commands
- Rotate Supabase boot JWT: `make -C pmoves supabase-boot-user`.
- Restart UI dev: `make -C pmoves ui-dev-stop && make -C pmoves ui-dev-start`.
- One‑click Agents (APIs+UIs): `make -C pmoves up-agents-ui`.

## Tailscale (optional)

You can auto-join a tailnet during `make first-run` by setting the following in `pmoves/env.shared`:

```
TAILSCALE_AUTO_JOIN=true
TAILSCALE_TAGS=tag:pmoves,tag:homelab
# Provide a key via either of these
TAILSCALE_AUTHKEY=tskey-...
TAILSCALE_AUTHKEY_FILE=CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/tailscale/tailscale_authkey.txt
```

- Save/update the key interactively: `make -C pmoves tailscale-save-key` (or pass `TAILSCALE_AUTHKEY=… make -C pmoves tailscale-save-key`).
- Join manually anytime: `make -C pmoves tailscale-join`.
- Force re-auth: `make -C pmoves tailscale-rejoin`.
- Status: `make -C pmoves tailscale-status`.

When Tailnet Lock is enabled, the init script attempts to sign the key (configurable via `TAILSCALE_SIGN_AUTHKEY`). If a new signed key is returned, it is written back to the secret file with 0600 permissions.

## PostgREST vs Supabase REST
- Preferred: the Supabase CLI REST at `http://host.docker.internal:65421/rest/v1`.
- Historical note: a standalone PostgREST (3010/3011) previously served the `pmoves_core` schema via `Accept-Profile` because Supabase REST was only exposing `public`.
- Now: `supabase/config.toml` includes `pmoves_core` and `pmoves_kb` under `[api] schemas`, and DB grants are applied so Supabase REST can serve these schemas directly.
- Action: keep `POSTGREST_URL` commented in `pmoves/env.shared`. If you started the compose PostgREST, stop it: `docker stop pmoves-postgrest-1 pmoves-postgrest-cli-1`.
- Verify: `curl -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -H 'Accept-Profile: pmoves_core' http://127.0.0.1:65421/rest/v1/personas?limit=1` → HTTP 200.
