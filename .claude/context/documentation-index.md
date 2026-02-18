# PMOVES.AI Documentation Index

**Last Updated:** February 2026
**Purpose:** Cross-reference navigation for PMOVES.AI documentation

---

## Quick Navigation Matrix

| Topic | Primary Doc | Implementation | NATS Subjects |
|-------|-------------|----------------|---------------|
| **CHIT/CGP** | `PMOVESCHIT.md` | `IMPLEMENTATION_STATUS.md` | `geometry-nats-subjects.md` |
| **Flute Voice** | `flute-gateway.md` | `FLUTE_PROSODIC_ARCHITECTURE.md` | `nats-subjects.md` |
| **Personas** | `PERSONAS.md` | `voice-personas.md` | `voice.persona.*` |
| **Services** | `services-catalog.md` | CLAUDE.md | `nats-subjects.md` |
| **Brand** | `CATACLYSM_STUDIOS_INC.md` | Services | N/A |
| **Agents/CODEX** | `CODEX_OPERATOR_HOME.md` | `CODEX_CLAUDE_PARITY_MAP.md` | — |
| **Tooling Audit** | `TOOLING_SCRIPT_AUDIT.md` | `AGENTS/` | — |

---

## Integration Layer

The [PMOVES.AI Integration Layer Overview](../../pmoves/docs/INTEGRATIONS_OVERVIEW.md) is the master entry point for all integration documentation, organized by five systems: Skill Registry, CHIT Tools, Secrets Pipeline, GPU Orchestration, and Damage Control Hooks.

| Document | Path | Purpose |
|----------|------|---------|
| Integration Overview | `pmoves/docs/INTEGRATIONS_OVERVIEW.md` | Master entry point for all integration docs |
| CHIT Tools Catalog | `pmoves/docs/CHIT_TOOLS_CATALOG.md` | All 13+ CHIT Python tools with usage |
| Secrets Pipeline Reference | `pmoves/docs/SECRETS_PIPELINE_REFERENCE.md` | Complete 6-step funnel, tier architecture |
| GPU Orchestration Guide | `pmoves/docs/GPU_ORCHESTRATION_GUIDE.md` | GPU API, CLI skills, make targets, hardware |
| Service Integration Guide | `pmoves/docs/INTEGRATIONS.md` | Service auth, API endpoints |
| Submodule Integration Guide | `pmoves/docs/PMOVES.AI_SUBMODULE_INTEGRATION_GUIDE.md` | Tier credentials, bootstrap |
| Submodule Contract | `pmoves/docs/SUBMODULE_INTEGRATION_CONTRACT.md` | Overlay structure and rules |
| Hooks README | `.claude/hooks/README.md` | Pre/post-tool hooks, damage control |

---

## PMOVESCHIT / GEOMETRY BUS

### Specifications

| Document | Path | Purpose |
|----------|------|---------|
| Core Specification | `pmoves/docs/PMOVESCHIT/PMOVESCHIT.md` | CGP v0.1 packet format |
| Implementation Status | `pmoves/docs/PMOVESCHIT/IMPLEMENTATION_STATUS.md` | What's implemented vs. spec |
| GEOMETRY BUS Guide | `pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md` | Service integration |
| NATS Subjects | `.claude/context/geometry-nats-subjects.md` | `tokenism.*`, `geometry.*` subjects |

### Decoder Specifications

| Document | Path | Status |
|----------|------|--------|
| Decoder v0.1 | `PMOVESCHIT_DECODERv0.1.md` | Spec only |
| Multi-Modal Decoder | `PMOVESCHIT_DECODER_MULTIv0.1.md` | Not implemented |
| SHIFT Test | `PMOVESSHIFTEST.md` | Conceptual |

### TypeScript Implementation

```
PMOVES-ToKenism-Multi/integrations/contracts/chit/
├── cgp-generator.ts        # CGP packet generation
├── dirichlet-weights.ts    # Dirichlet attribution
├── hyperbolic-encoder.ts   # Poincaré disk embedding
├── shape-attribution.ts    # Multi-modal shapes
├── swarm-attribution.ts    # EvoSwarm consensus
├── zeta-filter.ts          # Riemann zeta filtering
├── chit-nats-publisher.ts  # NATS integration
└── index.ts                # Unified exports
```

