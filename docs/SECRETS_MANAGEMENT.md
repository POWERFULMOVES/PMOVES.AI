# PMOVES.AI Secrets Management

**Version:** 5.0 (Active Fetching)
**Branch:** PMOVES.AI-Edition-Hardened
**Last Updated:** 2025-02-02

## Overview

PMOVES.AI uses a multi-layered secrets management system that supports:
- **Active credential fetching** from GitHub/Docker APIs (new in v5)
- **CHIT encoding** for secure secret storage in git
- **Tier-based environment architecture** for service isolation
- **Standalone mode** for submodules with independent credential sources

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CREDENTIAL SOURCES                            │
├─────────────────────────────────────────────────────────────────┤
│  1. Active Fetcher (GitHub/Docker APIs)  ← NEW IN V5           │
│  2. GitHub Secrets (CI/CD env vars)                               │
│  3. CHIT CGP files (encoded in git)                               │
│  4. Docker Secrets (/run/secrets/)                                │
│  5. Parent PMOVES.AI (docke mode fallback)                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    env.shared (local, NOT in git)               │
└─────────────────────────────────────────────────────────────────┘
                              │
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
┌─────────────────────────┐   ┌───────────────────────────────┐
│  CHIT Encoding          │   │  Direct Use                  │
│  (pmoves secrets encode)│   │  (source pmoves/env.shared)  │
└──────────┬──────────────┘   └───────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│  env.cgp.json (CHIT Geometry Packet)                            │
│  Location: pmoves/pmoves/data/chit/env.cgp.json                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Tier Files (pmoves env init)                                   │
├─────────────────────────────────────────────────────────────────┤
│  env.tier-llm    │  LLM provider keys, embeddings               │
│  env.tier-api    │  API gateway, Supabase                       │
│  env.tier-data   │  Postgres, Neo4j, Meilisearch                │
│  env.tier-media  │  Media processing, Whisper                   │
│  env.tier-agent  │  Agent Zero, orchestration                   │
│  env.tier-worker │  Background workers, ingestion               │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. First Time Setup

```bash
# Option A: Fetch from GitHub/Docker APIs (requires GITHUB_PAT)
GITHUB_OWNER=POWERFULMOVES GITHUB_REPO=PMOVES.AI pmoves credentials to-env-shared

# Option B: Manual env.shared creation
cp pmoves/env.shared.example pmoves/env.shared
# Edit pmoves/env.shared with your credentials

# Option C: Use bootstrap script (multi-source)
./scripts/bootstrap_credentials.sh
cat .env.bootstrap >> pmoves/env.shared
```

### 2. Encode to CHIT

```bash
pmoves secrets encode
# Creates: pmoves/pmoves/data/chit/env.cgp.json
```

### 3. Initialize Tier Files

```bash
pmoves env init
# Populates all env.tier-* files from CHIT
```

## Active Credential Fetcher (v5)

### What It Does

The active credential fetcher (`pmoves/tools/credential_fetcher.py`) can:

1. **Fetch from GitHub API** (with authentication)
   - Lists repository secrets metadata
   - Retrieves secret values from environment (if already loaded)
   - Supports both repository and organization secrets

2. **Fetch from Docker Config**
   - Reads `~/.docker/config.json`
   - Extracts registry credentials
   - Decodes base64 auth tokens

3. **Merge from Multiple Sources**
   - Environment variables (already loaded)
   - GitHub Secrets (with env values)
   - Docker credentials
   - Existing env files

### Configuration

| Environment Variable | Description |
|---------------------|-------------|
| `GITHUB_PAT` | GitHub Personal Access Token |
| `GITHUB_TOKEN` | Alternative to GITHUB_PAT |
| `GITHUB_OWNER` | Repository owner for API calls |
| `GITHUB_REPO` | Repository name for API calls |

### CLI Usage

```bash
# Fetch all credentials to env.shared
pmoves credentials fetch --github-owner POWERFULMOVES --github-repo PMOVES.AI

# List GitHub secrets (metadata only)
pmoves credentials list-github --owner POWERFULMOVES --repo PMOVES.AI

# List Docker credentials
pmoves credentials list-docker

# Fetch and write directly to env.shared
pmoves credentials to-env-shared --github-owner POWERFULMOVES --github-repo PMOVES.AI
```

### Python API

