# PMOVES: Local-First Multi-Agent Orchestration for Retrieval and Creative Automation

## Abstract
PMOVES weaves Agent Zero, Archon, and Hi-RAG into a local-first mesh that coordinates research, retrieval, and media automation workflows.  Agent Zero supervises Model Context Protocol (MCP) commands, Archon curates knowledge and task state across Supabase, and Hi-RAG provides hierarchical retrieval augmented generation with geometry-aware outputs.  Surrounding “muscle” services such as LangExtract, pmoves-yt, and ffmpeg-whisper deliver ingestion and transcription pipelines that feed structured memories back into the orchestration loop.  This paper summarizes the architecture, implementation, and validation plan so the platform’s theoretical guarantees can be scrutinized and reproduced.

## Introduction
The PMOVES repository describes a distributed, multi-agent mesh anchored by Agent Zero, Archon, and auxiliary services that instrument retrieval, enrichment, and creative production across homelab and edge deployments.[^readme]  The architecture primer frames the system as layered functional tiers with Agent Zero acting as a central brain, Archon and n8n powering support systems, and Hi-RAG, LangExtract, and ComfyUI serving as specialized AI muscles over shared data backbones such as Supabase and MinIO.[^arc]

## Related Work and Positioning
Compared with cloud-first agent stacks, PMOVES emphasizes local autonomy, reproducible provisioning, and composable MCP endpoints.  The architecture diagrams highlight how Agent Zero delegates tasks to workflow engines, knowledge managers, and creative toolchains while maintaining feedback loops into the data backbone for self-improvement.[^arc]  The repository roadmap further anchors this work within ongoing multi-agent enhancements, but the present paper focuses on the core orchestration trio and their media pipelines.

## System Architecture
### Agent Zero Supervisor
Agent Zero’s FastAPI wrapper exposes health, configuration, MCP enumeration, event publication, and memory management routes, enabling external orchestrators to inspect runtime state and issue tasks over HTTP.[^az-readme]  Internally, the service materializes configuration via `AgentZeroServiceConfig`, proxies MCP commands defined in `mcp_server.py`, and manages a subprocess watchdog that keeps the upstream Agent Zero runtime responsive while forwarding JetStream metrics through `/healthz`.[^az-main]

### Archon Knowledge Orchestrator
Archon ships as a vendor bundle with wrappers that retarget Supabase URLs, NATS credentials, and MCP bridge ports so the knowledge manager can ingest crawl results, vector embeddings, and task metadata directly from the PMOVES stack.[^archon]  It subscribes to ingest and crawl topics and republishes task updates, positioning Archon as the long-lived knowledge substrate that Agent Zero queries through MCP.

### Hi-RAG Retrieval Gateway
The Hi-RAG gateway provides text, geometry, and media decoding endpoints while enforcing optional Tailscale access control for deployments that restrict retrieval APIs to mesh members.[^hirag-readme]  Query handling composes sentence-transformer embeddings, Qdrant vector searches, optional Meili lexical scores, and graph boosts before returning merged results.  The service validates `namespace`, `k`, and `alpha`, applies namespace filters via Qdrant, and can rerank with CrossEncoder models when enabled.[^hirag-main]

### Media and Extraction Services
LangExtract exposes REST endpoints that convert raw text or XML into paragraph and question chunks, tagging each record with namespace, section, and chunk identifiers suitable for downstream indexing.[^langextract]  The pmoves-yt service wraps `yt-dlp` to download media, upload artifacts to MinIO/S3, seed Supabase tables, and publish `ingest.file.added.v1` envelopes that downstream agents consume.[^pmoves-yt]  When transcripts are required, the ffmpeg-whisper server extracts audio, runs Whisper-compatible models, and forwards segments to Supabase while optionally relaying payloads to the media-audio service for further processing.[^ffmpeg-whisper]

## Implementation Details
### MCP and Event Bridging
Agent Zero’s implementation centers on `AgentZeroRuntimeConfig` and `AgentZeroProcessManager`, which compute subprocess commands, manage environment passthrough, and issue readiness probes against the upstream runtime.[^az-main]  HTTP dependencies invoke `ensure_runtime_running` to lazily start the runtime, while `/events/publish` guards against NATS unavailability by inspecting controller readiness before enveloping payloads.  MCP execution proxies synchronous helpers through a threadpool so I/O-bound geometry or notebook commands do not block the FastAPI event loop.

