# GH_PAT → GitHub App Token Migration Checklist

**Goal:** eliminate the recurring `GH_PAT` expiry outage (the daily "🔴 GH_PAT Expired"
issues, broken CI, and Dependabot "couldn't access the repository") by moving CI,
the self-hosted runners, and the sidecar git remote onto **GitHub App installation
tokens**. Companion to `github-app-sitrep-and-pat-runbook.md` (§4) and
`github-app-permission-matrix.md`.

Verified against GitHub docs 2026-06-18 (see Sources). **Sequenced so the PAT stays
live as a fallback until the App path is proven — no lockout.**

---

## The actual blocker (one operator action unblocks everything)

The 6 build/runner workflows **already** call `actions/create-github-app-token` with
`client-id: ${{ secrets.GH_APP_CLIENT_ID }}` + `private-key: ${{ secrets.GH_APP_SEC }}`
+ least-privilege `permission-*`. The wiring is correct. Token generation fails only
because **`GH_APP_SEC` is empty, truncated, or holds the App *client secret* instead
of the private-key PEM** — these are different things (the repo also has
`GH_APP_CLIENT_ID`, which is easy to confuse with the PEM).

> Fix `GH_APP_SEC` and most of the migration is done.

---

## Phase 0 — OPERATOR: populate the private key (required, not automatable)

1. **Generate the PEM**: GitHub → the *PMOVES.AI* App → *Edit* → *Private keys* →
   *Generate a private key*. The `.pem` downloads once and **cannot be re-downloaded**
   (GitHub keeps only the public half). It is **PKCS#1** (`-----BEGIN RSA PRIVATE KEY-----`).
2. **Set the secret**: paste the **full multi-line PEM verbatim** (the whole
   `BEGIN…END` block) as the `GH_APP_SEC` Actions secret. `create-github-app-token`
   accepts PKCS#1 directly — **no base64, no PKCS#8 conversion** (it also auto-converts
   escaped `\n`, but pasting the real multi-line value is simplest). Org-level secret
   if you want a single rotation point across repos.
3. **Verify the key matches GitHub** (optional local sanity check):
   ```bash
   openssl rsa -in key.pem -pubout -outform DER | openssl sha256 -binary | openssl base64
   ```
   Compare to the fingerprint GitHub shows next to the key.
4. **Confirm install + permissions**: the App must be installed on `POWERFULMOVES/PMOVES.AI`
   with `contents`, `metadata`, `packages: write`, and (for runner registration)
   `administration`. See `github-app-permission-matrix.md`.

## Phase 1 — Prove it (canary, no risk)

Run `test-app-token.yml` via **workflow_dispatch** (it may be disabled —
`gh workflow enable test-app-token.yml` first). It exercises `client-id` +
`GH_APP_SEC` and verifies repo access. **Green = token GENERATION fixed.** Status
2026-06-18: **GREEN** ✅ (PEM set, token mints).

