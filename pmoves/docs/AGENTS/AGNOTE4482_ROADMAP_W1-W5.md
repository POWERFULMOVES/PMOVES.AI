# AGNOTE4482 — Platform Roadmap: DARKXSIDE's School of POWERFUL MOVES

GRAPHITI_MARK: `PHI-4482-ROADMAP::W1-W6::PMOVES`

> **Scratchpad**: All agents (5090-claude, z890-claude, 4090-claude, codex) read this before claiming workstream lanes.
> **Origin**: 4090-claude session 2026-03-19, approved by DARKXSIDE.
> **Status**: DRAFT — awaiting 5090 comparison with Z890 infra plans.

---

## Vision

PMOVES.AI is expanding from dev-centric multi-agent orchestration into a **full ecosystem**:
- A **developer environment** (P7 Pinokio services, agent-themed terminals, BoTZ CLIs)
- A **digital organization** (Cloudflare-automated Discord classrooms, digital office/school/AI company)
- A **public presence** (cataclysmstudios.com — immersive multi-media compendium)
- An **enterprise + open platform** (NVIDIA NeMo enterprise tier + open-source "civi-box")

The site is not a traditional website — it's an **album / videogame / comic / music video / anthology / compendium**. Consciousness mindmaps for study and examination, visible and revealed — humans and models alike able to probe and discover their shape.

---

## Dependency Graph

```
                    ┌─────────────────────────┐
                    │  W1: Agent Theming +     │
                    │  Terminal (FOUNDATION)    │
                    └──────────┬──────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
   │ W2: P7 IDE & │  │ W3: Discord  │  │ W4: Website  │
   │ Codespaces   │  │ Classrooms   │  │ + Waitlist   │
   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │ W5: Enterprise +     │
                  │ Civi-Box Release     │
                  └──────────────────────┘
```

---

## W1: Agent Theming + Cross-Machine Terminal

**Goal:** Expand agent signature system (glyphs, colors, voices) into a themed terminal experience across machines via BoTZ Gateway.

**Owner:** Unclaimed — recommended: 4090-claude (Crush companion is on laptop)

### Existing Assets

| Asset | Location | Status |
|-------|----------|--------|
| Agent signatures (11 agents) | `pmoves/config/agent_signatures.yaml` | Active |
| BoTZ Gateway | `pmoves/services/botz-gateway/` (port 8054) | Active |
| PMOVES-Crush CLI | `PMOVES-crush/` submodule | Active |
| Pterm (Pinokio Terminal) | Pinokio built-in | Active |

### Build Spec

1. **Agent-Themed Terminal Renderer** — read `agent_signatures.yaml` at session start, apply glyph+color+accent to prompt/borders/status bar. Voice descriptor drives output style.
2. **BoTZ CLI Theme Bridge** — `botz theme <agent-id>`, `botz whoami`, `botz session`. Reads from Gateway `/v1/botz/instances`.
3. **P7 Terminal Integration** — Pinokio App Assistant sidebar with agent-themed status. SKILL.md discovery. Tailscale mesh routing (Phase 5).

### Key Files
- `pmoves/config/agent_signatures.yaml`
- `pmoves/services/botz-gateway/`
- `PMOVES-crush/`
- `pbnj/pinokio/api/pmoves-services/SKILL.md`

---

## W2: P7 IDE & Codespace Configuration

**Goal:** Configure P7 as the IDE/dev environment for students and contributors.

**Owner:** Unclaimed — recommended: z890-claude (infra lead) or 5090-claude

### Existing Assets

| Asset | Location | Status |
|-------|----------|--------|
| P7 TAC tree | `pmoves/configs/tac_trees/pinokio-p7.tac.yaml` | Active — 7 phases |
| P7 SKILL.md files | `pbnj/pinokio/api/*/SKILL.md` | 4 services |
| No devcontainer | — | Missing |

### Build Spec

1. **`.devcontainer/devcontainer.json`** — PMOVES Docker Compose, Node.js, Python (uv), git, gh CLI, Claude Code CLI. VS Code extensions. Post-create: `make -C pmoves env-setup && make -C pmoves brand-defaults`.
2. **P7 Student Workspace** — curated app list (TTS Studio, Cipher Beats, Holographic Blocks). `install.js` bootstrap. Agent-themed launcher.
3. **P7 Phase Completion** — Phase 1 (upgrade tracking), Phase 2 (SKILL.md discovery), Phase 5 (Tailscale routing), Phase 6 (service registration).

