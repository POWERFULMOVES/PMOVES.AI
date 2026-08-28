# PMOVES.AI Edition — Hardened Integrations, Images, and CI/CD

_Last updated: 2026-02-13_

## Overview

- **Goal:** Treat each external integration as a first-class, hardened submodule with a pinned image in GHCR, reproducible builds, and CI parity with PMOVES.AI.
- **Scope:** 37+ submodules spanning agents, knowledge services, media pipelines, voice/speech, blockchain, infrastructure, and lifestyle integrations — plus core data services (Qdrant, Meili, Neo4j, MinIO, Supabase, NATS, TensorZero).
- **Deliverables:** Submodule layout, image catalog, hardening baseline, Phase 1/2 security status, CI/CD pipeline health, and verification gates.
- **Companion guidance:** Follow root `AGENTS.md` for stabilization/CI expectations and `pmoves/AGENTS.md` for pmoves subtree coding norms.

## Security Hardening Status

### Phase 1: Container Security — COMPLETE

| Control | Coverage | Status |
|---------|----------|--------|
| Non-root execution (UID 65532) | 29/29 PMOVES-built services | DONE |
| Read-only root filesystems | 30/30 services | DONE |
| tmpfs mounts for writable paths | All services | DONE |
| `cap_drop: ["ALL"]` | All services | DONE |
| `no-new-privileges: true` | All services | DONE |
| K8s SecurityContext template | 1 template | DONE |
| Validation script | `pmoves/scripts/validate-phase1-hardening.sh` | EXISTS |

**Hardened overlay:** `pmoves/docker-compose.hardened.yml`
**Deployment:** `docker compose -f docker-compose.yml -f pmoves/docker-compose.hardened.yml up -d`

### Phase 2: Infrastructure Security — 25% DONE

| Task | Status | Effort |
|------|--------|--------|
| 2.1 Harden-Runner (GH Actions) | DONE | — |
| 2.2 BuildKit Secrets (Archon) | DESIGNED | 2-3h |
| 2.3 Branch Protection Rules | DESIGNED | 15 min (user) |
| 2.4 Network Policies (5-tier) | DESIGNED | 1.5-2h |

**Critical finding (2.2):** Archon Dockerfile lines 49-79 use `ARG` defaults for sensitive config — secrets baked into image layers.

### Phase 3: Scanning & Detection — NOT STARTED

Planned: SAST, dependency scanning (Trivy/Snyk), secret scanning (TruffleHog), container hardening audit. Estimated 6-8h.

## Submodule Inventory (37 submodules)

All submodules track `PMOVES.AI-Edition-Hardened` branch unless noted.

### Core Agent & Orchestration (4 submodules)

| Submodule | Role | Initialized | Hardened |
|-----------|------|-------------|----------|
| PMOVES-Agent-Zero | Control-plane orchestrator, MCP API | No | Phase 1 |
| PMOVES-Archon | Supabase-driven agent service | Yes | Phase 1 |
| PMOVES-BoTZ | Skills marketplace framework | No | Phase 1 |
| PMOVES-BotZ-gateway | BoTZ API gateway | No | Phase 1 |

### Knowledge & Research Services (4 submodules)

| Submodule | Role | Initialized | Hardened |
|-----------|------|-------------|----------|
| PMOVES-A2UI | Next.js frontend UI | Yes | Phase 1 |
| PMOVES-Deep-Serch | Deep search service | No | Phase 1 |
| PMOVES-HiRAG | Hybrid RAG (standalone) | No | Phase 1 |
| Pmoves-hyperdimensions | Holographic visualization | Yes | Phase 1 |

### Agent Training & Research (4 submodules)

| Submodule | Role | Initialized | Hardened |
|-----------|------|-------------|----------|
| PMOVES-AgentGym | Agent training platform | No | Pending |
| Pmoves-AgentGym-RL | Reinforcement learning variant | No | Pending |
| PMOVES-llama-throughput-lab | LLM benchmarking | No | Pending |
| PMOVES-surf | Web browsing agent | No | Pending |

### E2B Danger Room — Sandboxed Execution (5 submodules)

| Submodule | Role | Initialized | Hardened |
|-----------|------|-------------|----------|
| PMOVES-E2B-Danger-Room | Primary sandbox | No | Pending |
| PMOVES-E2B-Danger-Room-Desktop | Desktop sandbox | No | Pending |
| PMOVES-Danger-infra | E2B infrastructure (6 Go services) | No | P1 done |
| PMOVES-E2b-Spells | Sandbox spell definitions | No | Pending |
| pmoves-e2b-mcp-server | MCP server for E2B | Yes | Pending |

