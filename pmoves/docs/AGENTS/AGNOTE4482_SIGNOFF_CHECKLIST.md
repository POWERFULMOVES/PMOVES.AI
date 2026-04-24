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

- [x] Rooms are described as the audience-facing topology. <!-- ROOM_MANIFEST_CONTRACT.md line 26: "audience-facing topology" — fixed 2026-04-23 -->
- [x] Stage is described as the live state model (`rehearsal`, `live`, `review`, `archive`). <!-- ROOM_MANIFEST_CONTRACT.md schema line 102: stage field added 2026-04-23 -->
- [x] Suits/personas are described as overlays, not as the whole platform. <!-- ROOM_MANIFEST_CONTRACT.md Core Rule 3: explicit boundary statement added 2026-04-23 -->
- [ ] P7, Discord, and site/docs language point at the same frame. <!-- FAIL: ROADMAP and NEXT_STEPS explicitly state this alignment has NOT happened yet. Requires Discord channel descriptions + site updates. -->

### 2. Agent Zero baseline

- [x] Upstream Agent Zero release state is explicitly named with date/version. <!-- v1.3, 2026-03-27 — gap report -->
- [x] PMOVES fork/gitlink state is explicitly named with date/commit. <!-- 2e000aa, 2026-03-07 — 24/502 gap -->
- [x] The current Agent Zero gap report is cited as the canonical sync reference. <!-- AGNOTE4482_AGENT_ZERO_V1_3_GAP_REPORT.md -->
- [x] Release-note/CVE intake cadence is documented before another gitlink bump. <!-- Weekly + sprint intake in gap report -->

### 3. ClaWz baseline

- [x] Upstream ClaW/OpenClaw release state is explicitly named with date/version. <!-- CLAWZ_GAP_REPORT: v2026.3.24, March 25, 2026 -->
- [x] PMOVES-ClawZ fork state is explicitly named with branch reality. <!-- CLAWZ_GAP_REPORT: main branch, no releases/tags, hardened branch Feb 15 -->
- [x] The orphaned PMOVES gitlink problem is called out directly. <!-- CLAWZ_GAP_REPORT: resolved 2026-04-18, before/after SHAs recorded -->
- [x] The ClaWz gap report is cited as the canonical branch/pin reality check. <!-- NEXT_STEPS.md line 87: "canonical ClaWz branch/pin reality check" -->

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
- [ ] Suit updates are framed as release concerns, not background chores. <!-- PARTIAL: standing rule added to hardening tracker 2026-04-23; no CI gate automation yet -->

### 7. P7 remaining items

- [x] P7 is framed as a room-aware stage manager, not only a launcher. <!-- AGNOTE4482.md line 27, AGNOTE_P7_PLAYGROUND.md line 340 -->
- [x] Remaining P7 work includes room-aware entry alignment. <!-- P7 Remaining Items table row 3, P0 -->
- [x] Remaining P7 work includes Agent Zero suit baseline work. <!-- P7 Remaining Items table row 2, P0 -->
- [x] Remaining P7 work includes ClaWz branch/pin and profile-baseline repair. <!-- P7 Remaining Items table rows 6-7, P0 — row 7 added 2026-04-23 -->

### 8. Docs parity and operator clarity

- [x] AGNOTE docs, `NEXT_STEPS`, and main `ROADMAP` agree on the current state. <!-- Aligned across #1138-#1147 merge cascade -->
- [x] The docs do not imply a production-ready suit baseline where one does not exist. <!-- Gap reports explicitly state pin is Mar 7, not v1.3 -->
- [x] The signoff artifact itself is linked from AGNOTE4482 canon. <!-- Added to AGNOTE4482.md Canonical Pointer section -->
- [x] Reviewer notes can point to one shared checklist instead of scattered comments. <!-- This file is the single gate -->


### 9. Branch hygiene