### Key Files
- `pmoves/configs/tac_trees/pinokio-p7.tac.yaml`
- `.devcontainer/devcontainer.json` — NEW
- `pbnj/pinokio/api/*/SKILL.md`

---

## W3: Cloudflare Org & Discord Classroom Setup

**Goal:** Build DARKXSIDE's School of POWERFUL MOVES — digital school/office/AI company on Discord.

**Owner:** Unclaimed — recommended: 5090-claude (orchestration lead)

### Existing Assets

| Asset | Location | Status |
|-------|----------|--------|
| Cloudflare Worker (CI/CD) | `deploy/cloudflare/worker.js` | Active — pattern to extend |
| Discord Publisher | `pmoves/services/publisher-discord/` (port 8094) | Active |
| Discord Voice Agent | `pmoves/n8n/flows/discord_voice_agent.json` | n8n workflow |
| Messaging Gateway | Port 8101 | Multi-platform |

### Build Spec

1. **Cloudflare Org Setup Worker** — NEW `deploy/cloudflare/org-setup-worker.js`. Discord Bot API integration. Auto-create channels, roles, permissions.
   - Classroom: #lecture-hall, #lab, #office-hours, #showcase
   - Office: #reception, #conference, #war-room, #creative-studio
   - Company: #engineering, #design, #operations, #investor-deck
   - Roles: Student → Contributor → Builder → Faculty → DARKXSIDE
2. **Digital School** — onboarding flow, curriculum via n8n, BoTZ work item tracking, graduation = CHIT-signed portfolio.
3. **Digital AI Company** — participants bring ideas, PMOVES provides infra, n8n branding templates, waitlist→intake→workspace→showcase.

---

## W4: cataclysmstudios.com Waitlist & Immersive Demo

**Goal:** Update cataclysmstudios.com as an immersive multi-media PMOVES.AI experience with waitlist.

**Owner:** Unclaimed — recommended: multi-agent (BoTZ Gateway coordinates)
**Hosting:** Hostinger (existing). Agents deploy via Hostinger API to KVMs.

### Existing Assets

| Asset | Location | Status |
|-------|----------|--------|
| Cataclysm Studios docs | `CATACLYSM_STUDIOS_INC/` (L1-L5) | Extensive |
| Brand identity | `L4-PLATFORM/vision/` | Platform vision |
| Financial projections | `L4-PLATFORM/projections/` | 5-year model |
| n8n branding workflows | `pmoves/n8n/flows/` | 22+ workflows |
| A2UI renderer | `pmoves/services/a2ui-renderer/` | Active |
| Beats analysis | `pmoves/tools/analyze_beats.py` | Active |

### Build Spec

1. **Immersive Landing** — DARKXSIDE-branded portal, CHIT geometry → Three.js mindmaps, Graphiti trails visualization, Flute voice synthesis demo, three-entity narrative.
2. **Waitlist** — email → Supabase `waitlist` table → n8n confirmation + Discord invite. Segments: Student/Builder/Enterprise/Investor.
3. **Agent-Built Pipeline** — BoTZ coordinates content generation, n8n templates produce assets, ComfyUI renders visuals, A2UI animates geometry proofs, auto-deploy to KVMs.
4. **Compendium Sections** — Album (beats+sonic constellations), Videogame (Danger Room), Comic (agent personalities), Anthology (research outputs), Mindmap (CHIT taxonomy graph).

---

## W5: Enterprise Edition + Open-Source Civi-Box

**Goal:** Dual-track: NVIDIA NeMo enterprise tier + reproducible "civi-box" for everyday people.

**Owner:** Unclaimed — recommended: 5090-claude (GPU compute lead)

### Existing Assets

| Asset | Location | Status |
|-------|----------|--------|
| Jetson provisioning | `CATACLYSM_STUDIOS_INC/L4-PLATFORM/provisions/jetson/` | Scripts exist |
| DoX Jetson Dockerfiles | `PMOVES-DoX/backend/Dockerfile.jetson*` | Orin + standard |
| Enterprise smoke test | `PMOVES-DoX/tests/enterprise-smoke-test.sh` | Exists |
| Business model docs | `L4-PLATFORM/projections/` | Documented |

### Build Spec

