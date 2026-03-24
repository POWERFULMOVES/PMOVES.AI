# Hardened Branch Reconciliation

**Date:** 2026-03-24
**Author:** z890-claude (infra node)
**Status:** Gap analysis — decision pending

---

## 1. What "Hardened" Means

`PMOVES.AI-Edition-Hardened` is the **production branch that uses Docker Hardened everything**:
- Docker Hardened Images (DHI) for zero-CVE base images (PR #1081)
- `docker-compose.hardened.yml` overlay (non-root, cap_drop, read-only FS)
- Tier-based secrets architecture (7 env.tier-* files)
- Signed images (Cosign keyless), SBOMs (CycloneDX/Syft), Trivy scanning
- 5-tier network segmentation

This is not a moniker — it IS the hardened deployment target.

---

## 2. Branch Strategy: Documented vs Reality

### Documented (pmoves/docs/BRANCH_STRATEGY.md)
```
feature/* → Integrations → Hardened → main
```

### Reality (as of 2026-03-24)
```
feature/* → main (directly via PR)
periodic sync: main → Hardened (chore commits)
```

### Divergence
| Metric | Count |
|--------|-------|
| main ahead of Hardened | **2332 commits** |
| Hardened ahead of main | **2182 commits** |
| Last Hardened sync | `a4ed3c03` "chore: sync main → Hardened (post P7 TAC trees + branch cleanup)" |
| Last main commit | `43d1d3f3` fix(tts): restore sequential load/synth/unload |

**Assessment:** The branches have diverged massively. Work flows directly to main via feature PRs. The Hardened branch receives periodic syncs but is not the active deployment target. The Integrations branch (`PMOVES.AI-Edition-Hardened-Integrations`) is effectively unused.

---

## 3. 44 Submodule Hardening Matrix

All 44 submodules pin to `PMOVES.AI-Edition-Hardened` branch in `.gitmodules`.

### Phase 1 Complete (20 submodules)

These have non-root execution, read-only FS, cap_drop ALL, no-new-privileges, healthchecks.

| # | Submodule | Base Image | DHI Available |
|---|-----------|------------|---------------|
| 1 | PMOVES-Agent-Zero | agent0ai/agent-zero:v0.9.8.2 | No (custom upstream) |
| 2 | PMOVES-Archon | python:3.12-slim | **Yes** → dhi.io/python:3.12 |
| 3 | PMOVES-BoTZ | — (no Dockerfile in submodule) | N/A |
| 4 | PMOVES-BotZ-gateway | python:3.11-slim | **Yes** → dhi.io/python:3.11 |
| 5 | PMOVES-A2UI | node:20-slim | **Yes** → dhi.io/node:20 |
| 6 | PMOVES-Deep-Serch | — | N/A |
| 7 | PMOVES-HiRAG | — | N/A |
| 8 | Pmoves-hyperdimensions | — | N/A |
| 9 | PMOVES-Danger-infra | — (Go services) | N/A |
| 10 | PMOVES-Ultimate-TTS-Studio | — (Pinokio-managed) | N/A |
| 11 | PMOVES-transcribe-and-fetch | — | N/A |
| 12 | PMOVES.YT | python:3.11-slim | **Yes** → dhi.io/python:3.11 |
| 13 | PMOVES-Jellyfin | — (upstream Jellyfin) | No |
| 14 | PMOVES-DoX | — (multiple Dockerfiles) | Partial |
| 15 | PMOVES-Creator | — | N/A |
| 16 | PMOVES-n8n | — (upstream n8n) | No |
| 17 | PMOVES-tensorzero | — (upstream TensorZero) | No |
| 18 | PMOVES-ToKenism-Multi | — (TypeScript library) | N/A |
| 19 | PMOVES-supabase | — (upstream Supabase) | No |
| 20 | Pmoves-Health-wger | ghcr.io/wger/wger:latest | No (upstream wger) |

### Phase 2 Needed (2 submodules)

Need infrastructure security hardening (BuildKit secrets, network policies).

| # | Submodule | Gap |
|---|-----------|-----|
| 21 | PMOVES-Open-Notebook | No USER directive, no /metrics |
| 22 | PMOVES-Wealth | No /healthz, no /metrics, no NATS |

### Pending — No Hardening Work Done (15 submodules)

Branch exists but no hardening overlays applied.

| # | Submodule | Category | Priority |
|---|-----------|----------|----------|
| 23 | PMOVES-AgentGym | Training | Low — research tool |
| 24 | Pmoves-AgentGym-RL | Training | Low — research tool |
| 25 | PMOVES-llama-throughput-lab | Training | Low — benchmarking |
| 26 | PMOVES-surf | Training | Low — web agent |
| 27 | PMOVES-E2B-Danger-Room | Sandbox | Medium — E2B manages isolation |
| 28 | PMOVES-E2B-Danger-Room-Desktop | Sandbox | Low — E2B manages isolation |
| 29 | PMOVES-E2b-Spells | Sandbox | Low — template definitions |
| 30 | pmoves-e2b-mcp-server | Sandbox | Medium — MCP bridge |
| 31 | PMOVES-Pipecat | Voice | Medium — active development |
| 32 | Pmoves-Jellyfin-AI-Media-Stack | Media | Low — overlay on Jellyfin |
| 33 | PMOVES-MAI-UI | UI | Medium — user-facing |
| 34 | PMOVES-Tailscale | Infra | Low — VPN client (upstream hardened) |
| 35 | PMOVES-Remote-View | Infra | Low — remote access tool |
| 36 | PMOVES-Headscale | Infra | Medium — VPN control plane |
| 37 | PMOVES-crush | Automation | Low — CLI tool |

### New (Not in Original Audit — 6 submodules)

Added after the initial hardening sweep. Need classification.

| # | Submodule | Notes |
|---|-----------|-------|
| 38 | PMOVES-Neo4j | Data — graph database fork |
| 39 | PMOVES-ClawZ | Research — auto-research |
| 40 | PMOVES-autoresearch | Research — auto-research |
| 41 | PMOVES-a0-plugins | Agent — Agent Zero plugins |
| 42 | Pmoves-cipher | Memory — knowledge graph |
| 43 | pmoves/integrations/archon | Integration — nested submodule |

### N/A (1 submodule)

| # | Submodule | Reason |
|---|-----------|--------|
| 44 | PMOVES-Pinokio-Ultimate-TTS-Studio | Pinokio launcher, not a container |

---

## 4. In-Repo Service Base Images (DHI Opportunity)

57 Dockerfiles in `pmoves/services/`. Base image distribution:

| Base Image | Count | DHI Available | DHI Image |
|------------|-------|---------------|-----------|
| python:3.11-slim | **38** | **Yes** | dhi.io/python:3.11 |
| python:3.12-slim | 5 | **Yes** | dhi.io/python:3.12 |
| python:3.10-slim | 2 | **Yes** | dhi.io/python:3.10 |
| node:20-slim | 2 | **Yes** | dhi.io/node:20 |
| nvidia/cuda:* | 3 | No | NVIDIA-managed |
| pytorch/pytorch:* | 2 | No | PyTorch-managed |
| nginx:alpine | 1 | **Yes** | dhi.io/nginx |
| agent0ai/agent-zero:* | 1 | No | Custom upstream |
| gcr.io/distroless/* | 1 | No | Already hardened |

**Total DHI-migratable:** 48/57 services (84%) — dominated by python:3.11-slim (38 services).

---

## 5. Gap Summary

| Dimension | Target | Reality | Gap |
|-----------|--------|---------|-----|
| Branch flow | feature → Integrations → Hardened → main | feature → main directly | Flow not followed; Hardened drifted 2332/2182 commits |
| Submodule P1 hardening | 44/44 | 20/44 | 24 submodules need P1 work or classification |
| Submodule P2 hardening | 44/44 | 2/44 started | 42 submodules need P2 |
| Submodule P3 scanning | All | None | Not started |
| DHI base images | All services | 0/57 | PR #1081 ready, needs merge + apply |
| CI hardening validation | Runs on Hardened branch | Hardened branch stale | CI validates wrong state |

---

## 6. Recommended Priorities (Z890 Perspective)

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 1 | **Merge PR #1081 (DHI manifest)** | Documents supply-chain migration path for 32 images | Review only |
| 2 | **Sync Hardened ← main** | Eliminates 2332-commit drift | `git merge main` on Hardened |
| 3 | **Classify 6 new submodules** | Updates hardening audit to 44/44 coverage | Audit only |
| 4 | **Apply DHI to python:3.11-slim (38 services)** | Single change covers 67% of services | 1 Dockerfile base swap |
| 5 | **P1 harden 15 Pending submodules** | Full coverage | Per-submodule (varies) |
| 6 | **Fix branch flow** | Align documented strategy with reality | Policy decision |

---

## 7. Related Documents

| Document | Location |
|----------|----------|
| Hardening Summary | `docs/PMOVES.AI-Edition-Hardened-Summary.md` |
| Hardening Full Guide | `docs/PMOVES.AI-Edition-Hardened-Full.md` |
| Implementation Plan | `docs/PMOVES.AI-Edition-Hardened-Full-Implementation-Plan.md` |
| Branch Strategy | `pmoves/docs/BRANCH_STRATEGY.md` |
| DHI Migration | `pmoves/docs/operations/DHI_MIGRATION_MANIFEST.md` (PR #1081) |
| Hardening Tracker | `docs/hardening/PMOVES-hardening-tracker.md` |
| Production Audit | `pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md` |
| Submodule Workflow | `.claude/context/submodule-workflow.md` |