### TAC Commands

| Command | Description |
|---------|-------------|
| `/chit:encode` | Encode content to CGP |
| `/chit:decode` | Decode CGP packet |
| `/chit:visualize` | Render as geometry |
| `/chit:bus` | GEOMETRY BUS operations |
| `/hyperdim:render` | Three.js surfaces |
| `/hyperdim:animate` | Animated visualizations |
| `/hyperdim:export` | Export to 3D formats |

---

## Voice & Flute

### Architecture

| Document | Path | Purpose |
|----------|------|---------|
| Flute API Reference | `.claude/context/flute-gateway.md` | Operational API |
| Full Architecture | `pmoves/docs/context/PMOVES Multimodal Communication Layer (Flute)...md` | Design spec |
| Prosodic Sidecar | `pmoves/docs/FLUTE_PROSODIC_ARCHITECTURE.md` | TTFS optimization |
| Voice Personas | `.claude/context/voice-personas.md` | Persona system |

### Deprecated Locations

| Document | Status |
|----------|--------|
| `docs/PMOVES Multimodal Communication Layer ("Flute")...md` | DEPRECATED → use `.claude/context/flute-gateway.md` |
| `pmoves/docs/context/PMOVES Multimodal Communication Layer ("Flute")...md` | DEPRECATED → duplicate |

### NATS Subjects

```
voice.tts.request.v1     # TTS synthesis request
voice.tts.chunk.v1       # Audio chunk streaming
voice.tts.completed.v1   # Synthesis complete
voice.stt.completed.v1   # Transcription complete
voice.persona.created.v1 # Persona events
agent.voice.speaking.v1  # Agent voice state
```

---

## Persona Framework

| Document | Path | Purpose |
|----------|------|---------|
| Persona Framework | `pmoves/docs/PERSONAS.md` | 325+ persona architecture |
| Voice Personas | `.claude/context/voice-personas.md` | Voice/TTS integration |
| CATACLYSM Brand | `pmoves/docs/PMOVESCHIT/CATACLYSM_STUDIOS_INC.md` | Brand alignment |

---

## Services Catalog

| Document | Path | Purpose |
|----------|------|---------|
| Services Catalog | `.claude/context/services-catalog.md` | All 60+ services |
| **Tier Architecture** | `.claude/context/tier-architecture.md` | **6-tier env + 5-tier network model** |
| NATS Subjects | `.claude/context/nats-subjects.md` | Event subjects |
| MCP API | `.claude/context/mcp-api.md` | Agent Zero MCP |
| Submodules | `.claude/context/submodules.md` | 20+ submodules |
| TensorZero | `.claude/context/tensorzero.md` | LLM gateway |

---

## Brand & Platform

| Document | Path | Purpose |
|----------|------|---------|
| CATACLYSM Overview | `pmoves/docs/PMOVESCHIT/CATACLYSM_STUDIOS_INC.md` | Platform vision |
| Platform Vision | `CATACLYSM_STUDIOS_INC/ABOUT/` | Brand identity |
| Fordham Pilot | (embedded in CATACLYSM docs) | Real-world deployment |

---

## Mathematical Foundations

| Document | Path | Purpose |
|----------|------|---------|
| Math Integration | `pmoves/docs/PMOVESCHIT/Integrating Math into PMOVES.AI.md` | Five pillars |
| UI Design Spec | `pmoves/docs/PMOVESCHIT/Mathematical_UI_Design_Specification.md` | Visual math |
| Implementation Plan | `pmoves/docs/PMOVESCHIT/Mathematical_UI_Implementation_Plan.md` | Roadmap |
| Human Side | `pmoves/docs/PMOVESCHIT/Human_side.md` | User-facing docs |

### Five Mathematical Pillars

1. **Dirichlet Distributions** → Fair attribution
2. **Hyperbolic Geometry** → Hierarchical embedding
3. **Merkle Proofs** → Integrity verification
4. **Zeta Functions** → Signal filtering
5. **Swarm Optimization** → Distributed consensus

---

## Research & Evaluation