```python
from pmoves.tools.credential_fetcher import CredentialFetcher

fetcher = CredentialFetcher()
credentials = await fetcher.fetch_all(
    github_owner="POWERFULMOVES",
    github_repo="PMOVES.AI",
    include_docker=True,
)
```

## Bootstrap Script

### Usage

```bash
# Source the script (loads to environment)
source scripts/bootstrap_credentials.sh

# Or run and source separately
./scripts/bootstrap_credentials.sh
source .env.bootstrap
```

### With Active Fetcher

```bash
# Enable active fetching with GitHub credentials
GITHUB_OWNER=POWERFULMOVES \
GITHUB_REPO=PMOVES.AI \
GITHUB_PAT=ghp_xxxx \
./scripts/bootstrap_credentials.sh
```

### Credential Sources (Tried in Order)

1. **Active Fetcher** - Python module calling GitHub/Docker APIs
2. **GitHub Secrets** - Environment variables in GitHub Actions/Codespaces
3. **CHIT CGP** - Encoded secrets in `pmoves/pmoves/data/chit/env.cgp.json`
4. **git-crypt** - GPG-encrypted `.env.enc` files
5. **Docker Secrets** - Container-standard `/run/secrets/` directory
6. **Parent PMOVES.AI** - Fallback to parent repo in docked mode

## CHIT Encoding/Decoding

### Encoding (env.shared → CGP)

```bash
pmoves secrets encode \
  --env-file pmoves/env.shared \
  --out pmoves/pmoves/data/chit/env.cgp.json
```

**Options:**
- `--no-cleartext` - Store as hex only (no plaintext values)

### Decoding (CGP → env format)

```bash
pmoves secrets decode \
  --cgp pmoves/pmoves/data/chit/env.cgp.json \
  --out pmoves/pmoves/data/chit/env.decoded
```

## Environment Management

### Initialize from CHIT

```bash
pmoves env init \
  --cgp pmoves/pmoves/data/chit/env.cgp.json \
  --manifest pmoves/chit/secrets_manifest_v2.yaml
```

**What it does:**
1. Loads CHIT CGP file
2. Decodes secrets
3. Applies manifest mappings to tier files
4. Syncs common credentials across tiers
5. Generates GitHub/Docker secrets JSON files

### Validate Tier Files

```bash
pmoves env validate --tier all
pmoves env validate --tier llm --connectivity
```

## Standalone Mode for Submodules

### Overview

PMOVES.AI submodules (PMOVES-DoX, PMOVES-Archon, etc.) can run in **standalone mode** with their own credential sources.

### Submodule Credential Sources

| Source | Location | Usage |
|--------|----------|-------|
| GitHub Secrets | Repository settings | `GITHUB_OWNER` + `GITHUB_REPO` |
| Docker Config | `~/.docker/config.json` | Automatic detection |
| CHIT CGP | Submodule `data/chit/` | `pmoves/submodule-env init` |
| Parent PMOVES.AI | Detected automatically | Docked mode only |

### Submodule Setup

```bash
# In a submodule (e.g., PMOVES-DoX)
cd /path/to/PMOVES-DoX

# Option 1: Use submodule-specific GitHub repo
GITHUB_OWNER=POWERFULMOVES \
GITHUB_REPO=PMOVES-DoX \
pmoves credentials to-env-shared

# Option 2: Encode submodule secrets
pmoves secrets encode \
  --env-file env.shared \
  --out data/chit/env.cgp.json

# Option 3: Initialize from submodule CGP
pmoves submodule-env init --cgp data/chit/env.cgp.json
```

### PMOVES Integration Pattern

Submodules can integrate with parent PMOVES.AI via:

1. **NATS Message Bus** - Default: `ws://localhost:9222` (parent) or `9223` (standalone)
2. **Shared Storage** - MinIO, Supabase with proper credentials
3. **Environment Detection** - Automatically detects parent presence

## Tier Environment Architecture

### Tier Files

| Tier | Purpose | Example Services |
|------|---------|------------------|
| `env.tier-llm` | LLM providers, embeddings | TensorZero, OpenRouter, Venice |
| `env.tier-api` | API gateway, external APIs | Supabase, PostgREST |
| `env.tier-data` | Databases, search | Postgres, Neo4j, Qdrant, Meilisearch |
| `env.tier-media` | Media processing | Whisper, YOLO, FFmpeg |
| `env.tier-agent` | Agent orchestration | Agent Zero, Archon |
| `env.tier-worker` | Background jobs | Extract Worker, LangExtract |

