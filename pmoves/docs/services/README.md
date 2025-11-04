# PMOVES Services — Documentation Index

This index groups service docs by role. Each service page follows a common structure: Overview, Compose/Ports, Dependencies, Env, API/Contracts, Runbook, Smoke Tests, Next Steps, and Roadmap alignment.

Implemented (compose-managed)
- [agent-zero](agent-zero/README.md)
- [archon](archon/README.md)
- [extract-worker](extract-worker/README.md)
- [ffmpeg-whisper](ffmpeg-whisper/README.md)
- [hi-rag-gateway](hi-rag-gateway/README.md)
- [hi-rag-gateway-v2](hi-rag-gateway-v2/README.md)
- [jellyfin-bridge](jellyfin-bridge/README.md)
- [jellyfin-ai](jellyfin-ai/README.md)
- [langextract](langextract/README.md)
- [media-audio](media-audio/README.md)
- [media-video](media-video/README.md)
- [mesh-agent](mesh-agent/README.md)
- [deepresearch](deepresearch/README.md)
- [pdf-ingest](pdf-ingest/README.md)
- [pmoves-yt](pmoves-yt/README.md)
- [presign](presign/README.md)
- [publisher-discord](publisher-discord/README.md)
- [render-webhook](render-webhook/README.md)
- [retrieval-eval](retrieval-eval/README.md)
- [open-notebook](open-notebook/README.md)
- [neo4j](neo4j/README.md)

Auxiliary / Libraries / Adapters
- [agents](agents/README.md)
- [common](common/README.md)
- [gateway](gateway/README.md)
- [graph-linker](graph-linker/README.md)
- [comfy-watcher](comfy-watcher/README.md)
- [comfyui](comfyui/README.md)
- [n8n](n8n/README.md)
- [supabase](supabase/README.md)

External Integrations (self-hosted stacks)
- [wger](wger/README.md)
- [firefly-iii](firefly-iii/README.md)

Notes
- Legacy directories kept for history: `agent_zero/` (underscore variant), `analysis-echo/`.
- For environment setup and CI expectations, see the consolidated docs in [PMOVES.AI PLANS](../PMOVES.AI%20PLANS/README_DOCS_INDEX.md).
- CHIT/Geometry Bus is first‑class: each service page now indicates whether and how it exposes, publishes to, consumes, or defers CHIT interactions.
