# CI/CD Research: Submodule Fleet Sync Automation

> **Date:** 2026-08-05
> **Researcher:** CRUSH-GLM52 (Z890)
> **Purpose:** Research GitHub best practices for production submodule/fork sync automation before changing PMOVES.AI CI/CD

## Current PMOVES State

- **58 submodules** tracking `PMOVES.AI-Edition-Hardened` across 359 forks
- **fork-sync.yml workflow**: weekly cron + manual dispatch, processes N forks per run
- **fork_registry.json**: 57 forks with sync=true/false decisions + reasons
- **GitHub App**: PMOVES.AI App with Administration:RW, Contents:RW, Packages:RW, Workflows:RW
- **Self-hosted runners**: KVM4-1, KVM4-2, KVM2 (disk pressure is recurring)
- **Process today**: fork-sync creates per-fork PRs → agent/operator merges → manual gitlink promotion via `git update-index`

## Research Findings

### 1. `repository_dispatch` Pattern (Child→Parent Event-Driven Sync)

**Source:** https://tommoa.me/blog/github-auto-update-submodules/

The canonical pattern for event-driven submodule updates:

1. **Child/submodule repo** has a workflow that fires on push:
```yaml
on: [push]
jobs:
  dispatch:
    steps:
      - uses: peter-evans/repository-dispatch@v3
        with:
          token: ${{ secrets.PAT }}
          repository: owner/parent-repo
          event-type: submodule-update
          client-payload: '{"module": "path/to/submodule", "sha": "${{ github.sha }}"}'
```

2. **Parent repo** has a workflow triggered by `repository_dispatch`:
```yaml
on:
  repository_dispatch:
    types: [submodule-update]
jobs:
  update:
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.PAT }}
          submodules: true
      - run: |
          git submodule update --init --remote -- "${{ github.event.client_payload.module }}"
          git commit -am "chore: update ${{ github.event.client_payload.module }}"
          git push
```

**Pros:** Real-time, event-driven, no polling. Each submodule push immediately triggers a parent update.
**Cons:** Requires a workflow in EVERY child repo (58 repos). Requires PAT or App token with cross-repo dispatch permission. For third-party upstreams (not our forks), this doesn't work — we don't control their repo.

