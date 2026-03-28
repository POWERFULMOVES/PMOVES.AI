# AGNOTE4482 — Multi-Agent Signoff Checklist

GRAPHITI_MARK: `AGNOTE4482::SIGNOFF::CHECKLIST`

> **Purpose**: one shared signoff gate for AGNOTE4482 prospectus, room/stage, suit, and control-plane updates.
> **Rule**: each participating agent signs only for the sections they actually reviewed or executed.
> **Status**: ACTIVE on 2026-03-28

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

- [ ] Rooms are described as the audience-facing topology.
- [ ] Stage is described as the live state model (`rehearsal`, `live`, `review`, `archive`).
- [ ] Suits/personas are described as overlays, not as the whole platform.
- [ ] P7, Discord, and site/docs language point at the same frame.

### 2. Agent Zero baseline

- [ ] Upstream Agent Zero release state is explicitly named with date/version.
- [ ] PMOVES fork/gitlink state is explicitly named with date/commit.
- [ ] The current Agent Zero gap report is cited as the canonical sync reference.
- [ ] Release-note/CVE intake cadence is documented before another gitlink bump.

### 3. ClaWz baseline

- [ ] Upstream ClaW/OpenClaw release state is explicitly named with date/version.
- [ ] PMOVES-ClawZ fork state is explicitly named with branch reality.
- [ ] The orphaned PMOVES gitlink problem is called out directly.
- [ ] The ClaWz gap report is cited as the canonical branch/pin reality check.

### 4. Config and coding-plan alignment

- [ ] Approved remote coding lanes are named explicitly.
- [ ] Local-first routing remains the primary contract.
- [ ] Suit-bearing lanes are profile-governed, not raw-env governed.
- [ ] Profile-id naming drift is called out where tooling still uses legacy placeholders.

### 5. PMOVES control-plane alignment

- [ ] `pmoves/config/profiles/*.yaml` is named as the real profile source.
- [ ] `pmoves/tools/profile_loader.py` is named as a real control-plane hook.
- [ ] `pmoves/tools/models/apply_profile.sh` and `models_sync.py` are named as real suit-routing hooks.
- [ ] `pmoves/scripts/supabase/apply_env_profile.py` is included where env-profile coupling matters.

### 6. Release, CVE, and hardening funnel

- [ ] Weekly intake path is documented.
- [ ] Sprint-level sync decision path is documented.
- [ ] Canonical sinks are named (`hardening tracker`, `NEXT_STEPS`, `ROADMAP`, audit dashboard).
- [ ] Suit updates are framed as release concerns, not background chores.

### 7. P7 remaining items

- [ ] P7 is framed as a room-aware stage manager, not only a launcher.
- [ ] Remaining P7 work includes room-aware entry alignment.
- [ ] Remaining P7 work includes Agent Zero suit baseline work.
- [ ] Remaining P7 work includes ClaWz branch/pin and profile-baseline repair.

### 8. Docs parity and operator clarity

- [ ] AGNOTE docs, `NEXT_STEPS`, and main `ROADMAP` agree on the current state.
- [ ] The docs do not imply a production-ready suit baseline where one does not exist.
- [ ] The signoff artifact itself is linked from AGNOTE4482 canon.
- [ ] Reviewer notes can point to one shared checklist instead of scattered comments.

---

## Signoff Ledger

Use one row per participating reviewer/agent. Add rows instead of overwriting older ones.

| Agent | Role | Scope Reviewed | Status | Timestamp | Notes |
|------|------|----------------|--------|-----------|-------|
| `CODEX-GPT5` | docs/prospectus convergence | ClaWz gap report, coding-plan alignment, AGNOTE/P7 planning docs | SIGNED | 2026-03-28 | Docs-only lane; runtime publisher edits intentionally excluded |
| `5090-CODEX` | pending | — | PENDING | — | |
| `Z890-CODEX` | pending | — | PENDING | — | |
| `KILO-CODE` | pending | — | PENDING | — | |
| `CLAUDE` | pending | — | PENDING | — | |
| `AGENT-ZERO` | pending | — | PENDING | — | Runtime/ops signoff once suit baseline work is real |
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
