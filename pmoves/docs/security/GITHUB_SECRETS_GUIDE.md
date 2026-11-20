# GitHub Secrets Guide for PMOVES.AI

> **Part of the [PMOVES.AI Integration Layer](../INTEGRATIONS_OVERVIEW.md)** | Category: Secrets & Credentials | See also: [Secrets Pipeline Reference](../SECRETS_PIPELINE_REFERENCE.md)

This guide covers how PMOVES.AI stores secrets in GitHub and how its workflows read them.

> **Correction (2026-11-20).** Earlier revisions of this guide described a `PMOVES_` name prefix (`PMOVES_OPENAI_API_KEY`, `PMOVES_SUPABASE_URL`, ...) and per-environment prefixes (`PMOVES_DEV_*`, `PMOVES_STAGING_*`, `PMOVES_PROD_*`). **No workflow reads any of those names.** Measured at this revision: `.github/workflows/*.yml` references 145 distinct `secrets.<NAME>` values, and none of them starts with `PMOVES_`. Secrets use the **bare name of the env var they feed**, for example `OPENAI_API_KEY` and `SUPABASE_JWT_SECRET`. The secret-to-env map lives in `.github/workflows/sync-secrets-local.yml` (the Supabase rows are at `:222-227`). If you created a secret under a `PMOVES_` name because of the old guide, nothing reads it.

## Overview

GitHub Secrets hold the production values of PMOVES credentials. They reach a node in one of two ways:

- **Runner nodes**: `sync-secrets-local.yml` encodes the mapped secrets into a CHIT bundle and writes `local.env`. Then `make -C pmoves secrets-funnel` overlays `local.env` into `env.shared` through `secrets-local-hydrate`.
- **Runnerless nodes**: `make -C pmoves secrets-funnel-from-prod` pulls the published bundle and does the same.

Two things follow from this:

1. A secret that has **no row** in the `sync-secrets-local.yml` env map never reaches any node, even if it is registered in the CHIT manifest. `pmoves/tools/secrets_bundle_map_gap.py` guards that gap.
2. Rotating a value in GitHub changes nothing on a node until that node re-funnels. See [`../handoffs/SECRET_ROTATION_RUNBOOK.md`](../handoffs/SECRET_ROTATION_RUNBOOK.md) § "Stale local value".

## Limits and scopes

Per GitHub's documentation (<https://docs.github.com/en/actions/reference/security/secrets>):

> "You can store up to 1,000 organization secrets, 100 repository secrets, and 100 environment secrets."

> "Secrets are limited to 48 KB in size."

**Repository scope and environment scope do not pool.** Each environment has its own 100-secret cap, separate from the repository's 100. A key that is "in GitHub" might be in the repository scope, in an environment such as `Prod`, or in both.

**Measured 2026-11-20:**

| Scope | Count | State |
|---|---|---|
| repository | 90 / 100 | 10 slots left |
| environment `Prod` | 100 / 100 | **AT CAP**: no new secret can be added |
| environment `PMOVES` | 1 / 100 | |

Some keys exist as **duplicate copies** in the repository scope and in `env:Prod`. If you rotate only one copy, a workflow that reads the other copy keeps shipping the stale value. Rotate both.

Tooling:

- `make -C pmoves gh-secret-capacity-audit [ENV=Prod]` reconciles the CHIT manifest's `github_secret` targets against the cap. It exits `1` on findings and `3` if it cannot measure. (Through `make`, every nonzero exit shows up as `2`. Call `pmoves/tools/github_secret_capacity_audit.py` directly when you need the real exit code.)
- `pmoves/tools/push-gh-secrets.sh --env <Env>` pushes to one environment. `--routed` pushes each `github_secret` target of the v2 CHIT manifest to the scope it is routed to. Add `--dry-run` first.
- **GitHub Apps.** Because the cap rules out one-scope-fits-all, repository and environment secrets are managed through the PMOVES.AI GitHub App (`GH_APP_ID`, `GH_APP_CLIENT_ID`, `GH_APP_INSTALLATION_ID`, `GH_APP_SEC`). Mint a token with `make -C pmoves gh-app-token`. `GHCR_APP_*` (`GHCR_APP_CLIENT_ID`, `GHCR_APP_SEC`) is a **different** app, the CI packages app for GHCR, so do not swap the two. `GH_APP_SEC` and `GHCR_APP_SEC` are PEM private keys. See the runbook's GH_APP_SEC subsection for the storage format.

## Supabase keys are per-node

Each node runs **its own** Supabase and Kong, so a Supabase key is only correct on the node that minted it. The workflow already refuses to ship the URL-shaped Supabase values for this reason. `SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`, and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are deliberately **not mapped** (`sync-secrets-local.yml:365-377`; the anon key is derived per node from `SUPABASE_JWT_SECRET`).