### Voice & Speech Services (4 submodules)

| Submodule | Role | Initialized | Hardened |
|-----------|------|-------------|----------|
| PMOVES-Pipecat | Multimodal voice pipeline | No | Pending |
| PMOVES-Pinokio-Ultimate-TTS-Studio | Pinokio launcher for TTS | No | N/A (launcher) |
| PMOVES-Ultimate-TTS-Studio | Multi-engine TTS (7 engines) | Yes | Phase 1 |
| PMOVES-transcribe-and-fetch | Transcription UI + backend | Yes | Phase 1 |

### Media & Content Services (3 submodules)

| Submodule | Role | Initialized | Hardened |
|-----------|------|-------------|----------|
| PMOVES.YT | YouTube ingestion service | No | Phase 1 |
| PMOVES-Jellyfin | Jellyfin media server fork | No | Phase 1 |
| Pmoves-Jellyfin-AI-Media-Stack | Jellyfin AI overlay | No | Pending |

### Knowledge Base & Notes (2 submodules)

| Submodule | Role | Initialized | Hardened |
|-----------|------|-------------|----------|
| PMOVES-Open-Notebook | SurrealDB knowledge base | No | P2 needed |
| Pmoves-open-notebook | Open Notebook variant | No | Pending |

### Document Processing (2 submodules)

| Submodule | Role | Initialized | Hardened |
|-----------|------|-------------|----------|
| PMOVES-DoX | Documentation tools | No | Phase 1 |
| PMOVES-Creator | Content creation tools | Yes | Phase 1 |

_Note: PMOVES-DoX tracks `PMOVES.AI-Edition-Hardened-DoX` branch (contains nested Agent Zero for standalone mode)._

### Workflow & Automation (2 submodules)

| Submodule | Role | Initialized | Hardened |
|-----------|------|-------------|----------|
| PMOVES-n8n | Workflow orchestrator | No | Phase 1 |
| PMOVES-crush | Multimedia processing | No | Pending |

### LLM Gateway (1 submodule)

| Submodule | Role | Initialized | Hardened |
|-----------|------|-------------|----------|
| PMOVES-tensorzero | TensorZero LLM gateway | No | Phase 1 |

### Financial & Lifestyle (2 submodules)

| Submodule | Role | Initialized | Hardened |
|-----------|------|-------------|----------|
| PMOVES-Wealth | Firefly-III finance management (renamed from PMOVES-Firefly-iii) | No | P2 needed |
| Pmoves-Health-wger | Fitness tracking (wger) | Yes | Phase 1 |

### Blockchain & Tokenization (1 submodule)

| Submodule | Role | Initialized | Hardened |
|-----------|------|-------------|----------|
| PMOVES-ToKenism-Multi | CHIT/Solidity integration | Yes | Phase 1 |

### UI & Frontend (1 submodule)

| Submodule | Role | Initialized | Hardened |
|-----------|------|-------------|----------|
| PMOVES-MAI-UI | AI UI variant | No | Pending |

### Networking & Infrastructure (3 submodules)

| Submodule | Role | Initialized | Hardened |
|-----------|------|-------------|----------|
| PMOVES-Tailscale | VPN client | No | Pending |
| PMOVES-Remote-View | Remote desktop access | No | Pending |
| PMOVES-Headscale | Self-hosted VPN control plane | No | Pending |

### Integration & Data (2 submodules)

| Submodule | Role | Initialized | Hardened |
|-----------|------|-------------|----------|
| PMOVES-supabase | Supabase fork | No | Phase 1 |
| pmoves/integrations/archon | Archon integration link | Yes | Phase 1 |

### Initialization Summary

- **Initialized locally:** 9/37 — PMOVES-A2UI, PMOVES-Archon, PMOVES-Creator, PMOVES-ToKenism-Multi, PMOVES-Ultimate-TTS-Studio, PMOVES-transcribe-and-fetch, Pmoves-Health-wger, Pmoves-hyperdimensions, pmoves-e2b-mcp-server
- **Not initialized:** 28/37 — Available for `git submodule init && git submodule update --remote`

## Hardened Image Catalog (Baseline Controls)

### Supply Chain

- **Reproducible builds:** Pinned tags + digests; prefer distroless/alpine where appropriate
- **SBOM:** CycloneDX generated via Syft; attached to GHCR images
- **Signing:** Cosign keyless (OIDC); verified in `make verify-all`
- **Vulnerability scan:** Trivy in CI; gate on HIGH/CRITICAL with allowlist for false positives