### Secrets Manifest

The `pmoves/chit/secrets_manifest_v2.yaml` maps secrets to tier files:

```yaml
version: "2"
entries:
  - id: openrouter-api-key
    source:
      type: cgp
      label: OPENROUTER_API_KEY
    targets:
      - file: env.tier-llm
        key: OPENROUTER_API_KEY
      - github_secret: PMOVES_OPENROUTER_API_KEY
      - docker_secret: pmoves_openrouter_api_key
```

## Security Considerations

### Files That Should NOT Be Committed

| File | Pattern | Reason |
|------|---------|--------|
| `env.shared` | Never | Contains actual API keys |
| `env.cgp.json` | Cleartext version | May contain secrets |
| `.env.bootstrap` | Generated | Contains loaded credentials |
| `.env.*` | Local only | User-specific configuration |

### Files That CAN Be Committed (Encoded)

| File | Format | Safety |
|------|--------|--------|
| `env.cgp.json` | CHIT with hex encoding | Safe if `--no-cleartext` used |
| `env.shared.example` | Template | Safe (placeholder values) |
| `env.tier-*` | Service credentials | Safe (non-sensitive defaults) |

### Best Practices

1. **Never commit actual API keys** to git
2. **Use `--no-cleartext`** when encoding sensitive CGP files
3. **Restrict CGP file access** with filesystem permissions
4. **Rotate credentials** regularly via GitHub Secrets
5. **Use fine-grained PATs** with minimum required scope

## Troubleshooting

### "CHIT CGP file not found"

```bash
# Check if CGP exists
ls -la pmoves/pmoves/data/chit/env.cgp.json

# Create from env.shared
pmoves secrets encode
```

### "GitHub PAT not found"

```bash
# Set via environment
export GITHUB_PAT=ghp_xxxxx

# Or create file
echo "ghp_xxxxx" > ~/.github-pat
chmod 600 ~/.github-pat
```

### "Docker config not found"

```bash
# Login to registry
docker login ghcr.io

# Check config
cat ~/.docker/config.json
```

### Submodule Can't Find Parent

In docked mode, submodules need parent PMOVES.AI:

```bash
# Check parent detection
pmoves env init --detect-parent

# Force parent path
export PMOVES_PARENT=/path/to/PMOVES.AI
pmoves env init
```

## Migration from v4 to v5

### What Changed

1. **Active credential fetcher** added as primary source
2. `bootstrap_credentials.sh` updated to v5
3. New `pmoves credentials` commands
4. Improved submodule standalone support

### Migration Steps

```bash
# 1. Update bootstrap script
git pull origin PMOVES.AI-Edition-Hardened

# 2. Set up GitHub PAT for active fetching
echo "ghp_xxxxx" > ~/.github-pat
chmod 600 ~/.github-pat

# 3. Test active fetcher
pmoves credentials list-github --owner POWERFULMOVES --repo PMOVES.AI

# 4. Fetch and encode
pmoves credentials to-env-shared
pmoves secrets encode
pmoves env init
```

## Related Documentation

- `docs/SECRETS.md` - Original secrets documentation (deprecated)
- `docs/ARCHITECTURE.md` - Overall system architecture
- `docs/subsystems/` - Individual subsystem documentation
- `.claude/context/nats-subjects.md` - NATS message bus integration

## API Reference

### Python Modules

| Module | Location | Purpose |
|--------|----------|---------|
| `credential_fetcher` | `pmoves/tools/` | Active GitHub/Docker fetching |
| `chit_encode_secrets` | `pmoves/tools/` | Encode env to CGP |
| `chit_decode_secrets` | `pmoves/tools/` | Decode CGP to env |
| `secrets_sync` | `pmoves/tools/` | Apply manifest to tiers |
| `mini_cli` | `pmoves/tools/` | CLI entry point |

### CLI Commands

| Command | Purpose |
|---------|---------|
| `pmoves credentials fetch` | Fetch from GitHub/Docker APIs |
| `pmoves credentials list-github` | List GitHub secrets metadata |
| `pmoves credentials list-docker` | List Docker credentials |
| `pmoves credentials to-env-shared` | Fetch and write to env.shared |
| `pmoves secrets encode` | Encode env.shared to CGP |
| `pmoves secrets decode` | Decode CGP to env format |
| `pmoves env init` | Initialize tier files from CGP |
| `pmoves env validate` | Validate tier configuration |
