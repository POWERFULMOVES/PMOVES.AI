# JuiceFS Phase 3 — Data Migration + Cutover Runbook

**Status:** Operator runbook (2026-06-28). **Owner lane:** Z890-CLAUDE (storage).
**Decision (operator, 2026-06-28):** JuiceFS metadata engine = **Postgres** (reuse `supabase-db`),
revisit Redis-vs-Postgres when the multi-node replicated backend (Phase 4) is designed.
**Prereqs:** Phase 1 PoC (#1865) + Phase 2 single-switch (#1888) merged. `JUICEFS_OBJECT_STORE_MIGRATION.md` §6/§8.

> Phase 3 is a **live data cutover** — it mirrors real MinIO data into JuiceFS and flips the
> default S3 endpoint. Run it deliberately, with the data tier up, and keep MinIO available
> for rollback through the whole window.

## 0. Metadata engine — Postgres
The PoC used Redis. For production use Postgres on the existing `supabase-db`:
- Create the metadata schema once (idempotent seed, ships with this PR):
  `supabase/initdb/00_2_juicefs_meta_schema.sql` → `create schema if not exists juicefs_meta`.
- Set the meta URL (env.shared / deploy):
  ```
  JUICEFS_META_URL=postgres://<SUPABASE_DB_USER>:<SUPABASE_DB_PASSWORD>@supabase-db:5432/postgres?search_path=juicefs_meta&sslmode=disable
  ```
  (Both `juicefs format` and `juicefs gateway` read `JUICEFS_META_URL`; default is the redis PoC.)
- `juicefs-redis` is then unused — leave it in the `juicefs` profile for PoC/fallback, or drop it from the bring-up service list once Postgres is validated.

## 1. Stand up JuiceFS (Postgres metadata)
```
# data tier must be up (supabase-db reachable). Then, with JUICEFS_META_URL set to postgres://:
make -C pmoves up-juicefs        # juicefs-format (one-time, idempotent) + juicefs-gateway
make -C pmoves juicefs-status    # gateway healthy (/minio/health/live)
```

## 2. Create the buckets in JuiceFS
The S3 consumers use `assets`, `outputs`, `pmoves-comfyui`. The gateway runs `--multi-buckets`,
so each is a top-level dir. `make juicefs-mirror` (step 3) creates them via `mc mb -p`.

## 3. Mirror MinIO → JuiceFS
Run an `mc` job on the `pmoves_data` network (where both MinIO and the JuiceFS gateway live)
with an alias for each. Substitute the live S3 creds (`MINIO_USER/MINIO_PASSWORD`, and
`JUICEFS_S3_USER/JUICEFS_S3_PASSWORD` — which default to the same MinIO creds):
```
docker run --rm --network pmoves_data \
  -e MC_HOST_minio="http://$MINIO_USER:$MINIO_PASSWORD@minio:9000" \
  -e MC_HOST_jfs="http://$JUICEFS_S3_USER:$JUICEFS_S3_PASSWORD@juicefs-gateway:9000" \
  minio/mc sh -lc '
    for b in assets outputs pmoves-comfyui; do
      mc mb -p "jfs/$b" || true
      mc mirror --overwrite "minio/$b" "jfs/$b"
    done'
```
(Pin `minio/mc` to the digest used elsewhere in the repo for a repeatable run.)

## 4. Validate parity (before flipping anything)
```
docker run --rm --network pmoves_data \
  -e MC_HOST_minio="http://$MINIO_USER:$MINIO_PASSWORD@minio:9000" \
  -e MC_HOST_jfs="http://$JUICEFS_S3_USER:$JUICEFS_S3_PASSWORD@juicefs-gateway:9000" \
  minio/mc sh -lc '
    for b in assets outputs pmoves-comfyui; do
      echo "== $b =="
      echo "  minio: $(mc ls --recursive minio/$b | wc -l) objects"
      echo "  jfs:   $(mc ls --recursive jfs/$b | wc -l) objects"
    done'
```
Counts (and a `du`/size spot-check) must match per bucket. Then spot-check a presigned GET from
a real consumer (e.g. `presign`) against the JuiceFS gateway before proceeding.

## 5. Flip the default (the cutover)
Phase 2 already made this a single switch. In `env.shared` (canonical pipeline):
```
S3_ENDPOINT=juicefs-gateway:9000
# comfy public URL follows automatically (PUBLIC_BASE_URL derives from S3_ENDPOINT)
```
Re-roll consumers (`make -C pmoves up-*` for the affected tiers). All S3 consumers
(presign, pdf-ingest, transcribe, media-*, pmoves-yt, comfy-watcher, render-webhook,
model-registry) now resolve to the JuiceFS gateway. Per-service `MINIO_ENDPOINT` overrides
still win if you need to stage the cutover one service at a time.

## 6. Soak + decommission (Phase 4)
- Keep MinIO running behind its profile for the soak window; do NOT delete MinIO data yet.
- After the soak passes (all consumers green, a backup cycle on JuiceFS), Phase 4 removes
  MinIO and designs the multi-node replicated backend.

## 7. Rollback
At any point before MinIO data is deleted:
```
# unset S3_ENDPOINT in env.shared (back to the minio:9000 default) and re-roll consumers.
```
Because the mirror is one-way (MinIO → JuiceFS) and MinIO stays untouched, rollback is just
flipping the endpoint back. Any writes that landed on JuiceFS during the window must be
re-mirrored back to MinIO (`mc mirror jfs/<bucket> minio/<bucket>`) before rolling back if you
want to keep them.

## Verification checklist
- [ ] JuiceFS gateway healthy on Postgres metadata (`juicefs-status`)
- [ ] `juicefs-mirror` completed without error for all 3 buckets
- [ ] `juicefs-mirror-verify` parity OK (counts + sizes match)
- [ ] presign / comfy GET round-trips against the gateway
- [ ] `S3_ENDPOINT` flipped; affected consumers re-rolled + healthy
- [ ] MinIO kept available behind its profile for the soak window (rollback path intact)
