# PMOVES.AI GitHub App — platform automation primitive

The **PMOVES.AI** GitHub App is the fleet's cross-repo automation identity. It is
installed on **All repositories** under `POWERFULMOVES`. Its live permission set
(validated against the App's Permissions tab **2026-06-09**) is broad — Read &
write on: **administration**, contents, pull requests, **workflows**, actions,
actions variables, checks, code, code quality, codespaces (+ lifecycle/secrets),
commit statuses, custom properties, dependabot (alerts/secrets), deployments,
discussions, environments, issues, merge queues, packages, pages, repository
advisories, repository hooks, secret scanning (+ bypass), **secrets**, security
events, attestations, agent secrets/tasks/variables, copilot agent settings;
Admin on repository projects. That is a powerful primitive — treat it as one, and
guard it. (The earlier 2026-06-07 enumeration here **omitted `administration`**;
it is in fact granted — see § Branch protection. The breadth also strengthens the
roadmap's "drop unused permissions + rotate `GH_APP_SEC`" item below.)

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

## Node-side mint (the dsh GitHub agent Known Road)

For runs OUTSIDE CI (pr-monitor sweeps, harness containers, fork tooling), the
same identity is available locally — **the one sanctioned exception** to
"never ad-hoc", because it reuses the workflow's rules rather than
re-implementing them:

```bash
make -C pmoves gh-app-token REPOSITORIES=PMOVES.AI PERMISSIONS=contents:read,pull_requests:read
# over-broad escape hatch, deliberately two-keyed:
make -C pmoves gh-app-token ALL=1 CONFIRM=1
```

- `pmoves/tools/gh_app_token.py` — JWT is RS256 via **PyJWT against `GH_APP_SEC`** (no hand-rolled crypto); scopes through the SAME truth table (explicit `--repositories` + minimal `--permissions`; `--all` refuses without `--yes`).
- **Secret hand-off is a 0600 file** (`~/.pmoves/gh_app_token`), never stdout-by-default — only metadata prints (`--print` exists for controlled piping and warns). Consume with `GH_TOKEN=$(cat ~/.pmoves/gh_app_token)`.
- Why: installation tokens carry their **own >=5,000/hr REST quota per installation** — fleet automation stops burning the shared user PAT (measured exhausted 2026-09-05 by B850 + SPARK monitor runs) and acts as the App (bot identity, clean audit trail).
- **Prerequisite**: `GH_APP_SEC` on the node must be the real PEM. The funnel tier files have carried a 40-hex placeholder on some nodes — Actions secrets are write-only, so the real key reaches nodes only via the prod CHIT bundle (`make -C pmoves secrets-pull && make -C pmoves secrets-funnel-from-prod`). The tool hard-refuses non-PEM values rather than minting garbage.
- CI stays on `_app-token.yml` — nothing here changes the workflow path.

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
      audit gap below. **App already has Administration:RW** (validated 2026-06-09)
      — ready to run (dry-run → apply); no operator grant needed.

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

> ✅ **Prerequisite satisfied — Administration:RW is granted.** Confirmed against
> the App's Permissions tab **2026-06-09**: the installation has **Administration:
> Read & Write** (the 2026-04-23 permission matrix's design was applied; the
> 2026-06-07 list in this doc's header had simply omitted it). So
> `branch-protection-sync.yml` runs without any further grant. It still
> **self-validates**: if the grant were ever revoked, `create-github-app-token`
> fails at mint with *"the app does not have permission to request
> 'administration'"*. Operator flow is just: run `dry_run=true` (audit) → re-run
> `dry_run=false` (apply).

## Security guardrails

- Name `repositories:` + minimal `permission-*`; never blanket `owner`.
- Pin actions to full SHAs (incl. create-github-app-token).
- `permissions: {}` at top level; grant per-job.
- Never `pull_request_target` + untrusted-checkout-then-execute with the token in scope.
- `persist-credentials: false` on checkout; inject the App token explicitly.
- App-authored commits go through PRs + required checks — do NOT add the App as a
  branch-protection bypass actor.
