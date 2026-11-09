# SPARK VSS Integration — 2026-07-29

> **GRAPHITI_MARK:** SPARK-KIMI::SPARK-VSS-INTEGRATION::2026-07-29
> **Lane:** PM-Spark Video Search & Summarization for Claw / PMOVES agent mesh
> **Status:** foundation landed; compose/service wiring pending
> **Supersedes:** `pmoves/docs/handoffs/SPARK_HF_MCP_SERVER_WIRING_2026-07-28.md` § PM-Spark VSS opportunity

## Context

`PM-Spark-video-search-and-summarization` is the POWERFULMOVES fork of the NVIDIA VSS blueprint. It ships:

- GPU-accelerated video intelligence microservices (detection/tracking, embeddings, VLMs)
- Downstream analytics (behavior analytics, incidents, alerts)
- A VSS Agent layer exposing search/summarization/Q&A/report tools via MCP
- agentskills.io-compatible skills under `skills/` for deploy-time and runtime operations

The goal is to make VSS a first-class PMOVES capability: every agent (Claw, Claude, Kimi, Hermes, NemoClaw) can deploy and operate VSS workflows through the skill catalog, and the VSS Agent can publish/consume events on the PMOVES NATS bus.

## Foundation (this PR)

- [x] Add `PMOVES-Spark-VSS` submodule at repo root, tracking `main`.
- [x] Add `pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/PMOVES-Spark-VSS.md` Codex home overlay.
- [x] Update `SPARK_HF_MCP_SERVER_WIRING_2026-07-28.md` to mark VSS lane claimed.
- [x] Update `AGNOTE4482PHI.t1.md` claim/release entries.

## Next steps (future PRs)

### 1. VSS skills available to Claw

Install or symlink the VSS skill directories into Claw's managed skills directory:

```bash
# Per AGENTS.md skill-path guidance
~/.openclaw-autoclaw/skills/
├── vss-deploy-profile/
├── vss-ask-video/
├── vss-search-archive/
├── vss-summarize-video/
├── vss-generate-video-report/
├── vss-query-analytics/
├── vss-manage-alerts/
└── vss-manage-video-io-storage/
```

Each skill is self-contained with `SKILL.md` frontmatter. A `make` target or `pmoves/tools/install_vss_skills.py` script can copy/symlink from `PMOVES-Spark-VSS/skills/` and verify frontmatter.

### 2. `pmoves-vss-agent` compose service

Add a PMOVES-managed service that runs the VSS Agent inside the PMOVES docker network. This is intentionally lightweight for the first pass — the agent container connects to **externally provisioned** VSS backing services (NIM LLM/VLM, VST, Elasticsearch, Redis/Kafka) rather than trying to fold the entire NVIDIA blueprint into `docker-compose.yml`.

Recommended first shape:

| Field | Value |
|-------|-------|
| Service name | `pmoves-vss-agent` |
| Build context | `PMOVES-Spark-VSS/services/agent/` |
| Dockerfile | `docker/Dockerfile` |
| Internal port | `8000` |
| Host port | `8204` (next free after hf-mcp-server `:8203`) |
| Profile | `agents`, `media` |
| Networks | `pmoves_app`, `pmoves_bus` |
| Env file | `env.tier-media` or new `env.tier-vss` |
| Health | `GET /health` |
| MCP endpoint | `GET /mcp/sse` (verify contract after VSS Agent version) |

Required env (from VSS agent README):

- `HOST_IP`
- `EXTERNAL_IP`
- `INTERNAL_IP`
- `LLM_BASE_URL`
- `VLM_BASE_URL`
- `LLM_NAME`
- `VLM_NAME`
- `VST_INTERNAL_URL`
- `VST_EXTERNAL_URL`
- `VSS_AGENT_PORT`
- `NVIDIA_API_KEY` (if using NIM cloud endpoints)

### 3. Registry / team / catalog parity

Add `pmoves_vss_agent` to:

- `pmoves/config/agent_registry.yaml` — class `media`, health `/health`, MCP SSE endpoint.
- `pmoves/configs/agent-teams.yaml` — team `media`.
- `.claude/CATALOG.md` — host port, health, MCP surface.
- `pmoves/docs/SERVICE_DOCS_MATRIX.md` — service doc index.

### 4. Full VSS stack as optional compose overlay

Longer term, provide a `docker-compose.vss.yml` overlay (or use the submodule's own `deploy/docker/compose.yml`) that brings up the complete VSS profile (`base`, `search`, `lvs`, `alerts`) alongside PMOVES. This depends on:

- GPU host with NVIDIA Container Toolkit and supported driver.
- NIM microservice images (large downloads; require `NVIDIA_API_KEY`).
- Elasticsearch, Redis/Kafka, and MinIO/S3 storage.
- Port ranges that do not collide with PMOVES (`8200-8299` already used by HF services).

## Risks & open questions

- **Hardware:** VSS requires NVIDIA GPU with supported driver (580.x) and Docker Engine < 29.5.0. SPARK node must satisfy this before the full stack can run.
- **Port collision:** VSS default ports may overlap with PMOVES. Need a port-allocation pass before adding the full overlay.
- **Model licensing:** NIM microservices require NVIDIA AI Enterprise or NGC API key.
- **Scope creep:** The submodule is a full blueprint. Keep the first PMOVES integration to agent-only; let the `vss-deploy-profile` skill bring up backing services on demand.

## Verification

```bash
# Submodule present
git submodule status PMOVES-Spark-VSS

# Codex home overlay
ls pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/PMOVES-Spark-VSS.md

# VSS skill catalog
ls PMOVES-Spark-VSS/skills/
```

## Related

- Source: https://github.com/POWERFULMOVES/PM-Spark-video-search-and-summarization
- Prior handoff: `pmoves/docs/handoffs/SPARK_HF_MCP_SERVER_WIRING_2026-07-28.md`
- Skill install path: `.claude/PATTERNS.md` § Installing Skills
