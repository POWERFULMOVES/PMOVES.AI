---
name: ci-expedition
description: Diagnose PMOVES GHCR/CI failures by SIGNATURE before guessing a cause — startup_failure (YAML break / Actions allowlist) vs disk-no-space vs cancel vs real-CVE. Turns "CI is red again" into a 30-second triage with the matching fix. Use when a GHCR publish or any workflow run goes red/startup_failure.
---

# ci-expedition — PMOVES CI failure triage

"CI is red again" has at least five distinct causes that all surface as one red badge. The rollup label lies — **read the failure *mode* first**, then apply the matching fix. Codified from the 2026-06-05/06 GHCR cascade (PRs #1717/#1718/#1719/#1721/#1726/#1728/#1729). Full reference: memory `reference_ghcr_ci_failure_playbook`.

## When to use

- A GHCR publish (`integrations-ghcr.yml`) run goes red or `startup_failure`.
- A workflow shows repeated `startup_failure` (0 jobs) on every push/comment — notification spam.
- Trivy gate fails and you need to know if it's a real CVE, a disk problem, or a cancel.
- Before "just re-run it" — re-running a cancelled/disk-starved run wastes ~90 min.

## Step 0 — classify by signature (don't skip)

```bash
RUN=<id>   # gh run list --workflow=integrations-ghcr.yml --limit 5
# overall + per-image + per-step (the label lies; read steps)
gh run view "$RUN" --json status,conclusion,jobs --jq '.jobs[]|select(.name|test("Build "))|"\(.name): \(.conclusion)"'
# the failing step's conclusion (failure vs cancelled vs skipped matters):
gh run view "$RUN" --json jobs --jq '.jobs[]|select(.name=="Build archon")|.steps[]|{name,conclusion}'
```

| Signature | Cause | Fix |
|---|---|---|
| `startup_failure`, **0 jobs**, run shown by file **path** not workflow `name:` | workflow **uncompilable on the ref Actions resolved it from** — which is NOT always the default branch; see the trigger note below before validating `main` | Validate YAML: `gh api repos/{owner}/{repo}/contents/.github/workflows/X.yml?ref=main --jq .content \| base64 -d \| python -c "import yaml,sys;yaml.safe_load(sys.stdin)"`. Common: a `run: \|` block scalar broken by a **zero-indent** PR-body line (build the body with `printf`), or committed `<<<<<<<` conflict markers. |
| `startup_failure` but **YAML valid AND action SHAs resolve** | **repo Actions allowlist** blocks an action (generic "workflow file issue" message) | `gh api repos/{owner}/{repo}/actions/permissions/selected-actions`. If `allowed_actions:selected` and the action isn't in `patterns_allowed` → add `vendor/action@*` (PUT the **full** list, replace-not-append, keep `github_owned_allowed`). Tell: job **skips** when its `if:` is false but **startup-fails** when `if:` is true. |
| Trivy step **`cancelled`** (build+push succeeded) | concurrency cancel (two runs same `ref` in group `workflow-${ref}`) or runner shutdown | Don't chase it. `workflow_dispatch` is **exempt** from `cancel-in-progress` — trigger a manual dispatch for a stable verification run. Cancel redundant dupes. |
| Trivy **`failure`** + `FATAL ... no space left on device` (DB download) | **runner disk-full**, NOT a CVE | Workflow side: `docker image prune -af` + drop stale `.cache/trivy/db` + sweep `/tmp/{stereoscope,sbom-action,trivy}-*` before Trivy (#1728). Host side: see "Runner hygiene". **NEVER `docker volume prune`** (co-hosts fleet data volumes — `make -C pmoves volume-reset SERVICE=<name>`). |
| Trivy **`failure`** + real `Total: N (HIGH/CRITICAL)` table | **genuine CVEs** (gate has `ignore-unfixed:true`, so only fixable ones block) | Read the table (below). Bump deps in the fork → bump gitlink → re-run. For a Go-stdlib CVE in a prebuilt binary (esbuild etc.): verify the **embedded Go version** first — a bump only helps if upstream rebuilt with patched Go; else prune the build-only tool from the runtime image. |
| Job **fails on a missing input that an upstream job supplies** (classically `actions/checkout` → `Input required and not supplied: token`) **while the upstream job reports `success`** | **cross-job App-token revoke.** `actions/create-github-app-token` revokes in its post-step, which fires when the *minting job* ends — `_app-token.yml:82` says so ("auto-revoked at job end"). A downstream `needs.<job>.outputs.token` is therefore dead and masked to empty. | Mint **inline** in the consuming job, per `branch-protection-sync.yml:77-80` (which documents the same decision). Fixed for `review-collect.yml` in #2479. Tell: the mint job is green, the consumer is red, and the error names an input rather than a permission. |

### Trigger note — which ref supplies the workflow file

| Event | Workflow file comes from |
|---|---|
| `issue_comment` | **default branch** — always |
| `push` | **the pushed ref** — only the default branch when that is what was pushed |
| `pull_request`, `pull_request_review` | **PR head / merge ref** |

So a fix on `main` does NOT take effect for an open PR until that branch is rebased, and a `push` failure on a feature branch or tag must be triaged against **that ref**, not `main` — validating `main` there will show a file that is fine and hide YAML or action-reference breakage that exists only on the pushed ref.

Verified empirically while fixing #2479, not taken from docs:

| Run | PR head | Workflow that ran | Result |
|---|---|---|---|
| `31257145963` | pre-fix, while `main` already carried the fix | **old** (`token / mint` + `collect` jobs) | failed at checkout |
| `31257247543` | rebased onto `main`, so head carried the fix | **new** (single `collect` job) | green |

Practical consequence: when a `pull_request_review`-triggered workflow misbehaves, validate the **PR head's** copy of the file. Validating `main` will show a file that is fine and send the triage down the wrong path. To verify a merged workflow fix, rebase a PR and fire the event — merging alone proves nothing for open PRs.

## Reading the real Trivy CVE table

`gh run view --log` is often empty for in-progress/cancelled runs. Use the job-log API:

```bash
JID=$(gh run view "$RUN" --json jobs --jq '.jobs[]|select(.name=="Build archon")|.databaseId')
gh api "repos/{owner}/{repo}/actions/jobs/$JID/logs" | sed -E 's/\x1b\[[0-9;]*m//g' > /tmp/job.txt
grep -n "Total: [0-9]" /tmp/job.txt        # find the gating count
# the table after it: │ Library │ Vulnerability │ Severity │ Status │ Installed │ Fixed │
```

Verify an embedded Go version in a flagged binary (no `go` needed):
```bash
BIN=path/to/binary   # e.g. /app/node_modules/@esbuild/linux-x64/bin/esbuild
python -c "import re,sys;print(sorted(set(re.findall(rb'go1\.\d+(?:\.\d+)?',open(sys.argv[1],'rb').read()))))" "$BIN"
# CVE-2026-42504 fixed in go1.25.11/1.26.4 — a binary on go1.26.1 is STILL vulnerable.
```

## Build-source map (integrations-ghcr.matrix.json)

- `archon` / `archon-ui` ← `pmoves/services/archon/Dockerfile` + `pmoves/integrations/archon` submodule (PMOVES-Archon fork).
- `open-notebook` ← PMOVES-Open-Notebook fork branch directly.
- Dep-CVE remediation loop: bump in the **fork** (regen lockfile; watch root `overrides`/`resolutions` pinning below the range) → bump **gitlink** in PMOVES.AI → re-run GHCR.

## Verification cadence (verify-then-merge)

- **PR-event `Validate <svc> (PR)` builds the image without push** — that's the practical Dockerfile smoke test before merge.
- Per-image Trivy verdict: `gh run view <run> --json jobs --jq '.jobs[]|select(.name=="Build X")|.steps[]|{name,conclusion}'`.
- Always confirm green **before** an admin-merge — a `gh pr checks --watch` exit 0 does NOT mean all green (watch can exit while checks are red/pending). Re-read the rollup.

## Runner hygiene (host side)

Chronic kvm4 disk exhaustion is the root of the disk/cancel signatures. Documented path (FLEET_INVENTORY_LIVE.md): operator grants `Bash(ssh root@pmoves-kvm4-1:*)` OR Hostinger MCP.

**Use the Known Road. Do not inline the reclaim commands.**

```bash
make -C pmoves docker-fleet-cleanup-run       # reclaim now, this node
make -C pmoves docker-fleet-cleanup-status    # timer state + last run
sudo make -C pmoves docker-fleet-cleanup-install   # daily systemd timer (per node)
```

`docker-fleet-cleanup-run` is `@bash $(CLEANUP_SCRIPT)` → `deploy/provision/docker-fleet-cleanup.sh`. The target *delegates*; it does not re-implement. That anchoring is the point — a Make target that re-types the docker commands becomes another copy that drifts, which is exactly how #2473 ended up fixing two copies and missing two others.

For a remote runner, run the same target over ssh rather than pasting commands:

```bash
ssh root@pmoves-kvm4-1 'df -h /; make -C /path/to/PMOVES.AI/pmoves docker-fleet-cleanup-run; df -h /'
```

**The durable fix is the timer, not the manual run.** `docker-fleet-cleanup-install` puts a daily systemd timer on the node. If a runner is exhausting disk *chronically*, it needs the timer installed once — not this playbook re-run every incident.

What the script does, so you know what you are invoking: container prune, builder prune, `buildx rm --all-inactive`, a name-filtered dangling-volume sweep for leaked `buildx_buildkit_*_state` volumes, image prune >72h, and the `/tmp/{stereoscope,sbom-action,trivy}-*` + stale `.cache/trivy/db` cleanup. It does **not** prune volumes generally — the sweep is filtered by name *and* dangling, so it cannot reach a `pmoves_*` data volume.

> **Why the Known Road is mandatory here, not just preferred.** `.claude/hooks/pre-tool.sh` substring-scans the entire Bash parameter string against `BLOCKED_PATTERNS`. A raw volume-removal command is rejected **even when nested inside a quoted `ssh '...'`** — so an inlined playbook silently does nothing, and the operator reads "cleanup ran" from a command that never executed. Invoking the target keeps the blocked substring inside a committed, reviewed script where it belongs.

## Anti-patterns

- ❌ Re-running a cancelled/disk-starved run unchanged (wastes ~90 min). Fix the cause first.
- ❌ Trusting the rollup label / `gh pr checks --watch` exit code over the per-step conclusions.
- ❌ `docker volume prune` / `docker system prune --volumes` anywhere — destroys fleet data volumes.
- ❌ Inlining the reclaim commands into a shell one-liner instead of running `deploy/provision/docker-fleet-cleanup.sh`. The damage-control hook substring-scans the whole Bash parameter string, so a nested `docker volume rm` is blocked even inside a quoted `ssh '...'` — the copied command silently does nothing. It also re-creates the duplicate that drifted in the first place.
- ❌ Bumping a dep to "latest" without verifying the fix actually ships in latest (esbuild→go1.26.1 trap).
- ❌ Treating `startup_failure` as a code bug before checking the Actions allowlist.

## Citations
- Memory: `reference_ghcr_ci_failure_playbook` (signature table source), `feedback_no_docker_volume_prune`, `feedback_pr_trim_classifier_not_authoritative`.
- `.github/workflows/integrations-ghcr.yml`, `.github/workflows/integrations-ghcr.matrix.json`.
- `pmoves/docs/operations/FLEET_INVENTORY_LIVE.md` (runner access Known Road).