> **⚠️ Canary-green is necessary but NOT sufficient.** It proves the App can
> *authenticate*; it does **not** prove the App has `packages: write` on the
> **org** or `administration`. The known trap (documented in `GITHUB_APP.md` and
> in `integrations-ghcr.yml`'s GHCR login comments): **App login can succeed while
> the package blob PUT 403s** — `"installation not allowed to Write organization
> package"`. So:
> - **Before Phase 2** (App-first GHCR *push*): confirm/grant the App
>   **`packages: write`** at the **organization** level, then push a real image and
>   confirm the blob upload (not just login) succeeds. Until then, keep PAT/GHCR_TOKEN
>   first for GHCR push. (PR #1843 attempted App-first GHCR login and was reverted
>   for exactly this reason.)
> - **Before Phase 4** (runner registration): confirm/grant **`administration`**.
> Verify the live grants in the App settings (the repo `…/installation` endpoint
> needs an App JWT, so check it from a workflow using the minted token, or in the
> GitHub App admin UI).

## Phase 2 — Cut over GHCR / build auth (keep fallback)

In the 4 build workflows (`build-images.yml`, `integrations-ghcr.yml`,
`self-hosted-builds.yml`, `self-hosted-builds-hardened.yml`): make the App-token step
authoritative for `docker login ghcr.io` (token as password, user = app-slug).
**Leave the `|| secrets.GH_PAT_PUBLISH || github.token` fallback in this round** so a
misconfig can't red-wall CI. Verify a real build pushes to GHCR.

## Phase 3 — Cut over the sidecar git remote / private clone

`integrations-ghcr.yml` uses `CI_GIT_CLONE_TOKEN || GH_PAT_PUBLISH` (lines ~112, ~421).
Replace with an App-minted token. Because installation tokens expire in **~1h**, a
long-running sidecar must hold the **PEM (ideally from Vault / the CHIT secrets-funnel),
not a static token**, and re-mint every <60 min (mint JWT from PEM →
`POST /app/installations/{id}/access_tokens` → rewrite the remote credential).

## Phase 4 — Cut over runner registration

PEM → JWT → installation token → `POST /repos/{owner}/{repo}/actions/runners/registration-token`
→ register with that ~1h token. **Never** leave the PEM or a long-lived token on the
runner; prefer a broker/proxy that hands the runner only the short-lived registration
token (e.g. `google-github-actions/github-runner-token-proxy`). Re-register one runner,
confirm it runs a job, then roll the rest. (App `administration` permission required.)

## Phase 5 — Remove the PAT LAST

Once Phases 1–4 are green on real runs: delete the `|| GH_PAT*` fallbacks; retire
`GH_PAT`, `GH_PAT_PUBLISH`, `CI_GIT_CLONE_TOKEN`; drop/repurpose `pat-health-check.yml`.
**Revoke the PAT on GitHub only after** the App path has run clean for a full cycle.

### PAT touchpoints to retire (grep targets)
- `GH_PAT` — `sync-secrets-local.yml`, `sync-secrets-spark.yml`, `pat-health-check.yml`
- `GH_PAT_PUBLISH` / `GHCR_TOKEN` GHCR-login fallbacks — all 4 build workflows
- `CI_GIT_CLONE_TOKEN || GH_PAT_PUBLISH` sidecar clone — `integrations-ghcr.yml`

---

## Going-forward hygiene (the durable win)

- **App private keys do not expire** (unlike the 7-day PAT) — they're revoked manually.
  The 1h installation tokens are short-lived and auto-re-minted. This removes the
  recurring expiry outage entirely.
- **Dual-key rotation, zero downtime**: an App supports up to 25 keys. Rotate by
  generating key #2 → updating `GH_APP_SEC` → re-running `test-app-token.yml` → deleting
  key #1 on GitHub.
- **`create-github-app-token` gotcha**: the token is revoked in the action's `post` step,
  so it **cannot be passed to another job** — mint per-job (or set `skip-token-revoke: true`).
  Always set explicit `permission-*` for least privilege; an unset permissions list grants
  everything the installation has.

## "Other ways" beyond a raw PEM secret (optional hardening)

| Option | Fit | Tradeoff |
|---|---|---|
| Raw PEM in `GH_APP_SEC` (Phase 0) | now — lowest lift | PEM leaves GitHub into the runner |
| **Org-level** PEM secret | many repos, one rotation point | same security, less duplication |
| **PEM from Vault / CHIT secrets-funnel at runtime** | best for self-hosted runners + sidecar | PEM never stored in GitHub; central audit; small bootstrap |
| **OIDC → KMS keyless JWT signing** (`create-github-app-token-aws-kms`) | gold standard | key never leaves HSM; larger IAM/OIDC lift |
| **OIDC → token-broker app** (`helaili/github-oidc-auth-app`) | no PEM shared to consumer repos | run/operate the broker |

PMOVES path: Phase 0 PEM now → optional Phase 2 fold the PEM into the Vault/CHIT
secrets-funnel for self-hosted + sidecar. OIDC/KMS is a later, larger hardening lift.

---

## Sources
- Managing private keys for GitHub Apps — https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps
- About authentication with a GitHub App — https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/about-authentication-with-a-github-app
- Generating an installation access token — https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app
- `actions/create-github-app-token` — https://github.com/actions/create-github-app-token
- Runner registration tokens (REST) — https://docs.github.com/en/rest/actions/self-hosted-runners
- Runner token proxy — https://github.com/google-github-actions/github-runner-token-proxy
- OIDC auth broker app — https://github.com/helaili/github-oidc-auth-app
- KMS keyless token — https://github.com/konippi/create-github-app-token-aws-kms