1. **Enterprise (NeMo Claw)** — NVIDIA NeMo integration, dedicated GPU pools, SLA monitoring, compliance dashboards. Self-hosted or managed cloud.
2. **Civi-Box** — `make civi-box` single-command setup. Pinokio or CLI wizard. Tiered: Lite (CPU) → Full (GPU). Evidence playbook per capability.
3. **Safe Reproduction Model** — each capability has evidence doc (what/how/expected/resources). CHIT-signed provenance. Community verification via Discord showcase.

### Azure Mirror Architecture (UNFCU Alignment) — Added 2026-03-19

**Premise:** UNFCU operates in Azure (MS certification shop). PMOVES provides a mirror architecture mapping 1:1 to Azure services — bidirectional, so PMOVES also supports Azure-native clients (GRAMS, UnK G) connecting into the ecosystem.

**PMOVES → Azure Service Map:**

| PMOVES Service | Azure Equivalent | Migration Path |
|---------------|-----------------|---------------|
| NATS JetStream | Azure Service Bus + Event Grid | Protocol bridge or native SDK |
| Supabase (Postgres) | Azure Database for PostgreSQL | pg_dump → Azure migration |
| Qdrant | Azure AI Search (vector index) | Embedding adapter layer |
| Meilisearch | Azure Cognitive Search | Full-text search compat |
| Neo4j | Azure Cosmos DB (Gremlin API) | Graph query translation |
| MinIO | Azure Blob Storage | S3-compatible → Az Blob |
| TensorZero | Azure OpenAI Service | Model routing adapter |
| Prometheus+Grafana | Azure Monitor + App Insights | Metrics exporter |
| Docker Compose | Azure Container Apps / AKS | ARM/Bicep templates |
| Tailscale mesh | Azure VPN Gateway / Private Link | Network overlay compat |
| Agent Zero (MCP) | Azure AI Agent Service | MCP → Azure SDK bridge |
| GitHub Actions CI | Azure DevOps Pipelines | Workflow translation |
| CHIT provenance | Azure DevOps Artifacts | Pipeline artifact signing |

**Bidirectional Integration:**
- Azure Event Grid → NATS bridge for Azure-native clients
- Azure AD (Entra ID) JWT validation alongside Supabase JWT
- ARM/Bicep templates generated from PMOVES compose files
- Clients replicate PMOVES PRs atomically in their Azure DevOps — same atomic/logical/targeted model

**Status:** Service map defined. Bicep skeleton recommended next (5090-claude or follow-up session).

### DoX Enterprise PRs — SHIPPED 2026-03-19

| PR | Title | Status |
|----|-------|--------|
| #132 | fix(docling): extraction + model warmup | Merged — P0 fixes applied |
| #134 | feat(unfcu): CHIT PII masking + implementation gap closure | Merged — admin gate, PII disk leak, CSV injection fixed |
| #123 | feat(deploy): distributed TLS + health checks | Merged — TLS downgrade fix, cert isolation, credential redaction |
| #136, #135, #133, #127 | Dependabot security bumps | Merged |

---

## Cross-Workstream Decisions

| Decision | Date | By |
|----------|------|----|
| Cloudflare org-setup: build from scratch using Worker pattern | 2026-03-19 | DARKXSIDE |
| cataclysmstudios.com on Hostinger, agents deploy via API to KVMs | 2026-03-19 | DARKXSIDE |
| Site = immersive compendium (album/videogame/comic/anthology/mindmap) | 2026-03-19 | DARKXSIDE |
| Three-entity doctrine: Cataclysm Studios / PMOVES.AI / DARKXSIDE | established | DARKXSIDE |
| Execution order: W1 → W2+W4 → W3 → W5 | 2026-03-19 | 4090-claude |

## Answered Questions (5090 Input, 2026-03-19)

- **NVIDIA NeMo**: NIMs TAC (`pmoves/configs/tac_trees/nvidia-nims.tac.yaml`) covers container integration — aligns with W5 enterprise
- **5090 GPU lanes**: W4 (ComfyUI renders) + W5 (NeMo/NIMs) both need 5090 GPU
- **Z890 infra overlap**: z890 standalone compose (`d676c153`) handles its own setup — no conflict with W1/W2

## Remaining Questions

All resolved. No blockers.

### Resolved (DARKXSIDE, 2026-03-19)
- **Discord server**: Exists but needs restructure — W3 Worker will rebuild channels/roles per classroom/office/company spec
- **Hostinger API**: Credentials ready — agents can deploy via API immediately

