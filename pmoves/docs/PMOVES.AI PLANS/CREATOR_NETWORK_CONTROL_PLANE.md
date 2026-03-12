# PMOVES Creator Network Control Plane
_Last updated: 2026-03-12_

## Purpose
Define the 2026 production target for PMOVES as a creator-network control plane, not just a downloader stack.

This lane combines:
- owned-channel management
- creator monitoring and ingestion
- transcript/search/geometry indexing
- Discord agent interaction
- outreach and attribution workflows
- value-tracking through Tokenism

## Operator outcomes
PMOVES should let the operator:
- manage PMOVES-owned YouTube channels and playlists
- monitor other creators and ingest selected content with provenance
- transcribe, summarize, index, and route content through PMOVES services
- show how PMOVES used creator content and link back in a human-reviewable way
- coordinate Discord and other agent surfaces around the same content graph
- track downstream value creation and attribution with Tokenism

## Core system map
### 1. Content control
- `PMOVES.YT`: authoritative YouTube ingest runtime
- `channel-monitor`: discovery, OAuth-backed source monitoring, queueing
- `PMOVES-transcribe-and-fetch`: deeper transcript/content extraction and fetch workflows
- `pmoves/scripts/backfill_jellyfin_metadata.py`: Jellyfin linkage via `POST /yt/search`

### 2. Agent control
- `PMOVES-BoTZ`: Discord, MCP, memory, and tool gateway lanes
- Agent Zero / Archon: orchestration, event routing, policy execution
- n8n: approval and automation workflows for ingest, attribution, and publishing

### 3. Knowledge and attribution
- Hi-RAG v2 + CHIT / Geometry Bus: transcript chunks, geometry/event publication, retrieval
- Supabase: control plane, content metadata, tool docs, workflow state, attribution tables
- Tokenism: value-share/accounting lane for derived network effects

## 2026 model-routing intent
Model selection must stay registry-driven per `pmoves/docs/MODEL_FABRIC_CONTRACT.md`.

Recommended role split:
- edge embeddings: smaller Qwen embedding or EmbeddingGemma lanes
- workstation embeddings/rerank: larger Qwen embedding and reranker lanes
- multimodal perception: Qwen multimodal lanes for audio/video understanding
- planning and agent reasoning: Nemotron-class local or hosted reasoning lanes
- cloud fallback and Google-native multimodal/embedding features: optional, explicit, and policy-gated

Do not hardcode specific model IDs into service logic. Bind them through aliases and registry mappings.

## YouTube channel and playlist control
Needed capabilities:
- list and manage owned playlists and sources
- ingest from owned playlists with stronger metadata and approval controls
- monitor third-party creators with source-level preferences
- preserve provenance for every ingest
- distinguish owned-channel actions from watched-channel actions

Preferred control path:
1. Google OAuth and YouTube API for owned-channel and playlist management
2. `channel-monitor` for scheduled discovery and ingest routing
3. `PMOVES.YT` for download/transcript/search/index operations
4. n8n + Discord agent for review and operator actions

## Outreach and commenting policy
PMOVES may assist with creator networking, attribution, and comment drafting.

Guardrail:
- outbound public comments on third-party videos should be human-approved by default

Allowed automation pattern:
- draft comment
- attach provenance and PMOVES usage summary
- show backlink target
- require approval in Discord/n8n/operator UI
- then publish via the approved channel-management lane

This keeps PMOVES useful for networking without turning the system into blind spam automation.

## Tokenism connection
Tokenism should track:
- source creator
- PMOVES derivative asset or workflow
- attributable engagement or conversion
- share-of-value rules for collaborations, referrals, or creator deployments

The target is not just simulation. The target is traceable value flow from content discovery -> processing -> publishing -> relationship -> network growth.

## Near-term production backlog
1. Make `PMOVES.YT` + `channel-monitor` the canonical YouTube control plane for owned and watched sources.
2. Add explicit source classes: `owned`, `partner`, `watched`, `candidate`.
3. Add Discord approval flows for attribution posts, outreach comments, and playlist actions.
4. Tie `PMOVES-transcribe-and-fetch` into the same content registry and provenance model.
5. Add Supabase tables/views for creator relationships, attribution links, and Tokenism value events.
6. Expose model-role mappings for creator workflows through the model registry rather than env-only defaults.

## Related docs
- `pmoves/docs/MODEL_FABRIC_CONTRACT.md`
- `pmoves/docs/PMOVES.AI PLANS/JELLYFIN_YOUTUBE_INTEGRATION.md`
- `pmoves/docs/PMOVES.AI PLANS/PMOVES.yt/CHANNEL_MONITOR_IMPLEMENTATION.md`
- `PMOVES.YT/PMOVES.AI_INTEGRATION.md`
- `PMOVES-transcribe-and-fetch/AGENTS.md`
- `PMOVES-BoTZ/AGENTS.md`
