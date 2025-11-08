# Secret Management Playbook

Updated: 2025-10-21

This note explains how PMOVES shares configuration secrets across the stack and
how to keep them safe while still making it easy for operators to provide the
required values.

---

## 1. Canonical Environment Files

| File | Purpose | Notes |
| --- | --- | --- |
| `pmoves/env.shared` | Single source of truth for shared credentials | Checked into `.gitignore`. Always populate Supabase keys here. |
| `pmoves/.env` | Local overrides for docker compose | Generated/maintained via `make env-setup`. |
| `pmoves/.env.local` | Runtime defaults for app services | Also maintained by `make env-setup` |

Run `make env-setup` after edits; the script now syncs the Supabase keys from
`env.shared` into `.env` and `.env.local`. You can confirm the sync with:

```bash
make env-check
```

The Supabase entries should report `env.shared=ok` and `.env` / `.env.local`
`match`. Live Supabase CLI keys start with `sb_publishable_` (anon) and
`sb_secret_` (service role). Use `make supa-status` to display the current
values after a rotation.

---

## 2. Extending Secrets to All Services

Every docker service that requires Supabase credentials includes
`env.shared` in its `env_file`. Once `env.shared` is updated, restart the
profiles that cache env vars on boot:

```bash
make up-agents           # Archon, Agent Zero, publisher-discord, mesh-agent
make up-external         # Firefly, Wger, Jellyfin, etc. (as needed)
```

Other integration tokens (Firefly, Wger, Jellyfin, n8n, etc.) should also be
defined in `env.shared` so they propagate consistently. Reference the
`env.shared.example` file for the full key list.

---

## 3. Secrets via CHIT Geometry Packets

For secure transmission you can wrap the environment values inside a
CHIT Geometry Packet (CGP) using the documented v0.1 spec. Two helpers are now
available:

```bash
# Encode env.shared into a CGP payload (cleartext by default)
make chit-encode-secrets ARGS="--env-file pmoves/env.shared --out pmoves/data/chit/env.cgp.json"

# Decode a CGP payload back to KEY=VALUE lines
make chit-decode-secrets ARGS="--cgp pmoves/data/chit/env.cgp.json --out pmoves/data/chit/env.decoded"
```

Use `--no-cleartext` to store the values using base64 form inside the CGP.
The encoder/decoder modules live under `pmoves/chit/` and align with the spec in
`pmoves/docs/PMOVESCHIT/PMOVESCHIT.md`. These helpers are intentionally simple
so we can plug in stronger encryption (HMAC + AES-GCM) as part of a future
iteration.

`pmoves/chit/secrets_manifest.yaml` provides the canonical mapping between CGP
labels and the env files we materialize locally. Generate the runtime files via
`python3 -m pmoves.tools.onboarding_helper generate` (or `make env-setup`, which
calls the same helper). The script writes `.env.generated` and
`env.shared.generated`, and Compose now prefers those files ahead of any manual
overrides. Run `python3 -m pmoves.tools.onboarding_helper status` to verify the
bundle before spinning up containers.

---

## 4. Provider Integrations & Vaults

The `scripts/env_setup.{ps1,sh}` helpers can import secrets from:

- Doppler (`make env-setup --from doppler`)
- Infisical (`--from infisical`)
- 1Password (`--from 1password`)
- SOPS (`--from sops`)

Place provider-specific exports into `pmoves/.env.generated`; the script
will merge them into `env.shared` and `.env`.

For long-term storage, prefer hosting the secrets in your vault provider and
exporting on demand. The CHIT flow above is ideal for handing off bundles for
air-gapped machines while keeping a cryptographically structured payload.

---

## 5. Checklist

1. Rotate Supabase CLI keys (`make supa-stop && make supa-start`).
2. Run `make supa-status` and update `env.shared` with the new `sb_secret_…`
   / `sb_publishable_…` values.
3. `make env-setup && make env-check` to propagate into `.env` + `.env.local`.
4. Restart the services that consume Supabase credentials (`make up-agents`,
   etc.).
5. Optionally encode the bundle via `make chit-encode-secrets` for secure
   hand-off.

## 6. CI Secret Sync

- `pmoves/config/ci_secrets_manifest.yaml` captures the subset of credentials
   required by GitHub Actions (integration image builds, smoke harnesses, etc.).
- Run `python pmoves/scripts/secrets_sync.py diff` to confirm local values match
   across CHIT bundles, `env.shared`, and GitHub repository secrets.
- To stage updates, generate an env file with `python pmoves/scripts/secrets_sync.py download`
   and feed it to the GitHub CLI (`gh secret set --repo POWERFULMOVES/PMOVES.AI --env-file …`).
- You can also push directly via `python pmoves/scripts/secrets_sync.py upload --include-optional`.
