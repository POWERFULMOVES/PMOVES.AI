# RFC — Deterministic Hardening Ratchet Across the Fork Fleet

**Status:** Draft · **Date:** 2026-09-20 · **Author:** 4090-claude
**Supersedes framing in:** PR #3116 RELEASE scope items 1 and 4

---

## 1. Problem

`PMOVES.AI-Edition-Hardened` was promoted to default branch on part of the fork
fleet and the promotion stopped partway. The branch was intended to carry a real
defense-in-depth posture — Docker Hardened Images practice plus GitHub security
best practice — and on the forks it is currently a name with nothing behind it.

This is not drift that a reconciliation pass fixes. It is structural:

> `hardening-validation.yml` triggers on
> `branches: [main, PMOVES.AI-Edition-Hardened, PMOVES.AI-Edition-Hardened-Integrations]`
> — branches **of PMOVES.AI**. It has no reach into any fork.

41 forks carry a branch named hardened. Zero of them run a hardening gate. There
is no mechanism by which they could, so "hardened" cannot mean anything on a fork
until one is built.

## 2. Measured state (2026-09-20)

All figures re-derived this session, not quoted from a prior report.

| Fact | Value | Source |
|---|---|---|
| Repos under POWERFULMOVES | 458 | `gh repo list --limit 1000` |
| Default branch = `PMOVES.AI-Edition-Hardened` | **41** | same |
| …present in `fork_registry.json` | 30 | cross-tab |
| …present in `fork-sync.yml` FORKS list | 20 | cross-tab |
| …unaccounted for by registry or its exclusion lists | **3** | cross-tab |
| Forks hardcoded in `fork-sync.yml` | 28 | heredoc parse |
| Registry entries | 84 (31 `sync:true`, 53 `sync:false`) | registry |
| Submodules in `.gitmodules` | 81 | parse |
| `hardening_ratchet` known gaps | 9 | `_known_gaps.yaml` |

The three unaccounted repos split into two different problems, which running the
gate made clear:

| Repo | Submodule? | Gate status |
|---|---|---|
| `PMOVES-n8n-FlooS` | yes | **already flagged** by `fork_registry_ratchet` today |
| `Pmoves-ComfyUI-VibeVoice` | no | no gate has any opinion about it |
| `Pmoves-a0-plugin-pmoves-notes` | no | no gate has any opinion about it |

The other eight initially flagged are legitimately declared in `_excluded` /
`_first_party`.

So the coverage cross-check is **not** broken — it catches the one repo in its
scope and reports it as an open problem. The real gap is narrower and different:
`_validate_coverage` binds registry ↔ `.gitmodules`, so a fork that is
hardened-default but *not a submodule* falls outside every existing check by
design. Two repos are in that state.

### 2.1 Four disagreeing sources of truth

| # | Source | Says | Maintained by |
|---|---|---|---|
| 1 | GitHub default branch | 41 hardened | **observed** |
| 2 | `fork_registry.json` `branch:` | 62 carry the override | hand |
| 3 | `fork-sync.yml` FORKS heredoc | 28 entries | hand |
| 4 | `.gitmodules` | 81 submodules | hand |

Only #1 is observed. The rest are assertions, and three of the four are
hand-maintained lists that nothing forces into agreement.

### 2.2 The dependency arrow points backwards

`fork_registry.json` `_schema` defines its own `branch` field as:

```json
"branch": "optional branch override (3rd FORKS column in fork-sync.yml)"
```

The registry is documented as a **shadow of the hardcoded list** it ought to be
the source for. 62 entries carry that override; only 28 repos appear in the
heredoc, so roughly 34 overrides describe a column in a list their repo is not
in. They are inert by construction and nothing reports them as inert.

`fork_registry.json` *does* appear in `fork-sync.yml` — at line 8, inside
`on.push.paths`. It is a **trigger, not an input**. Editing the registry launches
the sync; the sync then reads its hardcoded list and ignores the edit.

### 2.3 The consent hold is not enforced

The registry defines `sync: false` as *"explicitly opted out"*, and the reason
text on several entries is specific about why:

> *"Promoting to `sync: true` also widens the App-token scope (Workflows:write on
> the fork), so it is a deliberate, reviewable act rather than a default."*

Four repos are `sync:false` **and** in the workflow's hardcoded list:
`PMOVES.YT`, `PMOVES-crush`, `PMOVES-Headscale`, `PMOVES-Jellyfin`. The workflow
never reads the registry, so the opt-out has no effect. What protects them today
is the unrelated CRITICAL drift guard (`AHEAD_MAX` / `BEHIND_MAX`), a
cost-and-conflict heuristic whose thresholds are workflow inputs documented as
settable to `0` to disable. Incidental, not consent.

`PMOVES.YT` is simultaneously the cautionary example in
`fork_registry_ratchet._validate_coverage`'s own docstring and one of the four.

## 3. Constraints

