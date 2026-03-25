# Docker Hardened Images (DHI) Migration Manifest

**Generated:** 2026-03-24
**Branch:** `feat/dhi-hardened-images`
**Registry:** `dhi.io` (free tier, Apache 2.0, no subscription required)
**Catalog:** 1,000+ images — zero-CVE baseline, SLSA Level 3 provenance, signed SBOMs

---

## Executive Summary

PMOVES.AI uses **71 unique third-party Docker images** across **307 total references** (compose files, Dockerfiles, submodules). Of these, **32 images have free DHI equivalents**, covering **~120 of 307 references (39%)** — including the highest-volume images (python 79×, node 26×, postgres 7×).

**Impact:** Migrating to DHI eliminates CVEs from base images across all services, provides signed provenance for supply-chain auditing, and aligns with PMOVES's existing hardened-image policy.

---

## Verified Tags (via `docker dhi catalog get`, 2026-03-24)

| Image | Available Versions | CVEs (production) | Distros |
|---|---|---|---|
| `dhi.io/nats` | **2.12.x only** (no 2.11) | 0 critical, 0 high | debian 13 |
| `dhi.io/python` | 3.9, 3.10, 3.11, 3.12, 3.13 | 0 critical, 0 high | alpine 3.22/3.23, debian 12/13 |
| `dhi.io/node` | 18, 20, 22, 24 | 0 across all | alpine 3.22/3.23, debian 12/13 |
| `dhi.io/postgres` | 14, 15, 16, 17 | 0 across all | alpine 3.22, debian 13 |
| `dhi.io/redis` | 7.x | 0 across all | debian 13 |
| `dhi.io/neo4j` | 5.x | 0 across all | debian 13 |
| `dhi.io/clickhouse-server` | 24.x | 0 across all | debian 13 |
| `dhi.io/grafana` | 11.x | verified | debian 13 |
| `dhi.io/prometheus` | 2.x | verified | debian 13 |
| `dhi.io/loki` | 3.x | verified | debian 13 |
| `dhi.io/promtail` | 3.x | verified | debian 13 |

**Key constraint:** NATS DHI starts at 2.12 — upgrading from 2.11.8 requires compat testing.

---

## Migration Tiers

### Tier 1 — High Volume (127 references, 41% of total)

| Current Image | Count | DHI Equivalent | FIPS | STIG | Notes |
|---|---|---|---|---|---|
| `python:3.11-slim` | 45+ | `dhi.io/python:3.11` | yes | yes | Strip `-slim` suffix; DHI is minimal by default |
| `python:3.12-slim` | 8 | `dhi.io/python:3.12` | yes | yes | Same — strip variant |
| `python:3.12` | 2 | `dhi.io/python:3.12` | yes | yes | Direct swap |
| `python:3.10-slim` | 2 | `dhi.io/python:3.10` | yes | yes | Strip variant |
| `python:3.9-slim` | 1 | `dhi.io/python:3.9` | yes | yes | Strip variant |
| `node:20-slim` | 12 | `dhi.io/node:20` | yes | yes | Strip `-slim` |
| `node:22-alpine` | 4 | `dhi.io/node:22` | yes | yes | Strip `-alpine` |
| `node:20-alpine` | 3 | `dhi.io/node:20` | yes | yes | Strip `-alpine` |
| `node:20.18.1-alpine` | 4 | `dhi.io/node:20` | yes | yes | Strip patch + variant |
| `node:18-alpine` | 1 | `dhi.io/node:18` | yes | yes | Strip variant |
| `node:24-bookworm` | 2 | `dhi.io/node:24` | yes | yes | Strip variant |
| `alpine:3.19` | 3 | `dhi.io/alpine-base:3.19` | yes | yes | Note: `alpine-base` not `alpine` |
| `alpine:3.20` | 2 | `dhi.io/alpine-base:3.20` | yes | yes | |
| `alpine:3.22` | 2 | `dhi.io/alpine-base:3.22` | yes | yes | |
| `postgres:15-alpine` | 3 | `dhi.io/postgres:15` | yes | yes | Strip `-alpine` |
| `postgres:16-alpine` | 1 | `dhi.io/postgres:16` | yes | yes | |
| `postgres:15` | 3 | `dhi.io/postgres:15` | yes | yes | Direct swap |
| `postgres:14` | 1 | `dhi.io/postgres:14` | yes | yes | Direct swap |
| `nginx:1.27-alpine` | 3 | `dhi.io/nginx:1.27` | yes | yes | Strip `-alpine` |
| `nginx:alpine` | 2 | `dhi.io/nginx` | yes | yes | Pin a version |