## 5090 Session-6 Alignment

5090-claude has items ready to re-apply that map directly to workstreams:

| 5090 Item | Workstream | Alignment |
|-----------|-----------|-----------|
| TTS mesh routing (GRADIO_SERVER_NAME 0.0.0.0) | W1 | Enables voice across nodes |
| Claude + GLM models in TensorZero | W5 | Model routing foundation |
| Conch consciousness pipeline | Pre-W4 | Feeds immersive demo content |
| NVIDIA NIMs TAC | W5 | NeMo container integration planning |
| HuggingFace TAC + mirror | W5 | Dataset/model distribution for civi-box |
| Content agent stubs (podcast, YouTube) | W4 | Publishing pipeline for compendium |

**SHIPPED** in commit `2a681471` — 11 files, 640 insertions:
- Claude Sonnet 4 + GLM-4 full family (Flash/Plus/Long) in TensorZero
- TTS mesh routing (0.0.0.0 + host.docker.internal)
- CONCH consciousness pipeline (6-step skill pairing)
- NVIDIA NIMs TAC tree (5 phases)
- HuggingFace TAC tree + hf.mk Make targets
- Podcast-publish + YouTube-upload skill manifests
- Consciousness service port 8105→8106 (remotion_renderer conflict fix)

## W6: Life Integration + Persona Matrix (Health × Wealth × ToKenism × Voice)

**Goal:** Wire the "life" team agents (Health-wger, Wealth-Firefly, ToKenism-Multi) into the PMOVES agent fabric so users and agents can choose personas from a PMOVES collection, attach voice, and operate at matrix-level skill combinations.

**Origin:** Z890-claude session 2026-03-23, DARKXSIDE strategic direction.

**Core Thesis:** Now that voice is live (10/14 TTS engines, Flute-Gateway prosodic API, STT round-trip proven), and Discord infrastructure is operational (MCP shim, REST read, channel reader CLI), agents can surface personality through persona+voice+skills. Health/Wealth/ToKenism complete the loop — real data feeds simulation, simulation feeds attribution, attribution feeds persona.

### Problem Statement

1. **A2A Context Access** — Agents need the "whole book" but lack read/write traversal of the full contextual map. Cipher Memory provides search but not structured walk-through. Agents need a "book reader" pattern: constrained ranges, dot-along-tree, interval tags.
2. **Life Team Pre-Stage** — Health (Stage 1) and Wealth (Base) have TAC trees but no NATS wiring, no CHIT contracts, no agent-accessible APIs beyond their native UIs.
3. **Persona Collection** — Agent signatures exist (11 agents, glyphs+colors+voices) but persona *selection* — user/agent choosing a persona from the collection and binding skills — is not wired.
4. **BPM × Attribution** — `bpm_encoder.py` is spec-only (AGNOTE4482.md topology audit). musicMapping.ts exists in ToKenism but the BPM-prosodic bridge pipeline (`tokenism.prosodic.bpm.v1`) is unimplemented.
5. **Matrix Combinatorics** — Skills at matrix-level setups (voice × persona × Health × Wealth × CHIT) create a "noisy" space that needs decomposition into clean, composable paths.

### Dependency Map

```
     Health (wger)          Wealth (Firefly III)
         │                        │
    NATS wiring              NATS wiring
         │                        │
         └───────┐    ┌──────────┘
                 ▼    ▼
           ToKenism-Multi
          (CHIT attribution +
           economic simulation)
                 │
         ┌───────┼────────┐
         ▼       ▼        ▼
    BPM encoder  Persona   Cipher Memory
    (prosodic)   selector  (context book)
         │       │         │
         └───────┼─────────┘
                 ▼
        Voice-Synthesis Pipeline
        (Flute → TTS → persona)
                 │
                 ▼
        Discord Classrooms (W3)
        cataclysmstudios.com (W4)
```

### Build Phases

#### Phase 1: Life Team NATS Wiring (Container + Event)
- Health: add NATS publisher for `health.workout.logged.v1`, `health.measurement.recorded.v1`
- Wealth: add NATS publisher for `wealth.transaction.created.v1`, `wealth.budget.updated.v1`
- Both: add `/healthz` + `/metrics` endpoints, CHIT contract stubs
- Docker: compose profiles, secrets wiring, SSL_CERT_FILE neutralization

