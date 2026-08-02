# PMOVES-Spark-VSS

**Submodule:** `PMOVES-Spark-VSS/`
**Repository:** https://github.com/POWERFULMOVES/PM-Spark-video-search-and-summarization.git
**Upstream:** NVIDIA AI Blueprint for Video Search and Summarization
**Branch tracked:** `main` (native PMOVES fork; no upstream `PMOVES.AI-Edition-Hardened` branch)

## Scope

NVIDIA AI Blueprint for Video Search and Summarization (VSS), forked for PMOVES/SPARK. Provides GPU-accelerated vision agents and video analytics:

- **Layer 1 — Real-time video intelligence:** RT-CV detection/tracking, RT-Embed semantic video embeddings, RT-VLM captions/incident detection.
- **Layer 2 — Downstream analytics:** Behavior analytics, alert contextualization, incidents/metrics to Elasticsearch.
- **Layer 3 — Agent & offline processing:** VSS Agent exposes search, summarization, visual Q&A, and clip retrieval via Model Context Protocol (MCP).

## Use this when

- The user wants video understanding, search, summarization, or incident analysis.
- Claw or another PMOVES agent needs to deploy or operate a VSS workflow.
- You are wiring a `pmoves-vss-agent` compose service or exposing VSS tools to the PMOVES MCP mesh.

## PMOVES companions

- **Claw** — install VSS skills into `~/.openclaw-autoclaw/skills/` so Claw can deploy/operate VSS.
- **Agent Zero** — route VSS MCP tools through the agent mesh.
- **NATS** — VSS publishes features/incidents to a message broker; PMOVES can consume these via NATS.
- **MinIO / S3** — VSS uses object storage for clips and snapshots.
- **Elasticsearch** — VSS analytics layer stores incidents, metrics, tracker data.

## Core checks

```bash
# Submodule present and on expected branch
git submodule status PMOVES-Spark-VSS

# VSS skills catalog
ls PMOVES-Spark-VSS/skills/

# Agent service build context
ls PMOVES-Spark-VSS/services/agent/docker/

# Compose profiles in submodule
cat PMOVES-Spark-VSS/deploy/docker/compose.yml
```

## Related parity tokens

- `pmoves/docs/handoffs/SPARK_VSS_INTEGRATION_2026-07-29.md` — integration lane plan
- `pmoves/docs/handoffs/SPARK_HF_MCP_SERVER_WIRING_2026-07-28.md` — prior SPARK handoff that surfaced VSS opportunity
- `.claude/PATTERNS.md` § *MCP / SSE Service Review Patterns*

## Notes

- This submodule is a **developer-side blueprint**, not a single container. Integration into PMOVES compose is a multi-step lane documented in the handoff above.
- Skills are [agentskills.io](https://agentskills.io/specification)-compatible; install location is `~/.openclaw-autoclaw/skills/<skill-name>/` per AGENTS.md skill-path guidance.
