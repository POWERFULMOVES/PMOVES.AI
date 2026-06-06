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
| `startup_failure`, **0 jobs**, run shown by file **path** not workflow `name:` | workflow **uncompilable on default branch** (GitHub uses default-branch file for `issue_comment`/`pull_request_review`/push) | Validate YAML: `gh api repos/{o}/{r}/contents/.github/workflows/X.yml?ref=main --jq .content \| base64 -d \| python -c "import yaml,sys;yaml.safe_load(sys.stdin)"`. Common: a `run: \|` block scalar broken by a **zero-indent** PR-body line (build the body with `printf`), or committed `<<<<<<<` conflict markers. |
| `startup_failure` but **YAML valid AND action SHAs resolve** | **repo Actions allowlist** blocks an action (generic "workflow file issue" message) | `gh api repos/{o}/{r}/actions/permissions/selected-actions`. If `allowed_actions:selected` and the action isn't in `patterns_allowed` → add `vendor/action@*` (PUT the **full** list, replace-not-append, keep `github_owned_allowed`). Tell: job **skips** when its `if:` is false but **startup-fails** when `if:` is true. |
| Trivy step **`cancelled`** (build+push succeeded) | concurrency cancel (two runs same `ref` in group `workflow-${ref}`) or runner shutdown | Don't chase it. `workflow_dispatch` is **exempt** from `cancel-in-progress` — trigger a manual dispatch for a stable verification run. Cancel redundant dupes. |
| Trivy **`failure`** + `FATAL ... no space left on device` (DB download) | **runner disk-full**, NOT a CVE | Workflow side: `docker image prune -af` + drop stale `.cache/trivy/db` + sweep `/tmp/{stereoscope,sbom-action,trivy}-*` before Trivy (#1728). Host side: see "Runner hygiene". **NEVER `docker volume prune`** (co-hosts fleet data volumes — `make -C pmoves volume-reset SERVICE=<name>`). |
| Trivy **`failure`** + real `Total: N (HIGH/CRITICAL)` table | **genuine CVEs** (gate has `ignore-unfixed:true`, so only fixable ones block) | Read the table (below). Bump deps in the fork → bump gitlink → re-run. For a Go-stdlib CVE in a prebuilt binary (esbuild etc.): verify the **embedded Go version** first — a bump only helps if upstream rebuilt with patched Go; else prune the build-only tool from the runtime image. |

## Reading the real Trivy CVE table

`gh run view --log` is often empty for in-progress/cancelled runs. Use the job-log API:

```bash
JID=$(gh run view "$RUN" --json jobs --jq '.jobs[]|select(.name=="Build archon")|.databaseId')
gh api "repos/{o}/{r}/actions/jobs/$JID/logs" | sed -E 's/\x1b\[[0-9;]*m//g' > /tmp/job.txt
grep -n "Total: [0-9]" /tmp/job.txt        # find the gating count
# the table after it: │ Library │ Vulnerability │ Severity │ Status │ Installed │ Fixed │
```

Verify an embedded Go version in a flagged binary (no `go` needed):
```bash
python -c "import re;print(sorted(set(re.findall(rb'go1\.\d+(?:\.\d+)?',open(BIN,'rb').read()))))"
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

Chronic kvm4 disk exhaustion is the root of the disk/cancel signatures. Documented path (FLEET_INVENTORY_LIVE.md): operator grants `Bash(ssh root@pmoves-kvm4-1:*)` OR Hostinger MCP. Guard-safe reclaim (no `rm -rf`, no volume prune):
```bash
ssh root@pmoves-kvm4-1 'df -h /; docker builder prune -af; docker image prune -af; docker container prune -f; \
  find /tmp -maxdepth 1 \( -name "stereoscope-*" -o -name "sbom-action-*" -o -name "trivy-*" \) -mtime +0 -depth -delete 2>/dev/null; \
  find /opt/actions-runner*/_work -type d -path "*/.cache/trivy/db" -depth -delete 2>/dev/null; df -h /'
```

## Anti-patterns

- ❌ Re-running a cancelled/disk-starved run unchanged (wastes ~90 min). Fix the cause first.
- ❌ Trusting the rollup label / `gh pr checks --watch` exit code over the per-step conclusions.
- ❌ `docker volume prune` / `docker system prune --volumes` anywhere — destroys fleet data volumes.
- ❌ Bumping a dep to "latest" without verifying the fix actually ships in latest (esbuild→go1.26.1 trap).
- ❌ Treating `startup_failure` as a code bug before checking the Actions allowlist.

## Citations
- Memory: `reference_ghcr_ci_failure_playbook` (signature table source), `feedback_no_docker_volume_prune`, `feedback_pr_trim_classifier_not_authoritative`.
- `.github/workflows/integrations-ghcr.yml`, `.github/workflows/integrations-ghcr.matrix.json`.
- `pmoves/docs/operations/FLEET_INVENTORY_LIVE.md` (runner access Known Road).