| Document | Path | Purpose |
|----------|------|---------|
| A2UI Evaluation | `research/A2UI_EVALUATION_REPORT.md` | UI framework analysis |
| CHR Pipeline | `pmoves/docs/PMOVESCHIT/Constellation-Harvest-Regularization/` | Entropy analysis |
| Doc2Structure | `pmoves/docs/PMOVESCHIT/doc2structure.py` | Document processing |

---

## CODEX Operations

| Document | Path | Purpose |
|----------|------|---------|
| Operator Home | `pmoves/docs/AGENTS/CODEX_OPERATOR_HOME.md` | Codex quickstart & runbooks |
| Claude Parity Map | `pmoves/docs/AGENTS/CODEX_CLAUDE_PARITY_MAP.md` | Claude ↔ Codex command translation |
| Submodule Audit | `pmoves/docs/AGENTS/CODEX_SUBMODULE_INTEGRATION_AUDIT.md` | Submodule Codex coverage |
| Tooling Audit | `pmoves/docs/AGENTS/TOOLING_SCRIPT_AUDIT.md` | Scripts & Make target inventory |
| Known Roads | `.claude/CLAUDE.md` (Known Roads table) | Dangerous ops → Make targets |
| Infra Makefile | `pmoves/mk/infra.mk` | volume-reset, docker-prune targets |

---

## Cross-Reference: Services ↔ NATS

| Service | Port | Key NATS Subjects |
|---------|------|-------------------|
| Hi-RAG v2 | 8086 | `geometry.packet.encoded.v1` |
| Flute-Gateway | 8055/8056 | `voice.tts.*`, `voice.stt.*` |
| Agent Zero | 8080 | `agent.*`, `claude.code.*` |
| SupaSerch | 8099 | `supaserch.request.v1` |
| DeepResearch | 8098 | `research.deepresearch.*` |

---

## Cross-Reference: CGP Specs ↔ TypeScript

| CGP Field | TypeScript Module | Function |
|-----------|-------------------|----------|
| `super_nodes` | `cgp-generator.ts` | `generateCGP()` |
| `dirichlet_alpha` | `dirichlet-weights.ts` | `computeWeights()` |
| `hyperbolic_coords` | `hyperbolic-encoder.ts` | `embedPoincare()` |
| `swarm_consensus` | `swarm-attribution.ts` | `evolvePopulation()` |
| `zeta_filter` | `zeta-filter.ts` | `filterSignal()` |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 2025 | Initial index, PR #343 alignment |
| 2.0 | Feb 2026 | CODEX parity, Known Roads, tooling audit, Agent Zero DoX |
| 2.1 | Feb 2026 | Submodule-skill registry, Skills Reference, CLAUDE.md inventory |

---

## Skills & Commands Reference

All Claude Code CLI skills are stored in `.claude/commands/` as Markdown files organized by category.

| Category | Count | Key Skills |
|----------|-------|------------|
| `agent-sdk/` | 4 | `create`, `handoff`, `resume`, `run` |
| `agents/` | 2 | `status`, `mcp-query` |
| `botz/` | 4 | `init`, `mcp`, `profile`, `secrets` |
| `chit/` | 4 | `encode`, `decode`, `visualize`, `bus` |
| `crush/` | 2 | `setup`, `status` |
| `db/` | 3 | `backup`, `migrate`, `query` |
| `deploy/` | 7 | `up`, `services`, `secrets-funnel`, `preflight`, `audit-layers`, `bootstrap-env`, `smoke-test` |
| `github/` | 4 | `actions`, `issues`, `pr-review`, `security` |
| `gpu/` | 3 | `status`, `models`, `optimize` |
| `health/` | 3 | `check-all`, `metrics`, `quick` |
| `hyperdim/` | 3 | `render`, `animate`, `export` |
| `k8s/` | 3 | `deploy`, `logs`, `status` |
| `langextract/` | 4 | `extract`, `process`, `provider`, `status` |
| `model/` | 2 | `load`, `unload` |
| `n8n/` | 4 | `execute`, `nodes`, `suggest`, `workflows` |
| `pipecat/` | 2 | `connect`, `status` |
| `search/` | 3 | `hirag`, `deepresearch`, `supaserch` |
| `tensorzero/` | 1 | `models` |
| `test/` | 2 | `pr`, `smoke` |
| `tts/` | 4 | `status`, `synthesize`, `test-all`, `voices` |
| `workitems/` | 3 | `claim`, `complete`, `list` |
| `worktree/` | 4 | `cleanup`, `create`, `list`, `switch` |
| `yt/` | 10 | `add-channel`, `ingest-video`, `status`, `check-now`, + 6 more |
| _(root)_ | 1 | `pr-monitor` |
| **Total** | **84** | |