### 3.1 POWERFULMOVES is a personal user account — verified

`gh api users/POWERFULMOVES --jq .type` → `User`.

This removes two roads that would otherwise be obvious:

| Capability | Availability | Evidence |
|---|---|---|
| Organization-level runners / runner groups | **unavailable** | `gh api orgs/POWERFULMOVES/actions/runners` → 404 |
| Required workflows via org rulesets | **unavailable** | org/enterprise only, Enterprise Cloud plan |

Central enforcement of a hardening gate across the fleet is therefore not merely
less preferable than per-fork self-gating — it is not offered on this account
type. **Self-gating per fork is the only available road.** Runners are
repository-level only.

### 3.2 Existing runner fleet

9 runners registered to `POWERFULMOVES/PMOVES.AI`, 6 online: `4090`, `b850` (×3,
2 online), `kvm4-1`, `kvm4-2`, `spark`, `elder-melchor` (offline). All
repo-scoped to PMOVES.AI. None are reachable from a fork today.

### 3.3 App scopes

The design needs two installation permissions:

| Permission | For | Status |
|---|---|---|
| `administration: write` | mint runner registration / JIT config tokens | requested by 6 workflows today |
| `workflows: write` | write `.github/workflows/` into a fork | requested by 2 workflows today |

Both are already requested by existing workflows, so neither is new to the fleet.
`workflows: write` is the exact scope the `sync:false` reasons were guarding —
this RFC is the "deliberate, reviewable act" those reasons asked for.

> **Not verified from this node.** `gh api user/installations` returns 403 for a
> non-App-authorized token. The live grant must be confirmed by an operator
> before rollout (§7 step 0). `deploy/runbooks/github-app-permission-matrix.md`
> is a *planning* table of estimates, not observed state.

## 4. Design

Principle: **derive, never declare.** One fact is observed; every list is a
derived assertion that either matches or fails CI.

### Rule 1 — the sync list is computed, not written

`fork-sync.yml` drops the `FORKS=` heredoc and reads `fork_registry.json` at run
time, selecting `sync: true`. The registry becomes the input it is already
documented to be, and the dependency arrow in §2.2 reverses.

Removes source-of-truth #3. Landable immediately; independent of everything else
in this RFC.

### Rule 2 — registry must match the observed default branch

A ratchet rule asserts, for every registry entry, that any `branch` override
agrees with the repo's actual default branch from the API. Disagreement fails.

This is the keystone: the default branch is *observed*, so it cannot drift from
itself. Requires one `gh repo list` call, so it runs in the fork-sync workflow
(networked) rather than in `fork_registry_ratchet.py`, which is deliberately a
no-network <100 ms PR gate and must stay that way.

Removes source-of-truth #2.

### Rule 3 — close the two gaps the coverage check cannot see

`fork_registry_ratchet._validate_coverage` already binds registry ↔ `.gitmodules`
and already flags `PMOVES-n8n-FlooS`. That one needs *fixing*, not a new rule —
declare it under `forks` with a reason, and the existing gate goes green.

The new rule covers the case the existing check cannot reach: a repo whose
observed default branch is hardened but which is **not a submodule**, and so
appears in no list at all (`Pmoves-ComfyUI-VibeVoice`,
`Pmoves-a0-plugin-pmoves-notes`). Rule 2's observed-default-branch enumeration
is what surfaces these, since it starts from the API rather than from
`.gitmodules`. Each must be declared or explicitly excluded, with a reason.

Its docstring already names the problem this RFC closes:

> *"the fork-sync lists, the registry and .gitmodules were three separate
> hand-maintained facts with nothing tying them together."*

Three facts named, two bound. Rules 1–2 bind the third.

### Rule 4 — hardened-default implies a hardening gate runs there

For every repo whose observed default branch is `PMOVES.AI-Edition-Hardened`, a
hardening workflow must exist in that repo and must be passing. A repo that
claims the name without the gate fails the ratchet.

This is what makes "hardened" mean something, and it is the bulk of the work.

## 5. Per-fork gate mechanics

### 5.1 Thin caller, central logic

Each hardened-default fork receives a small workflow that calls a reusable one
here:

```yaml
name: Hardening Validation
on:
  push:
    branches: [PMOVES.AI-Edition-Hardened]
  pull_request:
    branches: [PMOVES.AI-Edition-Hardened]
jobs:
  harden:
    uses: POWERFULMOVES/PMOVES.AI/.github/workflows/_hardening-ratchet.yml@main
    secrets: inherit
```

The ratchet logic stays in one place and is versioned here. Only the caller is
distributed, so a logic change is one commit in PMOVES.AI, not 41.

### 5.2 Fan-out is structurally impossible under this design

Each fork's workflow triggers on **that fork's own** push/PR. One repo updated
means one repo's checks run. This satisfies the "hardening checks should not run
on all repos when one is updated" constraint by construction rather than by
configuration.