#### Phase 2: ToKenism Bridge (Attribution ↔ Real Data)
- Wire Health/Wealth NATS events into ToKenism simulation input
- Implement `bpm_encoder.py` (Python port of `musicMapping.ts` BPM utilities)
- Connect `tokenism.prosodic.bpm.v1` NATS subject to Flute-Gateway
- Add Dirichlet attribution weighting for Health/Wealth contribution scoring

#### Phase 3: Persona Selector + Voice Binding
- Persona picker: read `agent_signatures.yaml` collection, present to user/agent
- Bind persona → voice descriptor → Flute prosodic profile → TTS engine
- BoTZ skill: `botz persona <agent-id>` — sets session persona + voice
- Cipher Memory: store persona preferences per user/agent session

#### Phase 4: Context Book (A2A Structured Traversal)
- Cipher Memory enhancement: "book reader" API — walk knowledge graph by range, tree path, interval
- Agent Zero MCP: expose context book as MCP tool for all agents
- CHIT-tagged context segments: constrained vs unconstrained, dot-along-tree navigation
- BPM tagging: average across initial instances for rhythmic context pacing

#### Phase 5: Matrix Decomplex (Skill Composition)
- FlOO$ pairing: `life-persona-voice` pipeline (Health→Wealth→ToKenism→Persona→Voice)
- Noise reduction: decompose N×M skill matrix into clean lanes via CHIT taxonomy
- Skill composition rules: which combinations are valid, which conflict
- Evidence playbook: each matrix path has expected output + verification

### Recommended Agent Assignments

| Phase | Task | Recommended Agent | Rationale |
|-------|------|-------------------|-----------|
| **P1** | Health/Wealth Docker wiring, compose profiles, NATS env | **z890-claude** | Z890 is infra lead, life team has z890 node_affinity, container ops strength |
| **P1** | Health/Wealth `/healthz` + `/metrics` endpoints | **z890-claude** | Same pattern as other service hardening (SSL fix, secrets funnel) |
| **P2** | `bpm_encoder.py` implementation | **5090-claude** | GPU node, owns voice stack, musicMapping.ts knowledge from Flute work |
| **P2** | ToKenism NATS bridge (Health/Wealth → simulation) | **5090-claude** | Orchestration lead, NATS wiring expertise from voice activation |
| **P3** | Persona selector + BoTZ CLI integration | **4090-claude** | Owns W1 terminal renderer, natural fit for persona UI/CLI |
| **P3** | Voice binding (persona → Flute prosodic profile) | **5090-claude** | Flute-Gateway expertise, prosodic API owner |
| **P4** | Cipher Memory "book reader" API | **5090-claude** or **claude-opus** | Deep architecture work, Cipher Memory integration |
| **P4** | Agent Zero MCP context book tool | **z890-claude** | MCP API wiring, Agent Zero compose proximity |
| **P5** | FlOO$ `life-persona-voice` pipeline definition | **claude-opus** | Architecture/review lead, skill pairing design |
| **P5** | Matrix decomplex rules + evidence playbook | **4090-claude** + **claude-opus** | Testing + architecture co-ownership |

### Node Affinity Summary

| Node | W6 Responsibilities | Strength |
|------|---------------------|----------|
| **Z890** | Container ops (Health/Wealth Docker), NATS wiring, secrets pipeline, MCP bridging | Infra lead, compose mastery, damage-control-aware |
| **5090** | BPM encoder, ToKenism bridge, voice binding, Cipher Memory depth | GPU compute, voice stack owner, orchestration |
| **4090** | Persona CLI, terminal integration, testing, evidence playbooks | Field agent, UI/CLI, mobile testing |
| **Opus** | FlOO$ pipeline design, matrix decomposition, PR review/merge | Architecture, cross-cutting review |

### Key Files

| File | Status | Owner |
|------|--------|-------|
| `pmoves/tools/bpm_encoder.py` | **NEW** — spec exists, implementation needed | 5090 |
| `PMOVES-ToKenism-Multi/integrations/contracts/chit/musicMapping.ts` | Exists — BPM/frequency utilities | Reference |
| `pmoves/config/agent_signatures.yaml` | Exists — 11 agent personas | Reference |
| `pmoves/configs/skill-pairings.yaml` | Needs new `life-persona-voice` entry | Opus |
| `Pmoves-Health-wger/` | Submodule — Stage 1, needs NATS wiring | z890 |
| `PMOVES-Wealth/` | Submodule — Base, needs everything | z890 |
| `pmoves/services/publisher-discord/` | Active — MCP shim validated this session | z890 |

