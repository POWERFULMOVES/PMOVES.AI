# Jetson Combiner Fleet — Crush Bootstrap + SPARK Pairing Plan

> **GRAPHITI_MARK:** CRUSH-GLM52::JETSON-SPARK-COMBINER-PLAN::2026-07-30
> **From:** ◇ Crush (Z890, GLM-5.2)
> **Status:** PLAN — operator review before execution

## Vision

Three Jetson Orin Nano Super (JONS) nodes act as **local combiner agents** — edge inference
leaves that pair with SPARK (GB10 128GB) in a distributed pipeline for image generation,
voice, and multimodal processing. The Jetsons handle the edge layer (STT, lightweight LLM,
image preprocessing, object detection); SPARK handles the heavy layer (70B inference,
ComfyUI image gen, full TTS engines). NATS is the bus that binds them.

## Hardware Inventory

| Node | Board | Unified Mem | GPU | TOPS | Tailscale Host | Role |
|------|-------|-------------|-----|------|----------------|------|
| SPARK | GB10 Grace-Blackwell | 128 GB | SM_110 | ~900 | pmoves-gb10-spark | Heavy inference / ComfyUI / 70B |
| JONS-1 | Orin Nano Super | 8 GB | SM_87 | 67 | pmoves-jons-1 | Edge STT + image preprocess |
| JONS-2 | Orin Nano Super | 8 GB | SM_87 | 67 | pmoves-jons-2 | Edge LLM + object detection |
| JONS-3 | Orin Nano Super | 8 GB | SM_87 | 67 | pmoves-jons-3 | Edge voice + relay |

All four nodes are ARM64 + NVIDIA unified memory. NATS leaf-node topology connects them.

## Combiner Configurations

### Config A: Voice Pipeline (STT → LLM → TTS)
```
[Audio] → JONS-1 (Whisper small-int8) → NATS → SPARK (70B LLM) → NATS → SPARK (TTS) → [Output]
```
- JONS-1: real-time speech-to-text via Faster-Whisper INT8 on Orin GPU
- SPARK: LLM processing (qwen3.5:35b or hermes3:70b) + voice synthesis
- NATS subjects: `voice.stt.partial.v1`, `voice.llm.response.v1`, `voice.tts.complete.v1`

### Config B: Image Generation (Edge Prompt → ComfyUI)
```
[Prompt] → JONS-2 (phi3-mini prompt expansion) → NATS → SPARK (ComfyUI :8188) → [Image]
                                                          ↘ JONS-1 (YOLOv8 post-analysis)
```
- JONS-2: lightweight prompt enhancement/expansion via phi3-mini
- SPARK: full ComfyUI SDXL/FLUX pipeline on GB10 (128GB unified = no VRAM ceiling)
- JONS-1: optional post-generation object detection / safety check via YOLOv8n-TensorRT
- NATS subjects: `image.prompt.expanded.v1`, `image.gen.complete.v1`, `image.analysis.v1`

### Config C: Parallel Transcription (3x Whisper)
```
[Audio Stream 1] → JONS-1 (Whisper) ─┐
[Audio Stream 2] → JONS-2 (Whisper) ─┤→ NATS merge → SPARK (summarization) → [Output]
[Audio Stream 3] → JONS-3 (Whisper) ─┘
```
- All 3 Jetsons run Whisper simultaneously for 3x throughput
- SPARK merges transcripts and summarizes via 70B model
- NATS subjects: `voice.stt.parallel.v1`, `voice.stt.merged.v1`

### Config D: Island Mode (SPARK offline)
```
[Input] → JONS-1/2/3 (phi3-mini round-robin via NATS) → [Output]
```
- When SPARK is offline, Jetsons fall back to phi3-mini (3.8B) in round-robin
- Reduced capability but functional — mesh-agent detects SPARK absence via heartbeat timeout
- NATS subjects: `mesh.node.absent.v1`, `edge.fallback.active.v1`

### Config E: Creator Relay (ComfyUI remote control)
```
[4090/Z890] → NATS → JONS-3 (relay + queue) → SPARK (ComfyUI :8188) → JONS-2 (post-process)
```
- JONS-3 acts as NATS relay/queue manager for image gen requests from workstation nodes
- SPARK executes ComfyUI workflows (heavy GPU)
- JONS-2 handles lightweight post-processing (resize, format, watermark via TensorRT)
- NATS subjects: `image.gen.request.v1`, `image.gen.result.v1`

## Crush Bootstrap: Jetson Nodes

### Prerequisites (per Jetson)

| Requirement | Command | Notes |
|-------------|---------|-------|
| JetPack 6.2+ | `cat /etc/nv_tegra_release` | L4T 36.4.x required |
| Docker + NVIDIA runtime | `docker info \| grep nvidia` | `jetson-postinstall.sh --mode full` |
| Tailscale online | `tailscale status` | Each JONS registered with tag:edge |
| NATS leaf node | `docker compose up -d nats-leaf` | Upstream to `ts:powerfulmoves:4222` |
| Ollama running | `curl localhost:11434/api/tags` | phi3-mini pulled |
| Python 3.10+ | `python3 --version` | System Python on JetPack |
| Crush binary (ARM64) | `go build` or release | Go binary, cross-compile for arm64 |