**PMOVES fit:** Works for our FORKS (we control them), but NOT for upstream sync (we don't control upstream repos). Need the fork-sync workflow for upstream→fork, and this pattern for fork→parent.

### 2. `update-submodules` GitHub Action (API-only, No Clone)

**Source:** https://github.com/marketplace/actions/update-submodules

Uses GitHub REST API to update submodule pointers **without cloning the repo**:

```yaml
- uses: runsascoded/update-submodules@v1
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
    branch: main
    refs: "submodule1=main submodule2=PMOVES.AI-Edition-Hardened"
```

**Pros:** Fast (no checkout), works at scale, custom refs per submodule.
**Cons:** Direct commit (no PR). No conflict resolution. Doesn't handle the upstream→fork layer.

**PMOVES fit:** Could replace the manual `git update-index --cacheinfo` step in our gitlink promotion. But we want PRs, not direct commits, for audit trail.

### 3. Dependabot for Submodules

**Source:** https://github.com/dependabot/dependabot-core/discussions/13534

Dependabot CAN update git submodules natively:
```yaml
# .github/dependabot.yml
- package-ecosystem: "gitsubmodule"
  directory: "/"
  schedule:
    interval: "daily"
```

**Limitations:**
- Always bumps to latest commit on tracked branch (no tag-based releases)
- Doesn't handle PMOVES.AI-Edition-Hardened fork pattern (tracks branch, not tag)
- Can create excessive PR noise (58 submodule PRs per day)
- Doesn't run fork-sync (only gitlink bump, no upstream→fork merge)
- Known issues with non-default branches and private repos

**PMOVES fit:** Could work for the gitlink-bump layer (fork HEAD → parent gitlink), but NOT for the upstream→fork layer. Would need `allow` filtering to only bump forks that are already synced. High PR noise is a concern.

### 4. GitHub Actions Security Best Practices (Production)

**Sources:**
- https://docs.github.com/en/actions/reference/security/secure-use
- https://blog.gitguardian.com/github-actions-security-cheat-sheet/
- https://github.com/github/awesome-copilot/blob/main/skills/github-actions-hardening/SKILL.md

Key rules for production workflows:

1. **Least-privilege GITHUB_TOKEN**: Set `permissions: contents: read` as default; escalate per-job
2. **SHA-pin all actions**: Never use `@v4` or `@main` — use `@<full-sha>` (PMOVES already enforces this)
3. **OIDC for cloud auth**: No long-lived cloud credentials; use `id-token: write` + cloud OIDC
4. **Secret scoping**: Environment-level secrets for deployment; repo-level for CI only
5. **Self-hosted runner isolation**: Ephemeral runners preferred; persistent runners need network ACLs + disk monitoring
6. **Workflow allowlist**: Restrict which workflows can run on PRs from forks
7. **Artifact/Cache pruning**: Automated cleanup to prevent disk exhaustion (relevant for KVM runners)
8. **persist-credentials: false**: On `actions/checkout` to prevent token leakage in git config

### 5. Hybrid Trigger Strategy (Recommended Pattern)

Based on the research, the production pattern for PMOVES should be a **3-layer** approach:

#### Layer 1: Upstream → Fork (fork-sync.yml)
- **Trigger**: `schedule` (daily, not weekly) + `workflow_dispatch` + `repository_dispatch` (from fork PRs)
- **What it does**: For each `sync=true` fork, fetch upstream, merge into `PMOVES.AI-Edition-Hardened`, create PR on the fork repo
- **Guard**: ahead_max=20, behind_max=1000 (existing)
- **Change needed**: increase batch from 3→20; add daily cron; add `repository_dispatch` trigger for fork PR events

#### Layer 2: Fork → Parent Gitlink (submodule promotion)
- **Trigger**: `workflow_run` on fork-sync PRs merging + `workflow_dispatch` + `push` to `.gitmodules`
- **What it does**: After a fork's hardened branch advances (fork-sync PR merged), auto-promote the gitlink in PMOVES.AI
- **Implementation**: `update-submodules` action or custom script using GitHub API (no clone needed)
- **Guard**: only promote if fast-forward; create PR (not direct commit)

#### Layer 3: KVM Runner Health (disk-cleanup.yml)
- **Trigger**: `schedule` (daily) + `workflow_dispatch`
- **What it does**: `docker builder prune`, `docker image prune`, log rotation check, disk space report
- **Guard**: skip if disk >80% free; alert if <20%

### 6. What NOT to Do

- **Don't use Dependabot for gitsubmodule**: too noisy, doesn't handle the fork layer, can't target specific branches
- **Don't direct-commit gitlinks**: always create PRs for audit trail (production requirement)
- **Don't increase batch size without rate-limit awareness**: GitHub API has secondary rate limits on rapid compare calls
- **Don't use PAT for cross-repo operations**: use the GitHub App token (already provisioned, scoped, rotatable)

## Proposed Plan (For Review — Not Implementation)

### Phase 1: Fix fork-sync cadence (low risk)
- Change cron from weekly to daily
- Increase default max_forks from 3 to 20
- Add `push` trigger on `.gitmodules` and `fork_registry.json` changes

### Phase 2: Auto-promote gitlinks on fork PR merge (medium risk)
- New workflow: `gitlink-promoter.yml`
- Triggers on fork-sync PR merges (via `workflow_run` or GitHub webhook)
- Creates a PR in PMOVES.AI with the gitlink bump (not direct commit)
- Runs submodule-smoke CI check on the PR

### Phase 3: Fork PR dispatch (higher complexity)
- Each PMOVES fork gets a `.github/workflows/dispatch-parent.yml`
- On push to `PMOVES.AI-Edition-Hardened`, dispatches to PMOVES.AI
- PMOVES.AI receives `repository_dispatch` and runs gitlink promoter

### Phase 4: Runner health automation
- Daily `docker system prune` on KVM runners
- Alert when disk <20%
- Auto-clean buildkit cache when runner is idle

## Open Questions for Operator

1. Should fork-sync run daily or on-push? (Daily is simpler; on-push is faster but needs fork-side workflows)
2. Should gitlink promotion be automatic (PR) or remain manual (agent)? (Automatic PR is production-safe; manual is slower)
3. Should we add Dependabot for action version updates (not submodules)? (Security best practice; low noise)
4. Should KVM runner cleanup be a GitHub Action or a cron on the KVM host? (GitHub Action is auditable; cron is simpler)
