# AGNOTE4482 — ClaWz + Coding-Plan Alignment

GRAPHITI_MARK: `AGNOTE4482::CLAWZ::CODING_PLAN_ALIGNMENT`

> **Purpose**: make the PMOVES suit/config conversation respect the real paid coding lanes, the local-first hybrid-cloud contract, and the practical limit of how many Agent Zero / ClaW instances should run at once.
> **Validated with operator constraints on**: 2026-03-28

---

## Core Constraint

PMOVES should assume:

- **deep local-first hybrid cloud**
- **as many Agent Zero and ClaW instances as the infra can safely allow**
- **configs must stay coding-plan aligned**, not hardcoded around whichever remote provider happens to be easiest that day

This means suit growth is not just a UI/theme question. It is a control-plane question.

---

## Approved Remote Coding Inventory

These are the approved remote coding lanes currently in play and should be treated as named capacity, not vague cloud fallback.

| Lane | Inventory | Intended role in PMOVES |
|------|-----------|-------------------------|
| OpenAI | ChatGPT Business, 4 seats | approved OpenAI coding/review lane for high-trust operator work |
| Anthropic | Claude Code Max | primary Claude-oriented implementation/review lane |
| GLM | coding plan Max | approved coding-plan fallback / overflow lane |
| MiniMax | token plan | token-budget overflow lane where profile policy allows |
| Alibaba | coding plan | approved auxiliary coding-plan lane |

**Rule:** these lanes should be referenced by profile/policy names in PMOVES, not by one-off hardcoded endpoint assumptions.

---

## PMOVES Routing Posture

### 1. Local lanes stay primary

- local Ollama, vLLM, LM Studio-compatible endpoints, GPU orchestrator lanes, and on-box TTS/media services stay first
- remote coding plans are escalation and overflow lanes, not the default personality of the platform

### 2. Coding plans are role-bound

- Agent Zero / ClaW suits should use coding-plan-backed providers only where the role really needs them:
  - coding
  - review
  - long-context comparison
  - operator escalation
- creator/media/search/runtime lanes should remain local-first unless the model fabric explicitly says otherwise

### 3. Scale should be profile-governed

- "more suits" does **not** mean every instance gets unconstrained remote access
- concurrency and fallback should be determined by named profiles, seat/token limits, and node capacity
- safe density matters more than theoretical maximum count

---

## Existing PMOVES Hooks To Use

Use the tools already in-repo instead of inventing a parallel config path:

- `pmoves/tools/models/apply_profile.sh`
- `pmoves/tools/models/models_sync.py`
- `pmoves/tools/profile_loader.py`
- `pmoves/scripts/supabase/apply_env_profile.py`
- `pmoves/docs/MODEL_FABRIC_CONTRACT.md`

These should remain the bridge between:

- local-first model routing
- approved cloud/coding-plan fallbacks
- suit-specific profile selection in Agent Zero / PMOVES-ClawZ

---

## Safe Instance Classes

### Class A — Local-primary suits

- preferred default for most concurrent Agent Zero / ClaW instances
- backed by local routing, local GPUs, local storage, local observability

### Class B — Coding-plan-assisted suits

- used for coding/review/operator tasks where a paid remote lane is justified
- should be attached to explicit profiles and kept observable

### Class C — Escalation suits

- only for high-value or blocked work where local + lower-cost lanes are not enough
- should be deliberate, sparse, and reviewable

---

## Review Checklist For Future Suit Work

Before adding or expanding a new Agent Zero / ClaW suit:

1. Name the suit's intended room and stage role.
2. Decide whether it is Class A, B, or C.
3. Bind it to a profile, not a raw provider secret.
4. Verify local-first fallback remains intact.
5. Check seat/token/capacity implications against the approved inventory.
6. Make sure the room/stage docs and model-fabric contract reflect the change.

---

## Recommendation

The next clean move is:

1. keep Agent Zero `v1.3` sync as its own submodule lane
2. treat ClaWz/provider alignment as a shared profile contract across suits
3. make P7 the stage manager that selects:
   - room
   - stage
   - suit
   - profile

That gives PMOVES a path to scale many instances without letting config drift or subscription confusion become the hidden bottleneck.

---

## Current Repo Reality (2026-03-28)

The policy above is still correct, but the live ClaWz repo state is not as mature as the Agent Zero suit lane.

- upstream `openclaw/openclaw` is already shipping current releases, with `v2026.3.24` published on **March 25, 2026**
- the PMOVES fork `POWERFULMOVES/PMOVES-ClawZ` has no fork-specific releases/tags right now
- fork `PMOVES.AI-Edition-Hardened` is an old upstream-derived branch from **February 15, 2026**
- ~~the root PMOVES gitlink is pinned to `cfb4e3a936262315948628d2da32d7158c4fbb30`, which is not resolvable~~ — **RESOLVED 2026-04-18**: root now pins to `f05fd3f547` (see CLAWZ_GAP_REPORT)

**Interpretation:** ClaWz currently needs branch/pin repair more than it needs fresh suit ornamentation.

### Profile alignment is partly there, but naming drift remains

- the real repo-backed hardware profiles are:
  - `desktop-9950xd`
  - `intel-265kf-3090ti`
  - `laptop-4090`
  - `jetson-orin-nano`
  - `jetson-nano`
  - `esp32-sonatino`
- `pmoves/tools/models/apply_profile.sh` and the `Makefile` model targets still default `HOST=workstation_5090`
- there is no matching `workstation_5090` profile id in `pmoves/config/profiles`

**Implication:** coding-plan-aware ClaWz suits should be bound to the profile ids that actually exist in PMOVES, not to legacy host placeholders.

### Recommended artifact targets

When the team converts this from docs into runtime work, the main artifact set should be:

- `pmoves/config/profiles/*.yaml`
- `pmoves/tools/profile_loader.py`
- `pmoves/tools/models/apply_profile.sh`
- `pmoves/tools/models/models_sync.py`
- `pmoves/scripts/supabase/apply_env_profile.py`
- `pmoves/docs/AGENTS/AGNOTE4482_CLAWZ_GAP_REPORT.md`

That keeps ClaWz/provider alignment anchored to the real PMOVES control plane instead of drifting into one-off env conventions.