---

## Submodule CLAUDE.md Inventory

Submodule context files that Claude Code CLI may load based on the context tier strategy.

| Submodule | CLAUDE.md Path | Tier | Scope |
|-----------|---------------|------|-------|
| PMOVES-Archon | `PMOVES-Archon/CLAUDE.md` | 2 | Agent service architecture |
| PMOVES-BoTZ | `PMOVES-BoTZ/.claude/CLAUDE.md` | 2 | Skills marketplace framework |
| PMOVES-DoX | `PMOVES-DoX/CLAUDE.md`, `PMOVES-DoX/.claude/CLAUDE.md` | 2 | Document processing |
| PMOVES-Danger-infra | `PMOVES-Danger-infra/CLAUDE.md` | 3 | E2B infrastructure |
| PMOVES-Headscale | `PMOVES-Headscale/CLAUDE.md` | 3 | Mesh VPN coordinator |
| PMOVES-Open-Notebook | `PMOVES-Open-Notebook/CLAUDE.md` | 2 | Knowledge base (SurrealDB) |
| PMOVES-Pipecat | `PMOVES-Pipecat/CLAUDE.md` | 2 | Voice/multimodal comms |
| PMOVES-tensorzero | `PMOVES-tensorzero/CLAUDE.md` | 2 | LLM gateway + observability |
| PMOVES-ToKenism-Multi | `PMOVES-ToKenism-Multi/CLAUDE.md` | 2 | Token economy / CHIT |

**Nested contexts** (Tier 4 - load only when working on specific component):
- `PMOVES-Archon/archon-example-workflow/CLAUDE.md`
- `PMOVES-BoTZ/features/skills/repos/*/CLAUDE.md`
- `PMOVES-Open-Notebook/*/CLAUDE.md` (13+ nested contexts)
- `PMOVES-tensorzero/*/CLAUDE.md` (3 nested contexts)

---

## Submodule-Skill Registry

**Registry file:** `pmoves/configs/submodule_skill_registry.json`

Machine-readable JSON mapping every submodule to relevant skills, context files, AGENTS docs, domain tags, and context tier. Used by Claude Code CLI context orchestration and validated by `make -C pmoves skill-registry-validate`.

**Validation:** Integrated as step 10 of `audit-layers-static` in `pmoves/mk/preflight.mk`.

**Companion tools:**
- `pmoves/tools/skill_registry_validate.py` - Validates registry against `.gitmodules` + skill files
- `pmoves/tools/skill_tag_injector.py` - Injects context-tag blocks into submodule CLAUDE.md files

---

## Production Audit

| Document | Path | Purpose |
|----------|------|---------|
| **Production Audit Dashboard** | `pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md` | **Single source of truth** — consolidates 17 audit docs |
| Blocker Status | `pmoves/docs/PRODUCTION_AUDIT_BLOCKER_STATUS.md` | B1-B5 resolution details (resolved) |
| Readiness Audit | `pmoves/docs/PRODUCTION_READINESS_AUDIT_2026-02-07.md` | Master checklist (active — health/DB pending) |
| CI Audit | `pmoves/docs/CI_AUDIT_REPORT_2026-02-08.md` | GHCR failures (active) |
| Env Tier Audit | `pmoves/docs/ENV_TIER_AUDIT_2026-02-07.md` | Missing credentials (active) |
| Submodule SITREP | `pmoves/docs/SUBMODULE_ALIGNMENT_SITREP_2026-02-14.md` | Diagnostic snapshot |

All 17 audit documents have navigation headers pointing to the dashboard.

---

## Related

- Main CLAUDE.md: `.claude/CLAUDE.md`
- Testing Strategy: `.claude/context/testing-strategy.md`
- Learnings: `.claude/learnings/`
