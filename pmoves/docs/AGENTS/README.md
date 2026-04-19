# PMOVES.AI Agents Documentation

**Last updated:** 2026-04-01
**Files:** 107 documents across 7 tiers (66 root + 41 SUBMODULE_CODEX_HOMES)
**Registry:** 71 agents in `pmoves/config/agent_registry.yaml` (taxonomy v1.4.0)

---

## Start Here

1. **[agent_registry.yaml](../../config/agent_registry.yaml)** — Single source of truth for all 71 agents (class, type, port, NATS, CHIT toggles)
2. **[PMOVES_AGENT_CLASS_TAXONOMY.md](./PMOVES_AGENT_CLASS_TAXONOMY.md)** — 4 classes (legendary/standard/specialized/utility), 7 service tiers, evolution stages
3. **[AGENT_TAXONOMY_CROSS_REFERENCE.md](./AGENT_TAXONOMY_CROSS_REFERENCE.md)** — Maps 18 documents with change-impact matrix
4. **[IMPLEMENTATION_GAP_ANALYSIS.md](./IMPLEMENTATION_GAP_ANALYSIS.md)** — What's built vs. what's planned
5. **[CODEX_ECOSYSTEM_TRAVERSAL.md](./CODEX_ECOSYSTEM_TRAVERSAL.md)** — Codex-first traversal path across skills, memory, personas, voice, services, and submodules

### External Contributor Lanes

The runtime registry keeps deployable services in `agents`, while Git-based AI
contributors live in `external_contributors`. Codex is part of that contributor
list and should be treated as a first-class PMOVES traversal/operator lane.

Canonical identity sources:
- `pmoves/config/agent_registry.yaml` -> `external_contributors`
- `pmoves/config/agent_signatures.yaml` -> `codex`
- `pmoves/docs/AGENTS/CODEX_ECOSYSTEM_TRAVERSAL.md`

## 2026 Creator Network Fast Path

Use this path when the task involves creator operations, channel growth, YouTube ingest,
transcripts, Jellyfin playback, Discord outreach, or model-routing across the PMOVES stack.

1. **[CODEX_OPERATOR_HOME.md](./CODEX_OPERATOR_HOME.md)** — Codex-first operator runbook with creator control plane commands
2. **[../PMOVES.AI PLANS/CREATOR_NETWORK_CONTROL_PLANE.md](../PMOVES.AI%20PLANS/CREATOR_NETWORK_CONTROL_PLANE.md)** — 2026 creator-network operating model
3. **[SUBMODULE_CODEX_HOMES/PMOVES-Creator.md](./SUBMODULE_CODEX_HOMES/PMOVES-Creator.md)** — creator strategy, networking, and campaign lane
4. **[SUBMODULE_CODEX_HOMES/PMOVES-Open-Notebook.md](./SUBMODULE_CODEX_HOMES/PMOVES-Open-Notebook.md)** — planning, drafting, evidence, and operator memory lane
5. **[PMOVES_YT_CONTROL_WORKTREE_REVIEW.md](./PMOVES_YT_CONTROL_WORKTREE_REVIEW.md)** — PMOVES.YT integration worktree runbook across discovery, transcripts, playback, control, and model routing
6. **[JELLYFIN_CREATOR_WORKTREE_REVIEW.md](./JELLYFIN_CREATOR_WORKTREE_REVIEW.md)** — Jellyfin/creator worktree review and current gaps
7. **[SUBMODULE_CODEX_HOMES/PMOVES.YT.md](./SUBMODULE_CODEX_HOMES/PMOVES.YT.md)** — authoritative YouTube runtime traversal
8. **[SUBMODULE_CODEX_HOMES/PMOVES-transcribe-and-fetch.md](./SUBMODULE_CODEX_HOMES/PMOVES-transcribe-and-fetch.md)** — transcript/fetch auxiliary lane
9. **[../PMOVESCHIT/CATACLYSM_STUDIOS_INC.md](../PMOVESCHIT/CATACLYSM_STUDIOS_INC.md)** — platform, brand, and governance context for creator actions

