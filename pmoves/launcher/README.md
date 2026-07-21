# PMOVES Launcher Profiles

This directory contains launcher-readable profiles for Pinokio / P8 one-click deployments. Each profile maps a PMOVES node to its Hermes AI profile and room manifest.

## Format

Each file is a JSON profile with these fields:

| Field | Purpose |
|-------|---------|
| `node_id` | Canonical node identifier (e.g., `pmoves-z890`) |
| `pmoves_profile` | File under `pmoves/config/profiles/` (e.g., `z890-coordinator`) |
| `hermes_profile` | Hermes profile name to activate (e.g., `PMOVES-HERMES-Z890`) |
| `room` | Room manifest + stage + suits from `pmoves/config/rooms/` |
| `requirements` | Minimum hardware / software prerequisites |
| `env_secrets` | Secrets the launcher must prompt for (never commit values) |
| `skills` | PMOVES skills to auto-register in the Hermes profile |
| `launcher_refs` | Makefile / compose targets to expose in the launcher UI |
| `model_routing` | Local, remote GPU, and fallback model endpoints |
| `platform_toolsets` | Messaging platforms to enable |

## Current Profiles

| File | Node | Room | GPU | Purpose |
|------|------|------|-----|---------|
| `pmoves-hermes-z890.json` | Z890 | `z890-infra.room.fabric` | No | Local-first infra coordinator with legal/email/messaging workflows |

## How a launcher uses this

1. Read `pmoves/launcher/profiles/<profile>.json`.
2. Verify `requirements` (RAM, Docker Desktop, Hermes CLI, Ollama).
3. Prompt for any missing `env_secrets` and write them to the Hermes profile `.env`.
4. Activate the Hermes profile: `hermes profile use <hermes_profile>`.
5. Apply the PMOVES profile by copying compose overrides / env variables into `pmoves/env.shared` and `.env.local`.
6. Launch the selected services via the listed `launcher_refs` and the PMOVES Makefile.

## Helper script

`pmoves/tools/launcher_profile_select.py` applies a launcher profile to the local Hermes profile.

```bash
# Dry run
python pmoves/tools/launcher_profile_select.py --profile pmoves-hermes-z890

# Apply to live Hermes profile
python pmoves/tools/launcher_profile_select.py --profile pmoves-hermes-z890 --write

# Force overwrite existing values
python pmoves/tools/launcher_profile_select.py --profile pmoves-hermes-z890 --write --force

# Test against a different profiles directory
python pmoves/tools/launcher_profile_select.py --profile pmoves-hermes-z890 --write --profiles-dir /tmp/test-hermes-profiles
```

The script always backs up the existing `config.yaml` before writing and creates an `.env.template` file for the secrets listed in the launcher profile.

## Security

- **Do not commit secrets.** `env_secrets` are names only; values live in the Hermes profile `.env` and `pmoves/env.shared`.
- The launcher should never write secret values back into this JSON file.
- Keep profiles local-only unless explicitly approved for remote sharing.
