# PMOVES.AI Submodules Reference

Comprehensive documentation of all 20 git submodules in the PMOVES.AI repository.

## Overview

PMOVES.AI uses git submodules to integrate external projects and specialized services. All submodules are configured with `ignore = all` to prevent accidental commits of submodule state changes.

**Repository:** `https://github.com/POWERFULMOVES/PMOVES.AI`

---

## Agent Coordination & Orchestration

### PMOVES-Agent-Zero
- **Path:** `PMOVES-Agent-Zero/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git
- **Branch:** `PMOVES.AI-Edition-Hardened`
- **Purpose:** Control-plane agent orchestrator with embedded runtime
- **Key Ports:**
  - `8080` - API server (health, MCP endpoints)
  - `8081` - Web UI
- **Integration Points:**
  - Exposes MCP API at `/mcp/*` for external agent integration
  - Subscribes to NATS for task coordination
  - Connects to Supabase, Hi-RAG, PMOVES.YT
- **Health Check:** `GET http://localhost:8080/healthz`
- **Docker Profile:** `agents`
- **README:** [PMOVES-Agent-Zero/README.md](../../../PMOVES-Agent-Zero/README.md)

### PMOVES-Archon
- **Path:** `PMOVES-Archon/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-Archon.git
- **Branch:** `PMOVES.AI-Edition-Hardened`
- **Purpose:** Supabase-driven agent service with prompt/form management
- **Key Ports:**
  - `8091` - API server
  - `3737` - Web UI
  - `8051/8052` - Internal MCP servers
- **Integration Points:**
  - Connects to Agent Zero's MCP interface
  - Uses Supabase for prompt storage and state management
  - NATS event coordination
- **Health Check:** `GET http://localhost:8091/healthz`
- **Docker Profile:** `agents`
- **README:** [PMOVES-Archon/README.md](../../../PMOVES-Archon/README.md)
- **Duplicate Path:** Also mounted at `pmoves/integrations/archon/`

---

## MCP Tools & Extensions

### PMOVES-BoTZ
- **Path:** `PMOVES-BoTZ/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-BoTZ.git
- **Branch:** `codex-bringup-stability-2025-12-14`
- **Purpose:** Unified multi-agent MCP tools ecosystem
- **Key Ports:**
  - `2091` - MCP Gateway
  - `3020` - Docling MCP (document processing)
  - `7071` - E2B Sandbox Runner
  - `7072` - Vision-Language Sentinel
  - `8081` - Cipher Memory (STDIO/HTTP)
  - `8110` - VPN MCP (Headscale + RustDesk management)
- **Features:**
  - Document processing (Docling)
  - Memory management (Cipher)
  - API testing and sandbox execution (E2B)
  - Vision-language processing (VL Sentinel)
  - VPN & Remote Desktop management (NEW)
  - MCP server catalog and gateway
- **Integration Points:**
  - MCP-compatible tools for agent consumption
  - Connects to Ollama for local model inference
  - NATS event publishing
  - Headscale API for VPN management
  - Supabase for session logging
- **README:** [PMOVES-BoTZ/README.md](../../../PMOVES-BoTZ/README.md)

---

## Content Creation & Media

### PMOVES-Creator
- **Path:** `PMOVES-Creator/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-Creator.git
- **Branch:** `PMOVES.AI-Edition-Hardened`
- **Purpose:** ComfyUI - visual AI engine for Stable Diffusion workflows
- **Key Ports:**
  - See ComfyUI documentation for specific ports
- **Features:**
  - Graph/nodes/flowchart based interface
  - Advanced stable diffusion pipelines
  - GPU-accelerated image generation
- **Integration Points:**
  - Render webhook callback to `render-webhook` service (port 8085)
  - Stores outputs to MinIO
  - Workflow automation via n8n
- **README:** [PMOVES-Creator/README.md](../../../PMOVES-Creator/README.md)

### PMOVES.YT
- **Path:** `PMOVES.YT/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES.YT.git
- **Branch:** `PMOVES.AI-Edition-Hardened`
- **Purpose:** YouTube ingestion service
- **Key Ports:**
  - `8077` - HTTP API
- **Key APIs:**
  - `POST /yt/ingest` - Ingest YouTube video
- **Integration Points:**
  - Downloads videos to MinIO
  - Retrieves transcripts (YouTube auto-captions or Whisper fallback)
  - Publishes NATS events: `ingest.file.added.v1`, `ingest.transcript.ready.v1`
  - Triggered by Channel Monitor service
- **README:** [PMOVES.YT/README.md](../../../PMOVES.YT/README.md)

---

## Knowledge & Research

### PMOVES-Deep-Serch
- **Path:** `PMOVES-Deep-Serch/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-Deep-Serch.git
- **Branch:** `PMOVES.AI-Edition-Hardened`
- **Purpose:** Deep research service (likely SupaSerch orchestrator)
- **Key Ports:**
  - `8098` - DeepResearch (LLM-based research planner)
  - `8099` - SupaSerch (multimodal holographic research)
- **Integration Points:**
  - NATS topics: `research.deepresearch.request.v1`, `supaserch.request.v1`
  - Auto-publishes results to Open Notebook
  - Coordinates with Archon/Agent Zero MCP tools
- **README:** [PMOVES-Deep-Serch/README.md](../../../PMOVES-Deep-Serch/README.md)

### PMOVES-HiRAG
- **Path:** `PMOVES-HiRAG/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-HiRAG.git
- **Branch:** `PMOVES.AI-Edition-Hardened`
- **Purpose:** Hybrid RAG (Retrieval-Augmented Generation) service
- **Key Ports:**
  - `8086` - Hi-RAG Gateway v2 (CPU)
  - `8087` - Hi-RAG Gateway v2 (GPU)
  - `8089` - Hi-RAG Gateway v1 (CPU, legacy)
  - `8090` - Hi-RAG Gateway v1 (GPU, legacy)
- **Key APIs:**
  - `POST /hirag/query` - Query endpoint
  - `GET /healthz` - Service health
- **Features:**
  - Combines Qdrant (vectors) + Neo4j (graph) + Meilisearch (full-text)
  - Cross-encoder reranking (BAAI/bge-reranker-base CPU, Qwen GPU)
  - CHIT Geometry Bus integration
  - Supabase realtime event broadcasting
- **README:** [PMOVES-HiRAG/readme.md](../../../PMOVES-HiRAG/readme.md)

### PMOVES-Open-Notebook
- **Path:** `PMOVES-Open-Notebook/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-Open-Notebook.git
- **Branch:** `fix/frontend-lockfile-sync`
- **Purpose:** Knowledge base / note-taking integration (SurrealDB)
- **Key Ports:**
  - See SurrealDB documentation for specific ports
- **Integration Points:**
  - Used by DeepResearch for persistent storage
  - Synced via `notebook-sync` service (port 8095)
  - Indexed via LangExtract and Extract Worker
- **README:** [PMOVES-Open-Notebook/README.md](../../../PMOVES-Open-Notebook/README.md)

---

## Document Processing

### PMOVES-DoX
- **Path:** `PMOVES-DoX/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-DoX.git
- **Branch:** `remotes/origin/HEAD`
- **Purpose:** Document intelligence platform - extract, analyze, structure data
- **Key Ports:**
  - `8092` - PDF Ingest service
- **Features:**
  - PDF, spreadsheet, XML log, CSV/XLSX processing
  - OpenAPI/Postman collection parsing
  - Local-first with Hugging Face + Ollama
  - AI-powered data extraction and analysis
- **Integration Points:**
  - Processes PDFs from MinIO
  - Sends to extract-worker for indexing
  - MCP/MS Teams Copilot compatible
- **README:** [PMOVES-DoX/README.md](../../../PMOVES-DoX/README.md)

---

## Media & Entertainment

### PMOVES-Jellyfin
- **Path:** `PMOVES-Jellyfin/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-Jellyfin.git
- **Branch:** `PMOVES.AI-Edition-Hardened`
- **Purpose:** Jellyfin media server integration
- **Key Ports:**
  - `8093` - Jellyfin Bridge (webhook & helper)
- **Integration Points:**
  - Syncs Jellyfin events to Supabase
  - Metadata webhook handler
  - Integrates with media processing pipeline
- **README:** [PMOVES-Jellyfin/README.md](../../../PMOVES-Jellyfin/README.md)

### Pmoves-Jellyfin-AI-Media-Stack
- **Path:** `Pmoves-Jellyfin-AI-Media-Stack/`
- **Repository:** https://github.com/POWERFULMOVES/Pmoves-Jellyfin-AI-Media-Stack.git
- **Branch:** `PMOVES.AI-Edition-Hardened`
- **Purpose:** AI-enhanced media stack for Jellyfin
- **Features:**
  - FFmpeg-Whisper transcription (port 8078)
  - Media-Video Analyzer with YOLOv8 (port 8079)
  - Media-Audio Analyzer (port 8082)
  - Extract Worker for embeddings (port 8083)
- **Integration Points:**
  - Reads/writes to MinIO
  - Indexes to Qdrant and Meilisearch
  - Outputs analysis to Supabase
- **README:** [Pmoves-Jellyfin-AI-Media-Stack/README.md](../../../Pmoves-Jellyfin-AI-Media-Stack/README.md)

---

## Personal Finance & Health

### PMOVES-Wealth
- **Path:** `PMOVES-Wealth/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-Wealth.git
- **Branch:** `fix/ci-gpg-optional-2025-12-15`
- **Purpose:** Firefly III - personal finance manager
- **Features:**
  - Open source personal finance tracking
  - Transaction management, budgeting, reporting
  - Multi-account support
- **Integration Points:**
  - Synced to Supabase via n8n workflow: `firefly_sync_to_supabase.json`
  - Monthly reports to CGP via n8n: `finance_monthly_to_cgp.json`
  - Real data calibration for PMOVES-ToKenism-Multi
- **README:** [PMOVES-Wealth/readme.md](../../../PMOVES-Wealth/readme.md)

### PMOVES-ToKenism-Multi
- **Path:** `PMOVES-ToKenism-Multi/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-ToKenism-Multi.git
- **Branch:** `PMOVES.AI-Edition-Hardened`
- **Purpose:** Token economy simulator for cooperative food systems
- **Features:**
  - 5-year business simulations (260 weeks)
  - Smart contract models (5 integrated token economy contracts)
  - Real data integration with Firefly-iii
  - Projection validation and confidence scoring
  - Event-driven architecture for contract communication
- **Integration Points:**
  - Calibrates with actual spending from Firefly-iii
  - Contains integrations for PMOVES-Firefly-iii and PMOVES-DoX
- **README:** [PMOVES-ToKenism-Multi/README.md](../../../PMOVES-ToKenism-Multi/README.md)

### Pmoves-Health-wger
- **Path:** `Pmoves-Health-wger/`
- **Repository:** https://github.com/POWERFULMOVES/Pmoves-Health-wger.git
- **Branch:** `PMOVES.AI-Edition-Hardened`
- **Purpose:** Wger workout and fitness tracking
- **Features:**
  - Workout planning and tracking
  - Exercise database
  - Nutrition tracking
- **Integration Points:**
  - Synced to Supabase via n8n workflow: `wger_sync_to_supabase.json`
  - Weekly health reports to CGP via n8n: `health_weekly_to_cgp.json`
  - Open Food Facts integration for nutrition data
- **README:** [Pmoves-Health-wger/README.md](../../../Pmoves-Health-wger/README.md)

---

## Infrastructure & Networking

### PMOVES-Tailscale
- **Path:** `PMOVES-Tailscale/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-Tailscale.git
- **Branch:** `main`
- **Purpose:** Tailscale VPN integration for secure mesh networking
- **Features:**
  - Private WireGuard networks
  - Zero-config VPN for service-to-service communication
  - Cross-platform support (Linux, Windows, macOS, FreeBSD, OpenBSD)
- **Integration Points:**
  - Provides secure networking layer for distributed PMOVES services
  - Used for remote access and multi-host coordination
- **README:** [PMOVES-Tailscale/README.md](../../../PMOVES-Tailscale/README.md)

### PMOVES-Remote-View
- **Path:** `PMOVES-Remote-View/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-Remote-View.git
- **Branch:** `PMOVES.AI-Edition-Hardened`
- **Purpose:** RustDesk - self-hosted remote desktop server
- **Features:**
  - Open source remote desktop solution
  - Self-hosted alternative to TeamViewer/AnyDesk
  - Cross-platform remote access
- **Components:**
  - `hbbs` - RustDesk ID/Rendezvous server
  - `hbbr` - RustDesk relay server
  - `rustdesk-utils` - CLI utilities
- **README:** [PMOVES-Remote-View/README.md](../../../PMOVES-Remote-View/README.md)

---

## Workflow & Automation

### PMOVES-n8n
- **Path:** `PMOVES-n8n/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-n8n.git
- **Branch:** `main`
- **Purpose:** n8n workflow automation for PMOVES.AI platform
- **Key Workflows:**
  - `echo_publisher.json` - Discord echo publishing
  - `approval_poller.json` - Content approval polling
  - `health_weekly_to_cgp.json` - Weekly health reports
  - `finance_monthly_to_cgp.json` - Monthly finance reports
  - `firefly_sync_to_supabase.json` - Firefly III sync
  - `wger_sync_to_supabase.json` - Wger health sync
  - `yt_docs_sync_diff.json` - YouTube docs sync
  - `pmoves_echo_ingest.json` - PMOVES echo ingestion
  - `pmoves_comfy_gen.json` - ComfyUI generation trigger
  - `pmoves_content_approval.json` - Content approval workflow
- **README:** [PMOVES-n8n/README.md](../../../PMOVES-n8n/README.md)

---

## Development Tools

### PMOVES-crush
- **Path:** `PMOVES-crush/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-crush.git
- **Branch:** `main` (configured to use `PMOVES.AI-Edition-Hardened`)
- **Purpose:** Charm Crush - terminal-based AI coding assistant
- **Features:**
  - Multi-model LLM support (OpenAI, Anthropic, local models)
  - Session-based context management
  - LSP-enhanced for code intelligence
  - Extensible via MCP (http, stdio, sse)
  - Cross-platform terminal support
- **Integration Points:**
  - Can integrate with TensorZero gateway for model routing
  - MCP-compatible for tool extensions
- **README:** [PMOVES-crush/README.md](../../../PMOVES-crush/README.md)

---

## Research & Training

### pmoves/vendor/agentgym-rl
- **Path:** `pmoves/vendor/agentgym-rl/`
- **Repository:** https://github.com/POWERFULMOVES/Pmoves-AgentGym-RL.git
- **Branch:** `main`
- **Purpose:** AgentGym-RL - training LLM agents via reinforcement learning
- **Features:**
  - Multi-turn interactive decision-making framework
  - Diverse real-world environment scenarios (27 tasks)
  - ScalingInter-RL algorithm for progressive interaction scaling
  - Visualized interactive UI for trajectory replay
  - Supports mainstream RL algorithms
- **Integration Points:**
  - Training framework for PMOVES agent models
  - Can integrate with Agent Zero for deployment
- **Dataset:** [AgentGym-RL-Data-ID on Hugging Face](https://huggingface.co/datasets/AgentGym/AgentGym-RL-Data-ID)
- **Paper:** [arXiv:2509.08755](https://arxiv.org/abs/2509.08755)
- **README:** [pmoves/vendor/agentgym-rl/README.md](../../../pmoves/vendor/agentgym-rl/README.md)

### pmoves/integrations/archon
- **Path:** `pmoves/integrations/archon/`
- **Repository:** https://github.com/POWERFULMOVES/PMOVES-Archon.git
- **Purpose:** Duplicate/integration mount of PMOVES-Archon
- **Note:** This is the same repository as `PMOVES-Archon/` but mounted at a different path for integration purposes.
- **README:** [pmoves/integrations/archon/README.md](../../../pmoves/integrations/archon/README.md)

---

## Submodule Management

### Initialization
```bash
# Initialize all submodules
git submodule update --init --recursive

# Initialize specific submodule
git submodule update --init PMOVES-Agent-Zero
```

### Updating
```bash
# Update all submodules to latest commit
git submodule update --remote --merge

# Update specific submodule
git submodule update --remote PMOVES-Agent-Zero
```

### Status Check
```bash
# View submodule status
git submodule status

# View detailed submodule info
git submodule foreach 'echo $name: $(git rev-parse HEAD)'
```

### Important Notes

1. **Ignore Configuration:** All submodules have `ignore = all` set in `.gitmodules` to prevent accidental commits of submodule state changes.

2. **Branch Tracking:** Most submodules track `PMOVES.AI-Edition-Hardened` branch for production stability.

3. **Integration Pattern:** Submodules provide specialized services that integrate with the core PMOVES.AI platform via:
   - HTTP APIs and health endpoints
   - NATS event bus for coordination
   - Supabase for shared state
   - MinIO for artifact storage
   - Docker Compose profiles for orchestration

4. **Development Workflow:**
   - Use existing submodule services via APIs (don't duplicate functionality)
   - Check submodule README for specific configuration and usage
   - Test submodule integration via `make verify-all` in pmoves/

---

## Quick Reference Table

| Submodule | Primary Port(s) | Purpose | Profile |
|-----------|----------------|---------|---------|
| PMOVES-Agent-Zero | 8080, 8081 | Agent orchestrator | agents |
| PMOVES-Archon | 8091, 3737 | Agent service + UI | agents |
| PMOVES-BoTZ | 2091, 3020, 7071, 7072, 8110 | MCP tools ecosystem + VPN | varies |
| PMOVES-Creator | varies | ComfyUI image generation | orchestration |
| PMOVES-Deep-Serch | 8098, 8099 | Research orchestration | orchestration |
| PMOVES-DoX | 8092 | Document processing | workers |
| PMOVES-HiRAG | 8086-8090 | Hybrid RAG | default |
| PMOVES-Jellyfin | 8093 | Media server bridge | varies |
| Pmoves-Jellyfin-AI-Media-Stack | 8078-8083 | AI media processing | workers |
| PMOVES-Open-Notebook | varies | Knowledge base (SurrealDB) | varies |
| PMOVES-Remote-View | varies | Remote desktop server | varies |
| PMOVES-Tailscale | N/A | VPN mesh networking | varies |
| PMOVES-ToKenism-Multi | N/A | Token economy simulator | N/A |
| PMOVES-Wealth | varies | Finance tracking (Firefly III) | varies |
| PMOVES-crush | N/A | Terminal AI assistant | N/A |
| PMOVES-n8n | varies | Workflow automation | varies |
| Pmoves-Health-wger | varies | Fitness tracking | varies |
| pmoves/vendor/agentgym-rl | N/A | RL training framework | N/A |

---

## See Also

- [CLAUDE.md](../../CLAUDE.md) - Main developer context
- [services-catalog.md](./services-catalog.md) - Complete service listing
- [nats-subjects.md](./nats-subjects.md) - NATS event subjects
- [testing-strategy.md](./testing-strategy.md) - Testing guidelines
