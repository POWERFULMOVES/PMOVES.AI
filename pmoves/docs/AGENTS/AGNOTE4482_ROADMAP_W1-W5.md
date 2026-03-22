# AGNOTE4482 — Platform Roadmap: DARKXSIDE's School of POWERFUL MOVES

GRAPHITI_MARK: `PHI-4482-ROADMAP::W1-W5::PMOVES`

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
| W1 (Flute-Gateway Gradio 4.x fix) | 5090-claude | 2026-03-22 | SHIPPED `24305c4f2`, PR #1069 | feat/tts-engine-capabilities-registry |
| W1 (voice activation: 10-engine sweep) | 5090-claude | 2026-03-22 | VERIFIED — 10/14 Flute, 6/6 STT | (same branch) |