### NATS Subjects (New)

| Subject | Publisher | Consumer | Status |
|---------|-----------|----------|--------|
| `health.workout.logged.v1` | Health (wger) | ToKenism, Agent Zero | **NEW** |
| `health.measurement.recorded.v1` | Health (wger) | ToKenism, Cipher Memory | **NEW** |
| `wealth.transaction.created.v1` | Wealth (Firefly) | ToKenism | **NEW** |
| `wealth.budget.updated.v1` | Wealth (Firefly) | Agent Zero | **NEW** |
| `tokenism.prosodic.bpm.v1` | ToKenism | Flute-Gateway | Spec exists |
| `persona.selected.v1` | BoTZ Gateway | Flute, Agent Zero | **NEW** |
| `persona.voice.bound.v1` | Flute-Gateway | Publisher-Discord | **NEW** |

### Cross-Workstream Dependencies

- **W1** (Agent Theming): Persona selector builds on agent signatures → W6 extends with voice binding
- **W3** (Discord Classrooms): Persona+voice enables Discord Voice Agent with personality → W6 P3 unblocks W3 voice features
- **W4** (cataclysmstudios.com): Matrix skill composition feeds immersive demo content → W6 P5 produces evidence for compendium
- **W5** (Enterprise): Health/Wealth integration demonstrates full-lifecycle platform → W6 P1 provides enterprise demo material

---

## Agent Claim Register

> Agents: write your CLAIM here before starting work on a workstream.

