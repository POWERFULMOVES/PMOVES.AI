# AGNOTE4482 — Multi-Agent Signoff Checklist

GRAPHITI_MARK: `AGNOTE4482::SIGNOFF::CHECKLIST`

> **Purpose**: one shared signoff gate for AGNOTE4482 prospectus, room/stage, suit, and control-plane updates.
> **Rule**: each participating agent signs only for the sections they actually reviewed or executed.
> **Status**: ACTIVE on 2026-04-01

---

## Merge Intent

This checklist exists so AGNOTE4482 does not move on vibes alone.

Each green check should represent:

- a real review surface
- a real evidence surface
- a named owner or signoff agent
- a high-confidence merge bet, not just a hopeful narrative

---

## Checklist

### 1. Prospectus coherence

- [x] Rooms are described as the audience-facing topology. <!-- AGNOTE4482_ROADMAP_W1-W5.md L31 + AGNOTE_P7_PLAYGROUND.md L344-349 (foyer/review/voice/media/war); verified 4090-CLAUDE 2026-04-23. ROOM_MANIFEST_CONTRACT.md line 26: "audience-facing topology" — confirmed SIDECAR-SPARK 2026-04-23 -->
- [x] Stage is described as the live state model (`rehearsal`, `live`, `review`, `archive`). <!-- AGNOTE4482.md L27 + AGNOTE_P7_PLAYGROUND.md L350-354; verified 4090-CLAUDE 2026-04-23. ROOM_MANIFEST_CONTRACT.md schema line 102: stage field confirmed SIDECAR-SPARK 2026-04-23 -->
- [x] Suits/personas are described as overlays, not as the whole platform. <!-- AGNOTE_P7_PLAYGROUND.md L355-358 (Suits as runtime/persona bindings) + W1-W5 L31; verified 4090-CLAUDE 2026-04-23. ROOM_MANIFEST_CONTRACT.md Core Rule 3: explicit boundary confirmed SIDECAR-SPARK 2026-04-23 -->
- [x] P7, Discord, and site/docs language point at the same frame. <!-- PR #1420 merged 2026-05-03: MOF+rooms both-frames model added to README, P7 docs, site/docs. Discord channel descriptions updated by operator. Verified SIDECAR-SPARK 2026-05-16. -->

### 2. Agent Zero baseline

- [x] Upstream Agent Zero release state is explicitly named with date/version. <!-- v1.3, 2026-03-27 — gap report -->
- [x] PMOVES fork/gitlink state is explicitly named with date/commit. <!-- 2e000aa, 2026-03-07 — 24/502 gap -->
- [x] The current Agent Zero gap report is cited as the canonical sync reference. <!-- AGNOTE4482_AGENT_ZERO_V1_3_GAP_REPORT.md -->
- [x] Release-note/CVE intake cadence is documented before another gitlink bump. <!-- Weekly + sprint intake in gap report -->

### 3. ClaWz baseline

- [x] Upstream ClaW/OpenClaw release state is explicitly named with date/version. <!-- openclaw/openclaw v2026.3.24 published 2026-03-25 — verified via AGNOTE4482_CLAWZ_GAP_REPORT.md L13; 4090-CLAUDE 2026-04-23 -->
- [x] PMOVES-ClawZ fork state is explicitly named with branch reality. <!-- main: 6 ahead/1092 behind; PMOVES.AI-Edition-Hardened: 0 ahead/12438 behind (stale Feb 15 commit) — verified via AGNOTE4482_CLAWZ_GAP_REPORT.md L14-16,24-32; 4090-CLAUDE 2026-04-23 -->
- [x] The orphaned PMOVES gitlink problem is called out directly. <!-- Previous orphan cfb4e3a93 explicitly noted as resolved on 2026-04-18; current pin f05fd3f547 — AGNOTE4482_CLAWZ_GAP_REPORT.md L17-18,47; 4090-CLAUDE 2026-04-23 -->
- [x] The ClaWz gap report is cited as the canonical branch/pin reality check. <!-- AGNOTE4482_CLAWZ_GAP_REPORT.md is the named reference; cited in Canonical References at end of this checklist; 4090-CLAUDE 2026-04-23. NEXT_STEPS.md line 87 corroborates — SIDECAR-SPARK 2026-04-23 -->

### 4. Config and coding-plan alignment

