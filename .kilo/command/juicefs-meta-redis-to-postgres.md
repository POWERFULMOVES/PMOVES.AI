# juicefs-meta-redis-to-postgres

Z890 lane (per the multi-engine voice design §1a operator decision: **JuiceFS
metadata engine = Postgres, not Redis**). Align the JuiceFS PoC compose onto the
Postgres metadata engine that the cross-node mount already uses, and retire the
Redis metadata service. Gate this before the voice catalog relies on JuiceFS.

## Arguments

- `meta_url` (string, optional): Postgres JuiceFS metadata DSN. Default matches
  `juicefs-mount-local`: `postgres://supabase_admin:${SUPABASE_DB_PASSWORD}@<host>:5432/postgres?search_path=juicefs_meta&sslmode=disable`.
- `retire_redis` (bool, optional, default true): remove `juicefs-redis` + its `juicefs-meta` volume once nothing references it.

## Implementation

Current state (verified on `main`): the **cross-node mount** already uses Postgres
(`pmoves/mk/egress.mk` `juicefs-mount-local` → `postgres://…?search_path=juicefs_meta`),
but the **PoC compose** still defaults to Redis
(`pmoves/docker-compose.yml`: `juicefs-redis` service + `juicefs-format`/`juicefs-gateway`
using `${JUICEFS_META_URL:-redis://juicefs-redis:6379/1}`). Unify on Postgres:

1. In `pmoves/docker-compose.yml`, change the `juicefs-format` + `juicefs-gateway`
   default `JUICEFS_META_URL` from `redis://juicefs-redis:6379/1` to the Postgres
   DSN (tier-data supabase; `search_path=juicefs_meta`). Drop the `juicefs-redis`
   `depends_on` and point `depends_on` at the supabase DB service instead.
2. Retire the `juicefs-redis` service + `juicefs-meta` volume (`retire_redis`).
3. Ensure `juicefs format` runs once against the Postgres meta (idempotent). The
   PoC FS is empty → no data migration; if any data exists, note it and use
   `juicefs load`/`dump` per the JuiceFS docs before reformat.
4. Regenerate the split overlay: `make -C pmoves compose-split`; verify
   `docker-compose.media.yml` (or the juicefs overlay) reflects the change and
   `make compose-split-check` is drift-clean.
5. Smoke: with the `juicefs` profile up, `make -C pmoves juicefs-status` and a
   round-trip write/read through `juicefs-gateway` (S3 drop-in) succeed against
   the Postgres-backed FS.

Files:
- `pmoves/docker-compose.yml` — `juicefs-format`, `juicefs-gateway`, remove `juicefs-redis` (+ volume)
- regenerated `pmoves/docker-compose.*.yml` via `compose-split`
- `pmoves/docs/architecture/JUICEFS_OBJECT_STORE_MIGRATION.md` — update the meta-engine section

## Related

- `pmoves/docs/architecture/JUICEFS_OBJECT_STORE_MIGRATION.md`
- `pmoves/mk/egress.mk` — `juicefs-mount-local` (the Postgres DSN precedent), `juicefs-cross-node-setup`, `juicefs-mount-status` (renamed from `juicefs-status`, which now unambiguously means the S3-gateway PoC target in `pmoves/Makefile`)
- `pmoves/scripts/juicefs-cross-node-setup.sh`
- multi-engine voice design §1a (metadata=Postgres decision) + §5 (voice catalog on JuiceFS, MinIO-interim until this lands)

## Notes

- Secrets: `SUPABASE_DB_PASSWORD` comes through the secrets pipeline — do NOT hand-edit tier env files; use the funnel. Never put the DSN password literal in compose (use `${SUPABASE_DB_PASSWORD}`).
- This is the **gate** before S7 (voice catalog on JuiceFS) — until it lands, the voice path uses the MinIO-interim catalog, so no voice work is blocked on it.
- Coordinate with the tier-data lane (the Postgres is supabase); `search_path=juicefs_meta` keeps JuiceFS tables namespaced away from app schemas.
- Profile-gated (`juicefs`) — default-up is unaffected; this only changes the `juicefs` profile's metadata backend.