### Retrieval Pipeline Cohesion
Hi-RAG’s `run_query` function assembles Qdrant filters keyed on namespace, merges lexical and vector scores, and can incorporate geometry graph boosts via Neo4j when configured, ensuring retrieval results align with LangExtract chunking and Archon’s knowledge graph.[^hirag-main]  Because LangExtract maintains doc/section/chunk identifiers, Agent Zero can reference consistent memory payloads when presenting results or persisting new observations.

### Media Ingestion Flow
The pmoves-yt orchestrator coordinates yt-dlp downloads, object storage uploads, Supabase writes, and event publication in a single transaction, ensuring downstream extractors observe consistent metadata and content URLs.[^pmoves-yt]  Its transcript endpoint reuses the ffmpeg-whisper API, forwarding bucket and key metadata so LangExtract and Hi-RAG can enrich vector indexes once audio is transcribed.[^pmoves-yt]

## Methodology and Reproducibility
Reproducing PMOVES workflows requires invoking the documented Make targets: `make up` brings up the core data and worker plane, `make up-agents` launches Agent Zero, Archon, and NATS, and `make up-yt` activates the ingestion and transcription services.[^make-targets]  The smoke harness outlines a twelve-step validation covering Qdrant, Meilisearch, Agent Zero health, and geometry event handling, while optional flows exercise n8n webhooks and creative automations.[^smokes]  Local CI guidance mandates running pytest suites, CHIT contract checks, Jellyfin verification, SQL linting, and environment preflight scripts before submitting changes, aligning with the evaluation metrics proposed below.[^local-ci]

## Evaluation Plan
New automated tests substantiate the retrieval and orchestration claims.  `pmoves/tests/test_multiagent_workflow.py` orchestrates pmoves-yt, LangExtract, and Hi-RAG stubs to assert that video ingestion yields consistent document identifiers, published envelopes, chunk extraction, and namespace-scoped retrieval results.[^multiagent-test]  Complementary Agent Zero tests under `pmoves/services/agent-zero/tests/test_main.py` verify that `/config/environment` surfaces environment overrides and that `/mcp/commands` and `/mcp/execute` expose the MCP registry and proxy command execution while startup hooks safely stub the runtime and controller.[^agentzero-tests]  Together with the smoke harness and local CI checks, these tests provide empirical backing for the paper’s theoretical guarantees and supply reproducible commands for future benchmarking.

## Future Work
Further validation should capture JetStream metrics over time, extend integration tests to cover Archon ingest flows, and formalize the schema lineage for ingestion events referenced by the YouTube pipeline.  Additionally, reranker and CLIP/CLAP fallback paths in Hi-RAG merit fault-injection tests so the retrieval guarantees hold when optional accelerators are offline.

[^readme]: `README.md`, lines 1-136.
[^arc]: `docs/PMOVES_ARC.md`, lines 1-180.
[^az-readme]: `pmoves/services/agent-zero/README.md`, lines 1-73.
[^az-main]: `pmoves/services/agent-zero/main.py`, lines 320-520.
[^archon]: `pmoves/services/archon/README.md`, lines 1-66.
[^hirag-readme]: `pmoves/services/hi-rag-gateway-v2/README.md`, lines 1-74.
[^hirag-main]: `pmoves/services/hi-rag-gateway/gateway.py`, lines 360-520.
[^langextract]: `pmoves/services/langextract/api.py`, lines 1-40; and `pmoves/libs/langextract/providers/rule.py`, lines 1-38.
[^pmoves-yt]: `pmoves/services/pmoves-yt/yt.py`, lines 234-333.
[^ffmpeg-whisper]: `pmoves/services/ffmpeg-whisper/server.py`, lines 1-180.
[^make-targets]: `pmoves/docs/MAKE_TARGETS.md`, lines 1-90.
[^smokes]: `pmoves/docs/SMOKETESTS.md`, lines 1-153.
[^local-ci]: `docs/LOCAL_CI_CHECKS.md`, lines 1-112.
[^multiagent-test]: `pmoves/tests/test_multiagent_workflow.py`, lines 1-144.
[^agentzero-tests]: `pmoves/services/agent-zero/tests/test_main.py`, lines 1-115.
