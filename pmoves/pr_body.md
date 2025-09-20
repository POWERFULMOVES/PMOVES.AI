## feat(dev): Supabase CLI mode + env switching; pmoves.yt hardening; NATS opt‑in

### Summary
This update adds a clean local Supabase CLI mode (no Compose Postgres/PostgREST conflict), easy env switching between local/remote Supabase, hardens pmoves.yt imports, and makes NATS eventing opt‑in with a helper target.

### Highlights
- `SUPA_PROVIDER=cli` default; `.env.local` overlay controls endpoints/keys.
- Helpers: `make supa-init|supa-start|supa-stop|supa-status`, `make supa-use-local|supa-use-remote`, `make supa-extract-remote`.
- pmoves.yt: import shim for `services.common.events`, `PYTHONPATH=/app`, non‑blocking NATS behind `YT_NATS_ENABLE` (default false).
- New `make up-nats` starts broker and writes `YT_NATS_ENABLE=true` + `NATS_URL=nats://nats:4222` to `.env.local`.
- Docs: `docs/SUPABASE_SWITCH.md`, `docs/MAKE_TARGETS.md`, and `docs/LOCAL_DEV.md` updates.

### How to Use (Local Supabase CLI)
1) Install CLI: `winget install supabase.supabase` (or `npm i -g supabase`)
2) `make supa-init` → `make supa-start`
3) `make supa-use-local` then `make supa-status` and paste keys into `.env.local`
4) `make up`

### Switch to Self‑Hosted Supabase
- `make supa-extract-remote` → `.env.supa.remote`
- `make supa-use-remote` → writes `.env.local`
- `make up`

### Events (NATS)
- `make up-nats` (starts broker and enables env)
- Restart emitters as needed (e.g., `docker compose -p pmoves up -d pmoves-yt`)

### Rebuild pmoves.yt if needed
`docker compose -p pmoves --profile data --profile workers build --no-cache pmoves-yt && docker compose -p pmoves --profile data --profile workers up -d pmoves-yt`

### Reviewer Checklist
- [ ] Pull branch: `git fetch origin feat/supabase-cli-switch && git checkout feat/supabase-cli-switch`
- [ ] Supabase CLI local mode: `make supa-start && make supa-use-local` (paste keys from `make supa-status` into `.env.local`)
- [ ] Bring up stack: `make up` then verify `docker compose -p pmoves ps`
- [ ] pmoves.yt health: `curl http://localhost:8077/healthz` returns `{ "ok": true }`
- [ ] Optional events: `make up-nats`, restart emitters (e.g., `docker compose -p pmoves up -d pmoves-yt`), verify no NATS errors in logs
- [ ] Self‑hosted switch: `make supa-extract-remote && make supa-use-remote && make up` (endpoints, keys respected)
- [ ] Docs render: skim `docs/MAKE_TARGETS.md` and `docs/SUPABASE_SWITCH.md`
