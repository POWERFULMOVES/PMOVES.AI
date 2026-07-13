# HERMES Agent Integration -- PMOVES.AI

GRAPHITI_MARK: `PHI-4482-HERMES::INTEGRATION::PMOVES`

> **For:** Operators and agents integrating NousResearch Hermes Agent into PMOVES.AI.
> **Status:** REHEARSAL -- gateway soak in progress.
> **Last updated:** 2026-06-04
> **Owner:** hermes-agent

---

## What This Is

This document defines the integration of [Hermes Agent](https://github.com/NousResearch/hermes-agent) (NousResearch) into the PMOVES.AI multi-agent orchestration platform. Hermes Agent is a provider-agnostic AI agent framework with persistent memory, skills, cron jobs, subagent delegation, multi-platform gateway (Discord, Telegram, Slack, etc.), and MCP server capabilities.

PMOVES.AI already references `hermes3:8b` / `hermes3:70b` (the NousResearch Hermes-3 LLM) in the demo room and model catalog. This integration is **distinct** -- it treats Hermes Agent (the runtime/framework) as a first-class PMOVES citizen with its own room, profile, TAC tree, and NATS bridge.

## Integration Architecture

```
+-----------------------------------------------------------------------+
|                        PMOVES.AI MOF Lattice                          |
|  +--------+  +--------+  +--------+  +--------+  +--------+          |
|  |  Z890  |  |  5090  |  |  4090  |  |  Spark |  | B850   |          |
|  |3090 Ti |  |  5090  |  | Mobile |  |  GB10  |  |R9700x2 |          |
|  |Windows |  |  32GB  |  |  16GB  |  | 128GB  |  | 64GB   |          |
|  +--------+  +--------+  +--------+  +--------+  +--------+          |
|       |           |           |           |           |              |
|       +-----------+-----------+-----------+-----------+              |
|                           |                                          |
|                  NATS Message Bus                                    |
|                           |                                          |
|       +-------------------+-------------------+                      |
|       |                                       |                      |
|  +--------------------+          +----------------------+            |
|  | HERMES Agent Room  |          | Agent Zero (port 8080)|           |
|  | (port 7700)        |          | Orchestration backbone |           |
|  +--------------------+          +----------------------+            |
|       |                                                           |
|       |  Gateway (Discord/Telegram/Slack)                          |
|       |  MCP Server -> NATS relay                                  |
|       |                                                            |
|  +----+--------------------+----+                                   |
|  |    Local Model Mesh      |    |                                  |
|  |  Spark: 70B primary      |    |                                  |
|  |  5090: 8B + 70b staging  |    |                                  |
|  |  Z890/B850/4090: 8B      |    |                                  |
|  |  TensorZero -> Ollama    |    |                                  |
|  +----------------------------+    |                                  |
+-----------------------------------------------------------------------+
```

### Local Model Mesh

Hermes Agent routes inference through a **local model mesh** rather than always hitting cloud APIs:

1. **TensorZero Gateway** (port 3030) acts as the fleet-wide model router
2. **Ollama** on each GPU node serves local models:
   - Spark (GB10): `hermes3:70b` primary, `hermes3:8b` secondary
   - 5090: `hermes3:8b` primary, `hermes3:70b` staging
   - Z890/B850/4090: `hermes3:8b` only
3. **Tailscale mesh** makes Ollama endpoints available across nodes:
   - `http://pmoves-spark:11434` for 70B fallback
   - `http://pmoves-5090:11434` for 8B fallback
4. **Hermes Agent `model` config** defines fallback chains per profile:
   - Primary: local Ollama (`ollama/hermes3:8b` or `ollama/hermes3:70b`)
   - Fallback: OpenRouter (`nousresearch/hermes-3`)
   - Emergency: cloud provider (OpenAI, Anthropic)

This means a Z890 operator can run `hermes chat -q "..."` and the agent will:
1. Try local `hermes3:8b` on Z890 first
2. If the task needs 70B, delegate to Spark via `delegate_task` or Tailscale Ollama
3. If all local options fail, fall back to OpenRouter


## Distinguishing Hermes Agent vs Hermes-3 Model

| Attribute | `hermes` (existing) | `hermes-agent` (new) |
|-----------|---------------------|----------------------|
| What | Hermes-3 LLM model | Hermes Agent framework |
| Ollama tag | `hermes3:8b`, `hermes3:70b` | N/A (runtime, not model) |
| Role | Reasoning assist inside demo room | Cross-platform gateway + skill orchestrator |
| Identity | `agent_signatures.yaml` -> `hermes` | `agent_signatures.yaml` -> `hermes-agent` |
| Room | `demo.room.rehearsal` (app) | `hermes-agent.room.control` (dedicated room) |
| Port | N/A (model via Ollama) | 7700 (gateway HTTP) |
| NATS | Subscribed as consumer | Publishes gateway + MCP events |

## Files Created / Modified

### New files
| File | Purpose |
|------|---------|
| `.claude/agents/hermes-agent.md` | Three-Body Delivery Body agent definition |
| `pmoves/config/rooms/hermes-agent.room.control.json` | Room manifest |
| `pmoves/configs/tac_trees/node-hermes-agent.tac.yaml` | TAC integration roadmap |
| `.claude/skills/hermes-agent-integration/SKILL.md` | Operator skill |
| `pmoves/docs/AGENTS/HERMES_AGENT_INTEGRATION.md` | This document |

### Modified files
| File | Change |
|------|--------|
| `pmoves/config/rooms/catalog.json` | Added `hermes-agent.room.control` entry |
| `pmoves/config/agent_registry.yaml` | Added `hermes-agent` contributor + agent entry |
| `pmoves/config/agent_signatures.yaml` | Added `hermes-agent` signature |

## Bridge Contracts (PMOVES <-> HERMES)

| PMOVES | HERMES | Binding Detail |
|--------|--------|----------------|
| Room | Profile | `hermes profile use pmoves-hermes` per room role |
| Stage | Session source | `--source rehearsal/live/review/archive` |
| Suit | Toolset + skills | `hermes -s <skill>` preloads suit capabilities |
| P7 Launch | Gateway + NATS | `p7.nats.launch` triggers profile activation |
| CHIT Trail | Memory + provenance | `memory` toolset + skill `created_by: agent` |
| Agent Zero | `delegate_task` | Leaf subagent for bounded tasks |
| NATS Bus | `messaging` + MCP | Cross-platform event relay |

## Practice Context: Ageless Beauty (Elder-Melchor)

**Elder-Melchor is the primary workstation for a Nurse Practitioner with her own practice: Ageless Beauty.**
This node serves dual roles:
1. **Clinical practice workstation** -- HIPAA-compliant patient care, scheduling, charting
2. **PMOVES.AI development node** -- Hermes Agent integration, skill curation, theme design

### Practice-Specific Requirements
| Domain | Integration | Status |
|--------|-------------|--------|
| **Patient Records** | HIPAA-compliant EHR via Hostinger-hosted portal | Planned |
| **Scheduling** | Appointment booking + reminders (Discord/Telegram gateway) | Configured |
| **Telehealth** | Secure video calls (Tailscale mesh, NATS relay) | Configured |
| **BPM (Business Process)** | Workflow automation for intake, insurance, follow-up | Planned |
| **Chakra** | Wellness tracking + patient energy assessments | Planned |
| **Health Stack** | PMOVES-Health-wger integration for patient fitness plans | Planned |
| **Wealth Stack** | PMOVES-Wealth integration for practice financials | Planned |

### Hostinger Hosting
- **Website**: Ageless Beauty public-facing site on Hostinger
- **HIPAA Compliance**: Hostinger VPS with encrypted storage, TLS 1.3, access logs
- **Patient Portal**: Separate subdomain with CHIT-signed authentication
- **Backups**: Automated to PMOVES-Jellyfin media stack (encrypted)

### Pinokio HERMES Mod
- **Custom CLI skin**: Ageless Beauty branded terminal theme (rose gold + sage green)
- **Voice activation**: "Ageless Beauty, activate" wake word for hands-free charting
- **Patient mode**: Auto-redact all patient data from logs, memory, NATS events
- **4090 CLAUDE theme work**: Referenced below in Theme Integration section

### Cloud-First Model Strategy (Resource Conservation)
Given the practice workload, Elder-Melchor reserves local GPU for:
- Patient data embedding (local, HIPAA-safe)
- Lightweight inference for quick lookups

All heavy inference routes to cloud providers:
- **Z.AI Coding Plan**: Code generation, documentation, PR review
- **MiniMax Token Plan**: Creative content, patient education materials
- **Ollama Cloud**: Remote model serving (not local GPU)
- **Fleet offload**: Spark/5090 for 70B or GPU-heavy tasks

## BPM Three-Layer Bridge Architecture

PMOVES.AI uses "BPM" as a **multi-layered bridge concept** -- the same acronym intentionally connects three domains:

| Layer | Full Name | Domain | System | NATS Subject |
|-------|-----------|--------|--------|--------------|
| **BPM¹** | **Beats Per Minute** | Audio/Musical | Flute Gateway + ToKenism | `tokenism.prosodic.bpm.v1` |
| **BPM²** | **Bridge Protocol Module** | Geometry/Information | CHIT Cymatic-Holographic Transfer | `tokenism.geometry.event.v1` |
| **BPM³** | **Business Process Management** | Workflow/Clinical | Ageless Beauty Practice Automation | `hermes.mcp.toolcall.v1` |

### Layer 1: Beats Per Minute (Audio)
- **Flute Gateway** prosodic TTS with pause-to-BPM mapping
- **Boundary mapping**: SENTENCE→60 BPM (Largo), CLAUSE→90 BPM (Andante), PHRASE→120 BPM (Allegro), BREATH→80 BPM (Adagio), NONE→150 BPM (Presto)
- **Practice use**: 60 BPM meditation audio, 90 BPM gentle appointment reminders
- **Modifiers**: fast_tempo (F5-TTS speed 1.4), slow_groove (F5-TTS speed 0.75)
- **Pipeline**: text-generate → prosodic-analyze → tts-synthesize

### Layer 2: Bridge Protocol Module (Geometry)
- **CHIT** encodes meaning as hyperbolic geometry (K = -1 curvature)
- **Components**: hyperbolic_encoder, dirichlet_weights, shape_attribution (SHA-256 Shape ID for 30-day replay), zeta_filter, swarm_attribution
- **CHIT types**: CGP (Computational Geometry Packet), BPM (Prosodic marker), swarm (Population geometry), cipher (Encrypted)
- **Practice use**: Patient data as CHIT geometry (HIPAA-safe shape IDs), Chakra energy mapped to hyperbolic coordinates
- **Cross-ref**: `pmoves/docs/PMOVESCHIT/02_GEOMETRY_BUS.md`

### Layer 3: Business Process Management (Workflow)
- **Workflow engine**: n8n / temporal / custom (TBD post-PR)
- **Workflows**: patient_intake → insurance_processing → follow_up → wellness_plan → billing
- **CHIT integration**: Every workflow step emits CHIT-signed checkpoints
- **Practice use**: End-to-end automation from patient arrival to follow-up with HIPAA audit trails

### BPM Interconnect
All three layers communicate through NATS:
```
tokenism.prosodic.bpm.v1   (Layer 1 audio → Layer 2 geometry)
tokenism.geometry.event.v1 (Layer 2 geometry → Layer 3 workflow)
hermes.mcp.toolcall.v1     (Layer 3 workflow → Layer 1 audio output)
```

## PMOVES.AI Submodule Fleet

All PMOVES services are organized as Git submodules in `.gitmodules` (repo root).
**Status**: Most submodules are not initialized on this node (empty directories).
**Init command**: `git submodule update --init <submodule-path>`

### Submodule Tiers (10 categories, 50+ repos)

| Tier | Submodules | Branch | Purpose |
|------|-----------|--------|---------|
| **Core Agent** | PMOVES-Agent-Zero, PMOVES-Archon, PMOVES-BoTZ, PMOVES-BotZ-gateway | Hardened/main | Agent orchestration |
| **Knowledge** | PMOVES-A2UI, PMOVES-Deep-Serch, PMOVES-HiRAG, Pmoves-hyperdimensions, PMOVES-Open-Notebook | Hardened | Research & knowledge base |
| **Agent Training** | PMOVES-AgentGym, Pmoves-AgentGym-RL, PMOVES-llama-throughput-lab, PMOVES-surf | Hardened | RL training & benchmarking |
| **E2B Sandbox** | PMOVES-E2B-Danger-Room, PMOVES-E2B-Danger-Room-Desktop, PMOVES-Danger-infra, PMOVES-E2b-Spells, pmoves-e2b-mcp-server | main/Hardened | Sandboxed code execution |
| **Voice/Speech** | PMOVES-Pipecat, PMOVES-Pinokio-Ultimate-TTS-Studio, PMOVES-Ultimate-TTS-Studio, PMOVES-transcribe-and-fetch | Hardened/main | TTS, STT, voice pipelines |
| **Media/Content** | PMOVES.YT, PMOVES-Jellyfin, Pmoves-Jellyfin-AI-Media-Stack | Hardened | Video hosting, content generation |
| **Documents** | PMOVES-DoX, PMOVES-Creator | Hardened | Document processing |
| **Workflow** | PMOVES-n8n, PMOVES-crush | Hardened | BPM automation |
| **LLM Gateway** | PMOVES-tensorzero | Hardened | Model routing & inference |
| **Financial/Health** | PMOVES-Wealth, Pmoves-Health-wger | Hardened | **Ageless Beauty practice** |
| **Network** | PMOVES-Tailscale, PMOVES-Remote-View, PMOVES-Headscale | Hardened/main | Mesh VPN & remote access |
| **Data** | PMOVES-ToKenism-Multi, PMOVES-supabase, PMOVES-Neo4j | Hardened | Attribution, DB, graph |
| **Security** | Pmoves-cipher, pmoves-cipher-mcp | main | Encryption, identity |
| **Plugins** | PMOVES-a0-plugins, PMOVES-autoresearch, PMOVES-ClawZ, PMOVES-space-agent | Hardened/main | Agent Zero plugins |
| **Skills** | skills/Pmoves-skills, skills/PMOVES-awesome-agent-skills, skills/pmoves-fork-repository-skill, skills/PMOVES-agent-sandbox-skill, skills/Pmoves-claude-d3js-skill | main | Reusable agent skills |

### Ageless Beauty Practice Submodules (Priority)

| Submodule | Git URL | Branch | Status | Init Command |
|-----------|---------|--------|--------|--------------|
| **Pmoves-Health-wger** | github.com/POWERFULMOVES/Pmoves-Health-wger | Hardened | Not initialized | `git submodule update --init Pmoves-Health-wger` |
| **PMOVES-Wealth** | github.com/POWERFULMOVES/PMOVES-Wealth | Hardened | Not initialized | `git submodule update --init PMOVES-Wealth` |
| **PMOVES-n8n** | github.com/POWERFULMOVES/PMOVES-n8n | Hardened | Not initialized | BPM workflow engine |
| **PMOVES-MAI-UI** | github.com/POWERFULMOVES/PMOVES-MAI-UI | main | Not initialized | Practice web UI |
| **Pmoves-Jellyfin-AI-Media-Stack** | github.com/POWERFULMOVES/Pmoves-Jellyfin-AI-Media-Stack | Hardened | Not initialized | Patient education media |
| **PMOVES-supabase** | github.com/POWERFULMOVES/PMOVES-supabase | Hardened | Not initialized | Patient data backend |

## Node Profiles & Local Model Mesh

PMOVES.AI runs a **heterogeneous GPU fleet**. Hermes Agent must route inference to the right node based on model size and GPU backend (CUDA vs ROCm). The profiles below define per-node `config.yaml` overrides and local model assignments.

### Shared base (`pmoves-hermes` profile)
```bash
hermes profile create pmoves-hermes
```
- Skills dir: `pmoves/hermes-skills` (gitignored, per-node)
- Memory provider: sqlite (default)
- Default toolsets: `web`, `terminal`, `file`, `messaging`, `cronjob`, `delegation`
- Remote model: `openrouter/nous-hermes` (fleet-wide fallback)
- NATS MCP: wired to `pmoves-nats:4222`

### Local Model Routing Matrix

| Model | Ollama Tag / HF ID | VRAM | Nodes | Backend |
|-------|-------------------|------|-------|---------|
| Hermes V4 8B | `hermes3:8b` | ~5GB | Z890, 5090, 4090, B850 | CUDA or ROCm |
| Hermes V4 70B | `hermes3:70b` | ~40GB | **Spark only** | CUDA (GB10) |
| Gemma4 Embed | `google/gemma-embedding-exp-03-07` | ~4GB | Z890, 5090, Spark, B850 | CUDA or ROCm |
| NeMo Omni VL | `nvidia/NVLM-D-72B` | ~80GB | **Spark only** | NeMo >= 2.1 |
| Unsloth Hermes 8B | `unsloth/Hermes-3-Llama-3.1-8B` | ~4.5GB | 5090, 4090, B850 | GGUF / CUDA / ROCm |
| Unsloth Hermes 70B | `unsloth/Hermes-3-Llama-3.1-70B` | ~38GB | **Spark only** | GGUF / CUDA |

### Per-node profiles

#### Elder-Melchor (THIS NODE)
```bash
hermes profile create pmoves-hermes-elder --clone-from pmoves-hermes
hermes profile use pmoves-hermes-elder
```
- **Hardware**: Intel Core i7-9750H @ 2.60GHz (6C/12T laptop), 32GB RAM
- **GPU**: NVIDIA GeForce GTX 1650 4GB (discrete) + Intel UHD Graphics 630 128MB (integrated)
- **Storage**: 954 GB total, ~64% used
- **OS**: Windows 10 64-bit
- **Hostname**: <HOSTNAME_ELDER_MELCHOR> (renaming to Elder-Melchor after restart)
- **Gateway port**: 7700
- **Ollama**: localhost:11434
- **Local models**:
  - `hermes3:8b` (PRIMARY, may need CPU offload or Q4 quantization due to 4GB VRAM)
- **Model fallback**: Tailscale -> `pmoves-5090:11434` or `pmoves-spark:11434` for heavier inference
- **Toolsets**: `web`, `terminal`, `file`, `browser`, `messaging`, `cronjob`, `skills`, `memory`
- **Disabled toolsets**: `image_gen`, `video`, `rl`, `moa` (GTX 1650 insufficient)
- **TTS**: edge (default)
- **STT**: faster-whisper local (`base` model)
- **Power management**: Laptop mode -- gateway disabled on battery-saver, reduced turns
- **Windows quirks**: Ctrl+Enter for newline, forward-slash paths, UTF-8 without BOM

#### Z890 (Windows Workstation)
```bash
hermes profile create pmoves-hermes-z890 --clone-from pmoves-hermes
hermes profile use pmoves-hermes-z890
```
- **Hardware**: RTX 3090 Ti 24GB, Windows 11 Pro, 20C/32GB RAM
- **Terminal backend**: local (bash via git-bash; PowerShell fallback disabled)
- **Gateway port**: 7700
- **Ollama**: localhost:11434 (Windows native or WSL2)
- **Local models**:
  - `hermes3:8b` (PRIMARY local model, ~5GB VRAM)
  - Gemma4 embed via HuggingFace (cpu/gpu hybrid)
- **Model fallback**: Tailscale -> `pmoves-5090:11434` or `pmoves-spark:11434` for 70B
- **TTS**: edge (default, free)
- **STT**: faster-whisper local (`base` model)
- **Toolsets**: `web`, `terminal`, `file`, `browser`, `image_gen`, `vision`
- **Windows quirks**:
  - Use **Ctrl+Enter** for newline (Alt+Enter trapped by Windows Terminal fullscreen)
  - Forward-slash paths preferred in bash (`C:/Users/...`)
  - Config must be UTF-8 without BOM (re-save if `hermes doctor` throws HTTP 400)
  - WinError 10106 in sandbox = missing `SYSTEMROOT` env var (allowlisted in Hermes)

#### 5090 (Primary GPU)
```bash
hermes profile create pmoves-hermes-5090 --clone-from pmoves-hermes
hermes profile use pmoves-hermes-5090
```
- **Hardware**: RTX 5090 32GB, primary GPU workhorse
- **Gateway port**: 7700
- **Ollama**: localhost:11434 (primary Ollama host for fleet)
- **Local models**:
  - `hermes3:8b` (~5GB VRAM)
  - `hermes3:70b` (STAGING ONLY, ~40GB VRAM -- 5090 can load it but Spark is preferred)
  - Gemma4 embed via Ollama (2560d)
  - Unsloth Hermes 8B GGUF (optimized)
- **Toolsets**: `web`, `terminal`, `file`, `browser`, `image_gen`, `vision`, `rl`, `moa`, `video`
- **TTS**: elevenlabs (premium) or edge
- **STT**: faster-whisper (`small` or `medium`)
- **Cron**: enabled for fleet maintenance
- **TensorZero**: gateway (3030) routes to Ollama when local is preferred

#### 4090 (Mobile)
```bash
hermes profile create pmoves-hermes-4090 --clone-from pmoves-hermes
hermes profile use pmoves-hermes-4090
```
- **Hardware**: RTX 4090 Mobile 16GB
- **Gateway port**: 7700 (disabled when battery-saver active)
- **Ollama**: localhost:11434
- **Local models**:
  - `hermes3:8b` (PRIMARY, ~5GB VRAM)
  - Unsloth Hermes 8B GGUF (mobile-optimized)
- **Toolsets minimal**: `web`, `terminal`, `file`, `messaging`
- **Memory**: sqlite (no cloud sync on mobile)
- **Model fallback**: Tailscale -> 5090 for heavier inference

#### Spark (DGX-Spark GB10)
```bash
hermes profile create pmoves-hermes-spark --clone-from pmoves-hermes
hermes profile use pmoves-hermes-spark
```
- **Hardware**: GB10 Grace-Blackwell 128GB unified memory
- **Role**: PRIMARY inference node for 70B+ models and NeMo Omni
- **Gateway port**: 7700 (optional -- primarily inference host)
- **Ollama**: localhost:11434
- **Local models**:
  - `hermes3:70b` (PRIMARY 70B host, ~40GB VRAM) -- **SPARK ONLY**
  - `hermes3:8b` (secondary / testing, ~5GB VRAM)
  - NeMo Omni VL (`nvidia/NVLM-D-72B`, requires NeMo >= 2.1)
  - Gemma4 embed via HuggingFace sentence-transformers
  - Unsloth Hermes 70B GGUF (optimized for GB10)
- **Toolsets**: `web`, `terminal`, `file`, `browser`, `image_gen`, `vision`, `rl`, `moa`, `video`
- **Cron**: enabled for model-sync and dataset prep
- **TTS**: elevenlabs (premium) or edge
- **STT**: faster-whisper (`medium` or `large-v3`)
- **NATS**: publishes large inference completion events
- **IMPORTANT**: 70B models are **Spark-only**. Do not attempt on 5090 (unstable at limit), 4090 (OOM), Z890 (OOM), or B850 (ROCm compatibility untested at 70B).

#### B850 / RDNA4 (PMOVES-Knuckles)
```bash
hermes profile create pmoves-hermes-b850 --clone-from pmoves-hermes
hermes profile use pmoves-hermes-b850
```
- **Hardware**: Dual AMD R9700 64GB VRAM total, ROCm 7.1
- **Role**: Linux container host + ROCm dual-GPU inference
- **Gateway port**: 7700
- **Ollama**: localhost:11434 (ROCm backend)
- **Local models**:
  - `hermes3:8b` (Ollama ROCm, ~5GB VRAM per GPU)
  - Gemma4 embed via HuggingFace sentence-transformers + ROCm
  - GGUF row-split across dual R9700 (llama.cpp with ROCm)
- **Toolsets**: `web`, `terminal`, `file`, `messaging`, `cronjob`, `code_execution`
- **TTS**: edge (local)
- **STT**: faster-whisper (`base`)
- **Notes**:
  - ROCm stack required (`rocm-dev`, `hip-runtime`). **Not CUDA**.
  - Row-split inference tested with Gemma4 GGUF; Hermes GGUF pending ROCm validation.
  - Use `HIP_VISIBLE_DEVICES=0,1` for dual-GPU visibility.

#### KVM4-1 (Headless VPS)
```bash
hermes profile create pmoves-hermes-kvm --clone-from pmoves-hermes
hermes profile use pmoves-hermes-kvm
```
- **Hardware**: No GPU
- **Gateway port**: 7700
- **Model**: `openrouter/nous-hermes` (no local inference)
- **Toolsets**: `web`, `terminal`, `file`, `messaging`, `cronjob`
- **No TTS/STT** (headless)
- **NATS leaf node** to `pmoves-nats`

## NATS Subject Catalog (Hermes-specific)

New subjects introduced by this integration:

```yaml
hermes.gateway.launched.v1:
  description: "Hermes gateway started on a node"
  payload: {room, node_id, profile, timestamp, version}
  publisher: hermes-agent
  subscriber: [p7, monitoring]

hermes.gateway.health.v1:
  description: "Periodic gateway health telemetry"
  payload: {status, uptime_ms, version, node_id}
  publisher: hermes-agent
  subscriber: [monitoring, p7]

hermes.mcp.toolcall.v1:
  description: "MCP tool execution event"
  payload: {room, tool, args, result, latency_ms, node_id}
  publisher: hermes-agent
  subscriber: [agent-zero, archon]

hermes.skill.curated.v1:
  description: "Skill install/update/uninstall event"
  payload: {skill_name, action, version, node_id}
  publisher: hermes-agent
  subscriber: [p7, skills-hub]

hermes.cron.executed.v1:
  description: "Cron job completion"
  payload: {job_id, schedule, output, exit_code, node_id}
  publisher: hermes-agent
  subscriber: [monitoring, p7]

hermes.delegate.completed.v1:
  description: "Subagent delegation completion"
  payload: {task_id, summary, artifacts, node_id}
  publisher: hermes-agent
  subscriber: [agent-zero, p7]
```

## Deployment Runbook

### 1. Install Hermes Agent
```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

### 2. Create PMOVES profile
```bash
hermes profile create pmoves-hermes --clone-from default
hermes profile use pmoves-hermes
```

### 3. Apply node-specific profile config
Copy the per-node YAML from `pmoves/config/profiles/hermes/` into your profile:

| Node | Command |
|------|---------|
| Z890 (this node) | `cp pmoves/config/profiles/hermes/z890.yaml ~/.hermes/profiles/pmoves-hermes/config.yaml` |
| 5090 | `scp pmoves/config/profiles/hermes/5090.yaml pmoves-5090:~/.hermes/profiles/pmoves-hermes/config.yaml` |
| 4090 | `scp pmoves/config/profiles/hermes/4090.yaml pmoves-4090:~/.hermes/profiles/pmoves-hermes/config.yaml` |
| Spark | `scp pmoves/config/profiles/hermes/spark.yaml pmoves-spark:~/.hermes/profiles/pmoves-hermes/config.yaml` |
| B850 | `scp pmoves/config/profiles/hermes/b850.yaml pmoves-b850:~/.hermes/profiles/pmoves-hermes/config.yaml` |
| KVM4-1 | `scp pmoves/config/profiles/hermes/kvm4-1.yaml kvm4-1:~/.hermes/profiles/pmoves-hermes/config.yaml` |

### 4. Pull local models per node

**Z890, 5090, 4090, B850 (8B models):**
```bash
ollama pull hermes3:8b
```

**Spark (70B + 8B):**
```bash
ssh pmoves-spark "ollama pull hermes3:70b"
ssh pmoves-spark "ollama pull hermes3:8b"
```

**B850 ROCm (8B):**
```bash
ssh pmoves-b850 "OLLAMA_BACKEND=rocm ollama pull hermes3:8b"
```

**HuggingFace models (Spark, Z890, B850):**
```bash
# Gemma4 embed
huggingface-cli download google/gemma-embedding-exp-03-07 --local-dir ~/.cache/huggingface/gemma4-embed

# NeMo Omni VL (Spark only)
ssh pmoves-spark "huggingface-cli download nvidia/NVLM-D-72B --local-dir ~/.cache/huggingface/nemo-omni-vl"

# Unsloth Hermes 8B GGUF
huggingface-cli download unsloth/Hermes-3-Llama-3.1-8B --local-dir ~/.cache/huggingface/unsloth-hermes-8b

# Unsloth Hermes 70B GGUF (Spark only)
ssh pmoves-spark "huggingface-cli download unsloth/Hermes-3-Llama-3.1-70B --local-dir ~/.cache/huggingface/unsloth-hermes-70b"
```

### 5. Populate secrets via CHIT funnel
```bash
make -C pmoves secrets-funnel
# Manually copy relevant keys from env.shared into ~/.hermes/profiles/pmoves-hermes/.env
# DO NOT commit .env
```

### 6. Configure model
```bash
hermes model
# Select primary provider (OpenRouter recommended for fleet consistency)
# Set fallback to local Ollama if available
```

### 7. Start gateway (5090 primary)
```bash
hermes --profile pmoves-hermes gateway run
# Or as background service:
hermes --profile pmoves-hermes gateway install
hermes --profile pmoves-hermes gateway start
```

### 8. Verify health
```bash
curl -sf http://localhost:7700/api/health
hermes --profile pmoves-hermes status
```

### 9. Install PMOVES skills
```bash
hermes --profile pmoves-hermes skills install https://raw.githubusercontent.com/POWERFULMOVES/hermes-skills-pmoves/main/pmoves-health/SKILL.md
```

## Security Boundaries

- Hermes `.env` and `auth.json` are **never committed** -- paths already gitignored by `.gitignore` (verify `*.env`, `auth.json`, `.hermes/` patterns)
- CHIT signing required for production gateway tokens (voice-activated, never auto-generated)
- Gateway port 7700 is internal/Tailscale-only -- do not expose to public internet without reverse proxy + auth
- `hermes-agent` agent definition disallows `EnterPlanMode` to prevent unbounded plan loops
- Secret redaction enabled by default -- disable only for debugging via `hermes config set security.redact_secrets false` + restart

## Troubleshooting

| Issue | Diagnostic | Fix |
|-------|------------|-----|
| Gateway port conflict | `lsof -i :7700` or `netstat -ano \| findstr 7700` | Change port in profile config or stop conflicting service |
| Model 403/401 | `hermes doctor` | Re-auth via `hermes auth add <provider>` |
| NATS not publishing | `nats sub hermes.gateway.health.v1` | Verify `NATS_URL` in profile `.env`; check NATS leaf connectivity |
| Skills not discovered | `hermes skills list` | `hermes skills config` to enable per-platform; `/reload-skills` in session |
| Windows Alt+Enter newline | Use Ctrl+Enter instead | Documented in Hermes Agent Windows quirks |
| UTF-8 BOM config error | `hermes config edit` | Re-save as UTF-8 without BOM |

## Roadmap to Live Stage

1. **Rehearsal** (current): Single node (5090) gateway; local profile; NATS subjects defined; room manifest in catalog.
2. **Review**: Multi-node soak (Z890, 4090, KVM4-1); CHIT signing wired; gateway health dashboards; security audit.
3. **Live**: Fleet-wide gateway deployment; Discord/Telegram community bridges active; MCP server serving Agent Zero tools; skills hub published.
4. **Archive**: Deprecated only if superseded by next-gen gateway (not anticipated).

## Provider Credential Mapping & Model Routing

> **Rev 4 (2026-07-03, cloud-hybrid inversion):** cloud coding plans are the
> ORCHESTRATOR tier; local models are autonomous WORKER SIBLINGS selected via
> the dynamic model plane (model-registry :8110 / Supabase, CHIT-signed
> candidates, gpu-orchestrator :8200) — never pinned in config. Canonical env
> names: `Z_AI_API_KEY`, `MOONSHOT_API_KEY` (alias KIMI_API_KEY),
> `ALIBABA_PRO_CODING_PLAN` (aliases ALIBABA/DASHSCOPE), `KILOCODE_API_KEY`,
> `OLLAMA_API_KEY`, `HF_TOKEN`. All routing goes through TensorZero functions
> `pmoves_orchestrator_*` / `pmoves_worker_*`. The table below is the original
> Elder-Melchor local-first framing, retained for history.

Elder-Melchor has multiple active subscriptions that feed the provider hierarchy.
All credentials are injected via CHIT secrets funnel (never committed).

| Tier | Provider | Plan | Credential Env Var | Model | Use Case |
|------|----------|------|-------------------|-------|----------|
| 1 | Ollama (local) | Self-hosted | `OLLAMA_BASE_URL` | `hermes3:8b` | Always try first. Q4/CPU offload if GTX 1650 OOM |
| 2 | Z.AI | Coding Plan | `ZAI_API_KEY` | `zai-coding` | Complex code gen, refactoring, agentic coding |
| 2 | Kimi | Allegro Coding Plan | `KIMI_API_KEY` | `kimi-k2.6` | Long-context reasoning, multi-file, Chinese |
| 2 | MiniMax | Token Plan | `MINIMAX_API_KEY` | `minimax-text-01` | Creative writing, dialogue, multi-modal |
| 2 | Alibaba | Coding Plan | `ALIBABA_API_KEY` | `qwen-coder` | Code completion, unit tests, Chinese coding |
| 3 | OpenRouter | Pay-per-use | `OPENROUTER_API_KEY` | `nousresearch/hermes-3` | General fallback, frontier access |
| 4 | Codex CLI | Max Plan | `OPENAI_CODEX_API_KEY` | `codex` | PR automation, GitHub workflow |
| 4 | Claude | Code Max (Copilot ACP) | `GITHUB_TOKEN` | `claude-sonnet-4` | Deep reasoning, security review |
| 5 | HuggingFace | Token | `HUGGINGFACE_TOKEN` | `unsloth/hermes3-8b-GGUF` | **FOLLOW-UP**: local advanced, Unsloth loaders |
| 6 | Spark (remote) | Fleet GPU | none (Tailscale) | `hermes3:70b` | 70B offload when local insufficient |
| 6 | 5090 (remote) | Fleet GPU | none (Tailscale) | `hermes3:8b` | GPU-heavy toolsets: image_gen, video, rl, moa |

### Fallback Chain
```
Ollama local > Z.AI ≈ Kimi ≈ MiniMax ≈ Alibaba > OpenRouter > Codex/Claude (context) > Spark/5090 offload
```

### Pool Rotation
- `ZAI_API_KEYS` (comma-separated) -- round-robin for Z.AI Coding Plan
- `OPENROUTER_API_KEYS` (comma-separated) -- round-robin for OpenRouter

### Docker MCP Toolkit
This instance has Docker Desktop + WSL2 integration:
- `DOCKER_HOST=tcp://localhost:2375`
- Container image: `nikolaik/python-nodejs:python3.11-nodejs20`
- Forwarded env vars: `ZAI_API_KEY`, `KIMI_API_KEY`, `OPENROUTER_API_KEY`
- **Review after PRs**: Add custom MCP servers (n8n, ComfyUI, Hi-RAG gateway, etc.)

### HuggingFace / Unsloth Follow-Up (Post-PR)
- Install `llama.cpp` + Unsloth loaders for GGUF optimization
- Spark node: NeMo Omni 72B via vLLM / TensorRT-LLM
- See research docs: `pmoves/research/RESEARCH_Neotron3_Ultra.md`

## Research Findings (2026-06-04)

### NVIDIA Neotron 3 Ultra (Spark Video: QF50fdpiIOc)
NVIDIA released Neotron 3 Ultra, a **550B parameter MoE model** (55B active) explicitly designed for agentic workloads. Key findings:

| Metric | Value |
|--------|-------|
| Total Parameters | 550 billion |
| Active Parameters | 55 billion |
| Architecture | Mixture of Experts (MoE) |
| Inference Speed | 300+ tokens/sec |
| Pinchbench (agent harness) | Best open-weights model |
| Cost | ~5-10x cheaper than Claude Opus |

**Training Method:** Multi-tier on-policy distillation:
1. Train base model
2. Fork into specialized teachers (code, tool-use, instruction, reasoning)
3. Distill all capabilities into single final model
4. Post-train on agent harness trajectories

**PMOVES Impact:** Neotron 3 Ultra is a **PRIMARY candidate for Spark node**. Its 55B active parameters fit within GB10's 128GB unified memory. NVIDIA is releasing training recipes, datasets, and RL environments openly. This validates PMOVES's multi-tool agent architecture.

See: `pmoves/research/RESEARCH_Neotron3_Ultra.md`

### NousResearch Hermes Agent Deep Dive (Video: pgQDbRMa2Eg)
NousResearch demoed Hermes Agent running inside **OpenShell** -- a policy-based sandboxing layer. Key findings:

**OpenShell Architecture:**
- **Policy-based egress** controls what sandboxes can access (Telegram, Discord, Slack, GitHub)
- **Environment variable masking** -- secrets masked inside sandbox, substituted at egress
- **Multi-user** support (Alice/Bob per-sandbox instances)
- **Onboard scripts** for automated user sandbox creation
- **Strict access controls** prevent unauthorized external access

**Hermes Agent Demo:**
- PR workflow automation: review PRs, cherry-pick commits, merge via rebase
- GitHub API integration with masked tokens
- Skill "salvaging" -- learns workflows and converts them to reusable skills
- Discord/Telegram/Slack platform integrations
- Memory-enabled ("learns workflows as you go")

**Key Quotes:**
> "Hermes is built to cultivate that feeling inside of a user system"
> "Models are going to make harnesses better. This is the beginning of another big loop"
> "We're serving the agent infrastructure layer today"

**PMOVES Impact:** OpenShell concepts should inform PMOVES agent room security:
1. Add `sandbox_policy` to room manifests
2. Implement environment variable masking in CHIT secrets funnel
3. Document multi-user sandboxing patterns
4. Create PR workflow automation skills

See: `pmoves/research/RESEARCH_Hermes_Agent_Deep_Dive.md`

## Atomic Commits & Targeted PRs

All HERMES integration changes follow PMOVES atomic commit rules:

### Commit Format
```
<type>(<scope>): <subject>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`  
Scopes: `hermes-agent`, `hermes-room`, `hermes-profile`, `hermes-skill`, `hermes-tac`, `hermes-registry`, `hermes-docs`, `hermes-research`

### PR Rules
- **One concern per commit** -- never bundle unrelated changes
- **< 400 lines per PR** -- split large changes into stacked PRs
- **Reviewable in < 30 min** -- focused, single-feature
- **CHIT-signed** -- every PR carries CHIT attestation
- **Hardware changes require live scan** -- update `system-specs.json` and `glances.conf`

### Hardware Correction Example (Z890)
**2026-06-04**: Live system scan corrected Z890 specs:
- **Before**: RTX 3090 Ti 24GB, Windows 11 Pro, 20C/32GB
- **Actual**: GTX 1650 4GB, Windows 10, 6C/12T @ 2.59GHz, 31.73GB RAM
- **Commit**: `fix(hermes-profile): correct Z890 GPU from RTX 3090 Ti to GTX 1650`
- **Files updated**: `z890.yaml`, `z890-glances.conf`, `elder-melchor-system-specs.json`, `HERMES_AGENT_INTEGRATION.md`

See full guide: `pmoves/docs/AGENTS/HERMES_ATOMIC_COMMITS.md`

## System Monitoring (Glances)

Each node runs Glances for real-time telemetry:

### Z890 (Elder-Melchor)
```bash
# Config location
pmoves/config/profiles/hermes/z890-glances.conf

# Start web UI
hermes --profile pmoves-hermes terminal   "glances -C pmoves/config/profiles/hermes/z890-glances.conf --webserver"

# Export JSON for NATS telemetry
glances --export json --time 60 --quiet
```

**Monitored metrics:**
- CPU: 6 physical / 12 logical cores
- RAM: 31.73 GB (alert at 50%/70%/90%)
- GPU: GTX 1650 4GB (alert at 50%/75%/90% VRAM)
- Disks: C:\ (NTFS), G:\ (FAT32)
- Network: Wi-Fi (<LOCAL_IP_ELDER_MELCHOR>), Tailscale (<TAILSCALE_IP_ELDER_MELCHOR>), WSL bridge

**Glances config features:**
- All network interfaces visible (including virtual)
- GPU monitoring via nvidia-smi
- JSON/CSV export to `pmoves/telemetry/`
- Alert thresholds tuned to actual hardware

## v0.18.2 Config Alignment (2026-07-12)

### Audit Summary

Live audit of Hermes Agent v0.18.2 on Elder-Melchor found the `pmoves-hermes-elder`
profile config used pre-v0.18 custom keys (`fallback_chain`, `provider_hierarchy`,
`ollama.models`) that Hermes does not parse. The profile .env had placeholder
values (`YOUR_ZAI_KEY_HERE`) instead of real API keys. Config version was v0
(latest: v33). No fallback providers were configured on the default profile.

### Changes Applied

| Item | Before | After |
|------|--------|-------|
| Active profile | `default` (kimi-k2.7-code) | `pmoves-hermes-elder` (zai-coding) |
| Config version | v0 | v33 (migrated via `hermes config migrate`) |
| `fallback_providers` | `[]` (empty) | 4-tier cascade: kimi → minimax-oauth → openrouter → ollama-cloud |
| `credential_pool_strategies` | `alibaba: fill_first` | zai, kimi-coding (fill_first), openrouter (round_robin), alibaba |
| Profile .env keys | Placeholders | Real GLM_API_KEY, KIMI_API_KEY, DEEPSEEK_API_KEY, OLLAMA_API_KEY |
| `privacy.redact_pii` | false | true (HIPAA-aware — PII redaction for patient data) |
| `hermes doctor` | 3 issues | All checks passed (reported status — see `hermes doctor` output) |

### Default Profile Fallback Chain

```text
Primary:   glm-5.2 (via ollama-cloud)
Fallbacks: zai-coding → kimi-k2.7-code → minimax-text-01 → nousresearch/hermes-3 → hermes3:8b
```

### pmoves-hermes-elder Profile Fallback Chain

```text
Primary:   zai-coding (via zai)
Fallbacks: kimi-k2.7-code → minimax-text-01 → nousresearch/hermes-3 → hermes3:8b
```

### Key Env Var Mapping

PMOVES .env uses `ZAI_API_KEY`; Hermes v0.18.2 expects `GLM_API_KEY` for the Z.AI
provider. Both are now set in the profile .env with the same value.

| PMOVES Name | Hermes v0.18.2 Name | Provider |
|-------------|---------------------|----------|
| `ZAI_API_KEY` | `GLM_API_KEY` | zai |
| `KIMI_API_KEY` | `KIMI_API_KEY` | kimi-coding |
| `MINIMAX_API_KEY` | `MINIMAX_API_KEY` | minimax (API key) |
| — | `minimax-oauth` (browser OAuth) | minimax-oauth (separate provider) |
| `OPENROUTER_API_KEY` | `OPENROUTER_API_KEY` | openrouter |
| — | `OLLAMA_API_KEY` | ollama-cloud |

### Upstream PRs Reviewed

| PR | Title | PMOVES Relevance |
|----|-------|-----------------|
| #20893 | `refactor(gateway): run auth checks before processing hooks` | Security — prevents info leak to unauthorized gateway users. Important for patient-facing Discord/Telegram. |
| #20920 | `fix(cross-platform): honor HERMES_HOME in file_safety and code_execution_tool` | Profile safety — fixes cross-profile data corruption when using non-default profiles. Directly relevant to `pmoves-hermes-elder`. |
| #20876 | `feat(context-files): add @<path> include expansion` | Context includes — enables SSoT pattern (`@~/.agents/AGENTS.md`) in context files. Useful for PMOVES AGNOTE4482_SITREP reference pattern. |
| #63168 | `fix(cron): handle repeat field as plain int (v0.18+ format)` | Cron fix — relevant for PMOVES appointment reminders, backup schedules. |
| #62871 | `perf(memory): run post-turn memory retain off the reply path` | Memory perf — speeds up turns on practice workstation. |

### Kilo Gateway / Kilocode Integration

Kilo Gateway (`api.kilo.ai/api/gateway`) is now a **built-in Hermes provider** (`kilocode`
with `KILOCODE_API_KEY`). Confirmed via [Kilo blog](https://blog.kilo.ai/p/how-to-use-kilo-gateway-with-hermes)
and Hermes v0.18.2 fallback-providers docs.

**PMOVES Impact:**
- PMOVES-crush integration can use Kilo as a provider/fallback without custom code
- `hermes model` → Kilo Code picker; or add as fallback: `{provider: kilocode, model: auto-balanced}`
- Kilo recommends 64K+ context window for reliable agentic performance — PMOVES
  uses each provider's native context window which can differ across the cascade
- No `KILOCODE_API_KEY` configured yet on Elder-Melchor — add when Kilo subscription activated

**Kilo vs Hermes Gateway Clarification:**
- **Kilo Gateway**: unified API endpoint for model inference (the "brain")
- **Hermes Messaging Gateway**: communication hub for Discord/Telegram/Slack (the "mouth")
- PMOVES uses both: Kilo for compute, Hermes gateway for patient/staff comms

## Canonical References

- Hermes Agent docs: https://hermes-agent.nousresearch.com/docs/
- Hermes Agent repo: https://github.com/NousResearch/hermes-agent
- Fallback Providers docs: https://hermes-agent.nousresearch.com/docs/user-guide/features/fallback-providers
- Kilo Gateway + Hermes: https://blog.kilo.ai/p/how-to-use-kilo-gateway-with-hermes
- PMOVES AGNOTE4482: `pmoves/docs/AGENTS/AGNOTE4482.md`
- PMOVES SITREP: `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md`
- PMOVES Room Manifest Contract: `pmoves/docs/ROOM_MANIFEST_CONTRACT.md`
- PMOVES Rooms on a Stage: `pmoves/docs/ROOMS_ON_A_STAGE.md`
- PMOVES Agent Topology: `pmoves/docs/AGENTS/PMOVES_AGENT_TOPOLOGY.md`
- Neotron 3 Ultra Research: `pmoves/research/RESEARCH_Neotron3_Ultra.md`
- Hermes Agent Deep Dive Research: `pmoves/research/RESEARCH_Hermes_Agent_Deep_Dive.md`