The creator-network lane treats Codex as a legendary operator that can traverse:
- PMOVES-Creator for channel strategy, outreach posture, collaboration plays, and campaign framing
- PMOVES-Open-Notebook for draft assembly, evidence capture, notes, and reusable operator context
- PMOVES.YT for owned/watched channel ingest, playlist control, metadata sync, and downloader fallback
- Channel Monitor for source discovery, scheduling, and event routing
- transcribe-and-fetch for transcript and fetch augmentation
- Jellyfin and publisher surfaces for playback, packaging, and downstream publishing
- Discord via ClaWZ (PMOVES-ClawZ) for agent-mediated response, routing, and operator interaction
- CATACLYSM_STUDIOS_INC for business, brand, and community constraints that govern what the stack should do
- local and remote model tiers for extraction, embedding, rerank, narration, and orchestration

---

## Directory by Tier

### Tier 1: Core Taxonomy (4 files)

Foundation documents defining the agent classification system.

| File | Purpose |
|------|---------|
| [PMOVES_AGENT_CLASS_TAXONOMY.md](./PMOVES_AGENT_CLASS_TAXONOMY.md) | Class definitions, evolution stages, layer model (v1.5.0) |
| [PMOVES_UNIFIED_AGENT_TAXONOMY.md](./PMOVES_UNIFIED_AGENT_TAXONOMY.md) | Unified view across all 71 agents |
| [PERSONAS.md](./PERSONAS.md) | Persona framework: schema, inheritance, CHIT attribution, 325+ catalog vision |
| [PMOVES_AGENT_TOPOLOGY.md](./PMOVES_AGENT_TOPOLOGY.md) | Network topology and inter-agent communication patterns |

### Tier 2: Architecture & Integration (6 files)

Cross-cutting patterns that govern how agents interact.

| File | Purpose |
|------|---------|
| [AGENT_TAXONOMY_CROSS_REFERENCE.md](./AGENT_TAXONOMY_CROSS_REFERENCE.md) | 18-doc cross-reference hub with change-impact matrix |
| [AGENT_RESILIENCE_PATTERNS.md](./AGENT_RESILIENCE_PATTERNS.md) | 3-layer resilience model (preventive → Cipher recovery → registry systemic) |
| [AGENT_CONTEXT_PATTERNS.md](./AGENT_CONTEXT_PATTERNS.md) | Universal 4-tier context hierarchy for all agents |
| [PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md](./PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md) | Geometry visualization surface and toggle schema |
| [BOTZ_GATEWAY_AGENT_INTEGRATION.md](./BOTZ_GATEWAY_AGENT_INTEGRATION.md) | ~~BoTZ Gateway integration proposal~~ **ARCHIVED (2026-04-19)** — see `archive/founding-strategy/` |
| [PmovesSKillZ.md](./PmovesSKillZ.md) | Skill bundle definitions and marketplace patterns |

### Tier 3: Configuration (3 files)

Machine-readable configuration referenced by scripts and services.

| File | Location | Purpose |
|------|----------|---------|
| `agent_registry.yaml` | `pmoves/config/` | Single source of truth (71 agents) |
| `model_strengths.yaml` | `pmoves/config/` | Model capability ratings for routing |
| `skill-pairings.yaml` | `pmoves/configs/` | 7 FlOO$ skill pairings with dependencies |

### Tier 4: Operator Guides (10 files)

Runbooks for Codex and Claude operators.

