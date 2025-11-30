# Secrets Management Options

This project uses simple `.env` files by default for local development. To make setup easy and hard to mess up, use the interactive helpers and (optionally) a secrets provider.

- Default: `make env-setup` prompts for missing values and writes them to `pmoves/.env`.
- Verify: `make env-check` shows missing keys vs `.env.example` and common pitfalls.
- Auto‑load: copy `pmoves/.envrc.example` to `pmoves/.envrc` and enable `direnv` for smooth shells.

## Optional Providers (bring‑your‑own)

You can prefill secrets from a provider by running:

- PowerShell: `pwsh -File scripts/env_setup.ps1 -From doppler|infisical|1password|sops`
- Bash: `bash scripts/env_setup.sh --from doppler|infisical|1password|sops`

Supported CLIs (install separately):
- Doppler: `doppler secrets download --no-file --format env`
- Infisical: `infisical export --format=dotenv`
- 1Password CLI: `op item get PMOVES_ENV --format json` (expects an item named `PMOVES_ENV` with key/value fields)
- SOPS: `sops -d .env.sops`

These commands populate `.env.generated` (git‑ignored). The setup scripts then merge required keys from `.env.example`, prompting only for anything still missing.

## What’s “required”?

`pmoves/.env.example` defines the keys expected for local runs. The setup/check scripts use it as the single source of truth. Keep it up to date when you add new services or variables.

## CI/CD

For GitHub Actions or other CI, store secrets in the platform’s secret store (not `.env`). The local helpers are for developer machines only.