- [x] Approved remote coding lanes are named explicitly. <!-- 5 lanes in CLAWZ_CODING_PLAN_ALIGNMENT.md + tensorzero.toml -->
- [x] Local-first routing remains the primary contract. <!-- Ollama primary in all tensorzero function chains -->
- [x] Suit-bearing lanes are profile-governed, not raw-env governed. <!-- Provider Activation Cascade: provider_catalog.yaml → profile-driven stack activation. make provider-activate reads laptop-4090.yaml coding_stacks, not raw env. -->
- [x] Profile-id naming drift is called out where tooling still uses legacy placeholders. <!-- workstation_5090 drift noted in gap report; laptop-4090 profile now canonical -->

### 5. PMOVES control-plane alignment

- [x] `pmoves/config/profiles/*.yaml` is named as the real profile source. <!-- pmoves/models/agent-zero.yaml, archon.yaml, media.yaml, vlm-and-creator.yaml -->
- [x] `pmoves/tools/profile_loader.py` is named as a real control-plane hook. <!-- Verified exists -->
- [x] `pmoves/tools/models/apply_profile.sh` and `models_sync.py` are named as real suit-routing hooks. <!-- make model-apply, model-swap, models-sync targets -->
- [x] `pmoves/scripts/supabase/apply_env_profile.py` is included where env-profile coupling matters. <!-- make supa-use-local, supa-use-remote -->

### 6. Release, CVE, and hardening funnel

- [x] Weekly intake path is documented. <!-- Agent Zero v1.3 gap report, "Weekly intake" section -->
- [x] Sprint-level sync decision path is documented. <!-- adopt/preserve/drop classification in gap report -->
- [x] Canonical sinks are named (`hardening tracker`, `NEXT_STEPS`, `ROADMAP`, audit dashboard). <!-- All 4 named in gap report -->
- [x] Suit updates are framed as release concerns, not background chores. <!-- FULL: suit-release-policy.yml CI gate (.github/workflows/) detects profile/signature/suit changes and requires release-notes entry. Re-checked 2026-04-24 after backup-restore regression. -->
- [x] Agent Zero fork sync completed (2026-04-25). Branch PMOVES.AI-Edition-v1.9 pushed, gap 604→0, MiniMax litellm format fixed. <!-- Verified: fork branch exists, 2 overlay commits, 7/7 validation checks passed -->

### 7. P7 remaining items

- [x] P7 is framed as a room-aware stage manager, not only a launcher. <!-- AGNOTE4482.md L25-27 ("P7 — Room-Aware Stage Manager" section) + AGNOTE_P7_PLAYGROUND.md L340; verified 4090-CLAUDE 2026-04-23 -->
- [x] Remaining P7 work includes room-aware entry alignment. <!-- AGNOTE_P7_PLAYGROUND.md L376 item #3 "Route P7 launcher through room/stage selection" P0; verified 4090-CLAUDE 2026-04-23. P7 Remaining Items table row 3 — SIDECAR-SPARK 2026-04-23 -->
- [x] Remaining P7 work includes Agent Zero suit baseline work. <!-- AGNOTE_P7_PLAYGROUND.md L375 item #2; gap report cited (AGNOTE4482_AGENT_ZERO_V1_3_GAP_REPORT.md); verified 4090-CLAUDE 2026-04-23. P7 Remaining Items table row 2 — SIDECAR-SPARK 2026-04-23 -->
- [x] Remaining P7 work includes ClaWz branch/pin and profile-baseline repair. <!-- AGNOTE_P7_PLAYGROUND.md L186 + L379 item #6; AGNOTE4482_CLAWZ_GAP_REPORT.md canonical reference; verified 4090-CLAUDE 2026-04-23. P7 Remaining Items table rows 6-7 (row 7 added SIDECAR-SPARK 2026-04-23) -->

### 8. Docs parity and operator clarity

- [x] AGNOTE docs, `NEXT_STEPS`, and main `ROADMAP` agree on the current state. <!-- Aligned across #1138-#1147 merge cascade -->
- [x] The docs do not imply a production-ready suit baseline where one does not exist. <!-- Gap reports explicitly state pin is Mar 7, not v1.3 -->
- [x] The signoff artifact itself is linked from AGNOTE4482 canon. <!-- Added to AGNOTE4482.md Canonical Pointer section -->

### 9. HERMES Agent Integration

