# SPARK Autonomous Agent Showcase — Design Spec

**Status:** DRAFT — vision captured from DARKXSIDE 2026-08-04
**Date:** 2026-08-04
**Author:** Crush-GLM52 (SPARK)
**Scope:** Autonomous multi-agent showcase on SPARK + fleet (Jetsons + Z890), with scheduled wake/sleep cycles, Danger Room Desktop visible execution, WebRTC streaming, and Pinokio-powered creative tools

---

## 1. Vision

SPARK becomes a **living AI showcase** — not a 24/7 grind, but an autonomous system that wakes, works, creates, and dreams. Agents run in visible sandboxes (Danger Room Desktop), their work streams to remote viewers via WebRTC, and the fleet (SPARK + Jetsons + Z890) extends capabilities beyond one box. Pinokio provides the creative app ecosystem (ComfyUI, TTS, FLUX, ACE-Step, etc.). n8n orchestrates the autonomous schedule. Archon handles PR review via BoTZ/Gateway. Agent Zero orchestrates everything.

**Key principle:** "Autonomous doesn't mean 24/7 — models need to dream too."
The system has active cycles (work, create) and rest cycles (dream, consolidate, index).

---

## 2. What Exists (the zootopia)

### Serving tier (all live)
| Engine | Port | Models |
|---|---|---|
| Ollama | :11434 | 12 models (Qwen3.5-35B, Nemotron-120B, Kimi-K2.6, Qwen3-Coder-30B, etc.) |
| llama.cpp | :8130 | Qwen3-30B GGUF, ARM64+CUDA native build |
| NIM | :8132 | Llama-3.1-8B (DGX-Spark container) |
| TensorZero | :3030 | Routes to all engines + cloud fallback |

### Agent tier (all live)
| Agent | Role | Status |
|---|---|---|
| Agent Zero v2.8 | Orchestrator + DARKXSIDE identity | ✅ Healthy, A2A enabled, MCP working |
| Archon 0.6.0 | Remote coding + PR review + workflow orchestration | ✅ Healthy, bundled workflows |
| HF Agent | Model discovery (171 models seen) | ✅ Polling every 300s |
| HF Research Agent | Model scoring + candidate registration | ✅ Scoring, LFM2-2.6B passed |
| Gateway Agent | Fleet NATS coordination | ✅ Healthy |

