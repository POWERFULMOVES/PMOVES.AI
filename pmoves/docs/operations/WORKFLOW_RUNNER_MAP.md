# GitHub Actions Workflow → Runner Map

> Maps all workflows to their runner assignments, triggers, and target nodes.
>
> Last updated: 2026-03-14

---

## Workflow Inventory (19 workflows)

### CI / Testing Workflows

| Workflow | File | Trigger | Runner(s) | Purpose |
|----------|------|---------|-----------|---------|
| **Python Tests** | `python-tests.yml` | push, PR, schedule | `ubuntu-latest` | pytest matrix (Python 3.11) |
| **UI Tests** | `ui-tests.yml` | push, PR, schedule | `ubuntu-latest` (4 jobs) | Node 20 frontend tests |
| **SQL Policy Lint** | `sql-policy-lint.yml` | push, PR (sql/, migrations/) | `ubuntu-latest` | Migration validation |
| **CHIT Contract** | `chit-contract.yml` | push, PR | `ubuntu-latest` | CHIT schema validation |
| **Integration Gate** | `integration-gate.yml` | push, PR | `ubuntu-latest` | Integration contract checks |
| **Integration Contract** | `integration-contract.yml` | push, PR | `ubuntu-latest` | Python 3.11 contract validation |
| **Codex Parity Advisory** | `codex-parity-advisory.yml` | push, PR | `ubuntu-latest` | Codex compatibility check |

### Security & Hardening

| Workflow | File | Trigger | Runner(s) | Purpose |
|----------|------|---------|-----------|---------|
| **CodeQL** | `codeql.yml` | push (main), PR, schedule (Fri 20:16 UTC) | PR: `ubuntu-latest`; protected: `self-hosted, Linux, X64` | Security scanning |
| **Hardening Validation** | `hardening-validation.yml` | push/PR (Dockerfiles, compose) | `ubuntu-latest` (4 jobs) + `self-hosted, ai-lab` (docker-bench) | Container hardening |

### Build & Deploy

| Workflow | File | Trigger | Runner(s) | Purpose |
|----------|------|---------|-----------|---------|
| **Self-Hosted Builds** | `self-hosted-builds.yml` | push (main/develop), PR, dispatch | GPU: `ai-lab, gpu` (disabled); CPU: `self-hosted, Linux, X64`; Staging: `cloudstartup, staging`; Prod: `kvm4, production` | Main build pipeline |
| **Self-Hosted Builds (Hardened)** | `self-hosted-builds-hardened.yml` | push (main/develop), dispatch | Same as above (hardened variant) | Hardened build pipeline |
| **Build Images** | `build-images.yml` | dispatch | Setup: `ubuntu-latest`; Build: `self-hosted, Linux, X64` | Multi-arch image builds |
| **Deploy Gateway Agent** | `deploy-gateway-agent.yml` | push (main), dispatch | Validate: `ubuntu-latest`; Build+Test: `ai-lab`; VPS: `kvm4` | Gateway Agent deployment |
| **Integrations GHCR** | `integrations-ghcr.yml` | push, dispatch | Setup: `ubuntu-latest`; Build: `self-hosted, Linux, X64` | Integration image builds |

### Maintenance & Tooling

| Workflow | File | Trigger | Runner(s) | Purpose |
|----------|------|---------|-----------|---------|
| **Sync Secrets Local** | `sync-secrets-local.yml` | dispatch | `self-hosted, ai-lab` | Pull GitHub Secrets → local .env |
| **Env Preflight** | `env-preflight.yml` | push, dispatch | `windows-latest` | Windows environment validation |
| **Webhook Smoke** | `webhook-smoke.yml` | dispatch | `ubuntu-latest` | Render-webhook smoke test |
| **yt-dlp Bump** | `yt-dlp-bump.yml` | schedule (Mon 08:00 UTC) | `ubuntu-latest` | Auto-update yt-dlp dependency |
| **Python Images Canary** | `python-images-toolchain-canary.yml` | schedule (Mon 09:00 UTC), dispatch | `self-hosted, Linux, X64, vps` | Python base image freshness |

---

## Runner Assignment Summary

| Runner | Workflow Count | Typical Use |
|--------|---------------|-------------|
| `ubuntu-latest` | 12 (sole or partial) | Tests, linting, validation, lightweight CI |
| `self-hosted, Linux, X64` | 5 | CPU builds, image publishing, contract validation |
| `self-hosted, ai-lab, gpu` | 3 | GPU builds (currently disabled in main pipeline) |
| `self-hosted, cloudstartup, staging` | 2 | Staging deployments |
| `self-hosted, kvm4, production` | 2 | Production deployments |
| `self-hosted, vps` | 1 | Python images canary |
| `windows-latest` | 1 | Windows env preflight |

---

## Deployment Pipeline Flow

```text
Push to main
  → self-hosted-builds.yml
    ├── setup-matrix (ubuntu-latest)
    ├── build-gpu (self-hosted, ai-lab, gpu) [DISABLED]
    ├── build-cpu (self-hosted, X64) — 9 service matrix
    ├── validate-contracts (self-hosted, X64)
    ├── deploy-staging (self-hosted, cloudstartup) — needs: build-cpu
    ├── functional-tests (self-hosted, X64) — needs: deploy-staging
    └── deploy-production (self-hosted, kvm4) — needs: build-cpu, deploy-staging
```

---

## Key Credentials for Workflows

| Secret | Used By | Purpose |
|--------|---------|---------|
| `GHCR_TOKEN` | build-images, self-hosted-builds, integrations-ghcr | Push to GitHub Container Registry |
| `GH_PAT_PUBLISH` | build-images | Cross-repo publishing |
| `DOCKERHUB_TOKEN` | build-images | Push to Docker Hub |
| `GH_APP_ID` / `GH_APP_SEC` | deploy-gateway-agent | GitHub App token generation |
| `HOSTINGER_API_KEY` | deploy-gateway-agent | Hostinger API access |
| `TAILSCALE_AUTHKEY` | deploy-gateway-agent | Tailscale node join |
| `DISCORD_WEBHOOK_URL` | self-hosted-builds | Deployment notifications |

---

## Concurrency Strategy

All workflows use:
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
```

- **PRs:** Cancel stale runs (saves runner minutes)
- **main branch:** Never cancel (all runs complete)
