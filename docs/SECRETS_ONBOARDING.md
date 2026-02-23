# Secrets Onboarding & Rotation Checklist

## Storing secrets (preferred order)
1) GitHub Actions secrets (environment-scoped for Dev/Prod). Avoid repository-level if you can scope narrower.
2) Docker/Compose secrets via `*_FILE` mounts (e.g., `SUPABASE_SERVICE_ROLE_KEY_FILE`).
3) Local dev: `.env.local` (gitignored) and `pmoves/env.shared` with placeholder defaults only.

## When a secret scan/alert fires
- Assume compromise; rotate immediately in the upstream system (AWS/Supabase/Discord/etc.).
- Update GitHub Secrets and any runtime secret stores.
- If the secret was in code history, rotate all sibling credentials in the same provider.
- Record the rotation in the PR/issue and note scope (dev/prod).

## Secret scanning allowlist (keep minimal)
- Only allowlist generated test keys that cannot be removed. Prefer generating keys at test runtime instead.
- Location for allowlist file: `.github/secret-scanning-allowlist.json` (create only if necessary) with comments explaining each entry and expiry dates.

## Adding new secrets
- Use descriptive names, include environment suffix (e.g., `SUPABASE_SERVICE_ROLE_KEY_DEV`).
- Avoid putting real values in `env.shared.example`; keep placeholders.
- For local runs, use `.env.local` and never commit it.
- GHCR publishing:
  - Prefer `github.token` in workflows.
  - If a PAT is required, include `write:packages` + `read:packages` (and `repo` for private repos).
  - If using PAT auth, set both `GHCR_TOKEN` and `GHCR_USERNAME` secrets so login-action uses a matching username/token pair.
  - Local bootstrap shortcut (reuses existing env credentials and writes GHCR secrets):
    - `make -C pmoves ghcr-bootstrap-secrets GH_SECRET_ENV=Dev GH_REPO=POWERFULMOVES/PMOVES.AI`
  - For local GitHub App/webhook setup (Smee/cloudflared), see `docs/GITHUB_APP_LOCAL_SETUP.md`.

## Rotation cadence
- Mandatory rotation when alerted.
- Suggested periodic rotation for high-privilege keys (service-role, cloud provider) every 90 days.

## Required pre-merge audit
- Run `make -C pmoves secrets-audit` before production-facing merges. It checks CHIT path drift, secret-sync output location/encoding, exported workflow cookie leaks, and placeholder hygiene in tracked env templates.

## Checklist (per incident or new secret)
- [ ] Rotate in provider
- [ ] Update GitHub Secrets / secret store
- [ ] Update compose/env files (dev only, if needed)
- [ ] Remove from code/history or add minimal allowlist entry
- [ ] Note rotation in PR/issue
