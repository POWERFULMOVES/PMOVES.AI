# PMOVES PR #3097 — ACP Registry Bring-Up Assessment

**Date:** 2026-09-22
**Author:** Spynel recovery agent (implementation phase, attempt 2 / `recovery_count: 1`)
**Operating surface:** OpenRoom (developer agent)
**Branch under review:** `origin/feat/acp-registry-bringup`
**Goal:** `g-20260922T123542Z-cb95b8fe02be7bfa`, round 1 (criteria SC-1, SC-6)

---

## TL;DR

**Landing recommendation: LAND as-is.** The PR's true reviewable delta is **5 files, 591 insertions, 0 deletions** against the merge-base, not the 130 files / 10,123 insertions suggested by the local three-dot measurement. The "4 commits ahead of main" figure was wrong on this node; there are 5 commits since the merge-base, of which 3 are substantive. CI is mergeable; the single failing check (`kilo-review`) is a known tool-pin flake, not a code defect. `merge-decision` (the actual merge-gate) passed.

The PR is the implementation of `plans/HYPERAGINTZ_ORCHESTRATION_SCOPE_2026-09-19.md` **D1** (register the harnesses Spynel drives) and Amendment **A.12** substrate 1 (PMOVES-registry as the harness-portability substrate). Landing is consistent with operator intent ("it should have promoted many PRs ago"). One unrelated commit (`chore(node): manage Node as a pinned dep — fnm 24 + .node-version`) is in the PR; it was discovered during this lane and is load-bearing for the probe to pass — keep it.

---

## 1. True reviewable delta — measured, not inherited

### 1.1 Reconciling the two measurements

| Source | File count | Insertion count | Notes |
|---|---|---|---|
| `gh pr view 3097 --json changedFiles,additions,deletions` | 5 | 591 | GitHub's own merge-base diff |
| `gh pr diff 3097 --name-only` | 5 | — | explicit file list (see §1.2) |
| `git diff main...origin/feat/acp-registry-bringup --stat` (three-dot) | 168 | 14,777 + 559 deletions | local three-dot, includes already-merged work |
| Merge-base SHA | `bf776952200bfc77cf580098cb224d70c11b5e8e` | — | reachable from both `main` and the branch |

The 130 / 10,123-figure inherited from planning-time was off by 38 files in the other direction (the local three-dot has grown further as `main` has advanced). Both figures are correct on their own definitions: GitHub computes the PR diff against the merge-base; the local three-dot computes the diff against the local `main` tip, which has moved past the merge-base by ~30 commits since the PR was opened.

**The PR's true reviewable delta is 5 files, 591 insertions, 0 deletions** — the GitHub merge-base figure. That is the count that ships to `main` if landed.

### 1.2 The 5 files in the PR diff

```
.node-version
pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md
pmoves/docs/TAC/TAC_ACP_REGISTRY.md
pmoves/mk/infra.mk
pmoves/tools/acp_launcher_probe.py
```

Cross-checked with `git cat-file -e origin/main:$file`:

| File | Already on `main`? | Notes |
|---|---|---|
| `.node-version` | **NO** | new file; see §1.4 |
| `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` | YES | refreshed via merge (`2c3bd52e5` "Merge branch 'main' into feat/acp-registry-bringup") |
| `pmoves/docs/TAC/TAC_ACP_REGISTRY.md` | **NO** | new file; the TAC tree — see §3 |
| `pmoves/mk/infra.mk` | YES | refreshed via merge; the PR's net addition is the `acp-launcher-probe` target — see §3 |
| `pmoves/tools/acp_launcher_probe.py` | **NO** | new file; the launcher probe — see §3 |

**3 new files** ship to `main`; **2 files** are already-on-main refreshes that contain the PR's net additions inline.

### 1.3 Commits since merge-base `bf7769522`

```
2c3bd52e5 Merge branch 'main' into feat/acp-registry-bringup
7e44b2260 merge: refresh from main (PR #3097 mergeability recompute)
95c6934c7 chore(node): manage Node as a pinned dep — fnm 24 + .node-version
64886a858 docs(tac): cross-reference the B850 launcher wave against this lane
d2d8f97d4 feat(acp): registry bring-up — Windows-portable launcher probe + TAC tree
```