### Tier 2 — Core Infrastructure (20+ references)

| Current Image | Count | DHI Equivalent | FIPS | STIG | Notes |
|---|---|---|---|---|---|
| `nats:2.11.8-alpine` | 3 | `dhi.io/nats:2.12` | yes | yes | **UPGRADE REQUIRED:** DHI only has 2.12.x. Test NATS 2.11→2.12 compat before migrating |
| `natsio/nats-box:0.14.5` | 1 | `dhi.io/nats-box` | yes | yes | |
| `neo4j:5.22` | 1 | `dhi.io/neo4j:5.22` | no | no | Direct swap |
| `neo4j:5.15` | 2 | `dhi.io/neo4j:5.15` | no | no | |
| `neo4j:5.15-community` | 1 | `dhi.io/neo4j:5.15` | no | no | Strip `-community` |
| `redis:7-alpine` | 2 | `dhi.io/redis:7` | yes | yes | Strip `-alpine` |
| `clickhouse/clickhouse-server:24.12-alpine` | 2 | `dhi.io/clickhouse-server:24.12` | no | no | Strip `-alpine` |
| `tailscale/tailscale:latest` | 3 | `dhi.io/tailscale` | no | no | Pin version |
| `tailscale/tailscale:v1.80.3` | 1 | `dhi.io/tailscale:1.80` | no | no | |
| `golang:1.25-alpine` | 1 | `dhi.io/golang:1.25` | yes | yes | |
| `rust:1.84-bookworm` | 2 | `dhi.io/rust:1.84` | no | no | Strip `-bookworm` |
| `mongo` | 1 | `dhi.io/mongodb` | yes | yes | Note: `mongodb` not `mongo` |

### Tier 3 — Monitoring Stack (6 references)

| Current Image | Count | DHI Equivalent | FIPS | STIG | Notes |
|---|---|---|---|---|---|
| `prom/prometheus:v2.55.1` | 1 | `dhi.io/prometheus:2.55` | yes | yes | Drop `v` prefix, verify |
| `grafana/grafana:11.2.0` | 1 | `dhi.io/grafana:11.2` | yes | yes | |
| `grafana/grafana:11.3.0` | 1 | `dhi.io/grafana:11.3` | yes | yes | |
| `grafana/loki:3.1.1` | 1 | `dhi.io/loki:3.1` | yes | yes | |
| `grafana/promtail:3.1.1` | 1 | `dhi.io/promtail:3.1` | yes | yes | |
| `prom/node-exporter:v1.8.1` | 1 | `dhi.io/node-exporter:1.8` | yes | yes | |

### Bonus — Available but Not Currently Used

| DHI Image | Potential Use |
|---|---|
| `dhi.io/prometheus-nats-exporter` | NATS metrics → Prometheus (add to monitoring stack) |
| `dhi.io/nats-server-config-reloader` | Hot-reload NATS config changes |
| `dhi.io/postgres-exporter` | Postgres metrics → Prometheus |
| `dhi.io/redis-exporter` | Redis metrics → Prometheus |
| `dhi.io/fluent-bit` | Replace `timberio/vector` for log forwarding |

---

## Non-Migratable Images (No DHI Equivalent)

These stay as-is. Sorted by risk surface:

| Image | Count | Reason |
|---|---|---|
| `supabase/*` (8 images) | 13 | Vendor-specific Supabase stack |
| `ollama/ollama` | 6 | ML inference engine, vendor-specific |
| `nvidia/cuda` | 4 | GPU CUDA runtime, NVIDIA-only |
| `n8nio/n8n` | 3 | Workflow engine, vendor image |
| `mariadb` | 3 | Not in DHI catalog (use `dhi.io/mysql` if compatible) |
| `lscr.io/linuxserver/jellyfin` | 3 | LinuxServer.io community image |
| `tensorzero/gateway` | 2 | Vendor-specific LLM gateway |
| `rustdesk/rustdesk-server` | 2 | Remote desktop, vendor-specific |
| `pytorch/pytorch` | 2 | ML framework + CUDA, vendor-specific |
| `quay.io/invidious/*` | 2 | Invidious, community project |
| `postgrest/postgrest` | 2 | PostgREST, distroless build |
| `agent0ai/agent-zero-base` | 2 | Agent Zero, Kali-based |
| `kalilinux/kali-rolling` | 1 | Security toolkit base |
| `minio/minio` | 1 | Object storage (DHI has chart only, no image) |
| `qdrant/qdrant` | 1 | Vector DB, vendor-specific |
| `getmeili/meilisearch` | 1 | Search engine, vendor-specific |
| `surrealdb/surrealdb` | 1 | Multi-model DB, vendor-specific |
| `kong` | 1 | API gateway (part of Supabase stack) |
| `darthsim/imgproxy` | 1 | Image processing (part of Supabase stack) |
| `gcr.io/cadvisor/cadvisor` | 1 | Container metrics |
| `gcr.io/distroless/python3-debian12` | 1 | Already distroless/minimal |
| `cloudflare/cloudflared` | 1 | Cloudflare tunnel |
| `ghcr.io/juanfont/headscale` | 1 | Headscale, community project |
| `timberio/vector` | 1 | Log aggregation (consider `dhi.io/fluent-bit`) |
| `brainicism/bgutil-ytdlp-pot-provider` | 1 | YouTube PoT, niche |
| `nicolargo/glances` | 1 | System monitoring |
| `runpod/comfyui` | 1 | ComfyUI, vendor-specific |
| `debian:bookworm-slim` | 2 | Use `dhi.io/debian-base` if standalone |

---

## Healthcheck Compatibility

DHI images strip non-essential binaries. Healthchecks using `wget` or `curl` may break.

### Services Needing Healthcheck Updates

| Service | File | Current Healthcheck | Issue | Fix |
|---|---|---|---|---|
| nats | docker-compose.yml:1957 | `wget --spider http://localhost:8222/varz` | `wget` may not exist in DHI | Use `nats-server --health` or `/healthz` endpoint with built-in HTTP client |
| clickhouse | docker-compose.yml:2550 | `wget` -based | Same | Use `clickhouse-client --query "SELECT 1"` |
| postgres (various) | multiple | `pg_isready` | OK — `pg_isready` is part of postgres | No change needed |
| redis | docker-compose.jellyfin-ai.yml | `redis-cli ping` | OK — redis-cli is part of redis | No change needed |
| nginx | docker-compose.external.yml | TBD | `curl` may be absent | Use `nginx -t` or TCP check |
| neo4j | docker-compose.yml:1089 | `wget` -based | Same | Use `cypher-shell` or native healthcheck |
| grafana | monitoring compose | `wget`/`curl` | May be absent | Use Grafana API `/api/health` with built-in tools |
| prometheus | monitoring compose | `wget`/`curl` | May be absent | Use `promtool` or `/-/ready` endpoint |

### Recommended Healthcheck Pattern for DHI

```yaml
# Instead of wget/curl, prefer native tools or TCP probes.
# Each service gets its own healthcheck block:

# NATS
healthcheck:
  test: ["CMD-SHELL", "nats-server --health || exit 1"]

# Postgres
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U postgres"]

# Redis
healthcheck:
  test: ["CMD-SHELL", "redis-cli ping"]

# ClickHouse
healthcheck:
  test: ["CMD-SHELL", "clickhouse-client --query 'SELECT 1'"]
```

---

## CI/CD Authentication

### GitHub Actions Runner Setup

```yaml
# Add to runner setup or workflow
- name: Login to DHI registry
  run: echo "${{ secrets.DHI_TOKEN }}" | docker login dhi.io -u "${{ secrets.DHI_USERNAME }}" --password-stdin
```