| File | Purpose |
|------|---------|
| [CODEX_OPERATOR_HOME.md](./CODEX_OPERATOR_HOME.md) | Codex-first operations guide with endpoint catalog |
| [CODEX_ECOSYSTEM_TRAVERSAL.md](./CODEX_ECOSYSTEM_TRAVERSAL.md) | Codex traversal map across PMOVES skills, memory, personas, voice, and submodules |
| [CODEX_RUNTIME_PROTOCOL.md](./CODEX_RUNTIME_PROTOCOL.md) | Focus/scout modes, confidence gates, PR sweep |
| [CODEX_CLAUDE_PARITY_MAP.md](./CODEX_CLAUDE_PARITY_MAP.md) | Token-by-token Codex ↔ Claude command mapping |
| [CODEX_CLAUDE_PARITY_GAPS.md](./CODEX_CLAUDE_PARITY_GAPS.md) | Auto-generated parity gap report (113/113 mapped) |
| [CODEX_CIPHER_MEMORY_IMPLEMENTATION_MAP.md](./CODEX_CIPHER_MEMORY_IMPLEMENTATION_MAP.md) | Codex + Cipher integration locations |
| [CODEX_PERSONA_STYLE_PLAYBOOK.md](./CODEX_PERSONA_STYLE_PLAYBOOK.md) | Persona voice/style configuration |
| [KRISS_KROSS_ACCORD.md](./KRISS_KROSS_ACCORD.md) | Multi-agent collision safety protocol (ratified 2026-02-25) |
| [KRISS_KROSS_ACK.md](./KRISS_KROSS_ACK.md) | Witness attestation for KRISS KROSS ratification |
| [OPERATOR_FACING_CLAUDE_MD_MIRRORS.md](./OPERATOR_FACING_CLAUDE_MD_MIRRORS.md) | Operator-facing mirrors of `.claude/CLAUDE.md` runbook sections (submodule recovery, CodeQL sanitizer) |

### Creator Control Plane

These docs matter when traversing PMOVES as a creator and media operations system rather than a
single-service codebase.

| File | Purpose |
|------|---------|
| [../PMOVES.AI PLANS/CREATOR_NETWORK_CONTROL_PLANE.md](../PMOVES.AI%20PLANS/CREATOR_NETWORK_CONTROL_PLANE.md) | 2026 creator-network map across PMOVES.YT, Channel Monitor, Discord, Jellyfin, and Tokenism |
| [SUBMODULE_CODEX_HOMES/PMOVES-Creator.md](./SUBMODULE_CODEX_HOMES/PMOVES-Creator.md) | Creator strategy, networking, and campaign traversal |
| [SUBMODULE_CODEX_HOMES/PMOVES-Open-Notebook.md](./SUBMODULE_CODEX_HOMES/PMOVES-Open-Notebook.md) | Planning, drafting, evidence, and notebook memory traversal |
| [PMOVES_YT_CONTROL_WORKTREE_REVIEW.md](./PMOVES_YT_CONTROL_WORKTREE_REVIEW.md) | Worktree-first review path for PMOVES.YT, channel-monitor, transcribe-and-fetch, Jellyfin, and model routing |
| [JELLYFIN_CREATOR_WORKTREE_REVIEW.md](./JELLYFIN_CREATOR_WORKTREE_REVIEW.md) | Current creator/Jellyfin worktree findings and follow-ups |
| [SUBMODULE_CODEX_HOMES/PMOVES.YT.md](./SUBMODULE_CODEX_HOMES/PMOVES.YT.md) | Codex home for YouTube ingest and creator control |
| [SUBMODULE_CODEX_HOMES/PMOVES-transcribe-and-fetch.md](./SUBMODULE_CODEX_HOMES/PMOVES-transcribe-and-fetch.md) | Codex home for transcript and fetch support |
| [../PMOVESCHIT/CATACLYSM_STUDIOS_INC.md](../PMOVESCHIT/CATACLYSM_STUDIOS_INC.md) | Cataclysm Studios platform/brand context that governs creator operations |

### Tier 5: Vision & Notes (12 files)

Cultural anchors, aspirational notes, and vision documents.