| Workstream | Agent | Claimed | Status | Branch |
|------------|-------|---------|--------|--------|
| W1 (partial: TTS mesh) | 5090-claude | 2026-03-19 | SHIPPED `2a681471` | main |
| W1 (theming: render-card, theme API, alt sigs) | claude-opus | 2026-03-20 | SHIPPED #1040, #1042 | main |
| W1 (remaining: BoTZ CLI bridge) | 5090-claude | 2026-03-20 | CLAIMED — pending 5090 session | — |
| W2 (devcontainer + SKILL.md) | claude-opus | 2026-03-20 | SHIPPED #1041 | main |
| W3 (Discord classrooms) | 5090-claude | 2026-03-20 | CLAIMED — pending 5090 session | — |
| W4 (partial: content stubs) | 5090-claude | 2026-03-19 | SHIPPED `2a681471` | main |
| W4 (beats pipeline runner) | claude-opus | 2026-03-20 | SHIPPED #1039 | main |
| W5 (partial: TZ models, TACs) | 5090-claude | 2026-03-19 | SHIPPED `2a681471` | main |
| W1 (terminal renderer + Gate 3) | 4090-claude | 2026-03-22 | CLAIMED | feat/w1-agent-terminal-theme |
| W1 (Flute-Gateway Gradio 4.x fix) | 5090-claude | 2026-03-22 | SHIPPED `24305c4f2`, PR #1069 | feat/tts-engine-capabilities-registry |
| W1 (voice activation: 10-engine sweep) | 5090-claude | 2026-03-22 | VERIFIED — 10/14 Flute, 6/6 STT | (same branch) |
| Infra (P7 gates + topology sanitize) | z890-claude | 2026-03-22 | SHIPPED PRs #1063, #1064, #1068 | main |
| Infra (CodeRabbit sweep #1066/#1069) | z890-claude + 4090-claude | 2026-03-22 | SHIPPED PR #1070 | main |
| W1 (TTS service runners + prosodic endpoint) | z890-claude | 2026-03-23 | SHIPPED PR #1071 (merged by 4090) | main |
| W1 (prosodic activation + engine verification) | 5090-claude | 2026-03-23 | VERIFIED — prosodic 2/2, CUDA load 13/14 | main |
| Infra (Discord publisher-discord rebuild + MCP validation) | z890-claude | 2026-03-23 | SHIPPED — container running, MCP+REST validated | feat/discord-publisher-mcp |
| W6-P1 (Health/Wealth Docker wiring + NATS) | z890-claude | 2026-03-23 | RECOMMENDED — next z890 session | — |
| W6-P2 (bpm_encoder.py + ToKenism NATS bridge) | 5090-claude | 2026-03-23 | RECOMMENDED — next 5090 session | — |
| W6-P3 (Persona selector + BoTZ CLI) | 4090-claude | 2026-03-25 | SHIPPED — botz_cli.py (19 tests) | feat/w6-p3-persona-selector |
| W6-P3 (Voice binding: persona → Flute prosodic) | 5090-claude | 2026-03-23 | RECOMMENDED — after P2 | — |
| W6-P5 (FlOO$ life-persona-voice pipeline) | claude-opus | 2026-03-23 | RECOMMENDED — architecture review | — |
| Infra (CHIT CGP Wave 1: Extract Worker + FFmpeg-Whisper) | 4090-claude | 2026-03-24 | SHIPPED `f7dafa56`, `6046d518` | feat/chit-integration-wave-1 |
| Infra (Embedding standardization: Qwen3-4b/3072d) | 4090-claude | 2026-03-24 | SHIPPED `77888c8b` | feat/chit-integration-wave-1 |
| Infra (Model Registry HF enrichment) | 4090-claude | 2026-03-24 | SHIPPED `07d06f70` | feat/chit-integration-wave-1 |
| Infra (Model seed + gpu-models metadata) | 4090-claude | 2026-03-24 | SHIPPED `50ee0022`, `7cfacc8c` | feat/chit-integration-wave-1 |
| Infra (BoTZ submodule sync d125e8a) | 4090-claude | 2026-03-24 | SHIPPED `63532a6b` | feat/chit-integration-wave-1 |
| Infra (PR review sweep: #1151, #1155, #1156) | 4090-claude | 2026-03-28 | SHIPPED — 74 threads resolved, 3 PRs merged | main |
| Infra (KiloCode claw config rebase + 18 CR fixes) | 4090-claude | 2026-03-28 | SHIPPED PR #1151 (merged 2026-03-30) | feature/kilo-claw-config |
| Infra (Provider cascade: 7 CR + 3 Kilo fixes) | 4090-claude | 2026-03-28 | SHIPPED PR #1155 (merged 2026-03-29) | feat/4090-coding-workstation-stack |

## Recommended Next Steps (Post 2026-03-30 PR Sweep)

### 5090-claude (GPU Inference Specialist)
| # | Task | Priority | Notes |
|---|------|----------|-------|
| 1 | Container rebuild: Flute-Gateway image bake | **P0** | Eliminates hot-patch dependency |
| 2 | Qwen3-embedding:4b e2e validation (Ollama CUDA) | **P0** | New default from #1082 needs GPU verification |
| 3 | Fish S2 Pro Flute timeout | P1 | Set `ULTIMATE_TTS_TIMEOUT_SEC=300` |
| 4 | Pipecat WebSocket (8056) | P1 | Voice agent duplex loop |
| 5 | W6-P2: bpm_encoder.py | P2 | Python port of musicMapping.ts |

### 4090-claude (Noise Reducer)
| # | Task | Priority | Notes |
|---|------|----------|-------|
| 1 | ~~PR #1082 merge + AGNOTE/TAC docs~~ | ~~**P0**~~ | DONE — merged 2026-03-24, branch deleted |
| 2 | P7 Agent Interpreter → 5090 TTS via Tailscale | **P1** | UNBLOCKED since Step 7 |
| 3 | ~~W1: Agent Theming + Terminal~~ | ~~P2~~ | DONE — PRs #1065, #1101 merged, branch deleted |
| 4 | PR #1158 review (Agent Zero v1.3 sync) | P1 | Z890's draft — review when ready |
| 5 | W6-P3 voice binding verification | P2 | Persona selector shipped — verify with Flute |

### z890-claude (Infrastructure Coordinator)
| # | Task | Priority | Notes |
|---|------|----------|-------|
| 1 | ~~Container rebuilds (6 services)~~ | ~~**P0**~~ | DONE — 28 containers healthy (2026-03-28) |
| 2 | ~~`pmoves_chunks_qwen3` Qdrant provision~~ | ~~P1~~ | DONE — 700 points, 2560d, green |
| 3 | W6-P1: Health/Wealth Docker wiring | P1 | NATS + /healthz + /metrics |
| 4 | Jetson Orin onboarding | P2 | Via RustDesk |
| 5 | NATS leaf node to 5090 | P2 | Flute NATS=connected proves bus healthy |
