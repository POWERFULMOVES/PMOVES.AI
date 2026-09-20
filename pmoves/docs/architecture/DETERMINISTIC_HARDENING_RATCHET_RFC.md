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

### 3.2 Existing runner fleet — capability-labelled, and already mapped

The fleet is not ad hoc. Node capability is probed by **glancer**
(`deploy/provision/glances-autodetect.{ps1,sh}` → `json-to-profile.py` →
`pmoves/config/profiles/<node>.yaml`, 20+ profiles including Jetson, Spark,
ESP32 and the desktop rigs), and the resulting runner labels are recorded in
`pmoves/config/runner_labels.json` (machine-emitted).

Labels are capability assertions, not names — `self-hosted, Linux, X64, ai-lab,
b850` / `self-hosted, Linux, ai-lab, ARM64, spark` / `self-hosted, Linux, X64,
vps, kvm4, production, kvm4-1`. A hardening job can therefore target capability
(`runs-on: [self-hosted, ai-lab]`) rather than a named host, and the arm64/x64
split is already expressed.

9 runners are registered to `POWERFULMOVES/PMOVES.AI`, 6 online: `4090`, `b850`
(×3, 2 online), `kvm4-1`, `kvm4-2`, `spark`; `elder-melchor` offline.

**Measured 2026-09-20 — every one of the 41 hardened-default forks reports
`total_count: 0` runners.** (Enumerated per repo; an earlier draft asserted this
by inference from PMOVES.AI alone, which was not evidence.)

So the gap is **registration, not hardware**. The capability-labelled fleet
exists and is profiled; no fork can currently reach it. This is what §5.3 has to
close, and it is why the count of *registrations* (41 × N) matters more than the
count of *machines* (~7).

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

Two constraints from the survey (§7.5) bind this rule:

- **Three outcomes, not two.** Emit `PASS` / `FAIL` / `N-A`, where `N-A` means
  the control has nothing to apply to (e.g. a repo with no Dockerfiles). `N-A`
  is reported separately and never counted as `PASS`.
- **Fail-open where there is no fallback.** On a fork with neither `main` nor
  `master`, the rule reports but does not block, until a fallback branch exists.
  Blocking the only branch of a repo turns a hardening gap into an outage.

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

### 5.2 Fan-out: one dimension is avoided, five are not

An earlier draft of this RFC claimed fan-out was "structurally impossible under
this design." That was wrong, and wrong in a way worth recording: it answered
one fan-out question, got a favourable answer, and generalised from it.

At 41 forks this is a fan-out problem in at least six dimensions:

| # | Dimension | Status under this design |
|---|---|---|
| 1 | **Trigger** — one repo's push firing checks on all 41 | **avoided.** Each fork's workflow triggers on that fork only |
| 2 | **Rollout** — distributing the caller workflow | 41 writes, each needing `workflows: write` |
| 3 | **Baselining** — generating `_known_gaps.yaml` | 41 scans |
| 4 | **Runner registration** | 41 registrations; **measured 2026-09-20: 0 of 41 forks have any runner** |
| 5 | **Central-workflow blast radius** | **not avoided** — see below |
| 6 | **Survey / audit** — "which forks comply?" | a 41-way query every time it is asked |

Only #1 is dissolved by the design. The operator constraint ("checks should not
run on all repos when one is updated") is specifically about #1, so it *is*
satisfied — but that is a narrow win, not a general property.

**#5 is the one that bites.** A caller pinned at
`uses: POWERFULMOVES/PMOVES.AI/.github/workflows/_hardening-ratchet.yml@main`
means a single commit to that file changes gate behaviour in 41 repositories on
their next run, with no staging ring and no announcement. That is runtime
fan-out with a one-commit blast radius.

Mitigation: **pin callers to a tag, not `@main`**, and promote the tag in rings
(1 fork → 5 → the rest). The ring structure is also what makes #2, #3 and #6
tractable, since each is naturally parallel and none of them is a single
sequential job.

> Note: a reusable workflow invoked via `uses:` executes on the **caller's**
> runners, so each fork needs runner capacity of its own. That is §5.3.

### 5.2.1 The rollout is a TAC fan-out, not a checklist

Dimensions 2, 3, 4 and 6 are parallel work over 41 independent targets, which is
exactly what this repo's TAC trees already model: `pmoves/configs/tac_schema.yaml`
gives each node an `action.type` (`file_exists` / `grep` / `command` / `http` /
`manual`), a `status`, children, and — critically — an **`agent_hint`** naming
the agent that should execute it. 47 trees exist and
`.github/workflows/validate-tac-ratchet.yml` validates them.

The rollout should therefore be authored as a TAC tree with one subtree per
fork, status rolling up at phase/parent nodes rather than being tracked per
leaf, rather than as prose steps in this document. That structure is what makes
41 targets legible and lets the work be dispatched in parallel instead of walked
serially.

### 5.3 Runners — ephemeral JIT on PMOVES hardware

