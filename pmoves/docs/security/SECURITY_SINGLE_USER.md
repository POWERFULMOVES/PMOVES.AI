# PMOVES Single‑User Mode (Owner Mode)

PMOVES is personal‑first. In Single‑User mode the local operator is the owner/admin and the console avoids login prompts while still keeping data access explicit and auditable.

- Owner identity: a Supabase “boot user” JWT (managed by `make supabase-boot-user`).
- UI behavior: if the boot JWT is valid, the browser adds `Authorization: Bearer <jwt>`; if expired or absent, the UI falls back to the anon role but derives `ownerId` from the token `sub` for safe, server‑filtered reads.
- Server reads: server components and API routes use the service‑role key; RLS continues to enforce `owner_id` and namespace scoping.

## Enable
- Set in `pmoves/env.shared` (already in example):
  - `SINGLE_USER_MODE=1`
  - `NEXT_PUBLIC_SINGLE_USER_MODE=1`
- Ensure the boot user exists and JWT is fresh:
  - `make -C pmoves supabase-boot-user`
  - Restart the console: `make -C pmoves ui-dev-stop && make -C pmoves ui-dev-start`

## UX
- Console shows an “Owner mode” chip in the nav.
- Ingestion and Videos pages continue working even if the boot JWT expires; the UI reads with anon and server filters by `ownerId`.
- You can still sign in manually if you disable `SINGLE_USER_MODE`.

## Security Notes
- Local development exposes PostgREST on localhost; service‑role keys remain on the server (Node) side.
- Do not publish service‑role keys in public builds. For remote/self‑host, front the stack with CHIT‑backed gateways and rotate secrets regularly.
- Future: CHIT encryption keys and attested flows will replace or front the boot JWT for stronger assertions.

## Troubleshooting
- “Boot token expired” banner but pages still work: this is expected; rotate the boot JWT to remove the banner.
- Videos list shows “Failed to load rows”: confirm anon can `select` from `videos` or keep the page backed by server routes.
