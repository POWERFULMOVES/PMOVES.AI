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

Quick start (single-env)
```bash
cp pmoves/env.shared.example pmoves/env.shared   # fill real values from vault/hand-off
make env-setup                                   # syncs .env, .env.local, generated files
make env-check                                   # optional sanity
./pmoves/tools/push-gh-secrets.sh --repo POWERFULMOVES/PMOVES.AI --env Dev  # mirror to GH Secrets
```

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

### Shortcut: push env.shared to GitHub secrets
Use `pmoves/tools/push-gh-secrets.sh` to send keys from `pmoves/env.shared` to GitHub Secrets without UI clicks:

```bash
./pmoves/tools/push-gh-secrets.sh --repo POWERFULMOVES/PMOVES.AI --env Dev
# or target a subset / specific manifest
./pmoves/tools/push-gh-secrets.sh --only SUPABASE_SERVICE_ROLE_KEY,SUPABASE_JWT_SECRET
./pmoves/tools/push-gh-secrets.sh --manifest pmoves/chit/secrets_manifest.yaml
```

Flags: `--env` selects a GitHub Actions environment (Dev/Prod), `--only` filters keys, `--dry-run` prints without pushing. Ensure `gh auth login` first.

---

## 7. Provider API Keys & TensorZero

Beyond Supabase, PMOVES uses a number of model and integration providers. These
all follow the same pattern:

- **Local**: define the key in `pmoves/env.shared` (using `env.shared.example` as reference).
- **CI / Docker**: mirror the key as a GitHub secret (or vault export) with the
  same logical name.
- **Rotation**: rotate at the provider console, update `env.shared`, run
  `make env-setup`, then update GitHub secrets via the `secrets_sync` helper.

Key mappings (non‑exhaustive):

| Provider | Env vars | Rotation source |
| --- | --- | --- |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_API_BASE` | https://platform.openai.com/api-keys |
| Groq | `GROQ_API_KEY` | https://console.groq.com/keys |
| Anthropic | `ANTHROPIC_API_KEY` | https://console.anthropic.com/settings/keys |
| Google / Gemini | `GEMINI_API_KEY`, `GOOGLE_API_KEY` | https://aistudio.google.com/app/apikey |
| Mistral | `MISTRAL_API_KEY` | https://console.mistral.ai/api-keys |
| DeepSeek | `DEEPSEEK_API_KEY` | https://platform.deepseek.com/api-keys |
| OpenRouter | `OPENROUTER_API_KEY` | https://openrouter.ai/keys |
| xAI | `XAI_API_KEY` | https://console.x.ai |
| ElevenLabs | `ELEVENLABS_API_KEY` | https://elevenlabs.io/app/api-keys |
| Voyage | `VOYAGE_API_KEY` | Voyage console |
| Cohere | `COHERE_API_KEY` | https://dashboard.cohere.com/api-keys |
| Fireworks | `FIREWORKS_AI_API_KEY` | https://fireworks.ai/console/api-keys |
| Perplexity | `PERPLEXITYAI_API_KEY` | https://www.perplexity.ai/settings/api |
| Together | `TOGETHER_AI_API_KEY` | https://api.together.ai/settings/api-keys |
| Cloudflare Workers AI | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | https://dash.cloudflare.com/profile/api-tokens |

### TensorZero & OpenAI-compatible routing

TensorZero is configured via:

- `TENSORZERO_BASE_URL` / `TENSORZERO_API_KEY`
- `TENSORZERO_MODEL` / `TENSORZERO_EMBED_MODEL`

Agent Zero’s supervisor normalises OpenAI‑compatible endpoints using these
values:

- If `OPENAI_COMPATIBLE_BASE_URL` / `OPENAI_API_BASE` are empty, it derives a
  base URL from `TENSORZERO_BASE_URL` and populates the OpenAI‑compatible envs.
- If `OPENAI_API_KEY` is empty but `TENSORZERO_API_KEY` is present, it copies
  the TensorZero key into `OPENAI_API_KEY` so standard OpenAI clients work out
  of the box.

When rotating TensorZero credentials:

1. Rotate the API key at your TensorZero deployment.
2. Update `TENSORZERO_BASE_URL` / `TENSORZERO_API_KEY` in `pmoves/env.shared`.
3. Run `make env-setup && make env-check`.
4. Update any CI secrets that mirror these values.

This keeps Agent Zero, Archon, and downstream workers in sync with the new
TensorZero configuration while preserving the single‑env contract.