### Runtime Security (compose defaults per service)

- Run as non-root (UID 65532); read-only root FS; `no-new-privileges: true`
- Drop all capabilities; add back only needed (`CAP_NET_BIND_SERVICE` for <1024 if applicable)
- Seccomp/AppArmor: default Docker profiles; exceptions documented
- Network: explicit `networks:` sections; disable inter-service connectivity by default; egress allowlist
- Resource limits: CPU/mem limits per service; healthchecks with backoff; restart `unless-stopped`
- Secrets: mount via env files (tier-based); rotate via `make supabase-boot-user` and CHIT bundles

### Tier-Based Secrets Architecture

| Tier File | Services | Secrets Scope |
|-----------|----------|---------------|
| `env.tier-data` | postgres, qdrant, neo4j, minio | Infrastructure only, NO API keys |
| `env.tier-api` | postgrest, hi-rag-v2, presign | Data tier + internal TensorZero |
| `env.tier-worker` | extract-worker, langextract | Processing credentials |
| `env.tier-agent` | agent-zero, archon, nats | Agent coordination |
| `env.tier-media` | pmoves-yt, whisper, media-* | Media processing |
| `env.tier-llm` | tensorzero-gateway ONLY | External LLM API keys |
| `env.tier-supabase` | supabase-db, gotrue, postgrest, kong, realtime, storage, studio | Supabase service keys and JWT |

### Observability

