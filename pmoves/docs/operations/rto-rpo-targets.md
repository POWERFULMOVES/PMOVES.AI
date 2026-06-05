# RTO / RPO Targets per Service Tier

**Status:** Living document · **Owner:** Infra (Z890-CLAUDE lane) · **Created:** 2026-06-05 · Closes #1428

> *"Having 10 TB of backup data means nothing if recovery takes days. RTO is the metric that matters."* — Eli (principle #4)
>
> Backups exist (`make -C pmoves backup`: Postgres dump, Qdrant snapshot, MinIO mirror, Meili dump) but were never paired with **targets**. Without an RTO/RPO per tier there is no way to validate that the backup/restore strategy meets operational needs, and no objective input for the disaster-recovery playbook or executive communication. This doc sets those targets, maps each to a recovery runbook, and notes split-brain risks.

## Definitions

| Term | Meaning | Set by |
|------|---------|--------|
| **RTO** — Recovery Time Objective | Max acceptable wall-clock time from outage to service restored | How fast we can rebuild/restore |
| **RPO** — Recovery Point Objective | Max acceptable data loss, measured as age of the last good backup | How often we snapshot |

RPO is **N/A** for stateless tiers — they hold no durable state, so there is nothing to lose; recovery is "redeploy the image and reconnect."

## Architecture anchor

PMOVES segments services into **environment tiers** (`pmoves/env.tier-*`, see `.claude/context/tier-architecture.md`). State concentrates almost entirely in **`tier-data`** (Postgres, Qdrant, Neo4j, Meilisearch, MinIO, NATS) and the **`tier-supabase`** stack that sits on the same Postgres. Everything else is largely stateless and recovers by redeploying from a pinned image and reconnecting to the data tier. **This is the central DR fact: protect `tier-data` and `tier-supabase`; the rest is fast, cheap rebuild.**

## Targets

| Tier | Representative services | Durable state? | **RTO** | **RPO** | Backup mechanism |
|------|------------------------|----------------|---------|---------|------------------|
| **tier-data** | Postgres, Qdrant, Neo4j, Meilisearch, MinIO, NATS (JetStream) | **Yes — core** | **1 hr** | **15 min** | `make backup` (pg_dump + Qdrant snapshot + MinIO mirror + Meili dump); Postgres WAL/PITR for 15-min RPO |
| **tier-supabase** | GoTrue, PostgREST, Realtime, Storage, Studio, Kong | **Yes** (shares Postgres + Storage→MinIO) | **1 hr** | **15 min** | Same Postgres dump + MinIO mirror as tier-data; auth users live in Postgres |
| **tier-api** | Presign, Hi-RAG Gateway, GPU Orchestrator | No (reads tier-data) | **30 min** | N/A | Redeploy image; stateless over data tier |
| **tier-worker** | Extract Worker, LangExtract, PDF-ingest, Notebook-sync | No (idempotent) | **30 min** | N/A | Redeploy; re-process from source-of-truth in data tier |
| **tier-agent** | Agent Zero, Archon, SupaSerch, DeepResearch | Partial (memory in Cipher/Postgres) | **30 min** | **1 hr** | Agent/conversation memory persists in Postgres + Cipher; covered by tier-data dump |
| **tier-llm** | TensorZero Gateway, TensorZero UI | No for routing; ClickHouse = observability | **15 min** | N/A (routing) · 1 hr (ClickHouse metrics) | Redeploy gateway; ClickHouse inference logs are observability, non-critical |
| **tier-media** | PMOVES.YT, FFmpeg-Whisper, Channel Monitor | Outputs → MinIO | **2 hr** | **1 hr** | Outputs reprocessable from source; MinIO objects in tier-data backup |
| **tier-ui** | Web UI, A2UI renderer | No | **15 min** | N/A | Redeploy from pinned image |
| **tier-vpn** | Headscale, RustDesk relay (hbbr/hbbs) | Headscale node DB | **15 min** | **1 hr** | Headscale SQLite/Postgres node state; relays are stateless |
| **monitoring** *(cross-tier)* | Prometheus, Grafana, Loki | Metrics/log history | **1 hr** | **1 hr** | Non-critical; dashboards are code (provisioned), history is best-effort |

**Recovery ordering (dependency-first):** `tier-data` → `tier-supabase` → `tier-llm` (TensorZero) → `tier-api`/`tier-worker` → `tier-agent` → `tier-media`/`tier-ui` → `monitoring`. Bringing agents up before the data tier just produces a wave of failed health checks. This matches the `make -C pmoves up-*` layering in `COMPOSE_LAYERING_RUNBOOK.md`.

## Per-tier recovery runbooks

Each runbook assumes the node is reachable and Docker is healthy. All commands run from `pmoves/`. Use `make -C pmoves up-<group>` layering — never raw `docker compose up`.

### tier-data (RTO 1 hr / RPO 15 min) — the one that matters

1. **Provision the host** (if lost): bring up Docker + restore the named volumes' parent disk. Confirm backups are **not** on the same disk (see Backup Isolation below).
2. **Start the data tier only:** `make -C pmoves up-core` (Postgres, Qdrant, Neo4j, Meili, MinIO, NATS).
3. **Restore Postgres:** `cat backups/<ts>/postgres.sql | docker exec -i <postgres> psql -U $POSTGRES_USER -d $POSTGRES_DB` (or PITR replay to the target timestamp for true 15-min RPO).
4. **Restore Qdrant:** recover the collection from `backups/<ts>/qdrant_snapshot.json` via the Qdrant snapshot recover API.
5. **Restore MinIO:** `mc mirror backups/<ts>/minio_<bucket> local/<bucket>`.
6. **Restore Meilisearch:** import `backups/<ts>/meili_dump.json` via the dumps API.
7. **Verify:** `make -C pmoves health-summary` / probe each store; confirm row counts and a known-key read.

> RPO note: `make backup` is a point-in-time full. To actually hit **RPO 15 min** for Postgres, enable WAL archiving / PITR (continuous) — a full dump every 15 min is too heavy. Qdrant/Meili/MinIO at 15-min full-snapshot cadence is acceptable given their size; revisit if they grow.

### tier-supabase (RTO 1 hr / RPO 15 min)
Recovers **with** tier-data (auth users + storage metadata live in the same Postgres; objects in MinIO). After tier-data restore: `make -C pmoves up-supabase`, then verify a login (GoTrue `/health`) and a PostgREST read. JWT secret must match the restored `env.tier-supabase` — a secret mismatch invalidates all existing tokens (expected; clients re-auth).

### tier-api / tier-worker (RTO 30 min / RPO N/A)
Stateless. `make -C pmoves up-hirag` (api) / `up-workers` (worker) once tier-data is healthy. Workers re-process from the data tier; no restore step. Verify `/healthz` + `/metrics` on each.

### tier-agent (RTO 30 min / RPO 1 hr)
Agent memory (conversations, Cipher store) persists in Postgres → covered by the tier-data dump. After tier-data + tier-tensorzero are up: `make -C pmoves up-agents`. Verify Agent Zero `/healthz` and an MCP round-trip. Stale gateway containers may need force-recreate (`up-agents` recreates).

### tier-llm (RTO 15 min / RPO N/A)
TensorZero Gateway is a stateless router. `make -C pmoves up-tensorzero`. ClickHouse inference logs are observability — if lost, accept the gap (don't block recovery on it). Verify a test completion routes through the gateway.

### tier-media (RTO 2 hr / RPO 1 hr)
Outputs land in MinIO (backed up with tier-data). In-flight jobs are reprocessable from source URLs. `make -C pmoves up-media`. Verify a small transcode/ingest end-to-end.

### tier-ui (RTO 15 min / RPO N/A)
Pure frontend. Redeploy the pinned image (`up-ui`); no state. Verify the dashboard loads and reaches the API tier.

### tier-vpn (RTO 15 min / RPO 1 hr)
Headscale node DB holds tailnet state (re-derivable by re-enrolling nodes, but a restore is faster). RustDesk relays (hbbr/hbbs) are stateless — redeploy. After restore, verify a node can authenticate and a relay handshake completes.

### monitoring (RTO 1 hr / RPO 1 hr)
Dashboards are provisioned-as-code (Grafana provisioning) → rebuild from repo. Metric/log history is best-effort; a gap is acceptable. `make -C pmoves up-monitoring`. Verify Prometheus targets are UP and Grafana loads dashboards.

## Split-brain prevention (HA pairs)

PMOVES is mostly **single-active** by design, which sidesteps most split-brain risk. The pairs that need explicit notes:

| Pair / risk | Design | Split-brain prevention |
|-------------|--------|------------------------|
| **NATS — island vs fleet** | Standalone sidecar (SPARK/edge, offline-capable) vs `pmoves_bus` network (Z890/5090 docked). *Intentional* partition. | Edge islands are **deliberately isolated**, not an HA cluster — they reconcile via explicit publish on reconnect, never auto-merge JetStream state. If JetStream clustering is ever enabled across nodes, require an odd-numbered quorum and a single stream leader. |
| **Postgres** | Single primary, no multi-primary. | Never run two writable primaries. If read-replicas/HA are added, use a fencing token / single-writer election (e.g., Patroni) — never accept two primaries. |
| **RustDesk relay (hbbr/hbbs across KVMs)** | Multiple relays exist across KVM nodes. | Clients should target **one** relay as primary; secondaries are warm standby, not simultaneously authoritative for the same session. |
| **gateway-agent (per-node)** | Each node runs its own; not an HA pair. | Per-node by design — no shared state, so no split-brain. Do not point two nodes at one shared gateway DB. |

## Backup isolation verification (Eli principle #23)

A backup on the same volume as production dies with production. Requirements:

- [ ] `BACKUP_DIR` (default `backups/<timestamp>`) must be **copied off the production disk** after `make backup` — the local dir is a staging area, not the durable copy.
- [ ] Durable target options: a separate physical disk, a Hostinger/KVM volume distinct from the app volume, or an offsite MinIO/S3 bucket **not** backed by the same MinIO instance being backed up.
- [ ] Verify isolation: `df` the backup target vs the Docker data-root (`docker info --format '{{.DockerRootDir}}'`) — they must be **different filesystems**.
- [ ] Restore is unproven until tested: run a periodic **restore drill** into a scratch namespace and confirm the verification step of the tier-data runbook passes.

## Validation cadence

| What | Cadence | Pass criteria |
|------|---------|---------------|
| `make backup` runs + artifacts non-empty | per RPO (15 min for Postgres via PITR; daily full) | All four artifacts present & non-zero |
| Backup copied off-host | each backup | Lands on a different filesystem than Docker root |
| tier-data restore drill | monthly | tier-data runbook verify step passes within RTO (1 hr) |
| Full-stack DR drill | quarterly | Recovery ordering completes; all tiers `/healthz` green |

## References

- `.claude/context/tier-architecture.md` — the env-tier model these targets map to
- `pmoves/Makefile` § *Backups / Restore helpers* (`make backup` / `make restore`) — the real backup mechanism cited above
- `pmoves/docs/operations/COMPOSE_LAYERING_RUNBOOK.md` — `up-*` layering = recovery ordering
- `pmoves/docs/operations/COMPLETE_BRING_UP_RUNBOOK.md` — full bring-up procedure (recovery from zero)
- Eli analysis principles #4 (RTO is the metric), #22, #23 (backup isolation / split-brain) — `research/`
- Trace #0 lessons — circuit-breaker / backup-strategy origin
