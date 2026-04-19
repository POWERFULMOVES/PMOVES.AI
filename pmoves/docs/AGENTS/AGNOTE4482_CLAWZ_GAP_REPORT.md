# AGNOTE4482 — PMOVES-ClawZ Gap Report

GRAPHITI_MARK: `AGNOTE4482::CLAWZ::GAP_REPORT`

> **Purpose**: validate the real upstream ClaW/OpenClaw release state, compare it against the PMOVES fork and root gitlink, and identify the config-control work needed before more suit expansion.
> **Validated on**: 2026-03-28
> **Scope**: upstream `openclaw/openclaw`, fork `POWERFULMOVES/PMOVES-ClawZ`, and the PMOVES.AI root gitlink pin.

---

## Validated State

- **Upstream source of truth**: `openclaw/openclaw` published release `v2026.3.24` on **March 25, 2026**.
- **PMOVES fork reality**: `POWERFULMOVES/PMOVES-ClawZ` is a fork of `openclaw/openclaw`, last pushed on **March 25, 2026**, with default branch `main`.
- **Fork release reality**: the PMOVES fork currently publishes **no GitHub releases or tags** of its own.
- **Hardened branch reality**: `PMOVES.AI-Edition-Hardened` points at commit `85b267aae9aa95b6da2f6a000ec247dbdcff5351`, an upstream-derived commit from **February 15, 2026**.
- **Current PMOVES gitlink reality**: the root PMOVES.AI repo is pinned to submodule commit `f05fd3f547d3b061717f14582d92f14071f9caaa` (resolved — see Resolution Update below).
- **Important note**: the previous orphaned pin (`cfb4e3a93`) was resolved on 2026-04-18.

---

## Commit Math

- `openclaw/openclaw:main -> POWERFULMOVES/PMOVES-ClawZ:PMOVES.AI-Edition-Hardened`
  - ahead by `0`
  - behind by `12438`
- `openclaw/openclaw:main -> POWERFULMOVES/PMOVES-ClawZ:main`
  - ahead by `6` (PMOVES-specific commits: NATS bridge, Nemotron catalog, compose wiring, integration dossier, review fixes, merge)
  - behind by `1092`
- `POWERFULMOVES/PMOVES-ClawZ:PMOVES.AI-Edition-Hardened -> POWERFULMOVES/PMOVES-ClawZ:main`
  - fork `main` is ahead by `11346`
  - behind by `0`

**Interpretation:** both fork branches are behind upstream, but `main` is dramatically newer than `PMOVES.AI-Edition-Hardened`. The hardened branch does not currently look like a maintained PMOVES overlay line.

---

## What This Means

### 1. There is no meaningful PMOVES-specific ClaWz divergence yet

- both fork branches compare as pure upstream ancestors
- neither branch is ahead of upstream `main`
- the current PMOVES story is mostly branch naming and pin drift, not a durable PMOVES overlay pack

### 2. The root pin policy needs repair before more suit growth

- the root gitlink points to an orphaned SHA
- that makes the current root state hard to reason about, hard to reproduce, and hard to promote safely
- before more ClaW/P7 room-stage suit work, PMOVES should pin to a real, reviewable branch head

### 3. The fork still matters

- the fork is still the correct place to carry PMOVES-specific overlays once they are real
- `main` already appears to be the more current upstream mirror
- the next PMOVES-hardened ClaWz branch should likely start from current fork `main`, not the old February branch

---

## Config And Profile Alignment Reality

PMOVES already has the right kind of control-plane hooks for ClaWz, but the naming is not fully aligned yet.

### Current profile/control artifacts in root PMOVES

- `pmoves/config/profiles/*.yaml`
- `pmoves/tools/profile_loader.py`
- `pmoves/tools/models/apply_profile.sh`
- `pmoves/tools/models/models_sync.py`
- `pmoves/scripts/supabase/apply_env_profile.py`
- `pmoves/docs/MODEL_FABRIC_CONTRACT.md`

### Current profile IDs in repo

- `desktop-9950xd`
- `intel-265kf-3090ti`
- `laptop-4090`
- `jetson-orin-nano`
- `jetson-nano`
- `esp32-sonatino`

### Naming drift that should be fixed

- `pmoves/tools/models/apply_profile.sh` still defaults `HOST=workstation_5090`
- `pmoves/Makefile` model-profile targets still document and default `HOST=workstation_5090`
- there is **no** matching hardware profile id named `workstation_5090` in `pmoves/config/profiles`

**Interpretation:** PMOVES already has a profile system, but ClaWz/Agent Zero suit wiring should use the actual profile ids that exist in-repo instead of legacy host placeholders.

---

## Why ClaWz Still Belongs In The Prospectus

Even though the branch/pin state is weak, ClaWz is not irrelevant. The root repo already expects real alignment between PMOVES control-plane tooling and ClaWz profile/auth/runtime concepts.

Signals already present in PMOVES:

- `pmoves/docs/AGENTS/TOOLING_SCRIPT_AUDIT.md` maps PMOVES profile, auth, secret, onboarding, and token tooling to many `PMOVES-ClawZ` paths
- the profile lane already points at:
  - `PMOVES-ClawZ/src/cli/profile.ts`
  - `PMOVES-ClawZ/src/cli/profile-utils.ts`
  - `PMOVES-ClawZ/src/browser/profile-capabilities.ts`
  - `PMOVES-ClawZ/src/agents/model-ref-profile.ts`
- this means the right move is not to ignore ClaWz, but to bring its branch/pin policy back in line with the PMOVES control plane

---

## Release Notes And CVE Funnel

ClaWz should follow the same weekly/sprint intake discipline now established for Agent Zero.

### Weekly intake

- check upstream `openclaw/openclaw` releases and tags
- capture only actionable release or security changes
- route them into the hardening tracker instead of leaving them in operator memory

### Sprint intake

- compare the current PMOVES fork target branch against upstream
- classify changes into:
  - adopt
  - preserve PMOVES overlay
  - ignore
- record the decision in AGNOTE/P7 planning when the result changes the suit story

### Canonical sinks

- `docs/hardening/PMOVES-hardening-tracker.md`
- `pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md`
- `pmoves/docs/NEXT_STEPS.md`
- `pmoves/docs/PMOVES.AI PLANS/ROADMAP.md`

---

## Recommended Next Move

1. Stop treating the current orphaned gitlink as an acceptable baseline.
2. Decide whether the next controlled PMOVES-ClawZ base is:
   - fork `main`, or
   - a fresh hardened branch cut from fork `main`
3. Normalize ClaWz/Agent Zero suit configs onto the real profile ids in `pmoves/config/profiles/*.yaml`.
4. Only after that, add PMOVES-specific ClaWz overlays for rooms, stage, auth, or operator suits.
5. Keep release-note and CVE intake active so ClaWz does not repeat the same hidden drift pattern.

---

## Prospectus Implication

For AGNOTE4482 and P7, the clean frame is:

- **rooms** are the audience-facing topology
- **stage** is the live state model
- **suits** are the runtime/operator overlays

But for ClaWz, PMOVES should not pretend the suit rack is already curated. First fix the branch/pin baseline, then let the room-aware suit work grow on top of a real profile contract.