- [ ] All branches follow the naming convention in SITREP (`feat/`, `fix/`, `infra/`, `docs/`, `refactor/`).
- [ ] Every non-main branch has an associated PR (no un-PR'd work branches).
- [ ] No orphan branches exist in the claim register (CLAIMED >7 days with no PR and no CHIT trail activity → ORPHANED).
- [ ] CHIT trail is recorded for branch lifecycle events (creation, PR link, merge, deletion) on NATS subject `branch.{branch_name}.trail.v1`.

---

## Signoff Ledger

Use one row per participating reviewer/agent. Add rows instead of overwriting older ones.

| Agent | Role | Scope Reviewed | Status | Timestamp | Notes |
|------|------|----------------|--------|-----------|-------|
| `CODEX-GPT5` | docs/prospectus convergence | ClaWz gap report, coding-plan alignment, AGNOTE/P7 planning docs | SIGNED | 2026-03-28 | Docs-only lane; runtime publisher edits intentionally excluded |
| `5090-CODEX` | pending | — | PENDING | — | |
| `Z890-CLAUDE` | infra/ops primary | Sections 2 (full), 4 (3/4), 5 (full), 6 (3/4), 8 (full). Agent Zero activated :8080, 23/23 containers healthy, 3 P0 blockers resolved, TensorZero 25+ models validated, Archon submodule + DeepResearch Dockerfile fixed. | SIGNED | 2026-03-28 | Runtime verification — not docs-only. 2 items deferred: profile-governed suit routing (Agent Zero UI still defaults OpenAI), automated CVE intake. |
| `KILO-CODE` | pending | — | PENDING | — | |
| `4090-CLAUDE` | 4090 node / provider cascade | Section 4 (4/4 — profile-governed routing delivered via Provider Activation Cascade). 4090 coding workstation: 5 stacks, VRAM budget, cross-node mesh. Provider catalog (13 providers), function demands (18 functions), cascade CLI verified. 6 cloud model strength profiles seeded. Runbook: 4 operational scenarios. NATS subjects: claw.provider.activated/deactivated.v1. | SIGNED | 2026-03-28 | Completes section 4 item 3 (suit-bearing lanes are now profile-governed via provider_catalog.yaml + laptop-4090.yaml). Manifest entries for MINIMAX_API_KEY/GLM_API_KEY deferred — CHIT-protected, needs make secrets-funnel. |
| `CLAUDE` | pending | — | PENDING | — | |
| `AGENT-ZERO` | pending | — | PENDING | — | Runtime/ops signoff once suit baseline work is real |
| `CLAUDE-OPUS` | self-review / docs audit | Sections 2 (gap report verified), 4 (profiles verified), 5 (control-plane files verified), 8 (docs parity verified). Sections 1, 3, 7 reviewed but cannot sign — require runtime/prospectus/ClaWz verification. 2 Known Gaps verified resolved (BoTZ JWT P0, BPM encoder P2). Agent/file counts updated. | SIGNED | 2026-04-01 | Docs-only self-review. No runtime verification performed. |
| `SIDECAR-SPARK` | docs audit + signoff gap closure | §1 (3/4 — fixed contract terminology, stage field, overlay boundary; §1.4 Discord/site external), §3 (4/4 — researcher-verified), §6.4 (4/4 — CI gate: suit-release-policy.yml), §7 (4/4 — added ClaWz row to P7 items). Also: doc count reconciliation (76/109/13), supabase config cleanup, CODING_PLAN_ALIGNMENT stale SHA fix. | SIGNED | 2026-04-23 | GB10 Blackwell sidecar. Research subordinates for §1+§6.4 and §3+§7. §1.4 requires Discord/site updates outside this session. |
| `OPERATOR` | decision authority | final merge/readiness judgment | PENDING | — | DARKXSIDE final say |

---

## Canonical References

- `pmoves/docs/AGENTS/AGNOTE4482_ROADMAP_W1-W5.md`
- `pmoves/docs/AGENTS/AGNOTE_P7_PLAYGROUND.md`
- `pmoves/docs/AGENTS/AGNOTE4482_AGENT_ZERO_V1_3_GAP_REPORT.md`
- `pmoves/docs/AGENTS/AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md`
- `pmoves/docs/AGENTS/AGNOTE4482_CLAWZ_GAP_REPORT.md`
- `pmoves/docs/NEXT_STEPS.md`
- `pmoves/docs/PMOVES.AI PLANS/ROADMAP.md`