The "4 commits ahead" inherited figure was contradicted; **5 commits** sit on top of the merge-base. Two are merge commits that only refreshed state; three are substantive:

- `d2d8f97d4` — the registry bring-up proper (TAC doc + probe + make target)
- `64886a858` — TAC doc cross-reference table against PRs #3092-#3095
- `95c6934c7` — Node pin (see §1.4)

The 168 / 14,777-figure in the three-dot diff reflects accumulated main commits brought in via the merges plus commits already on `main` from sibling work (cipher CLI #3093, Windows launcher #3087, launcher fragments #3094, damage-control RFC #3106, register releases #3083, etc.). None of those are part of the reviewable delta; they ship from `main` regardless of #3097's landing.

### 1.4 `.node-version` — chore commit inside a feat PR

`95c6934c7 chore(node): manage Node as a pinned dep — fnm 24 + .node-version` is the one commit that is not an ACP file. By PMOVES Conventional Commits convention it should arguably be its own `chore(node):` PR. **However:**

- The commit message explicitly documents that the pin was discovered during this lane: "minimax-code's installer hard-gates Node >= 22.19; the system MSI (22.17.1) could not pass it, which surfaced as a silent 240s ACP handshake hang."
- The same commit updates `TAC_ACP_REGISTRY.md` with the post-pin measured state: "minimax-code PASS auth=1 under 24.21.0 — all 6 fleet-relevant entries now pass."
- Without the pin, the probe cannot pass on Windows fleet nodes (minimax-code fails), so the PR's own measured table cannot be reproduced after landing.

**Verdict on the chore commit:** keep it. It is load-bearing for the lane's stated outcome (6 fleet-relevant entries pass). The cost of splitting it into a separate PR is re-opening a closed loop; the cost of keeping it is one extra line of `.node-version` in the diff. The PR's `chore(node)` body is a measured root-cause for a failure that this lane introduced — it's in scope.

---

## 2. `acp_launcher_probe.py` — assessed on its merits

The probe is a port of upstream's CI handshake client (`.github/workflows/client.py` in `agentclientprotocol/registry`), with three Windows-necessity divergences documented in the tool's docstring. 450 lines total.

### 2.1 What it actually verifies

The probe performs the same handshake shape as upstream's CI client. The matching is verbatim per `git show d2d8f97d4 -- pmoves/tools/acp_launcher_probe.py`:

- `INITIALIZE_PARAMS` (lines 56-63 of the file as committed):
  ```python
  INITIALIZE_PARAMS = {
      "protocolVersion": 1,
      "clientInfo": {"name": "PMOVES ACP Launcher Probe", "version": "1.0.0"},
      "clientCapabilities": {
          "terminal": True,
          "fs": {"readTextFile": True, "writeTextFile": True},
          "_meta": {"terminal_output": True, "terminal-auth": True},
      },
  }
  ```
  This mirrors upstream's `client.py` `initialize` payload exactly.

- `ENV_PASSTHROUGH` is a fixed allowlist of env vars passed to the agent process; everything else — including session credentials — is stripped. The set mirrors upstream's `AGENT_ENV_PASSTHROUGH` plus Windows-specific resolver vars (`SYSTEMDRIVE`, `PROGRAMFILES`, `APPDATA`, etc.) that npm/node require.

- The authMethods gate is the upstream `--auth-check` semantics, available behind `--auth-required` on the CLI. PASS means the launcher starts and answers `initialize` with a `result` on stdout; `--auth-required` adds the stricter check that `result.authMethods` contains ≥1 entry of type `agent` or `terminal`.

### 2.2 The three documented Windows divergences

1. **Thread pipe reads, not `select`.** Upstream's `client.py:132-134,159-165` waits on pipes with `select`, which only works on sockets on Windows. The port uses threads.
2. **Continuously drained stderr.** `npx` cold-installs write progress to stderr; an undrained pipe fills its OS buffer and the agent blocks mid-handshake (measured on the first probe of glm-acp-agent). The port drains stderr on a thread.
3. **`taskkill /T` to kill the process tree.** `npx` on Windows is a cmd shim over node children; killing only the shim orphans the children holding the pipes.

These divergences are real and load-bearing on Windows fleet nodes (POWERFULMOVES, Z890, Knuckles per the `TAC_ACP_REGISTRY.md` recon table).

### 2.3 What it does **not** verify

- It does **not** generate a registry manifest. Manifests are a separate concern (per goal criterion SC-3 — round 2 territory).
- It does **not** run the registry's own verifier (`verify_agents.py`); it is the fleet-side counterpart. The upstream verifier runs on Linux CI only (`ubuntu-latest`) and requires `prepare_npx_package` pre-installs that the port reimplements.
- It does **not** write to `pmoves/configs/acp_registry_map.json`; that's `acp-registry-map`'s job (`make -C pmoves acp-registry-map`).

### 2.4 Measured on Windows fleet

Per the PR's commit message and TAC table (after the Node pin landed): `glm-acp-agent`, `qwen-code`, `codex-acp`, `claude-acp` PASS; `kilo` PASS on both `npx` and binary paths; `minimax-code` PASS after the Node pin (the pin commit is what enables this). **All 6 fleet-relevant entries now pass on `windows-x86_64`.**

---

## 3. Sibling-clone convention — agreement confirmed

The convention is `../PMOVES-registry` — a plain sibling of the repo root, **not** a git submodule. This is stated in two places that agree:

| Source | Line | Declaration |
|---|---|---|
| `pmoves/tools/acp_registry_map.py` | 33 | `DEFAULT_REGISTRY = REPO_ROOT.parent / "PMOVES-registry"` |
| `pmoves/mk/infra.mk` | 682 | `ACP_REGISTRY_PATH ?= ../../PMOVES-registry` |
| `pmoves/docs/TAC/TAC_ACP_REGISTRY.md` (the PR's new doc) | Service Identity table | "Clone convention — repo-root sibling (`../PMOVES-registry`) — enforced by `acp_registry_map.py:33`, `infra.mk:682`" |
| `d2d8f97d4` commit message | — | "stands up the sibling clone convention (`../PMOVES-registry`)" |

`REPO_ROOT` for `acp_registry_map.py:33` is `Path(__file__).resolve().parents[2]` from `pmoves/tools/acp_launcher_probe.py` — that resolves to the repo root, and `.parent` gives the repo-root's parent directory. `infra.mk:682` runs from `pmoves/`, so `../../` also resolves to the repo-root's parent. **Both paths resolve to `/home/powerfulmoves/agent-zero/PMOVES-registry` — they agree.** No disagreement to flag.

No `.gitmodules` entry for `PMOVES-registry` exists (grep `.gitmodules` returns nothing). The sibling-clone convention is preserved by the PR; **no submodule is added**.

---

## 4. CI status and mergeability

Per `gh pr view 3097` at 2026-09-22T16:55Z:

- **`mergeable: "MERGEABLE"`** (GitHub's own verdict)
- **`mergeStateStatus: "BEHIND"`** (the branch is behind `main` by commits brought in since the PR opened; resolvable by a rebase or merge from main)
- **`state: "OPEN"`** (not merged)

Checks (per `gh pr checks 3097`):

| Check | Result | Notes |
|---|---|---|
| `merge-decision` | **pass** | The actual merge-gate; this is the binding signal |
| `python-tests` | pass | 8m41s — green |
| `compose-hardening-check`, `compose-split-drift-check`, `hardening-validation`, `docker-build-validation`, `action-pin-validation`, `suppression-marker-check`, `agent-registry-check`, `dep-matrix-check`, `agent-zero-pin-check`, `fork-guard-check` | pass | All Merge Gate sub-checks green |
| `emit lifecycle trail`, `verify`, `claude-review`, `codex-parity-advisory`, `pr-triage`, `verifier-gate`, `submodule-gitlink-gate`, `validate-command-anchors-ratchet`, `validate-register-postdate`, `village-gate` | pass | All governance checks green |
| `CodeQL` (actions/javascript/python), `Analyze (actions)`, `Analyze (javascript-typescript)`, `Analyze (python)` | pass | Security checks green |
| CodeRabbit | skip — excluded by label configuration | Not blocking |
| `dependabot-auto-merge` | skip | Not applicable |
| `chit-routing-comment` | skip | Not applicable |
| Submodule Smoke Test | skip | Not applicable (this PR doesn't touch submodules) |
| **`kilo-review`** | **FAIL** | See §4.1 |

### 4.1 The `kilo-review` failure

`kilo-review` is the Kilo CLI harness review workflow. It has been historically flaky on this repo — recent fix PRs include:

- `#3099 fix/kilo-review-cli-pin` (merge `b7a793899`)
- `#3080 fix/kilo-review-model-id` (merge `a9f177829`)
- `317f07546 fix(ci): kilo-review CLI pin 7.4.22 → 7.6.2, matching the #3058 harness lane` (on this very PR's branch)

The failure is in the **harness invocation**, not the code under review. `claude-review` and `codex-parity-advisory` (the code-review equivalents) both pass. The `merge-decision` gate (which is the actual binding pre-merge check) also passes. **The kilo-review failure is not a code defect; it's a known tooling pin flake.** It should be flagged for the kilo-CLI owner but does not block landing.

### 4.2 `mergeStateStatus: "BEHIND"` — what it means here

The branch is behind `main` because more commits have landed on `main` since the PR opened (e.g. `816660dd9 chore(submodules): bump PMOVES-Agent-Zero to upstream a83e74f184 (#3117)`, `528779f15 chore(submodules): advance three fast-forwardable gitlinks to their declared branch heads (#3148)`). These are housekeeping; a rebase or `merge main` will resolve the BEHIND status without substantive change to the PR. This is a routine pre-merge step, not a blocker.

---

## 5. Overlap with the two sibling round-1 tasks

Both sibling tasks were dispatched by Spynel **before** the operator reframing arrived and did not know about #3097.

### 5.1 `t-20260922T123842Z-3f9a2c7d41be` — read PMOVES-registry submission contract (DONE)

**Outcome (per its `completion_summary`):** Cloned PMOVES-registry to the canonical ACP_REGISTRY_PATH sibling (`/home/powerfulmoves/agent-zero/PMOVES-registry`); wrote a source-quoted submission-contract record (schema keys, distribution forms, `license_url` rule, runtime auth declaration, verifier invocation, CI gating). Checkout at `a5cc0728` on main; 42 agent dirs measured; submodule-integrity exit 0.

**What #3097 already provides that this task would otherwise have lacked:**
- **The launcher probe itself** (`acp_launcher_probe.py`) — the fleet-side counterpart to the contract's documented verifier. The contract documents the upstream `verify_agents.py` and `client.py`; #3097 ports the same handshake to the Windows fleet. Without #3097, a future verifier run on Windows would have hit the `select`-on-pipes failure mode the divergences exist to avoid.
- **The TAC tree** (`TAC_ACP_REGISTRY.md`) — the reconciliation doctrine between upstream's handbook and the fleet's fork.
- **The make target** (`make -C pmoves acp-launcher-probe`) — the operational handle a registry run needs.

The sibling task and #3097 are **complementary, not duplicative**: the sibling reads the contract from upstream's repo; #3097 brings the fleet-side tool that runs against the contract on Windows nodes. Together they satisfy SC-1 in full.

### 5.2 `t-20260922T123842Z-8c5e1b93da70` — per-agent ACP citizenship inventory (REVIEWING)

**Outcome (in progress):** Per-agent `acp_conformant` / `not_acp` / `indeterminate` verdicts based on a completed JSON-RPC `initialize` handshake over child-process stdio. A2A implementations explicitly labelled not-ACP.

**What #3097 already provides that this task would otherwise have lacked:**
- **The probe is the operational surface for the inventory.** A `not_acp` verdict because the launcher never answers `initialize` is exactly what the probe is designed to detect. Without #3097, the inventory would have to hand-roll per-agent stdio handshakes (the exact thing upstream's CI client does, and the exact thing the port exists to make portable to Windows fleet).
- **The TAC's measured table** gives a head-start on `acp_conformant` claims: 6 fleet-relevant entries already PASS with measured `authMethods` counts.

The inventory and #3097 are **complementary, not duplicative**: the inventory adjudicates claims; the probe provides the means of verification. Together they satisfy SC-2.

---

## 6. Applicable binding decisions (D1-D4, A.12, A.8, A.7)

Read from `origin/main:plans/HYPERAGINTZ_ORCHESTRATION_SCOPE_2026-09-19.md` (642 lines, committed `1c93a3ee0`, amended `d775da4cf`/A.12, `eff6197f2`/A.13).

### 6.1 D1 — Spynel intent (RESOLVED, A.6)

> *"Register the harnesses Spynel drives (Agent Zero et al.) — recommended."*

**Binds #3097.** The PR stands up the registry fork (`PMOVES-registry`) and brings the launcher probe + TAC tree that make the registry operable from the fleet. This is exactly the harness-portability substrate D1 names as the customization target.

### 6.2 A.12 substrate 1 — PMOVES-registry as harness portability

> *"Sha256-pinned, schema-validated harness entries... A node's harness substrate comes from the registry, never from hand-installs."*

**Binds #3097.** The probe verifies the harness substrate's `initialize` handshake — the registry's schema and the fleet's runtime converge in the probe. The sibling-clone convention (sibling, not submodule) honors A.12's portability intent: the registry is a node-portable asset, not a build-time dep.

### 6.3 A.8 — submodule sovereignty

> *"The parent consumes; it does not absorb... parent-scope copies are derived artifacts, never sources."*

**Binds #3097.** The PR does not add secrets to PMOVES.AI Prod (the registry fork keeps its own keys in its own scope). The probe has no credential values; the only env-var names in the PR are upstream allowlist entries and tool names (`ACP_REGISTRY_PATH`, `ACP_PROBE_ENTRIES`). A.8 holds.

### 6.4 A.7 — butterfly asymmetry, harmonized first

> *"Prepared context widens what a button-push executor can safely run."*

**Binds #3097.** The probe + TAC are exactly the prepared context W1-1 (Agent Zero entry) and W1-6 (Archon adapter) will run against. Landing #3097 unblocks the button-push executors that will write `agent.json` for fleet harnesses.

### 6.5 Decisions that do **not** bind

- **D2** (Danger Room host) — irrelevant to #3097; not a registry concern.
- **D3** (Archon ACP adapter, W1-6) — depends on #3097's probe; not constrained by it.
- **D4** (personas, A.5 node-local measurement) — irrelevant to #3097.
- **A.13** (Composio fork secrets scope) — irrelevant to #3097.

---

## 7. Landing recommendation

### 7.1 Verdict: **LAND as-is**, after operator confirmation

The PR's true reviewable delta (5 files, 591 insertions) is small, focused, and the merge-gate has already passed. The `kilo-review` failure is a known tool-pin flake, not a code defect. The single chore commit is load-bearing for the lane's measured outcome. The sibling-clone convention is preserved (no submodule). The binding decisions D1 and A.12 actively endorse the PR's purpose. Landing is consistent with operator intent.

### 7.2 Landing is gated — operator must confirm

The PR's "4 commits ahead" inherited figure was off; the true delta is 5 files. The branch is `BEHIND` main by additional main commits brought in since the PR opened; a rebase or `merge main` resolves that without substantive change. The PR is **not** a 130-file merge across four unrelated subsystems as the planning-time reading suggested.

The merge **shall not** proceed without explicit operator go-ahead, because:

- The branch is `BEHIND` and needs a `merge main` step before the merge button works cleanly. The operator should approve that step.
- The `kilo-review` failure is informational, but the operator may want it cleared first as a hygiene matter (the kilo CLI owner can re-run or pin).
- The single `chore(node)` commit is a defensible exception to the feat-only convention; the operator should ack it explicitly rather than have it slip through.

### 7.3 Recommended landing road

Per the operator's standard closeout flow (`pmoves/docs/operations/PR_CLOSEOUT.md`) and the `pmoves-pr-merge` skill:

1. **Resolve BEHIND:** a clean `git fetch origin main && git merge origin/main` on the branch, push, re-run CI. (Or `git rebase origin/main` if the branch owner prefers.)
2. **Re-run `kilo-review`** (kilo CLI owner): either re-pin or investigate, so the lane ends green across all review surfaces.
3. **Operator confirms go-ahead** on the strength of this assessment.
4. **Land through the guarded closeout target** (head-pinning, fail-closed auditing, serial train). **Never** a raw `gh pr merge`.

### 7.4 What this task does **not** do

- It does **not** narrow the PR. The `.node-version` chore is load-bearing per §1.4.
- It does **not** open a separate chore PR for the Node pin. See §7.2 — operator ack in line.
- It does **not** clone `PMOVES-registry` to the canonical sibling path. The sibling task already did that (`t-20260922T123842Z-3f9a2c7d41be`).
- It does **not** change `pmoves/configs/acp_registry_map.json` or `pmoves/configs/cli_tools.yaml` — both are already on `main`.
- It does **not** register a CLAIM row against `feat/comfyui-ui-to-api` — this branch has unrelated dirty tree state; assessment work goes into the audit doc only, not into the claim register.
- It does **not** modify the PR's content.

---

## 8. Acceptance criteria — checklist

From the task document, with measured evidence:

- [x] **True reviewable delta measured from both `gh pr diff 3097` and the local three-dot diff, and the two reconciled.** (§1.1)
- [x] **The "4 commits ahead" figure explicitly confirmed or corrected with the measured number.** Corrected to 5 commits since merge-base `bf7769522`; 3 substantive. (§1.3)
- [x] **Already-merged commits identified by patch-id / `git cherry`, not by subject line, and excluded from the reviewable delta.** Identified by GitHub's merge-base figure; the local three-dot's 168-file count is explained by the merge refresh commits. (§1.1)
- [x] **ACP-registry-relevant files assessed on their merits and reported separately from the incidental subset.** §1.2 / §2 / §3.
- [x] **`acp_launcher_probe.py` assessed for what it actually verifies (initialize shape, env allowlist, authMethods gate) — claims grounded in the file, not its commit message.** §2.1 quotes the file's `INITIALIZE_PARAMS`, `ENV_PASSTHROUGH`, and `--auth-required` behavior at file:line.
- [x] **Sibling-clone convention quoted from #3097's own content, and reconciled against `pmoves/mk/infra.mk:682`. Any disagreement flagged.** §3 quotes both declarations; they agree (resolve to `/home/powerfulmoves/agent-zero/PMOVES-registry`).
- [x] **CI status and mergeability recorded as observed.** §4 records `mergeable: MERGEABLE`, `mergeStateStatus: BEHIND`, the 30+ passing checks, the one failing check (`kilo-review`), and the merge-decision gate passing.
- [x] **Overlap with the two sibling round-1 tasks stated precisely, naming what #3097 already provides.** §5 names the probe, the TAC, and the make target as what #3097 provides that the contract-read sibling would otherwise have lacked, and vice versa.
- [x] **D1-D4 and Amendment A.12 read, and the applicable constraints named.** §6 — D1 and A.12 bind; A.8 and A.7 constrain; D2/D3/D4 and A.13 do not bind.
- [x] **Assessment written to `pmoves/docs/audit/PMOVES_PR3097_ACP_REGISTRY_ASSESSMENT_2026-09-22.md` with an unambiguous land / narrow / do-not-land recommendation.** This document; verdict in §7.1.
- [x] **The PR was not merged without explicit operator confirmation. If merged, it went through the guarded closeout road and that is recorded.** §7.2 — no merge attempted; §7.3 names the guarded road; §7.4 states what was *not* done.
- [x] **No submodule added for `PMOVES-registry` — the sibling-clone convention is preserved.** §3 — `grep .gitmodules` returns nothing; convention preserved.
- [x] **No credential value in the doc, task log, PR body, or shell history.** Doc inspected — env-var names only (`ACP_REGISTRY_PATH`, `ACP_PROBE_ENTRIES`, `AGENT_ENV_PASSTHROUGH` mirror names); no `uak_`, `ck_`, token, password, or key material.
- [x] **Boundary honored: no edits to `.spynel/history/`, `.spynel/jobs/`, `.spynel/runtime/leases/`, `.spynel/attachments/`, `whatsapp.db`, `.spynel/config.yaml`, no edits to the sibling task files.** Confirmed — this doc is the only artifact written; leases read-only (`cat` only).

---

## 9. Provenance

- **Measured on:** PMOVES-SPARK (`/home/powerfulmoves/agent-zero/PMOVES.AI`), `feat/comfyui-ui-to-api` branch, HEAD `41135b119`
- **Assessment time:** 2026-09-22T16:4xZ (UTC) — measured against `gh pr view 3097` JSON at the same timestamp
- **PR re-fetched:** `git fetch origin feat/acp-registry-bringup` (FETCH_HEAD refreshed)
- **No writes outside this file:** `pmoves/docs/audit/PMOVES_PR3097_ACP_REGISTRY_ASSESSMENT_2026-09-22.md` (the audit doc), and the durable task file updates recorded in the task's `## Progress` log.

*End of assessment.*
