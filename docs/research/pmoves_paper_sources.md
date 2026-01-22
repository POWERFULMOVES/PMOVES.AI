# PMOVES Scientific Paper Source Dossier

## Architecture Primers
- **Repository Overview** — `README.md` outlines the distributed, multi-agent mesh and directory map that anchors the paper's introductory narrative (lines 1-70).  It also enumerates orchestration services, creative bundles, and smoke harness checkpoints used later for evaluation (lines 38-136).
- **Multi-Agent Architecture Primer** — `docs/PMOVES_ARC.md` captures the layered Agent Zero/Archon/Hi-RAG topology, complete with Mermaid diagrams that trace orchestration, knowledge backbones, and media muscles (lines 1-180).

## Core Agent Services
- **Agent Zero** — `pmoves/services/agent-zero/README.md` documents the FastAPI supervisor, MCP endpoints, environment contract, and JetStream runtime wiring that the implementation section must restate (lines 1-73).  Complement with `pmoves/services/agent-zero/main.py` for configuration models, runtime client, controller loop, and HTTP routes (lines 1-840).
- **Archon** — `pmoves/services/archon/README.md` summarizes Supabase/NATS prerequisites, MCP ports, and ingest/publish topics needed to explain Archon's placement in the system pipeline (lines 1-66).
- **Hi-RAG Gateway v2** — `pmoves/services/hi-rag-gateway-v2/README.md` covers geometry endpoints, CHIT caches, make targets, and optional GAN sidecar behavior referenced by the retrieval discussion (lines 1-74).  Pair with `pmoves/services/hi-rag-gateway/gateway.py` for request validation, qdrant search composition, and Tailscale restrictions (lines 360-520).

## Retrieval, Extraction, and Media Pipelines
- **LangExtract** — `pmoves/services/langextract/api.py` plus `pmoves/libs/langextract/providers/rule.py` describe the HTTP façade, paragraph/question chunking, and publication hook that feed downstream retrieval (api.py lines 1-40; rule.py lines 1-80).
- **YouTube Ingest** — `pmoves/services/pmoves-yt/yt.py` details yt-dlp handling, S3 uploads, Supabase writes, and event emission into the multi-agent bus (lines 1-320).
- **Audio & Transcript Bridge** — `pmoves/services/ffmpeg-whisper/server.py` exposes transcription forwarding and Supabase persistence logic used when quantifying evaluation coverage (lines 1-220).

## Operations, Tooling, and Testing
- **Smoke Harness** — `pmoves/docs/SMOKETESTS.md` enumerates the twelve-step core stack smoke plus creative automations, informing the paper's reproducibility and evaluation plan (lines 1-200 & 117-153).
- **Local CI Expectations** — `docs/LOCAL_CI_CHECKS.md` spells out pytest, contract checks, and auxiliary verifications that align with the validation tests slated for the evaluation section (lines 1-120).
- **Make Targets** — `pmoves/docs/MAKE_TARGETS.md` is the authoritative command catalog referenced in methodology walkthroughs (lines 1-60).

## Known Gaps Requiring Deeper Research
- Clarify how the JetStream controller metrics emitted by Agent Zero should be sampled for longitudinal evaluation; `pmoves/services/agent-zero/main.py` exposes counters, but the capture cadence is undocumented.
- Validate cross-service error handling when the Hi-RAG gateway reranker or CLIP/CLAP models are disabled; the primer references fallback logic, yet regression coverage is light.
- Determine the authoritative data contract for `ingest.file.added.v1` envelopes so the paper's dataset section can cite schema lineage beyond the in-code publisher stub.