### Bootstrap Sequence (per JONS, from the node itself)

```bash
# 1. Clone repo
cd /opt/pmoves  # or ~/PMOVES.AI
git pull origin main

# 2. Secrets funnel (CHIT passphrase + API keys)
make -C pmoves secrets-funnel

# 3. Crush bootstrap (now with hostname fix — no CRUSH_NODE override needed)
make -C pmoves crush-bootstrap

# 4. Verify
crush -v
make -C pmoves sign-trail AGENT=crush-jons-1 SUMMARY="JONS-1 awakening" PHASE="session" --no-log
```

The hostname fix (`_hostname_short()` function) resolves `pmoves-jons-1` from the Tailscale
hostname automatically — no `CRUSH_NODE` env override needed on Linux/Jetson.

### Crush Config Per JONS

Each JONS gets a tailored crush.json:
- **Provider:** Z.AI GLM-5.2 (coding plan, shared fleet key)
- **MCP servers:**
  - `agent-zero`: SPARK's Agent Zero at `http://pmoves-gb10-spark:8080/mcp` (Tailscale)
  - `ollama-local`: `http://localhost:11434` (phi3-mini on-device)
  - `pmoves-nats-fleet`: stdio bridge to NATS bus
  - `comfyui-spark`: `http://pmoves-gb10-spark:8188` (remote ComfyUI)
- **Context paths:** `CRUSH.md`, `AGENT_TRAIL.md`, this plan doc, `secrets_manifest.yaml`
- **LSP:** pyright + typescript-language-server (gopls optional on ARM64)
- **Permissions:** `bash`, `ls`, `view`, `edit` (JONS agents can edit — they're delivery body)

## What's Missing (Gaps to Close)

### 1. Room Manifests (NONE exist for Jetsons)
The room catalog has 9 rooms, zero for Jetsons. Need:
- `jons-edge.room.control` — edge inference room manifest
- `jetson-spark.room.studio` — combiner room (Jetson + SPARK paired)

### 2. Agent Signatures (Phase 4 enrollment = status: future)
No Jetson entries in `agent_signatures.yaml`. Need:
- `jetson-1`, `jetson-2`, `jetson-3` with Nemotron/NemoClaw theme per TAC tree Phase 4

### 3. ComfyUI ARM64 Image
Current ComfyUI image (`ghcr.io/powerfulmoves/pmoves-comfyui:pmoves-latest`) targets x86_64
+ NVIDIA CUDA. Jetsons can't run full ComfyUI (8GB unified), but they need lightweight
image processing. Options:
- a) Don't run ComfyUI on Jetsons — SPARK only, Jetsons relay/preprocess (recommended)
- b) Build ARM64 ComfyUI-lite with TensorRT backend (heavy lift, low ROI for 8GB)

### 4. NATS Leaf-Node Compose
The TAC tree references `docker-compose.jetson-edge.override.yml` but it needs:
- NATS leaf-node stanza with upstream URL from secrets
- mesh-agent announcement with combiner role metadata

### 5. Hermes Profile for Jetsons
HERMES_AGENT_INTEGRATION.md has 6 node profiles, zero for Jetsons. Need a 7th:
- Profile: `jetson-edge`
- Gateway port: 7700 (standard)
- Ollama: localhost:11434 with phi3-mini
- Fallback: pmoves-gb10-spark:11434 for larger models
- Disabled: image_gen/video/rl/moa (SPARK handles those)

## Execution Order

1. **Hostname fix** (DONE — this session, `crush-fleet-bootstrap.sh:26-34`)
2. **PR the fix** — commit to current branch or dedicated `fix/crush-bootstrap-hostname`
3. **Jetson room manifests** — create `jons-edge.room.control` + `jetson-spark.room.studio`
4. **Agent signatures** — enroll 3 JONS agents in `agent_signatures.yaml`
5. **Hermes Jetson profile** — 7th node profile in HERMES_AGENT_INTEGRATION.md
6. **NATS leaf-node compose** — `docker-compose.jetson-edge.override.yml` with leaf stanza
7. **On-device bootstrap** — SSH into each JONS, run `crush-bootstrap`, verify trail signing
8. **SPARK pairing test** — verify NATS round-trip: JONS whisper → SPARK LLM → output
9. **Combiner configs A-E** — validate each pipeline end-to-end

## NATS Subject Catalog (Combiner Extensions)

New subjects needed for combiner patterns:

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `voice.stt.edge.v1` | JONS → mesh | Edge Whisper transcription result |
| `voice.stt.parallel.v1` | 3× JONS → merge | Parallel transcription fan-in |
| `image.prompt.expanded.v1` | JONS → SPARK | Prompt enhancement from edge LLM |
| `image.gen.request.v1` | Workstation → JONS → SPARK | ComfyUI job queue via edge relay |
| `image.gen.result.v1` | SPARK → JONS → mesh | Image gen result notification |
| `image.analysis.v1` | JONS → mesh | YOLOv8 post-gen safety check |
| `edge.fallback.active.v1` | JONS → mesh | Island mode announcement |
| `mesh.combiner.heartbeat.v1` | JONS ↔ SPARK | Combiner health heartbeat |