Standing runners do not scale here: repo-level registration on a user account
would mean 41 long-lived runner processes for workloads that are idle almost
always. That contradicts the dynamic-fleet principle (on-demand, no wasted
electricity).

Proposed instead: **just-in-time ephemeral runners** on the existing
capability-labelled PMOVES hosts (§3.2). Because labels come from glancer
profiles rather than hostnames, a JIT runner can be minted with the capability
set the job asks for — an `arm64` hardening scan lands on `spark`, an `ai-lab`
scan on `b850` or `4090` — without any fork knowing which machine ran it.

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
| 5 | Distribute thin caller to **one** hardened-default fork, pinned to a **tag**; verify end to end | first use of `workflows: write` |
| 6 | Promote in rings — 1 → 5 → 35 — baselining each | bounds §5.2 #5 blast radius |

Step 6 is authored as a TAC tree (§5.2.1) with a subtree per fork, not as a
linear list. Ring membership is the parent node; per-fork status is the leaf.

Steps 2 and 3 are unblocked by step 0 and can land first.

## 7.5 Survey findings — all 41 hardened-default forks, 2026-09-20

Surveyed in parallel across four agents. Read-only. Branch lists were paginated
after two repos landed on exactly 30 entries (GitHub's default page size), which
would otherwise have produced false "no `main`" verdicts. Git trees reported
`truncated: false` throughout; three repos exceeded a 12-Dockerfile sampling
threshold and are flagged as lower bounds, not full counts.

### 7.5.1 Headline numbers

| Measure | Count | Share |
|---|---|---|
| Hardened-default forks | 41 | — |
| **Zero Dockerfiles — the gate is inert** | **15** | **37%** |
| Repos with Dockerfiles | 26 | 63% |
| `master` only, no `main` | 10 | 24% |
| **Neither `main` nor `master`** | **5** | **12%** |
| **Would be mishandled by a literal `main`** | **15** | **37%** |

### 7.5.2 The gate needs three outcomes, not two

**15 of 41 forks contain no Dockerfile at all** — `PMOVES-AgentGym`,
`PMOVES-Deep-Serch`, `PMOVES-E2B-Danger-Room-Desktop`, `PMOVES-E2b-Spells`,
`PMOVES-HiRAG`, `PMOVES-Pinokio-Ultimate-TTS-Studio`, `PMOVES-a0-plugins`,
`PMOVES-autoresearch`, `PMOVES-space-agent`, `PMOVES-surf`,
`Pmoves-AgentGym-RL`, `Pmoves-ComfyUI-VibeVoice`,
`Pmoves-a0-plugin-pmoves-notes`, `Pmoves-hyperdimensions`, `pmoves-cipher-mcp`.

A binary pass/fail gate scores every one of them as **passing**. A rollout
metric reading "N of 41 compliant" would report 37% of the fleet as hardened on
the strength of a control that never executed.

Rule 4 therefore emits **PASS / FAIL / N-A**, N-A reported separately and never
folded into PASS. This generalises as controls are added (§5.4): the verdict is
per-repo-per-control, not per-repo.

### 7.5.3 Demotion is mostly unavailable — answers open question 1

The plan assumed a failing fork could be demoted to `main`. Measured:

| Fallback state | Count | Examples |
|---|---|---|
| `main` exists | 26 | `PMOVES-tensorzero`, `PMOVES-A2UI`, `PMOVES-Archon` |
| `master` only | 10 | **`PMOVES-supabase`**, **`PMOVES.YT`**, `PMOVES-Creator`, `PMOVES-Jellyfin` |
| **neither** | 5 | **`Pmoves-cipher`**, `PMOVES-neo4j`, `PMOVES-space-agent`, `PMOVES-transcribe-and-fetch`, `Pmoves-hyperdimensions` |

1. **Five forks have no non-hardened branch whatsoever.** A fail-closed gate on
   their default branch has no demotion target — it blocks the repo outright.
   Rule 4 is **fail-open (report-only)** on any fork lacking a fallback, or it
   converts a hardening gap into an outage. `Pmoves-cipher` is in this set and
   backs a live service.
2. **37% of the fleet breaks a literal `main` assumption.** Demotion must
   resolve the fallback branch by lookup against the observed branch list, never
   by the string `main`.

### 7.5.4 Two false-positive classes in the control itself

This is the finding that most affects Rule 4, because it is a defect in the tool
being distributed, not in the repos being measured.

**(a) Root-then-`gosu` privilege drop.** `PMOVES-Archon`'s root `Dockerfile`
ends with `USER root` as its literal last directive — deliberately. Its
`ENTRYPOINT` runs as root only to fix volume ownership and git safe-directory
config, then `exec`s the real process via `gosu appuser`. Runtime privilege *is*
dropped; the Dockerfile cannot express that.

`hardening_ratchet.py` has **no carve-out** for this — verified: no reference to
`gosu`, `su-exec`, `setpriv`, `tini`, `dumb-init`, or `ENTRYPOINT` anywhere in
the file. Its last-USER-wins rule scores this correct pattern as `ROOT_USER`.

**(b) Capability-requiring daemons.** `PMOVES-Tailscale`'s 4 Dockerfiles are all
root, but `tailscaled` commonly needs `CAP_NET_ADMIN`. That may be correct
upstream behaviour rather than debt — and this repo inherits upstream's real
security suite (CodeQL, `govulncheck`, `zizmor`, `checklocks`), so it is not an
unmaintained repo.

Both are absorbable today via `_known_gaps.yaml`'s existing `kind: deliberate` +
`reason` mechanism, which is already used for `pmoves/images/jellyfin/Dockerfile`.
But that creates a second-order problem worth fixing before distribution:

> `_known_gaps.yaml` is a **shrink-only debt ledger** — "Removing an entry is the
> goal... the count only goes down." A `kind: deliberate` entry describes a file
> that is *already correct* and will never be removed. Mixing accepted-by-design
> entries into a shrink-only list means the count can never reach zero, so the
> ratchet's goal state becomes unreachable and the number stops meaning
> "remaining debt."

**Recommendation:** split `known_gaps` (debt, shrink-only) from `accepted`
(correct-by-design, stable, requires a reason). At one repo this is cosmetic. At
41 repos — where `gosu` and capability-daemon patterns will recur — a gate that
flags correct code as debt will lose operator trust faster than it earns it.

### 7.5.5 CI volume is not hardening posture

- **`PMOVES-supabase`: 3 of 3 Dockerfiles run as root**, no `USER` anywhere —
  including app-serving `studio` and `lite-studio` — while carrying **44
  workflows**, the largest CI surface in the fleet. Its `zizmor.yml` scans
  Actions configuration, not containers. Merged to hardened 2026-09-17.
- **`Pmoves-cipher`: its one Dockerfile (`Dockerfile.pmoves`) has no `USER`
  directive and runs as root.** This is the image backing the **live Cipher
  memory service**, and it is the most recently pushed repo surveyed
  (2026-09-18). None of its 4 workflows reference hardening, USER checks, or
  image scanning. Highest-priority real finding in the survey.
- **`PMOVES.YT`'s runtime image is already compliant** —
  `pmoves_yt_service/Dockerfile` ends `USER pmoves:pmoves`. Only its
  desktop-bundle build image is root, a different risk class.
- **`PMOVES-Open-Notebook` already carries unmerged branches named
  `security/non-root-user`, `fix/phase-c-hardening`, `fix/phase-d-hardening`** —
  this exact work was scoped there previously and never landed. Check for prior
  art before redoing it elsewhere.
- **`Pmoves-Health-wger`'s `demo/Dockerfile` sets `USER wger` at line 102 then
  `USER root` at 133** — a genuine regression, and precisely the case
  last-USER-wins is designed to catch. The rule is right; §7.5.4 is about its
  blind spot, not its core.
- Security-named workflows exist in only a handful: `PMOVES-DoX`
  (`security-scan.yml` + `codeql.yml`), `PMOVES-tensorzero` (`security.yml` +
  `codeql.yml`), `PMOVES-Tailscale` (upstream suite), plus scattered CodeQL.
  **No fork runs a workflow enforcing the container-USER rule** — confirmed by
  grep across surveyed workflow YAML. The "Hardened" branch name is backed by no
  in-fork CI anywhere in the fleet.

`PMOVES-supabase` has 44 workflows and 3/3 root images;
`PMOVES-llama-throughput-lab` has 1 workflow and a compliant image. Workflow
count and hardening posture are uncorrelated here.

### 7.5.6 Ring-1 candidate

**`PMOVES-supabase`** — freshest merge into hardened, worst measured container
posture among high-traffic repos, and enough existing CI (44 workflows) that a
new caller workflow will not be the only thing running. It also exercises the
`master`-only fallback path (§7.5.3) on the first attempt rather than the
fortieth.

## 8. Open questions

1. ~~Do the hardened-default forks have a `main` to fall back to?~~
   **Answered, all 41 (§7.5.3): no.** 10 are `master`-only and 5 have no
   fallback branch at all — 37% of the fleet. Rule 4 is fail-open where no
   fallback exists, and demotion resolves the branch by lookup.
4. **Fix the false-positive classes before distributing (§7.5.4), or after?**
   Recommendation: before. A gate that flags `PMOVES-Archon`'s correct
   `gosu` drop as debt on first contact will be distrusted across all 41.
5. **`Pmoves-cipher` runs as root and backs a live service.** Fixing that is
   independent of this RFC and should not wait for it.
6. **Does `PMOVES-Tailscale` need root** (`CAP_NET_ADMIN` for `tailscaled`)?
   If yes it is an `accepted` entry, not debt — and it is the first real test
   of the split proposed in §7.5.4.
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