### Infrastructure tier
| Component | Status |
|---|---|
| NATS (6 streams) | ✅ JetStream live |
| Cipher Memory (hybrid BM25+dense+RRF) | ✅ Healthy |
| Hi-RAG v2 (Meilisearch + Qdrant) | ✅ 283+146 docs indexed |
| Model Registry | ✅ Live (Supabase-backed) |
| Model Fitness Bridge (G1) | ✅ Code merged (PR #2391) |
| Flute Gateway | ✅ Healthy (:8055) |
| Channel Monitor | ✅ Watching 10 YT channels |
| Supabase (13 services) | ✅ Healthy |
| n8n | ✅ Running (12 days uptime) |

### E2B Danger Room (self-hosted)
| Component | Status |
|---|---|
| PMOVES-E2B-Danger-Room | ✅ Submodule, Go codegen, SDK packages |
| PMOVES-E2B-Danger-Room-Desktop | ✅ Submodule, Python+JS SDK, sandbox examples |
| PMOVES-Danger-infra | ✅ Submodule, IaC (Terraform/Pulumi) |
| PMOVES-E2b-Spells | ✅ Submodule, CHIT integration, docker-compose |
| `make danger-room-desktop-up` | ✅ Make target exists |

### Pinokio creative apps (installed on SPARK)
| App | Purpose |
|---|---|
| ComfyUI Desktop | Image generation (FLUX, Stable Diffusion) |
| Ultimate-TTS-Studio | 14-engine TTS |
| ACE-Step | Music generation |
| Wan | Video generation |
| VoiceBox | Voice cloning |
| VibeVoice Realtime | Real-time TTS |
| LightOnOCR | OCR |
| Unsloth | Model fine-tuning |
| Customokio | Custom app scaffolding (gepeto) |
| SillyTavern | Character AI chat |
| Alexandria Audiobook | Audiobook generation |
| Directors Console | Content direction |

### Pinokio skills
- `gepeto` — scaffolds new Pinokio apps from prompts
- `pinokio` — native CLI

---

## 3. Architecture — The Wake/Dream Cycle

```
┌─────────────────────────────────────────────────────┐
│                  AUTONOMOUS SCHEDULER               │
│                     (n8n + cron)                     │
│                                                      │
│  06:00 ── WAKE ──→ Active Cycle                     │
│    │  • Agent Zero: review tasks, prioritize         │
│    │  • HF Agent: discover new models                │
│    │  • Archon: review open PRs                      │
│    │  • Danger Room: run coding/art tasks            │
│    │  • Fleet: delegate to Jetsons/Z890              │
│    │                                                 │
│  18:00 ── DREAM ──→ Rest Cycle                      │
│    │  • Cipher: consolidate memories                 │
│    │  • Hi-RAG: re-index new content                 │
│    │  • TensorZero: offline optimization             │
│    │  • Agents: checkpoint state                     │
│    │  • Display: show fleet topology + stats         │
│    │                                                 │
│  00:00 ── DEEP DREAM ──→ Consolidation              │
│       • Unsloth: fine-tune on day's trajectories     │
│       • AgentGym: RL training burst                  │
│       • Model Fitness: score + reweight              │
│       • NATS: archive day's events                   │
└─────────────────────────────────────────────────────┘
```

### n8n autonomous flows

| Flow | Schedule | What |
|---|---|---|
| `wake-up` | 06:00 | Publish `autonomous.wake.v1` → Agent Zero picks up task queue |
| `model-watch` | Every 30min (active) / off (dream) | HF Agent polls for new models |
| `pr-review-sweep` | Every 2hr (active) | Archon checks open PRs, triggers smart-review |
| `danger-room-task` | On-demand + scheduled | Agent Zero dispatches visible coding task |
| `art-generation` | 3x/day (active) | ComfyUI generates showcase art |
| `dream-consolidate` | 22:00 | Cipher consolidates day's memories into reasoning patterns |
| `deep-dream-train` | 01:00 (if GPU free) | Unsloth fine-tunes on day's best trajectories |
| `fleet-health-broadcast` | Every 5min | Gateway Agent broadcasts fleet status |

---

## 4. Danger Room Desktop — Visible Execution

### Architecture
```
Agent Zero task → Danger Room Desktop sandbox
  ├── Visible VNC/noVNC desktop (browser + terminal + editor)
  ├── Agent operates in the sandbox (computer use, coding, art)
  ├── Screen captured → WebRTC stream → remote viewers
  └── NATS publishes: danger.room.task.started.v1 / .completed.v1
```

### Implementation path
1. **E2B Danger Room Desktop** — self-hosted sandbox with visible desktop
   - SDK exists (`PMOVES-E2B-Danger-Room-Desktop/packages/python-sdk/e2b_desktop/main.py`)
   - `make danger-room-desktop-up` target exists
   - Needs: E2B infra stack deployed (Danger-infra has Terraform/Pulumi)

2. **noVNC frontend** — web-accessible desktop viewer
   - Mount in A2UI room panel (`kind: browser`)
   - Each agent session gets a unique VNC port

3. **WebRTC streaming** — broadcast the VNC desktop to multiple viewers
   - Options: mediasoup (SFU), janus-gateway, or simple WebRTC P2P
   - For small fleet (5-10 viewers): P2P is sufficient
   - For public showcase: SFU scales

---

## 5. Multi-Window Display

### Physical setup
SPARK node + 2 Jetsons + Z890 on a desk. Display shows:
```
┌──────────────────┬───────────────────┐
│ Agent Zero       │ Archon PR Review  │
│ (chat/orchestration)│ (BoTZ routing)  │
├──────────────────┼───────────────────┤
│ Danger Room      │ ComfyUI Live      │
│ (agent coding)   │ (art generation)  │
├──────────────────┼───────────────────┤
│ HF Agent Feed    │ Fleet Topology    │
│ (model watch)    │ (SPARK+Jetson+Z890)│
└──────────────────┴───────────────────┘
```

### Implementation
- A2UI room panels already support `kind: browser` + position/size layout
- Each panel is an iframe loading the agent's web UI
- The room manifest declares the panel layout
- P7 stage manager handles room transitions (rehearsal → live for showcase)

---

## 6. Archon → BoTZ PR Review Pipeline

```
cron triggers → Archon smart-pr-review workflow
  → scopes PR → classifies complexity
  → routes to review agents (code, error handling, test coverage)
  → BoTZ Gateway routes to fleet nodes for parallel review
  → synthesize → auto-fix CRITICAL/HIGH → post review
  → NATS: archon.review.completed.v1
```

Archon already has bundled `archon-smart-pr-review` workflow. The BoTZ Gateway (`pmoves-gateway-agent-1`) is running. Connection: Archon's workflow nodes call BoTZ via MCP or HTTP.

---

## 7. HF Agent Model Discovery for Local Models

The HF Agent polls all new models. Add a filter for GB10/ARM64 compatibility:
- `sm_121a` / `sm_120` (Blackwell consumer)
- `aarch64` / `arm64`
- Model size < 80GB (fits 128GB unified memory with room for context)
- Format: GGUF or HF safetensors

Filter triggers:
- `hf.model.evaluated.v1` → research agent scores model
- If score > 70 + compatible tags → auto-register as candidate (G4, already wired)
- model-registry → model-fitness-bridge → TensorZero weight assignment
- Optional: `ollama pull` on SPARK if model is small enough

---

## 8. Implementation Lanes

| Lane | What | Priority | Dependencies |
|---|---|---|---|
| **L1** | Deploy E2B Danger Room Desktop on SPARK | P0 | Danger-infra stack |
| **L2** | n8n autonomous wake/dream schedule | P0 | n8n running ✅ |
| **L3** | HF Agent local-model filter (GB10/ARM64) | P1 | HF Agent running ✅ |
| **L4** | Multi-window A2UI showcase room | P1 | A2UI on main ✅ |
| **L5** | WebRTC streaming from Danger Room | P1 | L1 |
| **L6** | Archon → BoTZ PR review pipeline | P2 | Both running ✅ |
| **L7** | Unsloth dream-cycle fine-tuning | P2 | Unsloth in Pinokio ✅ |
| **L8** | Fleet topology dashboard | P3 | Grafana running ✅ |

---

## 9. Autonomous Principles

1. **Wake/Dream rhythm** — not 24/7. Active cycle ~06:00-22:00, dream cycle 22:00-06:00.
2. **Pinokio is the creative engine** — ComfyUI, TTS, FLUX, ACE-Step all run via Pinokio natively.
3. **Danger Room is the visible stage** — agents work in sandboxes that viewers can watch.
4. **n8n is the conductor** — cron-triggered flows orchestrate the autonomous schedule.
5. **Fleet extends capacity** — Jetsons handle edge inference, Z890 handles coding/builds, SPARK handles orchestration + heavy models.
6. **Dreaming is productive** — rest cycles do consolidation, re-indexing, fine-tuning, offline optimization. Not idle.
7. **Every action has provenance** — CHIT-signed trails on NATS, Cipher memory consolidation.
8. **Models rotate** — HF Agent discovers, fitness bridge scores, TensorZero reweights. Stale models get unloaded.

---

## Cross-References

- E2B Danger Room: `PMOVES-E2B-Danger-Room/`, `PMOVES-E2B-Danger-Room-Desktop/`
- Danger Infra: `PMOVES-Danger-infra/` (Terraform/Pulumi)
- Pinokio apps: `~/pinokio/api/` (ComfyUI, TTS-Studio, ACE-Step, Wan, etc.)
- Pinokio curated: `pmoves/configs/pinokio-apps/curated/` (12 apps registered)
- n8n flows: `pmoves/n8n/flows/` + DARKXSIDE playlist ingestion
- Model lifecycle spec: `pmoves/docs/specs/model-lifecycle-pipeline-2026-07-30.md`
- A2UI components: `pmoves/web-components/` (10 components)
- Room manifests: `pmoves/config/rooms/` (12 rooms)
- Evolution Fabric: `pmoves/docs/architecture/EVOLUTION_FABRIC_RFC.md`
