# PR Draft: DARKXSIDES Research Integration + Hermes + LTX-Desktop + Pinokio Launchers

**Branch**: `feat/darkxside-hermes-ltx-pinokio-integration` → `main`
**Date**: 2026-05-18
**Scope**: Research synthesis, tool integration planning, workflow consolidation, launcher development
**Status**: DRAFT — awaiting DARKXSIDES paper synthesis (Researcher B) and playlist video analysis (Researcher C)

> **⚠️ UPDATED 2026-05-19**: Previous "Blocking Issue" (SPARK/DARKXSIDE compose files missing from repo) is **RESOLVED**. PR [#1533](https://github.com/POWERFULMOVES/PMOVES.AI/pull/1533) (merged 2026-05-18) added `docker-compose.{darkxside,spark}-sidecar.yml`. PR [#1538](https://github.com/POWERFULMOVES/PMOVES.AI/pull/1538) (open) adds `make up-darkxside-sidecar` / `make up-spark-sidecar` targets. CREATORFILES inventory corrected against live host listing.

---

## Summary

- **Character Creation Pipeline (SPARK Core Mission)**: Map PMOVES agent taxonomy → character designs → consistent art sets (Anima Base + ERNIE) → voice identities (CONCH → Flute → MiniMax TTS) → lip-sync video (LTX 2.3) → "Agent Trails" animated series
- **CONCH → Flute Bridge**: Close the core gap between CONCH persona wire format (`chit.cgp.v1.0`) and Flute's POML prompt generator to complete voice clone persona creator
- **LTX 2.3 Ultra Integration**: 22B model with 5 workflow modes (txt2vid, img2vid, first/middle/last frame, video extender, upscaler) as rendering backbone for character animation
- **Hermes Agent v0.14.0 Integration Plan**: Local proxy for shared subscriptions, Supergrok for X research, handoff system, DeepSeek v4 flash free tier
- **Video Intelligence Extraction**: 20+ repos from 7+ YouTube videos categorized by PMOVES relevance (Pixel3D, FiMotion, Cinema Audio, Drama Box, Articraft, etc.)
- **CREATORFILES Consolidation**: Move 5 missing files, deduplicate 6 pairs, populate PMOVES-LTX-Desktop repo
- **Pinokio/Gepeto/pterm Skill Gap**: Zero functional skills; 7 launchers planned (LTX-Desktop P0, Anima P1, Mickmumpitz P1, etc.)
- **DARKXSIDES**: HANDED OFF — DARKXSIDE sidecar owns paper synthesis; SPARK role is "bring it to light"

## Testing

```bash
# Verify research files exist on remote host
ls -la /home/powerfulmoves/Downloads/T*_*.md /home/powerfulmoves/Downloads/DEEP_*.md /home/powerfulmoves/Downloads/YOUTUBE_*.md

# Verify CREATORFILES current state
ls -la /home/powerfulmoves/agent-zero/CREATORFILES/*.json /home/powerfulmoves/agent-zero/CREATORFILES/*.7z

# Verify Downloads files not yet in CREATORFILES
ls -la /home/powerfulmoves/Downloads/260507_MICKMUMPITZ_MOVIE-BUILDER_1-1_ADV.json
ls -la /home/powerfulmoves/Downloads/260504_MICKMUMPITZ_MOVIE-BUILDER_1-0_SMPL.json
ls -la /home/powerfulmoves/Downloads/260504_MICKMUMPITZ_MOVIE-BUILDER_1-0_ADV.json
ls -la /home/powerfulmoves/Downloads/LTX-2-3-*.bat

# Verify existing Pinokio launcher
ls -la /home/powerfulmoves/agent-zero/PMOVES-Pinokio-Ultimate-TTS-Studio/ 2>/dev/null || echo 'TTS Studio not found at expected path'
```

### Required Checks
- [ ] `CHIT Contract Check` (CI will block the merge until this passes)
- [ ] Updated contracts, schemas, or topics if this change affects published events
- [ ] Added/updated documentation when altering behavior or workflows

### Review Coordination
- [ ] Requested Codex review (attach CLI transcript or note coverage in "Reviewer Notes")
- [ ] Requested GitHub Copilot review (use the PR "Copilot" button or `/copilot review` comment)

---

## Section 1: Video Intelligence Extraction

### 1.1 Open-Source Repos by PMOVES Relevance

#### HIGH Relevance (Direct Integration)

| Tool | Source Video | What It Does | Repo/Link | Size/VRAM | Integration Path |
|------|-------------|--------------|-----------|-----------|-----------------|
| **LTX 2.3** (Just Dub It base) | Weekly AI | Video generation with audio, lip-sync dubbing | GitHub: Lightricks/LTX-Video | 2.5GB dub model | PMOVES-LTX-Desktop core engine, Pinokio launcher P0 |
| **Pixel3D** | Weekly AI | Image-to-3D, pixel-aligned, beats Hunyuan3D | GitHub: (search Pixel3D) | 24GB total models | 3D asset pipeline for Creator workflows |
| **Asymmetric Flow Models** | Weekly AI | Image gen in pixel space (no VAE), 40% faster | GitHub: (search Asymmetric Flow) | Comparable to latent models | Evaluate for PMOVES image generation stack |
| **FiMotion** | Weekly AI | Physics-based video reward via MuJoCo | GitHub: (search FiMotion) | Lightweight reward model | Quality gate for video generation pipeline |
| **Cinema Audio** | Weekly AI | Expressive TTS from LTX 2.3 audio model | GitHub: (search Cinema Audio) | 16GB VRAM quantized | Replace/augment current TTS stack |
| **Drama Box** (Resemble AI) | Weekly AI | Expressive TTS from LTX 2.3, phonetic vocalizations | GitHub: ResembleAI/dramabox | 24GB peak VRAM | Alternative TTS with emotion control |
| **Articraft** | Weekly AI | Articulated 3D assets via coding agent | GitHub: (search Articraft) | Agent-agnostic | Robotic simulation + 3D asset generation |
| **Anima Base v1.0** | Anima Base | 2B anime AI, 6GB VRAM training | Citron/Anima repo | 2B params | CREATORFILES already has workflow, need Pinokio launcher |
| **TrackCrafter** | Weekly AI | 3D pixel tracking via video diffusion | GitHub: (search TrackCrafter) | Efficient | Video analysis pipeline for Creator |
| **MoCam** | Weekly AI | Camera movement change in video | Coming soon | TBD | Video post-production pipeline |

#### MEDIUM Relevance (Complementary)

| Tool | Source Video | What It Does | Integration Path |
|------|-------------|--------------|-----------------|
| **Hermes Agent v0.14.0** | Hermes | Persistent autonomous agent, MIT license | P7/Mesh/CLI integration (see Section 2) |
| **Warp as History** | Weekly AI | Interactive world generator | Evaluate for immersive content creation |
| **DreamX World** | Weekly AI | Interactive world generator (5B model) | Same as above, compare with Warp |
| **ReitLive** | Weekly AI | Video relighting, 24GB VRAM | Post-production pipeline |
| **CausalScene** | Weekly AI | Real-time multi-shot video generation | Paper only — monitor for code release |
| **Open-source music generator** | Weekly AI | Full songs from prompt+lyrics, 24GB | Audio pipeline, compare with current music tools |
| **MiniCPMv4.6** | Weekly AI | 2.6GB VLM for phones | Edge/mobile agent deployment research |
| **Qwen 3.7 Max Preview** | Qwen 3.7 | #13 Arena, strong coding + multilingual | Evaluate when open weights release |

#### LOW Relevance (Interesting But Not Priority)

| Tool | Source Video | Notes |
|------|-------------|-------|
| NVIDIA Sonnet WM | Weekly AI | 2.8B world model, not yet open source |
| Thinking Machines Interaction Models | Weekly AI | Not yet available |
| Korea 2 | Weekly AI | Closed source |
| Codex Mobile | Weekly AI | macOS only currently |
| Zy Nova Flex 2 | Weekly AI | Hardware, not software |
| Uni GD01 Mecha | Weekly AI | Hardware, $650K |
| Google DeepMind AI Cursor | Weekly AI | Chrome integration, not agent framework |

### 1.2 Key Video Insights for PMOVES

**Qwen 3.7 Max Preview**:
- Single-shot full web app generation (cron monitor with Telegram, systemd, live logs) — validates agent coding capability benchmark
- 75+ language native script accuracy — relevant for DARKXSIDES multilingual content
- When open weights release, evaluate as alternative to GLM-5-turbo for researcher profile

**Anima Base v1.0**:
- In-painting ControlNet now available — enhances CREATORFILES workflow capability
- LoRA training in 11 minutes on 6GB VRAM — feasible for SPARK sidecar (no GPU currently)
- `network_dim=32, network_alpha=32` for base model LoRAs (up from 20 for preview)
- CREATORFILES gap: v1-0 SMPL/ADV and v1-1 ADV Movie-Builder workflows not yet added

**Hermes Agent v0.14.0**: (See Section 2 for full integration plan)

**Weekly AI Roundup**:
- LTX 2.3 ecosystem exploding: Just Dub It, Cinema Audio, Drama Box all extracted from same base model
- Pixel3D represents paradigm shift in image-to-3D (pixel-aligned vs loose latent mapping)
- Asymmetric Flow Models may represent future of image generation (bypassing latent space entirely)
- Multiple interactive world generators (Sonnet WM, Warp, DreamX World) — market converging on this form factor

---

## Section 2: Hermes Agent v0.14.0 Integration Plan

### 2.1 Architecture Overview

Hermes is a **persistent autonomous agent** (MIT license) by Nous Research that runs 24/7, builds long-term memory, reusable skills, and evolves over time. v0.14.0 "Foundation Release" adds critical infrastructure features.

### 2.2 Local Proxy — Highest Priority Integration

**What it does**: Routes a single subscription (Claude/ChatGPT/Grok) across any coding tool or autonomous agent locally without separate API keys.

**PMOVES Integration**:

| Target | Integration Method | Benefit |
|--------|-------------------|---------|
| **P7** | Install Hermes on P7 host, configure proxy to expose OpenAI-compatible endpoint at `localhost:PORT` | Single Claude subscription serves Agent Zero, Claude Code, Codex CLI simultaneously |
| **Mesh** | Hermes proxy as NATS service — publish model availability, subscribe to routing requests | Mesh-wide model sharing without per-node API keys |
| **CLI** | Configure A0 CLI connector to use Hermes proxy as LLM provider in `settings.json` | `code_execution_remote` workflows use shared subscription |

**Implementation Steps**:
1. `curl -s https://raw.githubusercontent.com/nousresearch/hermes-agent/main/install.sh | bash`
2. `hermes setup` — configure Claude/ChatGPT/Grok subscription
3. `hermes proxy` — starts OpenAI-compatible API at `localhost:8000` (verify exact port)
4. Point PMOVES LiteLLM proxy or TensorZero to Hermes proxy endpoint
5. Test: ensure Agent Zero subordinate calls route through Hermes proxy

### 2.3 Supergrok Integration

**What it does**: Full Grok ecosystem access (Grok 4.3 text, TTS, image, video, X search) via browser login — 60 second setup.

**PMOVES Integration**:
- Configure as secondary provider in Hermes for X/Twitter research workflows
- DARKXSIDES content curation: use X search for real-time signal detection on playlist topics
- Map to existing `PMOVES-BoTZ` signal detection pipeline

### 2.4 Handoff System (`/slash handoff`)

**What it does**: Transfer entire live session (messages, tool calls, memory, workflows) across models/personas without dropping context.

**PMOVES Integration**:
- Start task on fast model (DeepSeek v4 flash — FREE on Nous Portal) → hand off to deep reasoning model (Claude) for refinement
- Analogous to PMOVES profile switching but preserves full session state
- Evaluate for cross-sidecar handoff: SPARK sidecar → P7 sidecar via NATS

### 2.5 Video Generation

**What it does**: Native AI video generation inside Hermes autonomous workflows.

**PMOVES Integration**:
- Hermes as orchestrator for LTX-2-3 video generation pipeline
- Complements PMOVES-LTX-Desktop: Hermes handles scheduling/prompting, LTX handles rendering
- Potential replacement for manual ComfyUI workflow triggering

### 2.6 Performance Improvements

| Feature | Impact | PMOVES Relevance |
|---------|--------|------------------|
| 19s faster cold start | Faster sidecar boot | Marginal — PMOVES sidecars run persistently |
| Persistent Chrome DevTools (180x faster) | Browser automation | HIGH — PMOVES browser automation could benefit if using Playwright via Hermes |
| 1-hour Claude prompt caching | Cheaper repeated calls | HIGH — memory review loops, background tasks |
| DeepSeek v4 flash FREE | Free agentic model | HIGH — offload non-critical tasks to free model |

### 2.7 Additional Features

- **X/Twitter Search**: Direct X search in workflows — replaces manual browser-based X research
- **Discord History Backup**: Process Discord conversations — maps to PMOVES Discord tools
- **Vision Model Support**: Image pixels instead of text summaries — better visual reasoning
- **LSP Semantic Diagnostics**: Catch coding errors immediately — useful for developer subordinate
- **N8N Integration**: Webhook-based automation — potential bridge to PMOVES NATS event system

---

## Section 3: CREATORFILES Workflow Consolidation

### 3.1 Current State

> **⚠️ UPDATED 2026-05-19** — Inventory corrected against live remote host file listing.

**CREATORFILES** (`/home/powerfulmoves/agent-zero/CREATORFILES/`):
- 11 ComfyUI workflow JSONs (7 Mickmumpitz SDXL variants incl. v07 + Anima Base Ultra + DREADMOR example)
- 2 Anima Base installer .bat files
- 2 Blender example archives (duplicated — `(1)` suffix)
- 1 Discord packaged app (full Electron app: `Discord/` dir with 50+ locale `.pak` files, `resources/app.asar`, `chrome-sandbox`, shared libs, `.desktop` entry)
- 1 PDF guide (`[EXCLUSIVE GUIDE] Install ComfyUI, Models & Advanced Workflows.pdf`)
- 2 Mickmumpitz Movie-Builder 1-0 example archives (duplicated — `(1)` suffix)
- 1 `side.png` (unidentified reference image)

**Downloads** (`/home/powerfulmoves/Downloads/`) — NOT in CREATORFILES:
- `260507_MICKMUMPITZ_MOVIE-BUILDER_1-1_ADV.json` — **NEW v1.1 workflow**
- `260504_MICKMUMPITZ_MOVIE-BUILDER_1-0_SMPL.json` — **Missing v1.0 simple variant**
- `260504_MICKMUMPITZ_MOVIE-BUILDER_1-0_ADV.json` — **Missing v1.0 advanced variant**
- `LTX-2-3-ULTRA-COMFYUI-MANAGER_AUTO_INSTALL.bat` — **LTX-2.3 installer**
- `LTX-2-3-MODELS-NODES_INSTALL.bat` — **LTX-2.3 models/nodes installer**

> **Note**: DREADMOR (`260504_DREADMOR_EXAMPLE_MOVIE_v01.json`) is already in CREATORFILES — no move needed.

### 3.2 Deduplication Required

> **Note**: DREADMOR is NOT a duplicate — it exists as a single copy in CREATORFILES already.

| File | Duplicates | Action |
|------|-----------|--------|
| `BlenderExample_RenderSetup.rar` | 2 copies | Remove `(1)` duplicate |
| `Mickmumpitz_AI-RENDERING_SDXL_ADV_v06.json` | 2 copies | Remove `(1)` duplicate |
| `Mickmumpitz_AI-RENDERING_SDXL_ADV_v07.json` | 1 copy | No action (unique, newest variant) |
| `Mickmumpitz_AI-RENDERING_SDXL_FREE_v02.json` | 2 copies | Remove `(1)` duplicate |
| `Mickmumpitz_AI-RENDERING_SDXL_IMG_ADV_v06.json` | 2 copies | Remove `(1)` duplicate |
| `Mickmumpitz_AI-RENDERING_SDXL_IMG_FREE_v03.json` | 2 copies | Remove `(1)` duplicate |
| `MOVIE-BUILDER_1-0_EXAMPLE-FILES.7z` | 2 copies | Remove `(1)` duplicate |

### 3.3 PMOVES-LTX-Desktop Repo Population

**GitHub repo**: `https://github.com/POWERFULMOVES/PMOVES-LTX-Desktop.git`
**Status**: NOT cloned locally or on remote host

**Proposed structure**:
```
PMOVES-LTX-Desktop/
├── install/
│   ├── LTX-2-3-ULTRA-COMFYUI-MANAGER_AUTO_INSTALL.bat
│   ├── LTX-2-3-MODELS-NODES_INSTALL.bat
│   └── LTX-2-3-ULTRA-COMFYUI-MANAGER_AUTO_INSTALL.sh  # Linux equivalent (to be created)
├── workflows/
│   ├── mickmumpitz/
│   │   ├── movie-builder-1-0-adv.json
│   │   ├── movie-builder-1-0-smpl.json
│   │   ├── movie-builder-1-1-adv.json
│   │   ├── sdxl-adv-v06.json
│   │   ├── sdxl-adv-v07.json
│   │   ├── sdxl-free-v02.json
│   │   ├── sdxl-img-adv-v06.json
│   │   └── sdxl-img-free-v03.json
│   ├── anima/
│   │   └── ANIMA_BASE_ULTRA_WORKFLOW.json
│   ├── dreadmor/
│   │   └── DREADMOR_EXAMPLE_MOVIE_v01.json
│   └── examples/
│       └── movie-builder-1-0-example-files/
├── pinokio/
│   ├── PMOVES-LTX-Desktop/
│   │   ├── install.js
│   │   ├── start.js
│   │   ├── pinokio.js
│   │   └── pinokio.json
│   └── PMOVES-Anima-Base-Ultra/
│       ├── install.js
│       ├── start.js
│       ├── pinokio.js
│       └── pinokio.json
├── README.md
└── LICENSE
```

---

## Section 4: Pinokio/Gepeto/pterm Skill Gap Analysis

### 4.1 Current State

| Component | Found? | Location | Status |
|-----------|--------|----------|--------|
| Pinokio functional launcher | Partial | `/home/powerfulmoves/agent-zero/PMOVES-Pinokio-Ultimate-TTS-Studio/` | Exists but not in git |
| Gepeto SKILL.md (build launchers) | No | — | Missing |
| Pinokio SKILL.md (use apps via pterm) | No | — | Missing |
| pterm CLI tool | No | — | Not installed |
| PINOKIO_LAUNCHER_GUIDE.md | Yes | `.claude/PINOKIO_LAUNCHER_GUIDE.md` | Reference doc only |
| Pinokio skill in .claude/skills/ | No | — | Missing |
| Pinokio skill in skills/ | No | — | Missing |

### 4.2 What Gepeto/pterm Actually Are

- **Gepeto** = Pinokio 7's built-in `SKILL.md` for *building* launchers (auto-generates `install.js`, `start.js`, `pinokio.js`)
- **Pinokio** = Pinokio 7's built-in `SKILL.md` for *using* installed apps via `pterm`
- **pterm** = CLI control plane at `127.0.0.1:42000` — talks to Pinokio's local API, NOT directly to app endpoints
- All follow SKILL.md open standard (same format as Claude Code, Codex CLI)

### 4.3 Missing Launchers — Build Plan

| Priority | Launcher | Workflow Source | Complexity | Dependencies |
|----------|----------|----------------|------------|-------------|
| **P0** | PMOVES-LTX-Desktop | LTX-2-3 install scripts + Movie-Builder workflows | High | ComfyUI, CUDA GPU, 24GB+ VRAM |
| **P1** | PMOVES-Anima-Base-Ultra | ANIMA_BASE_ULTRA_WORKFLOW.json + install bats | Medium | ComfyUI, 6GB VRAM |
| **P1** | PMOVES-Mickmumpitz-SDXL | 6 SDXL rendering workflow variants | Medium | ComfyUI, SDXL models |
| **P2** | PMOVES-Dreadmor-Example | DREADMOR_EXAMPLE_MOVIE_v01.json | Low | ComfyUI, example files |
| **P2** | PMOVES-Blender-Render | BlenderExample_RenderSetup.rar | Low | Blender |
| **P2** | Just-Dub-It | LTX 2.3 fine-tune | Medium | LTX 2.3 base, 2.5GB dub model |
| **P2** | Cinema-Audio | LTX 2.3 audio extraction | Medium | 16GB VRAM, Gemma encoder |

### 4.4 SKILL.md Installation Actions

1. Install Gepeto SKILL.md into `.claude/skills/gepeto/SKILL.md` — enables agents to BUILD launchers
2. Install Pinokio SKILL.md into `.claude/skills/pinokio/SKILL.md` — enables agents to USE apps via pterm
3. Install pterm CLI on remote host (SPARK) for headless launcher control
4. Update `PINOKIO_LAUNCHER_GUIDE.md` with Gepeto/pterm API references

---

## Section 5: DARKXSIDES Research Paper Synthesis

**STATUS**: ❌ HANDED OFF — DARKXSIDE owns this domain. SPARK role is "bring it to light", not "deep connect the dots".

14 research files (Palmer, MIT, Tuszynski, Levin, Hameroff + deep analyses + transcript analyses + FAISS recovery) remain at `/home/powerfulmoves/Downloads/`. DARKXSIDE's Agent Zero instance (`PMOVES-AGENT-ZERO-DARKXSIDE/`) handles synthesis. No action required from SPARK sidecar.

Existing DARKXSIDES content in PMOVES (`docs/papers/`): simulation-holographic-reality-ai-communication.md (38KB), holographic-ai-communication.pdf/docx, pmoves_multi_agent_paper.md — these stay as-is.

---

## Section 6: Additional Playlist Videos (Pending)

**STATUS**: Pending — Researcher C analyzing 3 videos

### 6.1 Videos Under Analysis

| Video | Channel | Expected PMOVES Relevance |
|-------|---------|--------------------------|
| The BMAD Method | AI LABS | HIGH — validate/update existing BMAD skill integration |
| This Changes How You Use Coding Agents | Rasmus Widing | MEDIUM — coding agent optimization patterns |
| Archon V3 Explained | DIY Smart Code | HIGH — competitive intelligence update to ARCHON_ROADMAP_MAY2026_ANALYSIS |

---

## Section 7: Archon V3 Competitive Update

### 7.1 Existing Intelligence (from ARCHON_ROADMAP_MAY2026_ANALYSIS.md)

Key gaps PMOVES should address:
1. **Provider mixing per node** — Archon lets each workflow node use different provider/model; PMOVES lacks this
2. **Workflow marketplace** — Homebrew model with `archon workflow install <slug>`; PMOVES has no equivalent
3. **Silent failure detection** — Archon acknowledges 40% failure rate; PMOVES CHIT signatures address this
4. **Architecture philosophy divergence** — Archon: "agents into system" (constrained pipes); PMOVES: "system into agent" (rich context)

### 7.2 Archon V3 Specific Updates

*(To be populated by Researcher C from DIY Smart Code video)*

---

## Section 8: Character Creation Pipeline (SPARK Core Mission)

> **SPARK's role**: "Bring it to light" — DARKXSIDE deep-connects the dots, SPARK renders them into characters, voices, and stories.

### 8.1 Pipeline Architecture

```
PMOVES Agent Taxonomy          DARKXSIDE Research          LTX 2.3 / Anima Rendering
─────────────────────          ───────────────────          ─────────────────────────
 Hacker profile        ──→     Non-locality themes    ──→     Character design sheets
 Developer profile     ──→     Fractal universe       ──→     Consistent art sets
 Researcher profile    ──→     Bioelectric intel      ──→     Animated shorts
 Security-auditor      ──→     Microtubule acoustics  ──→     Voice cloning (CONCH)
 BMAD personas         ──→     Time crystal dynamics  ──→     Lip-sync video (LTX 2.3)
                                                  ──→     "Agent Trails" episodes
```

### 8.2 Rendering Backbone

#### LTX 2.3 Ultra (22B params)

| Feature | Detail |
|---------|--------|
| Model size | 22B (up from 19B in LTX 2.0) |
| Quantization tiers | Q4 (<12GB VRAM), Q5 (12-16GB), Q8 (24GB+) |
| Workflow modes | 5: txt2vid, img2vid, first/middle/last frame, video extender, upscaler |
| Audio | Generated from scratch OR custom audio with lip-sync |
| Video extender | Clones voice + environment from 3s reference, extends by N seconds |
| Upscaler | Low-res → 1080p enhancement |
| Patreon workflow | `LTX-2-3-ULTRA` ComfyUI workflow (available) |
| Install scripts | `LTX-2-3-ULTRA-COMFYUI-MANAGER_AUTO_INSTALL.bat`, `LTX-2-3-MODELS-NODES_INSTALL.bat` |

#### Anima Base v1.0 / Preview 3 (2B params)

| Feature | Detail |
|---------|--------|
| Model size | 2B parameters |
| VRAM requirement | 6GB (generation + training) |
| Prompt format | Natural language + Danbooru tags (dual support) |
| Artist styles | 20,000+ embedded artist names |
| LoRA training | Citron trainer, ~20 min for 4 epochs, 6GB VRAM |
| Turbo LoRAs | Original (organic style) + P3 (Illustrious-like style), mixable |
| ControlNet | OpenPose, Depth, LineArt/Any — all with Anima-specific models |
| In-painting | New ControlNet for Anima Base v1.0 (from v1.1 video) |
| Patreon workflow | `ANIMA_BASE_ULTRA_WORKFLOW.json` (already in CREATORFILES) |

#### ERNIE Image Model

- Noted as good for character art generation
- Integration path: evaluate alongside Anima for character design sheets
- May be better for certain styles (Chinese anime, realistic portraits)

### 8.3 Voice Pipeline — CONCH → Flute Bridge

**STATUS**: CONCH pipeline exists at CHIT Layer 3. Core gap: wire format → POML bridge.

#### What CONCH Actually Is
CONCH (Consciousness Harvest) is an **internal PMOVES.AI pipeline** — NOT an external voice cloning tool.

**Input**: LOC map (loc.closertotruth.com/map) — Robert Lawrence Kuhn's 325 consciousness theories organized into 10 categories (Anomalous-Altered-States, Challenge-Theories, Dualisms, Idealisms, IIT, Materialism, Monisms, Non-Reductive-Physicalism, Panpsychisms, Quantum-Theories). Structured as `kuhn_full_taxonomy.json`.

**Architecture**: Supabase → consciousness-service (:8096, CHR engine) → NATS Geometry Bus → Downstream (Hi-RAG v2 / Neo4j / Hyperdimensions / Tokenism) — 16 services total.

**Pipeline stages**: Ingest (closertotruth.com + YouTube) → Extract (TextUnit[] for CHR) → CHR Processing (clustering via POST /chr/run) → PersonaGate Evaluation (thresholds: empirical_support ≥0.3, philosophical_coherence ≥0.4) → NATS Publication (geometry.cgp.v1, tokenism.cgp.ready.v1) → Downstream Consumption → **Voice (PLANNED, NOT BUILT)** → Output.

#### The Core Gap
CONCH-produced persona wire format (`chit.cgp.v1.0`) is **not yet bridged** to Flute's POML prompt generator for MiniMax TTS. This is THE work item to complete the voice clone persona creator.

```
CONCH Pipeline (EXISTS)                    Gap                     Flute Pipeline (EXISTS)
─────────────────────                   ────                    ─────────────────────
kuhn_full_taxonomy.json                                           
        ↓                                                              
consciousness-service (:8096)     ──→  chit.cgp.v1.0  ──→  POML prompt generator
        ↓                         →  wire format   →  (Flute layer)
NATS: geometry.cgp.v1                                          ↓
        ↓                                              MiniMax TTS synthesis
PersonaGate (thresholds)                                      ↓
        ↓                                              LTX 2.3 lip-sync
Downstream: Hi-RAG, Neo4j                                     ↓
                                                         Character video output
```

#### Persona Taxonomy → Agent Taxonomy Mapping
- LOC map's 325 theories → CONCH persona profiles → map to PMOVES agent profiles
- Both user-created AND model-generated interpretations supported
- loc.closertotruth.com/map provides the philosophical "deep layer" beneath each character

### 8.4 Creative Content Plan

#### Consistent Character Sets
- Map PMOVES agent taxonomy (hacker, developer, researcher, security-auditor, BMAD personas) to visual character designs
- Generate consistent art sets using Anima Base with artist style locks
- Create character sheets: front/side/back views, expressions, poses
- ERNIE model as alternative renderer for style variety

#### "Agent Trails" — The Show
- Concept: Animated series breathing life into PMOVES development journey
- Vibe: Pacific Rim Gypsy Danger — "PMOVES as a machine being built, run through GitHub like a Jaeger"
- Episodes: Each agent profile gets a character, each sprint gets a mission
- Rendering: LTX 2.3 for animated scenes, Anima for character art, CONCH for voices

#### Personal Remixes (Mom's Content)
- Megaman 2 / Megaman X inspired character designs (robot masters = agent profiles)
- Twilight Zone episode remixes with PMOVES characters
- Target audience: family-friendly, showcase agent capabilities through narrative

### 8.5 ComfyUI Fork Status

- User has forks of both ComfyUI and LTX-Video as git submodules
- Custom nodes may be needed for: automated batch rendering, character consistency locks, voice-to-lip-sync pipeline integration
- Pinokio launcher should reference fork repos, not upstream

---

## Section 9: Implementation Roadmap

### Phase 1: Foundation (This PR)
- [ ] Move 4 Downloads files to CREATORFILES (3 Mickmumpitz + 2 LTX-2-3 .bat install scripts), deduplicate 6 pairs
- [ ] Clone PMOVES-LTX-Desktop repo, populate with workflows + install scripts
- [ ] Install Gepeto + Pinokio SKILL.md into `.claude/skills/`
- [ ] Add research reports to `research/` directory
- [ ] Update `LIVING_DOCS_INDEX.md` with new research entries
- ~~Download LTX 2.3 Ultra + Anima Base Patreon workflows to CREATORFILES~~ — Anima Base workflow already present; LTX-2-3 install scripts in Downloads, move (not download)

### Phase 2: Character Design System (Core SPARK Mission)
- [ ] Map PMOVES agent taxonomy → character design briefs (hacker, developer, researcher, etc.)
- [ ] Generate consistent character art sets using Anima Base (artist style locks, expression sheets)
- [ ] Evaluate ERNIE image model as alternative renderer for style variety
- [ ] Create character sheet template: front/side/back, expressions, poses, color palette
- [ ] Build character consistency LoRAs with Citron trainer (6GB VRAM, ~20 min each)
- [ ] Design "Agent Trails" show format — Pacific Rim Gypsy Danger vibe, PMOVES as Jaeger

### Phase 3: Voice + Video Pipeline
- [ ] Integrate CONCH voice cloning into persona creator (pending Researcher E findings)
- [ ] Map loc.closertotruth.com/map persona taxonomy to PMOVES agent profiles
- [ ] Bridge CONCH → MiniMax TTS → LTX 2.3 lip-sync pipeline
- [ ] Build automated batch render pipeline: character art → voice → lip-sync video
- [ ] Create "Agent Trails" pilot episode from git history (PMOVES build as Gypsy Danger)

### Phase 4: Pinokio Launchers
- [ ] Build PMOVES-LTX-Desktop Pinokio launcher (P0) — LTX 2.3 + Movie-Builder workflows
- [ ] Build PMOVES-Anima-Base-Ultra launcher (P1) — character art generation
- [ ] Build PMOVES-Mickmumpitz-SDXL launcher (P1) — 7 rendering variants (incl. v07)
- [ ] Build PMOVES-Dreadmor-Example launcher (P2) — example movie workflow
- [ ] Build PMOVES-Blender-Render launcher (P2) — render setup from .rar
- [ ] Install pterm on SPARK sidecar for headless launcher control
- [ ] Build Just-Dub-It launcher (P2) — LTX 2.3 lip-sync dubbing
- [ ] Build Cinema-Audio launcher (P2) — expressive TTS from LTX 2.3 audio

### Phase 5: Hermes Integration
- [ ] Install Hermes Agent on P7 host
- [ ] Configure local proxy for shared subscription routing
- [ ] Integrate Hermes proxy as LiteLLM/TensorZero provider
- [ ] Configure Supergrok for X/Twitter research (DARKXSIDES signal detection)
- [ ] Test handoff system for cross-model workflows
- [ ] Evaluate Hermes video generation for LTX pipeline orchestration

### Phase 6: Creative Content Production
- [ ] Produce Megaman 2 / Megaman X inspired character designs (robot masters = agent profiles)
- [ ] Create Twilight Zone episode remixes with PMOVES characters
- [ ] Build "Agent Trails" episode pipeline: git log → narrative → character scenes → voice → video
- [ ] Evaluate Pixel3D for 3D character assets
- [ ] Benchmark Cinema Audio vs Drama Box vs MiniMax TTS for character voices

### Ongoing Evaluation
- [ ] Monitor Qwen 3.7 open weights release for researcher profile
- [ ] Test Asymmetric Flow Models for image generation quality
- [ ] Evaluate MiniCPMv4.6 for edge/mobile deployment
- [ ] Track Archon V3 updates for competitive intelligence

---

## Follow-up Tasks

- [ ] ~~DARKXSIDES paper synthesis~~ — HANDED OFF to DARKXSIDE sidecar
- [ ] Complete playlist video analysis (Researcher C — BMAD/Rasmus/Archon V3)
- [ ] Complete video repo extraction with verified GitHub URLs (Researcher A)
- [ ] **CONCH → Flute bridge**: Build `chit.cgp.v1.0` → POML prompt generator adapter
- [ ] **Character design briefs**: Map agent taxonomy (hacker, developer, researcher, security-auditor, BMAD personas) to visual character descriptions
- ~~Download LTX 2.3 Ultra + Anima Base v1.0 Patreon workflows to CREATORFILES~~ — Anima Base already present; LTX-2-3 scripts in Downloads (move, not download)
- [ ] Create Linux equivalent of LTX-2-3 install scripts (.sh)
- [ ] Build first character consistency LoRA with Citron trainer (test with one agent profile)
- [ ] Evaluate ERNIE image model alongside Anima for character art
- [ ] Design "Agent Trails" pilot episode format from git log narrative
- [ ] Benchmark Hermes proxy latency vs direct API calls
- [ ] Evaluate FiMotion as quality gate for video generation pipeline

## Reviewer Notes

### Critical Decisions Needed
1. **PMOVES-LTX-Desktop repo scope**: Should it include Pinokio launchers inline or reference them as submodules?
2. **Hermes vs TensorZero**: Should Hermes proxy replace TensorZero routing or sit alongside it as a subscription-sharing layer?
3. **Gepeto SKILL.md source**: Need to locate official Gepeto SKILL.md from Pinokio 7 docs or repo
4. **DARKXSIDES papers**: Should these be committed to `docs/papers/` or kept external and only synthesis stored?

### Risk Areas
- Hermes proxy adds a dependency on Nous Research infrastructure — need fallback if proxy goes down
- LTX-2-3 ecosystem is rapidly evolving — launchers may need frequent updates
- DARKXSIDES paper synthesis quality depends on Researcher B's thoroughness — manual review recommended
- Pinokio launcher development requires Windows testing (D:\pinokio\ path in guide) — no Windows CI available

### Existing Research Cross-References
- `research/ARCHON_ROADMAP_MAY2026_ANALYSIS.md` — Archon competitive intelligence baseline
- `research/CATALOG_STUDIOS_AI_PLAYLIST_ANALYSIS.md` — DARKXSIDE playlist signal analysis (1,795 videos)
- `research/PMOVES-LTX-DESKTOP_SKILL_WORKFLOW_GAP_ANALYSIS.md` — Skill/workflow gap analysis (Researcher D output)
- `research/COLE_MEDIN_VIDEO_ANALYSIS.md` — Prior Cole Medin transcript analysis
- `.claude/PINOKIO_LAUNCHER_GUIDE.md` — Pinokio launcher development guide