| File | Purpose |
|------|---------|
| [AGNOTE4482.md](./AGNOTE4482.md) | Health/Wealth integration snapshot (TAC phases 1-4 created) |
| [AGNOTE4482PHI.t1.md](./AGNOTE4482PHI.t1.md) | Active agent claim/release tracking |
| [AGNOTE4482.BEATS.md](./AGNOTE4482.BEATS.md) | Aspirational/cultural anchor (4 lines) |
| [AGNOTE4482.FlOO$.md](./AGNOTE4482.FlOO%24.md) | FlOO$ lyrical/cultural anchor |
| [AGNOTE4482FLUTE.md](./AGNOTE4482FLUTE.md) | Flute voice stack aspirational (4 lines) |
| [AGNOTE4482DnB.PHI.Orchestra.md](./AGNOTE4482DnB.PHI.Orchestra.md) | Z890 DnB convergence score — dual jewels, topology, handoff to 4090+5090 |
| [agent_vision_notes.md](./agent_vision_notes.md) | Prosodic bridge spec (BPM encoder — implemented in `pmoves/tools/bpm_encoder.py`, 574 lines, PR #1168) |
| [agnotes2.md](./agnotes2.md) | Shell output snapshot (historical) |
| [agnotes3.md](./agnotes3.md) | 4-line vision note (historical) |
| [CRUSH_OPERATOR_HOME.md](./CRUSH_OPERATOR_HOME.md) | Crush CLI companion operator guide |
| [DARKXSIDE_SIGNATURE.md](./DARKXSIDE_SIGNATURE.md) | DARKXSIDE agent signature definition |
| [ALIGNED_IMPLEMENTATION_ROADMAP.md](./ALIGNED_IMPLEMENTATION_ROADMAP.md) | Phase 1-3 implementation framework |
| [IMPLEMENTATION_GAP_ANALYSIS.md](./IMPLEMENTATION_GAP_ANALYSIS.md) | Gap analysis (updated 2026-03-01 with Phase 1 completions) |

### Tier 6: Audit & Review (4+ files)

Security audits, production readiness, and review artifacts.

| File | Purpose |
|------|---------|
| [SUBMODULE_AUDIT_REFERENCE.md](./SUBMODULE_AUDIT_REFERENCE.md) | Phase C submodule audit reference (8 critical submodules) |
| [PRODUCTION_AUDIT_SUBAGENT_PLAN.md](./PRODUCTION_AUDIT_SUBAGENT_PLAN.md) | 6-lane production audit roadmap |
| [GRAPHITI_SIG_REVIEW_2026-02-21.md](./GRAPHITI_SIG_REVIEW_2026-02-21.md) | Phase 5 Graphiti signature review snapshot |
| [CODERABBIT_HARDENING_PROFILE.md](./CODERABBIT_HARDENING_PROFILE.md) | CodeRabbit review configuration for hardening |
| [AI_GRAPHITI_PROTOCOL.md](./AI_GRAPHITI_PROTOCOL.md) | Graphiti trail attribution protocol |

### Tier 7: Submodule Homes (35+ files)

Per-submodule Codex operator overlays. See [SUBMODULE_CODEX_HOMES/README.md](./SUBMODULE_CODEX_HOMES/README.md).

### Reference Documents

Strategic and theoretical foundations (preserve as-is, no regular updates needed).

| File | Purpose |
|------|---------|
| [AI Agent Integration and Best Practices.md](<./AI Agent Integration and Best Practices.md>) | A2A blueprint and thread engineering patterns |
| [Aligning AI Agents with Indy Dev Dan.md](<./Aligning AI Agents with Indy Dev Dan.md>) | ~~Theoretical foundation~~ **ARCHIVED (2026-04-19)** — see `archive/founding-strategy/` |
| [PMOVES.AI Agentic Architecture Deep Dive.md](<./PMOVES.AI Agentic Architecture Deep Dive.md>) | Architecture deep dive with geometric cognitive architectures |

### Additional Files

| File | Purpose |
|------|---------|
| [OPERATION_DOCK_TIER_GIT_FLARE_PARITY.md](./OPERATION_DOCK_TIER_GIT_FLARE_PARITY.md) | Git parity runbook |
| [CODEX_SUBMODULE_INTEGRATION_AUDIT.md](./CODEX_SUBMODULE_INTEGRATION_AUDIT.md) | Submodule integration audit |
| [TOOLING_SCRIPT_AUDIT.md](./TOOLING_SCRIPT_AUDIT.md) | Tooling/script audit |
| [TBE_IMPLEMENTATION_CROSS_REFERENCE.md](./TBE_IMPLEMENTATION_CROSS_REFERENCE.md) | Thread-based engineering cross-reference |
| [HARDWARE_TTS_REQUIREMENTS.md](./HARDWARE_TTS_REQUIREMENTS.md) | TTS hardware requirements |
| [PMOVES_Engine_Templates.md](./PMOVES_Engine_Templates.md) | Engine template definitions |
| [JELLYFIN_CREATOR_WORKTREE_REVIEW.md](./JELLYFIN_CREATOR_WORKTREE_REVIEW.md) | Jellyfin/Creator worktree review |

---

## Quick Links

- **Agent count:** 71 registered agents (+ 13 external contributors) (`python -m pmoves.tools.agent_taxonomy_helper list`)
- **External contributors:** 13 listed in `pmoves/config/agent_registry.yaml` (`claude-opus`, `kilocode`, `codex`, `gemini`, `cline`, `powerfulmoves`, `crush`, `z890-claude`, `5090-claude`, `4090-claude`, `botz-architect`, `botz-builder`, `botz-auditor`)
- **Taxonomy version:** v1.5.0
- **Persona seeds:** 8 standard personas in `pmoves/supabase/initdb/17_persona_seed.sql`
- **Model registry:** `pmoves/config/gpu-models.yaml`
- **Skill pairings:** `pmoves/configs/skill-pairings.yaml` (7 FlOO$ pairings)
- **Model Integration Framework:** `pmoves/docs/PMOVES_MODEL_INTEGRATION_FRAMEWORK.md`
- **Submodule skill routing:** `pmoves/configs/submodule_skill_registry.json`
- **Mermaid diagrams:** 5 regenerable via `python -m pmoves.tools.agent_taxonomy_helper`

---

## Known Gaps (P0-P2)

| Priority | Gap | Owner |
|----------|-----|-------|
| ~~P0~~ | ~~BoTZ JWT HAS_JOSE fail-open~~ | **RESOLVED** — BoTZ PR #79 merged. `gateway.py` and `auth.py` both return HTTPException 500 (fail-closed) when HAS_JOSE or JWT_SECRET is missing. Verified 2026-04-01. |
| P0 | ~100+ unauthenticated NATS references in `pmoves/` (grep: `nats://(nats\|localhost):4222` excluding `@`; count varies by submodule state) | Batch migration not yet started — refs span services, integrations, docs |
| P0 | A2A server (`/.well-known/agent.json`) — code exists at `services/agent-zero/python/features/a2a/server.py` but compose exposure unconfirmed | Runtime verification needed |
| ~~P1~~ | ~~BoTZ Gateway integration speculative~~ | **ARCHIVED (2026-04-19)** — BoTZ era doc moved to `archive/founding-strategy/`. Discord now via ClaWZ. |
| ~~P2~~ | ~~BPM encoder spec exists but `bpm_encoder.py` not implemented~~ | **RESOLVED** — `pmoves/tools/bpm_encoder.py` implemented (574 lines), delivered in PR #1168 (Shift Crew tools, 2026-04-01). |
| P2 | Observability Map (`OBSERVABILITY_MAP.md`) referenced but doesn't exist | Create from Production Audit Lane C |

---

## Naming Conventions

- **SUBMODULE_CODEX_HOMES:** Files named by submodule path (`<submodule-basename>.md`)
  - Standard class: `PMOVES-Agent-Zero.md`
  - Specialized class: `Pmoves-cipher.md`
  - Path-based: `pmoves__integrations__archon.md` (double-underscore separators)
- **Main docs:** SCREAMING_SNAKE_CASE for operational docs, Title Case for reference/theoretical docs