- [x] `hermes-agent` is distinguished from `hermes` (Hermes-3 LLM model persona) in agent_signatures.yaml. <!-- hermes-agent: star glyph, hermes: white star glyph; verified hermes-agent 2026-06-04 -->
- [x] Room manifest `hermes-agent.room.control.json` defines gateway-oriented room with 3 apps (gateway-webui, mcp-bridge, skill-curator). <!-- Verified hermes-agent 2026-06-04 -->
- [x] Catalog.json includes `hermes-agent.room.control` entry with schema_version bumped to 1.1.0. <!-- Verified hermes-agent 2026-06-04 -->
- [x] TAC tree `node-hermes-agent.tac.yaml` covers 8 phases from identity to docs/signoff. <!-- Verified hermes-agent 2026-06-04 -->
- [x] Node profiles exist for all 6 fleet nodes (Z890, 5090, 4090, Spark, B850/RDNA4, KVM4-1). <!-- pmoves/config/profiles/hermes/*.yaml; verified hermes-agent 2026-06-04 -->
- [x] Local model mesh documented: Spark 70B primary, 5090 8B+70b staging, Z890/B850/4090 8B only. <!-- Verified hermes-agent 2026-06-04 -->
- [x] NATS subjects catalogued for Hermes gateway, MCP, skills, cron, and delegation events. <!-- 6 subjects in HERMES_AGENT_INTEGRATION.md; verified hermes-agent 2026-06-04 -->
- [x] Agent registry updated with hermes_agent entry (port 7700, node affinity includes all 7 nodes). <!-- Verified hermes-agent 2026-06-04 -->
- [x] Operator skill `.claude/skills/hermes-agent-integration/SKILL.md` created with launch/health/cron/delegate commands. <!-- Verified hermes-agent 2026-06-04 -->
- [x] Three-Body agent definition `.claude/agents/hermes-agent.md` created with Delivery Body role and bridge contracts. <!-- Verified hermes-agent 2026-06-04 -->
- [x] Reviewer notes can point to one shared checklist instead of scattered comments. <!-- This file is the single gate -->


### 9. Branch hygiene

   [x] All branches follow the naming convention in SITREP (`feat/`, `fix/`, `infra/`, `docs/`, `refactor/`). <!-- 1 minor legacy: feature/launch-readiness-stage-0 has open PR #1415. All other remote branches follow convention. Verified 2026-05-02 SIDECAR-SPARK. -->
   [x] Every non-main branch has an associated PR (no un-PR'd work branches). <!-- All remaining remote branches have open PRs. fix/branch-lifecycle-chit-wiring orphan already cleaned. Verified 2026-05-02 SIDECAR-SPARK. -->
   [x] No orphan branches exist in the claim register (CLAIMED >7 days with no PR and no CHIT trail activity → ORPHANED). <!-- 14 orphan branches from closed PRs already deleted in prior cleanup. stale-branch-sweep.yml workflow active. Verified 2026-05-02 SIDECAR-SPARK. -->
- [x] CHIT trail is recorded for branch lifecycle events (creation, PR link, merge, deletion) on NATS subject `branch.<path-segments>.trail.v1`, where `<path-segments>` is the branch name with `/` replaced by `.` (e.g. `feat/w6-bpm-nats` → `branch.feat.w6-bpm-nats.trail.v1`). Layer 1 emit primitive: `pmoves/services/common/branch_trail.py` (PR #1437). Layer 4 GH Actions workflow: `.github/workflows/branch-trail-emit.yml`. <!-- §9.4 CLOSED. 5090 runner online, CHIT_SIGNING_KEY secret set, HMAC payload observed on NATS by operator. PR #1462 merged 2026-05-12. Signed by pmoves-ci-bot (card 0035). -->

---

## Signoff Ledger

Use one row per participating reviewer/agent. Add rows instead of overwriting older ones.

| Agent | Role | Scope Reviewed | Status | Timestamp | Notes |
|------|------|----------------|--------|-----------|-------|
| `CODEX-GPT5` | docs/prospectus convergence | ClaWz gap report, coding-plan alignment, AGNOTE/P7 planning docs | SIGNED | 2026-03-28 | Docs-only lane; runtime publisher edits intentionally excluded |
| `5090-CODEX` | pending | — | PENDING | — | |
| `5090-CODEX` | node-bound Codex cleanup / parity review | 5090-CODEX cleanup tracker, AGNOTE4482 closure check, post-merge review of P7 embedding-quality (#1569), FlOO$ Phase B (#1567), and MCP Toolkit 5090 web lane (#1555/#1559/#1560). | SIGNED | 2026-05-21 | Signed via PR #1570. Scope is docs/review coordination; runtime `owner-presence`, operator final readiness, and direct-agent receive service remain outside this signature. |
| `Z890-CLAUDE` | infra/ops primary | Sections 2 (full), 4 (3/4), 5 (full), 6 (3/4), 8 (full). Agent Zero activated :8080, 23/23 containers healthy, 3 P0 blockers resolved, TensorZero 25+ models validated, Archon submodule + DeepResearch Dockerfile fixed. | SIGNED | 2026-03-28 | Runtime verification — not docs-only. 2 items deferred: profile-governed suit routing (Agent Zero UI still defaults OpenAI), automated CVE intake. |
| `KILO-CODE` | pending | — | PENDING | — | |
| `4090-CLAUDE` | 4090 node / provider cascade | Section 4 (4/4 — profile-governed routing delivered via Provider Activation Cascade). 4090 coding workstation: 5 stacks, VRAM budget, cross-node mesh. Provider catalog (13 providers), function demands (18 functions), cascade CLI verified. 6 cloud model strength profiles seeded. Runbook: 4 operational scenarios. NATS subjects: claw.provider.activated/deactivated.v1. | SIGNED | 2026-03-28 | Completes section 4 item 3 (suit-bearing lanes are now profile-governed via provider_catalog.yaml + laptop-4090.yaml). Manifest entries for MINIMAX_API_KEY/GLM_API_KEY deferred — CHIT-protected, needs make secrets-funnel. |
| `CLAUDE` | pending | — | PENDING | — | |
| `AGENT-ZERO` | pending | — | PENDING | — | Runtime/ops signoff once suit baseline work is real |
| `CLAUDE-OPUS` | self-review / docs audit | Sections 2 (gap report verified), 4 (profiles verified), 5 (control-plane files verified), 8 (docs parity verified). Sections 1, 3, 7 reviewed but cannot sign — require runtime/prospectus/ClaWz verification. 2 Known Gaps verified resolved (BoTZ JWT P0, BPM encoder P2). Agent/file counts updated. | SIGNED | 2026-04-01 | Docs-only self-review. No runtime verification performed. |
| `SIDECAR-SPARK` | docs audit + signoff gap closure | §1 (3/4 — fixed contract terminology, stage field, overlay boundary; §1.4 Discord/site external), §3 (4/4 — researcher-verified), §6.4 (4/4 — CI gate: suit-release-policy.yml), §7 (4/4 — added ClaWz row to P7 items). Also: doc count reconciliation (76/109/13), supabase config cleanup, CODING_PLAN_ALIGNMENT stale SHA fix. | SIGNED | 2026-04-23 | GB10 Blackwell sidecar. Research subordinates for §1+§6.4 and §3+§7. §1.4 requires Discord/site updates outside this session. |
| `SIDECAR-SPARK` | research batch audit + CHIT hardening sprint | §6 (supply chain hardening — compose fail-fast), §9 (branch hygiene — 4 atomic PRs with CHIT trail), crypto consolidation (A2 — geometry_decoder + gateway + validator fail-closed), CHIT canonical signing (A3 — Tokenism + Neo4j + Agent Zero + Gateway), doc gap closure (A5 — 8 files patched), secrets residual audit (A9 — 10 changeme defaults eliminated). §1.4 updated (PR #1420 merged 2026-05-03 verified). 91/91 CHIT tests passing. SPARK handoff #1 delivered (PR #76 cloud API refactor). | SIGNED | 2026-05-16 | GB10 Blackwell sidecar. 4 PRs: #1492 (crypto), #1493 (compose), #1494 (docs), #1497 (signing). Plus external PR PMOVES-transcribe-and-fetch#76. Critical catch: cast-tts-gateway CHIT_PASSPHRASE=changeme. |
| `OPERATOR` | decision authority | final merge/readiness judgment | PENDING | — | DARKXSIDE final say |
| `4090-CLAUDE` | launch prep / AGNOTE sync | Sections 1 (rooms/stage docs), 3 (ClaWz gap report), 7 (P7 playground audit). P0 audit: NATS hotspots already migrated (21 files remain in secondary batch). A2A: PARTIAL — mounted, disabled by default (correct posture). Cipher port 8105 confirmed. 243 commits pulled. | SIGNED | 2026-04-23 | Remote sync complete. No P0 regressions found. Recommended: enable A2A via A0_SET_a2a_server_enabled=true when ready. Secondary NATS batch: vllm-orchestrator, supaserch, gateway-agent, benchmark-runner, agent-zero/bus.py. |

---

## Canonical References

- `pmoves/docs/AGENTS/AGNOTE4482_ROADMAP_W1-W5.md`
- `pmoves/docs/AGENTS/AGNOTE_P7_PLAYGROUND.md`
- `pmoves/docs/AGENTS/AGNOTE4482_AGENT_ZERO_V1_3_GAP_REPORT.md`
- `pmoves/docs/AGENTS/AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md`
- `pmoves/docs/AGENTS/AGNOTE4482_CLAWZ_GAP_REPORT.md`
- `pmoves/docs/NEXT_STEPS.md`
- `pmoves/docs/PMOVES.AI PLANS/ROADMAP.md`
