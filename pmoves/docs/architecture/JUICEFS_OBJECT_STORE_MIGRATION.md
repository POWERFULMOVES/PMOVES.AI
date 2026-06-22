# JuiceFS Object-Store Migration (replace EOL MinIO)

**Status:** Design spec (2026-06-22). Build deferred. **Owner lane:** Z890-CLAUDE (#10 JuiceFS↔MinIO).
**Interim:** PR #1862 repins MinIO to its last real community tag so the data tier works until cutover.
**Related:** `project_supabase_multinode_juicefs_vision` (multi-node dual-write vision), `CAPABILITY_ADAPTIVE_STANDALONE.md` (the data tier this storage layer sits in).

## 1. Problem

MinIO Community Edition is **EOL / archived (Feb 2026)** and MinIO **stopped publishing `minio/minio` community images after `RELEASE.2025-09-07`**. The compose was pinned to a phantom `RELEASE.2025-12-20…` tag that 404s on Docker Hub, which broke every data-tier bring-up (found during the capability-adaptive Phase 3 live verify on Z890). PR #1862 repins to the last real tag as a band-aid, but the object store is now on a dead, unmaintained, unpatched base. JuiceFS was always the intended replacement (the "JuiceFS vision") but was **never wired in** — zero references in any compose/Makefile/docs today.

## 2. Goal

Replace the `minio:9000` S3 endpoint with a **maintained, S3-compatible** object store backed by **JuiceFS**, with **minimal consumer churn** (consumers keep talking S3 to the same DNS/endpoint), a **data-migration path** for existing buckets, and a **rollback** during cutover. Set the foundation for the multi-node dual-write storage vision.

## 3. Current MinIO surface (what must keep working)

**S3 consumers** (`MINIO_ENDPOINT=minio:9000`, on `pmoves_data`): `presign`, `pdf-ingest`, `transcribe-backend`, `ffmpeg-whisper`, `media-video`, `media-audio`, `pmoves-yt`, `comfy-watcher` — plus `render-webhook` and `model-registry` (per service comments). 
**Buckets:** `assets`, `outputs` (created by `make brand-defaults`), `pmoves-comfyui` (comfy), YT uses `assets`/`outputs`. 
**Public links:** `comfy-watcher` sets `PUBLIC_BASE_URL=http://minio:9000` → presigned/public URLs embed the endpoint; cutover must rewrite this. 
**Ops:** `make brand-defaults` (`mc mb` bucket create), backup via `mc mirror`. 
**Hardening:** MinIO uses the `*tier-data-hardened` anchor (non-root 65532, read-only, security_opt) — the replacement must too.

## 4. JuiceFS architecture

JuiceFS = a POSIX/object filesystem that splits **metadata** from **data**, plus a built-in **S3 gateway**:

```
S3 consumers ──S3──▶ juicefs-gateway (:9000, S3-compatible)
                          │
            ┌─────────────┴─────────────┐
        metadata engine            data backend
       (Postgres or Redis)     (local volume; later: replicated/object)
```

- **S3 gateway:** `juicefs gateway` serves an S3-compatible API (MinIO-derived gateway code) → **drop-in for `minio:9000`**. Consumers change only the endpoint host (or none, if we keep the service DNS name).
- **Metadata engine:** transactional KV/DB holding the filesystem tree + chunk index.
- **Data backend:** where chunks live.

### 4.1 Component choices (proposed, confirm in review)

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Metadata engine | **Postgres** (dedicated DB on `supabase-db`, or a small standalone) | Already in the stack; transactional; supports the multi-node vision better than SQLite. Redis is the alternative (faster, but another stateful service + persistence config). |
| Data backend | **local volume** initially (`file://` on a hardened named volume) | Simplest durable single-node store; the multi-node dual-write/replicated backend is the follow-on vision. |
| S3 gateway | `juicefs gateway` on **:9000** | Drop-in endpoint; keep buckets `assets`/`outputs`/`pmoves-comfyui`. |
| Image | pinned `juicedata/juicefs` (or build) per F-07 supply-chain | Maintained, unlike MinIO community. |

## 5. Drop-in strategy (minimal churn)

Two options (pick in review):
1. **Keep the DNS name** — name the gateway service so consumers still resolve `minio:9000` (alias/rename), zero consumer env changes. Lowest churn; slightly confusing naming.
2. **New endpoint var** — introduce `S3_ENDPOINT`/`OBJECT_STORE_ENDPOINT` defaulting to `juicefs-gateway:9000`, repoint each consumer's `MINIO_ENDPOINT`. Cleaner long-term; touches ~10 services.

Recommended: **(2)** with a compatibility default so unmigrated consumers still work, migrate consumers incrementally. `PUBLIC_BASE_URL` (comfy) updates to the gateway endpoint.

## 6. Data migration

For existing data: `mc mirror` (or `rclone`) from the running MinIO (`local/<bucket>`) into the JuiceFS gateway buckets, per bucket (`assets`, `outputs`, `pmoves-comfyui`). On fresh nodes (no MinIO data) just (re)create buckets via the existing `brand-defaults` flow pointed at the gateway. Verify object counts/sizes before flipping consumers.

## 7. Dependency ordering & hardening

Bring-up order: **metadata engine (healthy) → juicefs format (one-time) → juicefs-gateway (healthy) → S3 consumers**. Wire `depends_on: condition: service_healthy`. Apply the `*tier-data-hardened` anchor (non-root 65532, read-only rootfs + tmpfs, `cap_drop: ALL`, `no-new-privileges`) to the gateway, mirroring MinIO. Fits the capable-tier data layer (`up-core-capable`).

## 8. Rollback

Keep MinIO (last-real-tag pin from #1862) **available behind a profile/flag** through cutover. If the gateway misbehaves, repoint `*_ENDPOINT` back to `minio:9000`. Only remove MinIO after the gateway is validated across all consumers + a backup cycle.

## 9. Phased plan

- **Phase 1 — PoC:** add `juicefs-gateway` + metadata engine to compose (hardened, pinned, dep-ordered); format the FS; create `assets`/`outputs`; repoint **one** consumer (`presign`) via the new endpoint var; verify put/get + presigned URL.
- **Phase 2 — migrate consumers:** repoint the remaining S3 consumers + `PUBLIC_BASE_URL`; update `brand-defaults` bucket creation to target the gateway; keep MinIO as fallback.
- **Phase 3 — data + cutover:** `mc mirror` existing buckets into JuiceFS; validate; flip defaults to the gateway; MinIO behind a disabled profile.
- **Phase 4 — decommission + multi-node:** remove MinIO; design the replicated/dual-write backend for the multi-node vision.

## 10. Verification

- PoC: `presign` issues working URLs against the gateway; `mc ls`/S3 SDK put/get round-trips.
- Per-phase: each repointed consumer's health + a functional object op.
- Cutover: object parity (counts/sizes) MinIO vs JuiceFS; all consumers green on `service_health_check`.

## 11. Open questions (resolve in review)

- Metadata engine: dedicated Postgres DB vs Redis vs reuse `supabase-db` (blast-radius/coupling).
- Backend durability single-node now vs jumping to a replicated backend for multi-node.
- Naming: keep `minio:9000` DNS (drop-in) vs new `juicefs-gateway` endpoint var.
- Presigned-URL semantics parity (expiry, signature) between MinIO and the JuiceFS gateway.
- Capacity/quota + backup cadence for the JuiceFS volume.