The rejected central-matrix alternative had exactly the opposite property: any
change would scan all 41.

> Note: a reusable workflow invoked via `uses:` executes on the **caller's**
> runners, so each fork needs runner capacity of its own. That is §5.3.

### 5.3 Runners — ephemeral JIT on PMOVES hardware

Standing runners do not scale here: repo-level registration on a user account
would mean 41 long-lived runner processes for workloads that are idle almost
always. That contradicts the dynamic-fleet principle (on-demand, no wasted
electricity).

Proposed instead: **just-in-time ephemeral runners** on existing PMOVES hosts.

- `POST /repos/{owner}/{repo}/actions/runners/generate-jitconfig` (App,
  `administration: write`) mints a single-use config.
- A listener on the PMOVES hosts starts a container runner for one job, then the
  registration disappears.
- GitHub-hosted minutes are not consumed; the work stays on `4090` / `b850` /
  `spark` / `kvm4-*`.

> **Test first — do not assume.** The JIT endpoint takes a **required**
> `runner_group_id`, and runner groups are an organization feature. Whether a
> personal-account repository accepts a default group id is unverified. §7 step 1
> is a single-repo spike to settle it. If JIT is unavailable on this account
> type, fall back to registration tokens (`POST .../actions/runners/registration-token`,
> same App permission) with ephemeral `--ephemeral` runners, which is a heavier
> but well-trodden path.

### 5.4 What the gate checks

`pmoves/tools/hardening_ratchet.py` is the model to extend, not replace. It is
already deterministic in the way this RFC argues for:

- discovers Dockerfiles by scanning the tree — no hardcoded list
- baselines known gaps in `_known_gaps.yaml` (9 today)
- **only shrinks** — a fixed file still listed fails as `STALE`
- requires a written `reason` and a `kind:` to add an entry
- handles real edge cases: last-`USER`-wins ordering, `NO_FROM` fragments, and
  the #2285 incident where a hardening pass truncated 9 Dockerfiles

Its limitation is scope, not design: one control (non-root `USER`), one repo.
Defense-in-depth per Docker Hardened Images practice adds at least pinned base
digests, `cap_drop`, `no-new-privileges`, read-only rootfs, healthchecks, and
provenance/SBOM. Each additional control lands as another ratcheted check with
its own baseline, so no single step turns 41 repos red.

**Per-fork baselines.** Each fork carries its own `_known_gaps.yaml`. A shared
baseline would let one fork's debt mask another's.

## 6. What this does *not* do

- Does not convert POWERFULMOVES to an organization. Nothing here requires it.
- Does not change image paths or GHCR publishing.
- Does not promote any `sync:false` fork to `sync:true` — Rule 1 makes the
  registry authoritative, so those four stop being synced, which is what their
  recorded reason asked for.
- Does not touch the damage-control guard.

## 7. Rollout

| Step | Action | Gate |
|---|---|---|
| 0 | Operator confirms App holds `administration: write` + `workflows: write` | cannot be verified from a non-App token |
| 1 | JIT spike on **one** fork | settles §5.3; if it fails, switch to registration-token fallback |
| 2 | Land Rule 1 (registry-driven fork list) | independent; no new scope |
| 3 | Fix `PMOVES-n8n-FlooS` (existing gate already red); land Rule 3 for the two non-submodule repos | no new scope |
| 4 | Land Rule 2 (observed-default-branch check) | needs the networked call |
| 5 | Distribute thin caller to **one** hardened-default fork; verify end to end | first use of `workflows: write` |
| 6 | Widen to the remaining 40, baselining each | Rule 4 turns on per repo as it lands |

Steps 2 and 3 are unblocked by step 0 and can land first.

## 8. Open questions

1. **Do the 41 hardened-default forks have a `main` to fall back to**, or is
   hardened genuinely their only branch? Affects whether Rule 4 can demote a fork
   that cannot pass rather than blocking it.
2. **Baseline generosity.** A fresh `--write-baseline` on 41 forks records
   today's posture as acceptable. That is the only way to turn the gate on
   without mass red, but it means the initial number is a debt ledger, not a
   pass.
3. **`PMOVES.YT`** is both the ratchet docstring's cautionary example and one of
   the four bypassed repos. Worth confirming its hardened branch is what its
   `PMOVES.AI_INTEGRATION.md` authority claim assumes.

## 9. Related

- `pmoves/tools/hardening_ratchet.py` — the deterministic model reused here
- `pmoves/tools/fork_registry_ratchet.py` — Rules 2–3 extend it
- `.github/workflows/fork-sync.yml` — Rule 1 rewrites its fork list
- `.github/workflows/hardening-validation.yml` — parent-repo gate this extends
- `.github/workflows/_app-token.yml` — App token minting, already correct
- `deploy/runbooks/github-app-permission-matrix.md` — planning estimates, not
  observed grants
- PR #3116 — the RELEASE that handed over items 1 and 4