- Uniform `/healthz` and optional `/ready` endpoints
- Prometheus metrics at `/metrics` where available
- Loki labels standardized per service
- 52 health checks implemented (PR #355)

## CI/CD Pipeline Health

### Workflow Status (as of 2026-02-13)

| Workflow | Runner | Status | Notes |
|----------|--------|--------|-------|
| `env-preflight.yml` | `ubuntu-latest` | GREEN | Only consistently reliable workflow |
| `integrations-ghcr.yml` | `ubuntu-latest` | YELLOW | 10 build jobs; needs `CI_GIT_CLONE_TOKEN` for private repos |
| `codeql.yml` | `ubuntu-latest` | FIXED | Migrated from self-hosted; `paths-ignore` corrected |
| `hardening-validation.yml` | `ubuntu-latest` | FIXED | Migrated from self-hosted |
| `python-tests.yml` | `ubuntu-latest` | FIXED | Migrated from self-hosted; added Hardened branch trigger |
| `sql-policy-lint.yml` | `ubuntu-latest` | FIXED | Migrated from self-hosted; added Hardened branch trigger |
| `chit-contract.yml` | `self-hosted, ai-lab` | RED | Runner dependency |
| `self-hosted-builds.yml` | 4 runner types | DEPRECATED | Disabled; superseded by hardened variant |
| `self-hosted-builds-hardened.yml` | 4 runner types | RED | Requires self-hosted runners |
| `deploy-gateway-agent.yml` | 3 runner types | RED | Requires self-hosted runners |
| `sync-secrets-local.yml` | `self-hosted, ai-lab` | FIXED | Switched from cleartext to base64 encoding |
| `webhook-smoke.yml` | `self-hosted, vps` | YELLOW | Manual only |
| `yt-dlp-bump.yml` | `ubuntu-latest` | YELLOW | Runs, but cannot do what its name implies — it build-validates a non-deployed Dockerfile and files a tracker note without moving any pin (pmoves/docs/services/pmoves-yt/YTDLP_CURRENCY.md). Runner label corrected 2026-08-27: this row read `self-hosted, vps`; the workflow has `runs-on: ubuntu-latest`. |

### CI Improvements Made (2026-02-13)

1. Migrated `codeql.yml`, `python-tests.yml`, `sql-policy-lint.yml`, `hardening-validation.yml` to `ubuntu-latest`
2. Fixed CodeQL `paths-ignore` placement (was at `on:` level, moved to under `push:`/`pull_request:`)
3. Added `PMOVES.AI-Edition-Hardened` branch triggers to python-tests and sql-policy-lint
4. Deprecated `self-hosted-builds.yml` (disabled push triggers to prevent conflicts with hardened variant)
5. Fixed `sync-secrets-local.yml` — removed cleartext secret storage, switched to base64 encoding with restrictive file permissions
6. Fixed variable reference bug in sync-secrets-local.yml (`label` → `name`)

## Submodule Strategy

### Branching Convention

- Each submodule maintains a `PMOVES.AI-Edition-Hardened` branch carrying PMOVES overlays
- Exception: `PMOVES-DoX` uses `PMOVES.AI-Edition-Hardened-DoX` (nested Agent Zero for standalone)
- Policy: upstream PR first where viable; otherwise, keep overlay minimal and documented

### Migration Steps (per submodule)

1. Fork upstream repo to POWERFULMOVES organization
2. Create `PMOVES.AI-Edition-Hardened` branch with hardening overlays
3. Add as git submodule in `.gitmodules` with branch tracking
4. Update compose to prefer `image: ghcr.io/<org>/<name>:pmoves-latest`; keep `build:` behind dev-local toggle
5. Add release workflow: build, SBOM, sign, push, publish provenance

### E2B Migration Notes (2026-02-07)

E2B components were previously vendored under `pmoves/vendor/e2b/*`. They have been migrated to proper forked submodules. Vendor entries are commented out in `.gitmodules` to preserve history. No code was lost during migration.

## Verification Gates

- `make -C pmoves verify-all`:
  - Confirms image signatures and SBOM presence for integrations
  - Asserts `/healthz` 200 for Archon, Agent Zero, Channel Monitor, Jellyfin bridge, Hi-RAG gateways (CPU/GPU)
  - Ensures Supabase REST reachability from Archon

## Third-Party Image Security

| Category | Running as root | Mitigation |
|----------|-----------------|------------|
| Datastores (Qdrant, Neo4j, Meilisearch, MinIO) | Yes (upstream default) | Network isolation, read-only FS |
| Monitoring (Grafana, Prometheus) | Yes (upstream default) | Dedicated monitoring network |
| Media (Jellyfin, Ollama) | Yes (upstream default) | GPU group access, network isolation |
| Infrastructure (ClickHouse, Nginx) | Yes (upstream default) | Internal-only networks |

See `docs/submodules-audit-final-summary.md` for complete inventory.

## Voice Integration

- Voice agents wired end-to-end via n8n + Flute Gateway + TensorZero
- Default local model: `tensorzero::model_name::qwen2_5_14b`
- Publish `voice.agent.response.v1` on NATS
- FFmpeg-Whisper supports `POST /transcribe_file` for ad-hoc STT
- n8n flow exports use millisecond timeouts for HTTP Request nodes
- n8n production mode: use Postgres via `N8N_DB=postgres` + `N8N_DB_*`

## Archon Integration

- Supabase CLI stack using CLI-first environment contract
- Vendor expects `SUPABASE_URL` + `SUPABASE_SERVICE_KEY`; PMOVES wrapper maps accordingly
- Base URL resolution: `ARCHON_SUPABASE_BASE_URL` → fallback from `SUPA_REST_URL`
- Health: `/healthz` validates Supabase reachability; `/ready` blocks until checks pass
- Bring-up: `make -C pmoves supa-start` → `make -C pmoves supabase-boot-user` → `make -C pmoves bringup-with-ui`

## Open Items / Decisions

- Implement branch protection rules for `main` and `PMOVES.AI-Edition-Hardened` (see `docs/phase2-branch-protection-guide.md`)
- Complete BuildKit secrets migration for Archon Dockerfile (see `docs/phase2-buildkit-secrets-migration-plan.md`)
- Deploy 5-tier network segmentation (see `docs/phase2-network-policies-design.md`)
- Initialize remaining 28 submodules as needed for full deployment
- Add USER directive to PMOVES-Open-Notebook and PMOVES.YT Dockerfiles
- Add `/metrics` endpoint to PMOVES-Wealth (Laravel) and PMOVES-Danger-infra Go services
- Complete Phase 3 security scanning (SAST, dependency scanning, secret scanning)

## References

- Phase 1 docs: `docs/phase1-completion-summary.md`, `docs/phase1-deployment-guide.md`, `docs/phase1-deployment-quickref.md`
- Phase 2 docs: `docs/phase2-security-hardening-plan.md`, `docs/phase2-buildkit-secrets-migration-plan.md`, `docs/phase2-branch-protection-guide.md`, `docs/phase2-network-policies-design.md`
- Submodule audit: `docs/submodules-audit-final-summary.md`
- Hardened overlay: `pmoves/docker-compose.hardened.yml`
- Validation scripts: `pmoves/scripts/validate-phase1-hardening.sh`, `validate-hardening.sh`
- Services catalog: `docs/PMOVES.AI Services and Integrations.md`
- Implementation plan: `docs/PMOVES.AI-Edition-Hardened-Full-Implementation-Plan.md`
- Makefile refactor plan: `pmoves/docs/HARDENED_MAKEFILE_REFACTOR_PLAN.md`
- CHIT integration status: `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md`
- Security policy: `SECURITY.md`
