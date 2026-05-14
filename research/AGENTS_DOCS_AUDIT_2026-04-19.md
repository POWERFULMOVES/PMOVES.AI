# PMOVES.AI AGENTS/ Documentation Audit — 2026-04-19

**Scope**: `pmoves/docs/AGENTS/` (109 files: 108 .md + 1 other) + root-level BoTZ/Discord docs
**Context**: 15 PRs merged in 48h incl. CHIT P0-P3 (#1294), portable sidecar (#1299), A2A compose (#1293), rooms-on-a-stage README (#1308), Archon PR #12 (36 commits)

> **Note:** File count is a snapshot from `find pmoves/docs/AGENTS/ -type f | wc -l` at audit time. Actual count may differ after PR #1311 doc refresh (archived 4, updated 5).

---

## 1. Full File Inventory

| # | Filename | Lines | Last Modified | Assessment |
|---|----------|------:|---------------|------------|
| 1 | AGENT_CONTEXT_PATTERNS.md | 336 | Apr 17 | needs-update |
| 2 | AGENT_RESILIENCE_PATTERNS.md | 304 | Apr 17 | needs-update |
| 3 | AGENT_TAXONOMY_CROSS_REFERENCE.md | 117 | Apr 17 | stale |
| 4 | agent_vision_notes.md | 3 | Apr 17 | stale (stub) |
| 5 | AGNOTE4482_AGENT_ZERO_V1_3_GAP_REPORT.md | 131 | Apr 17 | needs-update |
| 6 | AGNOTE4482.BEATS.md | 329 | Apr 17 | current |
| 7 | AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md | 164 | Apr 17 | current |
| 8 | AGNOTE4482_CLAWZ_GAP_REPORT.md | 155 | Apr 19 | current |
| 9 | AGNOTE4482DnB.PHI.Orchestra.md | 272 | Apr 17 | current |
| 10 | AGNOTE4482.FlOO$.bpm.cgp.json | 449 | Apr 17 | current |
| 11 | AGNOTE4482.FlOO$.md | 55 | Apr 17 | current |
| 12 | AGNOTE4482FLUTE.md | 4 | Apr 17 | stale (stub) |
| 13 | **AGNOTE4482.md** | 216 | Apr 19 | needs-update |
| 14 | AGNOTE4482PHI.5090-SUBMODULE-AUDIT.md | 171 | Apr 17 | stale |
| 15 | AGNOTE4482PHI.t1.md | 610 | Apr 17 | needs-update |
| 16 | AGNOTE4482_ROADMAP_W1-W5.md | 570 | Apr 19 | current |
| 17 | AGNOTE4482_SIGNOFF_CHECKLIST.md | 110 | Apr 17 | needs-update |
| 18 | AGNOTE4482_SITREP.md | 120 | Apr 17 | stale |
| 19 | AGNOTE-dgx-spark.md | 22 | Apr 18 | current |
| 20 | AGNOTE_P7_PLAYGROUND.md | 684 | Apr 17 | needs-update |
| 21 | agnotes2.md | 1062 | Apr 18 | current (living) |
| 22 | agnotes3.md | 96 | Apr 17 | stale |
| 23 | AI Agent Integration and Best Practices.md | 492 | Apr 17 | stale |
| 24 | AI_GRAPHITI_PROTOCOL.md | 344 | Apr 17 | stale |
| 25 | ALIGNED_IMPLEMENTATION_ROADMAP.md | 1092 | Apr 17 | stale |
| 26 | Aligning AI Agents with Indy Dev Dan.md | 398 | Apr 17 | **superseded** |
| 27 | **BOTZ_GATEWAY_AGENT_INTEGRATION.md** | 442 | Apr 17 | **superseded** |
| 28 | CODERABBIT_HARDENING_PROFILE.md | 40 | Apr 17 | current |
| 29 | CODEX_CIPHER_MEMORY_IMPLEMENTATION_MAP.md | 99 | Apr 17 | stale |
| 30 | CODEX_CLAUDE_PARITY_GAPS.md | 69 | Apr 17 | stale |
| 31 | CODEX_CLAUDE_PARITY_MAP.md | 218 | Apr 17 | stale |
| 32 | CODEX_ECOSYSTEM_TRAVERSAL.md | 196 | Apr 17 | stale |
| 33 | CODEX_OPERATOR_HOME.md | 292 | Apr 17 | stale |
| 34 | CODEX_PERSONA_STYLE_PLAYBOOK.md | 27 | Apr 17 | stale (stub) |
| 35 | CODEX_RUNTIME_PROTOCOL.md | 105 | Apr 17 | stale |
| 36 | CODEX_SUBMODULE_INTEGRATION_AUDIT.md | 54 | Apr 17 | stale |
| 37 | CRUSH_OPERATOR_HOME.md | 138 | Apr 17 | needs-update |
| 38 | DARKXSIDE_SIGNATURE.md | 92 | Apr 17 | current |
| 39 | DEEP_DIVE_ALIGNMENT_2026-03-15.md | 183 | Apr 17 | stale |
| 40 | gepeto-SKILL.md | 479 | Apr 17 | current |
| 41 | GITHUB_APP_CREDENTIALS.md | 455 | Apr 17 | needs-update |
| 42 | GRAPHITI_SIG_REVIEW_2026-02-21.md | 45 | Apr 17 | stale (snapshot) |
| 43 | HANDOFF_CLAUDE_GRAPHITI_4482_2026-03-04.md | 62 | Apr 17 | stale (handoff) |
| 44 | HARDWARE_TTS_REQUIREMENTS.md | 646 | Apr 17 | needs-update |
| 45 | IMPLEMENTATION_GAP_ANALYSIS.md | 363 | Apr 17 | stale |
| 46 | JELLYFIN_CREATOR_WORKTREE_REVIEW.md | 66 | Apr 17 | stale (snapshot) |
| 47 | KRISS_KROSS_ACCORD.md | 124 | Apr 17 | needs-update |
| 48 | KRISS_KROSS_ACK.md | 130 | Apr 17 | needs-update |
| 49 | MINIMAX_CLAUDE_PARITY_MAP.md | 160 | Apr 17 | stale |
| 50 | MINIMAX_GLM_PARITY_ANALYSIS.md | 418 | Apr 17 | stale |
| 51 | OPERATION_DOCK_TIER_GIT_FLARE_PARITY.md | 42 | Apr 17 | stale |
| 52 | OPERATOR_FACING_CLAUDE_MD_MIRRORS.md | 139 | Apr 18 | current |
| 53 | **PERSONAS.md** | 549 | Apr 17 | needs-update |
| 54 | Pinokio-SKILL.md | 204 | Apr 17 | current |
| 55 | **PMOVES_AGENT_CLASS_TAXONOMY.md** | 496 | Apr 17 | **stale** |
| 56 | **PMOVES_AGENT_TOPOLOGY.md** | 524 | Apr 17 | **stale** |
| 57 | PMOVES.AI Agentic Architecture Deep Dive.md | 237 | Apr 17 | stale |
| 58 | PMOVES_Engine_Templates.md | 106 | Apr 17 | stale |
| 59 | PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md | 219 | Apr 17 | needs-update |
| 60 | PmovesSKillZ.md | 43 | Apr 17 | stale |
| 61 | PMOVES_UNIFIED_AGENT_TAXONOMY.md | 79 | Apr 17 | stale |
| 62 | PMOVES_YT_CONTROL_WORKTREE_REVIEW.md | 222 | Apr 17 | stale (snapshot) |
| 63 | PRODUCTION_AUDIT_SUBAGENT_PLAN.md | 146 | Apr 17 | stale |
| 64 | **README.md** | 218 | Apr 17 | needs-update |
| 65 | SUBMODULE_ATOMIC_PR_STRATEGY_2026-03-03.md | 72 | Apr 17 | stale (snapshot) |
| 66 | SUBMODULE_AUDIT_REFERENCE.md | 89 | Apr 17 | stale |
| 67 | SUBMODULE_CODEX_HOMES/ (38 files) | 658 | Apr 17 | stale (stubs) |
| 68 | TBE_IMPLEMENTATION_CROSS_REFERENCE.md | 539 | Apr 17 | stale |
| 69 | TOOLING_SCRIPT_AUDIT.md | 181 | Apr 17 | needs-update |

### Summary Counts

| Assessment | Count | % |
|------------|------:|--:|
| current | 10 | 11% |
| needs-update | 18 | 19% |
| stale | 37 | 40% |
| superseded | 2 | 2% |
| stale (stub/snapshot) | 26 | 28% |

---

## 2. Specific Findings by File

### 2.1 SUPERCCEEDED Files

#### `BOTZ_GATEWAY_AGENT_INTEGRATION.md` (442 lines)
- **What's wrong**: Entirely describes BoTZ Gateway (port 8054) and Gateway Agent (port 8100) as the primary Discord work distribution layer. No mention of ClaWZ/OpenClaw. Architecture diagram shows BoTZ CLI instances claiming work items — this workflow is superseded by ClaWZ.
- **What to do**: Add bold SUPERCCEEDED header pointing to ClaWZ gap report + coding plan alignment. Do NOT delete (historical reference for port/NATS subject decisions), but mark clearly.

#### `Aligning AI Agents with Indy Dev Dan.md` (398 lines)
- **What's wrong**: Early-stage strategic document from the IndyDevDan framework era. References ElizaOS, Venice.ai, "Codebase Singularity" concepts that are no longer the primary framing. The root BoTZ plan (below) is the evolved version of this same thinking.
- **What to do**: Move to `pmoves/docs/archive/` or add SUPERCCEEDED header.

### 2.2 STALE Files Requiring Priority Update

#### `PMOVES_AGENT_CLASS_TAXONOMY.md` (496 lines)
- **What's wrong**:
  - Header says "v1.4.0 (60 agents)" — actual registry has **71 agents** (per AGNOTE4482 self-review Apr 1)
  - No ClaWZ/OpenClaw entry in agent roster
  - BoTZ Gateway listed as Stage 1 agent with NATS subjects — should note ClaWZ transition
  - References `BOTZ_GATEWAY_AGENT_INTEGRATION.md` as source doc
  - ~~Publisher-Discord listed as active agent — `services/publisher-discord/` directory confirmed missing~~ **CORRECTION**: `services/publisher-discord/` exists (main.py, Dockerfile, tests, docker-compose.yml:2848, Makefile). Original claim was wrong — service is implemented.
  - Channel Monitor listed as Base stage — no ClaWZ equivalent for Discord interaction
- **What to do**: Bump to v1.5.0, update agent count to 71, add ClaWZ/OpenClaw entry, add ClaWZ-Ship subgraph equivalent, note BoTZ→ClaWZ transition. (Publisher-Discord is implemented — no action needed for that entry.)

#### `PMOVES_AGENT_TOPOLOGY.md` (524 lines)
- **What's wrong**:
  - Same "v1.4.0 (60 agents)" header
  - `BOTZ_SHIP["BoTZ Ship — Agent Runtime"]` subgraph is the primary agent runtime visual — no ClaWZ-Ship equivalent
  - NATS subject diagram lists `botz.heartbeat.v1`, `botz.register.v1`, `botz.workitem.*` — all BoTZ-specific
  - No A2A compose wiring visual (PR #1293)
  - No portable sidecar topology
- **What to do**: Add ClaWZ-Ship subgraph (or ClaWZ/OpenClaw integration node), add A2A wiring to topology, update agent count, add portable sidecar as deployment variant.

#### `AGNOTE4482.md` (216 lines)
- **What's wrong**:
  - Topology Audit Record (2026-02-20) references TAC_BOTZ.md and BoTZ as active — no ClaWZ note
  - P7 section is good (room-aware stage manager documented)
  - Missing: portable sidecar config (#1299), rooms-on-a-stage README (#1308), CHIT P0-P3 completion (#1294 full scope)
  - Self-Review (2026-04-01) noted NATS auth P0 (57 refs) — status unchanged, needs re-check post-#1294
  - No Archon PR #12 mention (nested sub recovery + MCP integration)
- **What to do**: Add convergence record for Apr 17-19 merge wave (#1293, #1294, #1299, #1308), note ClaWZ supersession of BoTZ in topology audit, re-verify NATS auth P0 count.

#### `PERSONAS.md` (549 lines)
- **What's wrong**:
  - Does NOT reference AGNOTE4482 as canonical source for suits/personas governance
  - No link to ClaWZ coding plan alignment (which defines suits as Class A/B/C)
  - "325+ personas" claim — not verified against current DB state
  - No mention of suits concept (rooms→stage→suits model from ClaWZ gap report)
  - Seed examples use `claude-sonnet-4-5`, `claude-opus-4-5`, `claude-haiku-4-5` — model names may need updating
  - CHIT integration code examples reference `from chit import hyperbolic_encoder` — verify this import path still valid
- **What to do**: Add canonical pointer to AGNOTE4482, add suits section cross-referencing ClaWZ coding plan alignment, verify persona count, update model names.

#### `README.md` (218 lines)
- **What's wrong**:
  - Line 50: "Discord and BoTZ for agent-mediated response" — no ClaWZ mention
  - Line 79: BOTZ_GATEWAY_AGENT_INTEGRATION.md listed as "speculative — not yet implemented" — should note superseded
  - Line 116: Creator network control plane references Discord without ClaWZ context
  - Line 188: External contributors list includes `botz-architect`, `botz-builder`, `botz-auditor` — should add ClaWZ contributors if any
  - Line 202: BoTZ JWT fail-open marked resolved — correct, but no ClaWZ security posture
- **What to do**: Add ClaWZ to Discord interaction line, update BOTZ gateway reference to superseded, add ClaWZ contributors, add ClaWZ security posture note.

#### `AGNOTE4482_AGENT_ZERO_V1_3_GAP_REPORT.md` (131 lines)
- **What's wrong**:
  - Validated Mar 28 — 3 weeks stale, 15 PRs merged since
  - Says "502 upstream-only commits" — this gap has likely grown
  - PMOVES pin still at `2e000aa` (March 7) per report — need to verify if #1299 or any recent PR updated the pin
  - No mention of portable sidecar implications for v1.3 sync
- **What to do**: Re-validate fork pin against current submodule state, update commit math, add sidecar deployment implications.

### 2.3 STALE Snapshot/Stub Files (Batch)

These are one-time audit/handoff/review artifacts that have served their purpose:

- `GRAPHITI_SIG_REVIEW_2026-02-21.md` — Feb 21 snapshot
- `HANDOFF_CLAUDE_GRAPHITI_4482_2026-03-04.md` — Mar 4 handoff
- `JELLYFIN_CREATOR_WORKTREE_REVIEW.md` — worktree review snapshot
- `PMOVES_YT_CONTROL_WORKTREE_REVIEW.md` — worktree review snapshot
- `SUBMODULE_ATOMIC_PR_STRATEGY_2026-03-03.md` — Mar 3 strategy snapshot
- `agent_vision_notes.md` — 3-line stub
- `AGNOTE4482FLUTE.md` — 4-line stub
- `CODEX_PERSONA_STYLE_PLAYBOOK.md` — 27-line stub
- All 38 `SUBMODULE_CODEX_HOMES/*.md` files — stub index cards

**Recommendation**: Move snapshots to `pmoves/docs/archive/` or `pmoves/docs/AGENTS/archive/`. Keep stubs if they serve as a living index, otherwise archive.

### 2.4 CODEX-era Files (Batch — 8 files)

These documents reference the "CODEX" agent persona (pre-Claude Code era):
- CODEX_CIPHER_MEMORY_IMPLEMENTATION_MAP.md
- CODEX_CLAUDE_PARITY_GAPS.md
- CODEX_CLAUDE_PARITY_MAP.md
- CODEX_ECOSYSTEM_TRAVERSAL.md
- CODEX_OPERATOR_HOME.md
- CODEX_PERSONA_STYLE_PLAYBOOK.md
- CODEX_RUNTIME_PROTOCOL.md
- CODEX_SUBMODULE_INTEGRATION_AUDIT.md

**Recommendation**: If CODEX is still an active agent identity, update references. If CODEX has been replaced by Claude Code / GLM / other agents, mark as historical. Total: ~1,060 lines.

---

## 3. AGNOTE4482 as Canonical Suits/Personas Reference

### Current State

AGNOTE4482 is a **living convergence record** (not a structured reference doc). It works well for:
- Audit trail (who did what, when, with what ACK)
- Cross-referencing other AGNOTE docs
- P7 room-aware stage manager definition
- Signoff governance

### What's Missing for Canonical Suits/Personas

| Gap | Detail |
|-----|--------|
| No suits definition section | AGNOTE4482 never defines "suits" — the term appears only in ClaWZ gap report ("suits are the runtime/operator overlays") and coding plan alignment (Class A/B/C) |
| No PERSONAS.md backlink | PERSONAS.md does not reference AGNOTE4482 — the two docs are disconnected |
| No ClaWZ integration doc | No single AGENTS/ file explains how ClaWZ replaces BoTZ for Discord interaction, what the integration architecture looks like, or how suits map to ClaWZ profiles |
| No rooms-on-a-stage model doc | P7 section mentions rooms but no doc explains the rooms→stage→suits model end-to-end |
| Stale SITREP | AGNOTE4482_SITREP.md (120 lines) was the cold-start orientation doc — last updated Apr 17 but likely still references old state |

### Recommendation

AGNOTE4482 should remain the governance/audit convergence record. But PMOVES needs a **separate canonical reference** for the suits/personas system that:
1. Defines suits (Class A/B/C from coding plan alignment)
2. Links to PERSONAS.md for the DB schema and seed data
3. Links to ClaWZ gap report for fork/pin state
4. Documents the rooms→stage→suits→profile selection chain
5. Is referenced by both AGNOTE4482 and PERSONAS.md

**Candidate location**: `pmoves/docs/AGENTS/PMOVES_SUITS_FRAMEWORK.md` (new file)

---

## 4. Root-Level BoTZ/Discord Docs — Cross-Reference

### `PMOVES-BoTZ-PLAN_w_INDY_DEV_DAN.md` (398 lines)

**Content**: Strategic architecture blueprint based on IndyDevDan's "Principled AI Coding" and "Thread-Based Engineering" frameworks. Describes "Codebase Singularity," Class 1-3 agents, Core Four primitives (Context/Model/Prompt/Tools), thread taxonomy (Base/Parallel/Chained/Fusion/Big/Zero Touch).

**Tech stack referenced**: Claude Code, mprocs, Verdant, ElizaOS (implied), n8n

**Status**: **SUPERCCEEDED** — This was the founding strategic document. The AGNOTE4482 suite has entirely replaced its governance role. The IndyDevDan framework concepts (threads, primitives) have been absorbed into PMOVES_AGENT_CLASS_TAXONOMY.md and AGNOTE4482PHI.t1.md in evolved form.

### `PMOVES Edition Comprehensive Discord Bot Architecture.md` (1797 lines)

**Content**: Extremely detailed Discord bot architecture: ElizaOS framework, Venice.ai Pro as LLM provider (qwen3-235b, venice-uncensored, mistral-31-24b), FastMCP, Discord.py 2.0+, n8n workflows, Supabase pgvector (3584-dim), Redis caching, three server contexts (Personal/Cataclysm Studios/UNFCU), character files with JSON configs, Coolify deployment.

**Status**: **SUPERCCEEDED** — ClaWZ/OpenClaw has replaced ElizaOS+Venice.ai+Discord.py as the primary Discord interaction layer. The multi-server context concept may still be relevant but the entire technology stack is wrong.

### Recommendation

| Doc | Lines | Action |
|-----|------:|--------|
| PMOVES-BoTZ-PLAN_w_INDY_DEV_DAN.md | 398 | Move to `pmoves/docs/archive/founding-strategy/` with SUPERCCEEDED header. Valuable as historical context for why PMOVES exists. |
| PMOVES Edition Comprehensive Discord Bot Architecture.md | 1797 | Move to `pmoves/docs/archive/founding-strategy/` with SUPERCCEEDED header. The ElizaOS/Venice.ai integration details are completely wrong for current stack but may have reusable pattern ideas (multi-server context isolation, character file structure). |

**Do NOT merge into AGENTS/** — they describe a different system. Archive with clear headers so no agent mistakenly treats them as current.

---

## 5. New Capabilities from Recent PRs — Documentation Gaps

| PR | Capability | AGENTS/ Doc Exists? | Gap |
|----|-----------|---------------------|-----|
| #1294 | CHIT crypto P0-P3 (full crypto stack: lazy accessor, sys.path, numpy guard, key separation, fail-closed passphrase, versioned KDF) | Partially in AGNOTE4482.md (post-merge section) | No dedicated CHIT crypto status doc. AGNOTE4482 mentions #1294 superseded #1275+#1279 but doesn't enumerate the 4 P-levels resolved. |
| #1299 | Portable sidecar config (standalone mode, any-device deployment, Ollama via host.docker.internal) | No | Zero AGENTS/ documentation. The sidecar config is only in `PMOVES_AI_CONFIG.promptinclude.md`. Need: sidecar deployment model doc, how it relates to docked mode, agent profile implications. |
| #1293 | A2A compose wiring (create_a2a_router, env vars, main.py mount) | Partially in AGNOTE4482.md (Apr 17 section) | No A2A integration architecture doc in AGENTS/. The topology has no A2A visual. Need: A2A endpoint catalog, auth model, compose vs standalone modes. |
| #1308 | Rooms-on-a-stage README | No (only unmerged remote branch) | Critical missing doc. The rooms→stage→suits model is referenced in 6+ AGNOTE files but has no canonical explanation. P7 section in AGNOTE4482 touches it but is insufficient. |
| Archon #12 | Nested sub recovery + MCP integration + Pinokio TTS | No | No Archon update in AGENTS/ since Feb. Archon listed as Stage 2 in taxonomy — need to verify if MCP integration bumps it. Pinokio TTS integration not documented. |
| ClaWZ fork pin fix | Root gitlink repaired (f05fd3f547) | In AGNOTE4482_CLAWZ_GAP_REPORT.md | Gap report updated but ClaWZ fork still 1092 behind upstream. No integration architecture doc. |

---

## 6. Priority Action Matrix

### P0 — This Sprint

| Action | File(s) | Effort |
|--------|---------|--------|
| Add SUPERCCEEDED headers to root BoTZ/Discord docs | 2 root files | 10 min |
| Move root BoTZ/Discord docs to `pmoves/docs/archive/founding-strategy/` | 2 root files | 5 min |
| Add SUPERCCEEDED header to BOTZ_GATEWAY_AGENT_INTEGRATION.md | 1 AGENTS file | 5 min |
| Update taxonomy header: 60→71 agents, date, version | PMOVES_AGENT_CLASS_TAXONOMY.md | 15 min |
| Update topology header: 60→71 agents, date, version | PMOVES_AGENT_TOPOLOGY.md | 10 min |
| Update README.md Discord line to mention ClaWZ | README.md | 10 min |

### P1 — Next Sprint

| Action | File(s) | Effort |
|--------|---------|--------|
| Create `PMOVES_SUITS_FRAMEWORK.md` (canonical suits reference) | New file | 2-3 hr |
| Add ClaWZ-Ship subgraph to topology | PMOVES_AGENT_TOPOLOGY.md | 1 hr |
| Add A2A wiring to topology | PMOVES_AGENT_TOPOLOGY.md | 30 min |
| Create portable sidecar deployment doc | New file | 1-2 hr |
| Create rooms-on-a-stage model doc | New file | 2-3 hr |
| Add AGNOTE4482 convergence record for Apr 17-19 merge wave | AGNOTE4482.md | 30 min |
| Link PERSONAS.md to AGNOTE4482 | PERSONAS.md | 15 min |
| Re-validate v1.3 gap report (commit math, pin state) | AGNOTE4482_AGENT_ZERO_V1_3_GAP_REPORT.md | 30 min |

### P2 — Backlog

| Action | File(s) | Effort |
|--------|---------|--------|
| Create ClaWZ integration architecture doc | New file | 3-4 hr |
| Update Archon section in taxonomy/topology (MCP, Pinokio TTS, nested sub recovery) | 2 files | 1 hr |
| Archive CODEX-era files (8 files, 1060 lines) | 8 files | 30 min |
| Archive snapshot/stub files (26+ files) | 26+ files | 30 min |
| Verify/reconcile persona count (325+ claim vs DB state) | PERSONAS.md | 30 min |
| Update CHIT integration code examples in PERSONAS.md | PERSONAS.md | 30 min |
| Re-verify NATS auth P0 count (was 57 refs across 34 files) | AGNOTE4482.md | 30 min |

---

## 7. Key Metrics

| Metric | Value |
|--------|-------|
| Total AGENTS/ files | 109 |
| Current docs | 10 (9%) |
| Needs-update docs | 18 (17%) |
| Stale docs | 37 (34%) |
| Superseded docs | 2 (2%) |
| Stale stubs/snapshots | 26 (24%) |
| Uncategorized files | 16 (15%) — added after initial audit; not yet classified |
| Files referencing BoTZ as primary | 8+ |
| Files referencing ClaWZ | 12 |
| Dedicated ClaWZ integration doc | 0 |
| Dedicated suits framework doc | 0 |
| Dedicated rooms-on-a-stage doc | 0 |
| Dedicated portable sidecar doc | 0 |
| Dedicated A2A wiring doc | 0 |
| Root-level superseded docs (lines) | 2,195 |
| CODEX-era stale docs (lines) | ~1,060 |