### Local Development

```bash
# One-time setup per machine
docker login dhi.io
# Uses Docker Hub credentials (same account)
```

### Make Target (Recommended)

```makefile
# Add to pmoves/Makefile
dhi-login:
	@docker login dhi.io
	@echo "DHI registry authenticated"
```

---

## Compose Variable Pattern

To make DHI migration reversible, use environment variable overrides:

```yaml
# docker-compose.yml
services:
  nats:
    image: ${NATS_IMAGE:-dhi.io/nats:2.12}

  # In .env or env.shared for fallback:
  # NATS_IMAGE=nats:2.11.8-alpine
```

This allows rolling back per-service without code changes.

---

## Implementation Sequence

### Phase 1 — Core Compose (pmoves/docker-compose.yml)
1. Swap NATS, postgres, neo4j, redis, clickhouse, nginx, alpine
2. Update healthchecks for affected services
3. Test with `make -C pmoves up-core`

### Phase 2 — Monitoring Stack
1. Swap prometheus, grafana, loki, promtail, node-exporter
2. Verify dashboards still work
3. Test with `make -C pmoves up-monitoring`

### Phase 3 — Service Dockerfiles (pmoves/services/*)
1. Swap all `FROM python:3.11-slim` → `FROM dhi.io/python:3.11`
2. Swap all `FROM node:20-slim` → `FROM dhi.io/node:20`
3. Rebuild and test each service image

### Phase 4 — Submodule Dockerfiles
1. PMOVES-DoX (19 refs)
2. PMOVES-BoTZ (16 refs)
3. PMOVES-ClawZ (6 refs)
4. PMOVES-Archon (4 refs)
5. PMOVES-Tailscale (3 refs)
6. Pmoves-Health-wger (3 refs)
7. Pmoves-cipher (2 refs)
8. PMOVES-A2UI (2 refs)

### Phase 5 — Variant Compose Files
1. docker-compose.z890.yml
2. docker-compose.jellyfin-ai.yml
3. docker-compose.external.yml
4. docker-compose.n8n.postgres.yml
5. docker-compose.tailscale.yml
6. docker-compose.vps.override.yml
7. Remaining integration compose files

---

## Tag Mapping Reference

DHI does **not** use variant suffixes. Map as follows:

| Official Tag Pattern | DHI Tag Pattern | Example |
|---|---|---|
| `image:X.Y-slim` | `dhi.io/image:X.Y` | `python:3.11-slim` → `dhi.io/python:3.11` |
| `image:X.Y-alpine` | `dhi.io/image:X.Y` | `nats:2.11.8-alpine` → `dhi.io/nats:2.12` |
| `image:X.Y-bullseye` | `dhi.io/image:X.Y` | `python:3.11-slim-bullseye` → `dhi.io/python:3.11` |
| `image:X.Y-bookworm` | `dhi.io/image:X.Y` | `rust:1.84-bookworm` → `dhi.io/rust:1.84` |
| `image:vX.Y.Z` | `dhi.io/image:X.Y` | `prom/prometheus:v2.55.1` → `dhi.io/prometheus:2.55` |
| `vendor/image:X.Y.Z` | `dhi.io/image:X.Y` | `grafana/grafana:11.2.0` → `dhi.io/grafana:11.2` |
| `image:latest` | `dhi.io/image` (pin!) | `nats:latest` → `dhi.io/nats:2.12` |

**Important:** Always verify exact tag availability with `docker dhi catalog get <image>` before migrating.

---

## Verification Checklist

Before merging DHI migration:

- [ ] `docker login dhi.io` succeeds on Z890
- [ ] All DHI tags exist: `docker dhi catalog get nats`, `docker dhi catalog get python`, etc.
- [ ] Services start: `make -C pmoves up`
- [ ] Healthchecks pass: `make -C pmoves verify-all`
- [ ] Monitoring stack works: Grafana dashboards load
- [ ] CI runners authenticated: `secrets.DHI_TOKEN` + `secrets.DHI_USERNAME` set
- [ ] Submodule builds pass: each submodule's CI green