The remaining `SUPABASE_*` rows (`SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `SUPABASE_REALTIME_*`, `SUPABASE_KEY`) **are** still mapped and delivered fleet-wide. That mapping is under review in [PR #3496](https://github.com/POWERFULMOVES/PMOVES.AI/pull/3496). Until the review settles it:

- Never run a bare `secrets-local-hydrate FORCE=1` on a node whose own Supabase is live. It overwrites that node's keys with another node's and breaks the Kong/cipher pairing.
- To refresh one rotated key, scope the hydrate: `make -C pmoves secrets-local-hydrate KEYS=<K> FORCE=1`.

## Reference in workflows

Use the bare name. If the job needs environment-scoped values, set `environment:` on the job. GitHub then resolves `secrets.<NAME>` from that environment first and falls back to the repository scope. **Do not encode the environment in the secret name**; environments already scope it.

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: Prod          # env-scoped secrets resolve from here
    steps:
      - uses: actions/checkout@v4
      - name: Deploy services
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: make deploy
```

A secret that feeds a node at runtime also needs a row in the `sync-secrets-local.yml` env map (see Overview).

### Skip a step when a secret is absent

`secrets.*` cannot be referenced directly in a step-level `if:`. Map it to an env var and test that:

```yaml
      - name: Test OpenAI
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          if [ -z "$OPENAI_API_KEY" ]; then echo "OPENAI_API_KEY not set; skipping"; exit 0; fi
          pytest tests/test_openai.py
```

## Secret names reference

These are the names the workflows actually read, as measured at this revision. To regenerate the full list (145 names):

```bash
grep -ho 'secrets\.[A-Z0-9_]*' .github/workflows/*.yml | sort -u
```

| Area | Names (bare, as read by workflows) |
|---|---|
| LLM providers | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `COHERE_API_KEY`, `MISTRAL_API_KEY`, `DEEPSEEK_API_KEY`, `TOGETHER_AI_API_KEY`, `FIREWORKS_AI_API_KEY` |
| Supabase (per-node, see above) | `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `SUPABASE_REALTIME_KEY`, `SUPABASE_REALTIME_SECRET`, `SUPABASE_KEY` (`SUPABASE_URL` is intentionally **not** a mapped secret) |
| GitHub Apps | `GH_APP_ID`, `GH_APP_CLIENT_ID`, `GH_APP_INSTALLATION_ID`, `GH_APP_SEC`; `GHCR_APP_CLIENT_ID`, `GHCR_APP_SEC` |
| Integrations | `DISCORD_WEBHOOK_URL`, `TELEGRAM_BOT_TOKEN`, `JELLYFIN_API_KEY` |

Several names listed in earlier revisions are read by **no** workflow: `POSTGRES_URL`, `MONGODB_URI`, `REDIS_URL`, AWS, GCP, Azure, Sentry, Datadog, New Relic, Honeycomb, Slack, and Spotify. They were illustrative and have been removed. If you need one, add the workflow row and the manifest entry together.

## Organization secrets

The organization scope has its own cap (1,000). Org secrets are shared across the repositories you select, and workflows read them with the same bare `secrets.<NAME>` syntax. PMOVES.AI does not currently rely on org-scoped secrets for the funnel.

## Best practices

1. **Naming**: use the bare env-var name the consumer reads. No `PMOVES_` prefix and no environment prefix.
2. **Rotation**: follow [`SECRET_ROTATION_RUNBOOK.md`](../handoffs/SECRET_ROTATION_RUNBOOK.md). Rotate every scope that holds a copy (repository **and** `env:Prod`), then re-funnel the nodes.
3. **Capacity**: run `gh-secret-capacity-audit` before adding a secret to `env:Prod`, because it is at cap.
4. **Least privilege**: use scoped tokens. `make -C pmoves gh-app-token` takes `REPOSITORIES=` and `PERMISSIONS=`, and an over-broad `ALL=1` requires `CONFIRM=1`.

## Troubleshooting

### Secret not accessible
1. Check that the name matches exactly (case-sensitive, bare, no `PMOVES_` prefix).
2. Check the scope. An `env:Prod` secret is invisible to a job that has no `environment: Prod`.
3. For runtime delivery, check that the name has a row in the `sync-secrets-local.yml` env map.

### Rotated in GitHub, but the node still has the old value
The node has not re-funnelled, or `secrets-local-hydrate` skipped the key because `env.shared` already held a non-placeholder value. See [`SECRET_ROTATION_RUNBOOK.md`](../handoffs/SECRET_ROTATION_RUNBOOK.md) § "Stale local value".

### Secret value masked in logs
This is expected. GitHub masks secret values in workflow logs.

## Moving values from env.shared into GitHub

Use the push tool rather than hand-copying values. It reads the env file and never echoes values:

```bash
pmoves/tools/push-gh-secrets.sh --env Prod --only KEY1,KEY2 --dry-run   # inspect
pmoves/tools/push-gh-secrets.sh --routed --dry-run                      # manifest-routed scopes
```

## See also

- [`SECRETS_ONBOARDING.md`](SECRETS_ONBOARDING.md): general secrets setup
- [`DOCKER_SECRETS_GUIDE.md`](DOCKER_SECRETS_GUIDE.md): Docker/K8s secrets
- [`../PMOVESCHIT/CHIT_USER_GUIDE.md`](../PMOVESCHIT/CHIT_USER_GUIDE.md): CHIT encoding
- [`../SECRETS_VAULT_INTEGRATION_RUNBOOK.md`](../SECRETS_VAULT_INTEGRATION_RUNBOOK.md): Vault (runtime secrets; GitHub scope and cap are covered here, not there)
