# WORKORDER — Migrate `GH_PAT` consumers to GitHub App installation tokens

**Author:** 5090-CLAUDE (Opus 4.8) · 2026-06-30
**Status:** OPEN — queued for **z890** (infra/secrets/GH App lane)
**Owner (recommended):** z890-CLAUDE — owns the GitHub App + secrets/runner infra
**Runbook:** `deploy/runbooks/github-app-sitrep-and-pat-runbook.md` §4 · context: `.claude/context/credentials-workflow.md`

## Trigger

`GH_PAT` (fine-grained, **30-day expiry**) silently expired ~2026-06-25 → **PAT Health Check failed daily on `main` for 5 days** (401 from `gh api user`), degrading CI (GHCR, cross-repo, secrets-sync). Operator rotated it 2026-06-30; manual re-trigger (run `28425655516`) is **green**. The 30-day cadence guarantees this recurs. DARKXSIDE: "should it be more, and should we use the gh app for this" → **use the App.**

## Decision

Migrate `GH_PAT` consumers to **GitHub App installation tokens** (1-hour, auto-minted, auto-refreshed — no expiry outage, short-lived + scoped). The App is installed and healthy: `GH_APP_ID/SEC/CLIENT_ID/INSTALLATION_ID` present; `GHCR_APP_*` rotated 2026-06-23.

## Findings (scoped 2026-06-30)

**7 workflows consume `secrets.GH_PAT`:**
`build-images.yml`, `integrations-ghcr.yml`, `self-hosted-builds.yml`, `self-hosted-builds-hardened.yml`, `sync-secrets-local.yml`, `sync-secrets-spark.yml`, `pat-health-check.yml`.

**6 of them already mint App tokens** (`create-github-app-token`): build-images, integrations-ghcr, self-hosted-builds, self-hosted-builds-hardened, sync-secrets-local, pat-health-check (+ `test-app-token.yml` as a reference). **The plumbing already exists** — migration is mostly "point the remaining `${{ secrets.GH_PAT }}` references at the already-minted App token," not a from-scratch build.

## Scope

**Straightforward (App token already minted in-file):** replace residual `GH_PAT` usage in the CI workflows — `build-images`, `integrations-ghcr`, `self-hosted-builds`, `self-hosted-builds-hardened`, `sync-secrets-local`. Verify the App installation has the permissions each step needs (contents, pull-requests, packages:write, workflow, issues for the trackers).

**Needs a decision (App tokens can't cover directly):**
1. **`pat-health-check.yml`** — tests `gh api user` (user context); an App token has no "user." Retire/rework once the PAT is gone (e.g., switch to an App-installation validity probe).
2. **Sidecar git remote** (runbook §3.3) — long-running container pushing with a static token; 1-hour App tokens need an **App-token-refresh sidecar**, or this one spot keeps a token.
3. **`on: push` chaining** — App-token pushes do **not** trigger downstream `on: push` workflows by default. Verify nothing relies on that, or use a PAT/App-with-elevated-event for those specific pushes.

## Recommendation

- **GitHub App by default** for all CI auth (kills the recurring 30-day outage).
- For the 2-3 edge cases: either keep **one** PAT bumped to **1-year expiry + the health check**, or add an **App-token-refresh sidecar** (preferred for the long-running git remote).
- Retire `pat-health-check.yml`'s user-context probe in favor of an App-installation health probe.

## Acceptance

- [ ] All CI workflows authenticate via App tokens; `grep -rn 'secrets.GH_PAT' .github/workflows` returns only the deliberately-retained edge case(s), each documented.
- [ ] A green run of each migrated workflow (GHCR push, cross-repo, secrets-sync).
- [ ] Health probe updated to validate the App installation (not a user PAT).
- [ ] Runbook §4 updated to reflect the migrated state.

## Coordination

z890 owns this lane. Separate from the Google OAuth vertical (PR #1908). No code in this work-order — analysis + scope only; z890 to spec → plan → implement.
