# PMOVES.AI GitHub App — platform automation primitive

The **PMOVES.AI** GitHub App is the fleet's cross-repo automation identity. As of
2026-06-07 it is installed on **All repositories** under `POWERFULMOVES` with
Read & write on: contents, pull requests, **workflows**, actions, deployments,
secrets, checks, issues, discussions, environments, packages, pages, security
events, dependabot, merge queues, commit statuses (+ admin on repository
projects). That is a powerful primitive — treat it as one, and guard it.

Credentials (secrets on PMOVES.AI): `GH_APP_CLIENT_ID` (v3 client-id),
`GH_APP_ID` (v1 app-id, legacy), `GH_APP_SEC` (private key),
`GH_APP_INSTALLATION_ID`. Standardize new work on **client-id (v3)**.

## The rule: mint via the reusable workflow, never ad-hoc

Call [`.github/workflows/_app-token.yml`](../../../.github/workflows/_app-token.yml)
— do **not** re-implement `actions/create-github-app-token` inline. One source of
truth = scoping + SHA-pinning bugs can't be reintroduced per-workflow (they were,
8 different ways — see Audit below).

```yaml
jobs:
  token:
    uses: ./.github/workflows/_app-token.yml
    secrets: inherit            # passes GH_APP_CLIENT_ID + GH_APP_SEC
    with:
      repositories: |           # EXACT repos — least privilege
        PMOVES-Archon
        PMOVES-Open-Notebook
      permission-contents: write
      permission-pull-requests: write
      # permission-workflows: write   # ONLY when pushing under .github/workflows/
  work:
    needs: token
    runs-on: ubuntu-latest
    steps:
      - env: { GH_TOKEN: "${{ needs.token.outputs.token }}" }
        run: gh api ...
```

### Token-scoping truth table (memorize)

| `owner` | `repositories` | Scope |
|---|---|---|
| empty | empty | current repo only |
| set | empty | **ALL repos in the installation — over-broad, avoid** |
| set | listed | exactly those repos ✅ |

Installation tokens are single-owner and live <=1h (auto-revoked at job end).
Always pair `owner` with an explicit `repositories:` list + minimal `permission-*`.

## Upstream->fork merges (fork-sync)

The REST `/merges` endpoint does **not** accept cross-repo `owner:branch` as
`head`; `/merge-upstream` is FF-only with no conflict handling. The robust pattern
is **local git in the runner**: clone fork -> add upstream remote -> fetch ->
merge -> push `sync/*` -> `gh pr create` (PR `head` must be `fork-owner:branch`).
Pushing a merge that touches `.github/workflows/` requires the App's
**Workflows: write** + `permission-workflows: write` on the minted token.

## Submodule sync pipeline (two layers)

1. **fork <- upstream** — `fork-sync.yml` (24 curated forks; local-git merge -> PR
   on each fork; auto-skips conflicts). App token scoped to the fork list.
2. **PMOVES.AI gitlink <- fork HEAD** — `submodule-update-check.yml` (promotes
   gitlinks; currently only 4 of 48 submodules — expansion is a tracked follow-up).

See `research/SUBMODULE_SYNC_AUDIT_2026-06-07.md` for the live drift backlog.

## Audit findings (2026-06-07) + remediation roadmap

- [x] App installed on All repositories + Workflows R/W (operator, 2026-06-07).
- [x] `fork-sync.yml` token scoped via `owner` + `repositories:` (#1736).
- [x] Reusable `_app-token.yml` established (this PR).
- [ ] **SHA-pin the 6 unpinned `@v3` token blocks** (build-images, self-hosted-builds
      x2, self-hosted-builds-hardened x2, test-app-token) — supply-chain risk: a
      push to the action's tag could exfiltrate `GH_APP_SEC`.
- [ ] **Migrate those 6 + integrations-ghcr + fork-sync to call `_app-token.yml`**
      (kills the duplication; standardizes on client-id v3).
- [ ] **Retire PATs the App can replace**: `GH_PAT`, `GH_PAT_PUBLISH`, `GHCR_TOKEN`,
      `ACTIONS_PAT`, (partly) `CI_GIT_CLONE_TOKEN`. Then retire `pat-health-check.yml`.
- [ ] **Fix GHCR org packages:write** so the App token stops falling back to PATs
      for image pushes (app-install setting, not a workflow change).
- [ ] **Drop unused App permissions** (e.g. secrets:write, security_events:write if
      no workflow needs them) and **rotate `GH_APP_SEC`** now that scope is broad.
- [ ] **Expand `submodule-update-check.yml`** from 4 -> all hardened submodules (or a
      batch `chore(submodules): promote` job) and connect fork-PR-merge -> gitlink.
- [ ] **Fork orphan-branch cleanup** — `stale-branch-sweep.yml` only sweeps
      PMOVES.AI; fork `sync/*` branches accumulate. Add cross-repo cleanup.
- [x] **Branch-protection automation** — `branch-protection-sync.yml` +
      `_app-token.yml` `permission-administration` knob (2026-06-09). Closes the
      audit gap below. **Gated on the operator granting Administration:RW** (see
      next section).

## Branch protection (consumable / hardened fork branches)

**Audit gap (2026-06-09):** 8 of 11 tracked hardened fork branches had **no
protection or zero required checks** (supabase, BoTZ, BotZ-gateway,
e2b-mcp-server, tensorzero, A2UI unprotected; Health-wger, Open-Notebook had a
rule but 0 checks). A "hardened" branch with no gate is aspirational — nothing
stopped a force-push from silently stripping the hardening overlay. This never
surfaced because branch protection was **not** on the original App roadmap.

`branch-protection-sync.yml` (manual dispatch, dry-run by default) derives each
fork's consumable branch from `.gitmodules` (self-maintaining) and applies one
**standard policy**:

| Setting | Value | Why |
|---|---|---|
| Require PR before merge | yes, **0 approvals** | Blocks direct pushes; 0 lets the App / dependabot self-merge sync PRs (no deadlock). Bump per-fork later. |
| Force pushes | **blocked** | Prevents history rewrite that strips hardening — the core guarantee. |
| Deletions | **blocked** | No accidental branch loss. |
| Conversation resolution | required | Hygiene. |
| `enforce_admins` | false | Operator break-glass; matches the sanctioned `--admin` merge path. |
| Required status checks | **null (default)** | Fork CI contexts vary + many need fork-only secrets; requiring an un-greenable check would permanently block the branch. Add per-fork, deliberately. |

> ⚠️ **Operator prerequisite — Administration:RW.** Applying protection needs the
> App installation to have **Administration: Read & Write** (App settings →
> Permissions). The in-repo docs disagreed on whether it was granted: the
> 2026-04-23 permission **matrix** *designed it in* (and lists it on the operator
> checklist), but the 2026-06-07 live-state list in this doc's header **omits it**
> — i.e. it was likely never ticked. The live source of truth is the App's
> Permissions tab. `branch-protection-sync.yml` **self-validates**: if the grant
> is missing, `create-github-app-token` fails at mint with *"the app does not have
> permission to request 'administration'"*. Grant it, then re-run dry-run → apply.

## Security guardrails

- Name `repositories:` + minimal `permission-*`; never blanket `owner`.
- Pin actions to full SHAs (incl. create-github-app-token).
- `permissions: {}` at top level; grant per-job.
- Never `pull_request_target` + untrusted-checkout-then-execute with the token in scope.
- `persist-credentials: false` on checkout; inject the App token explicitly.
- App-authored commits go through PRs + required checks — do NOT add the App as a
  branch-protection bypass actor.
