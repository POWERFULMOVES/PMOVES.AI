# PMOVES.AI Secrets Management Guide

**Universal credential management for all PMOVES.AI submodules and services.**

---

## Overview

PMOVES.AI uses a **three-tier credential loading system** that works across any submodule:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PMOVES.AI Secrets Management                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. CHIT Geometry Packet (CGP) ──────┐                              │
│     • Encoded secrets in git         │──► Recommended for most users │
│     • Portable, traceable            │                              │
│     • Geometry-based obfuscation     │                              │
│                                       │                              │
│  2. Docker Secrets ──────────────────┼─┐                            │
│     • /run/secrets/ mounting         │ │                            │
│     • Container-standard             │ ├──► For production deployments│
│     • Swarm/Compose support          │ │                            │
│                                       │─┘                            │
│  3. git-crypt ────────────────────────┐                              │
│     • GPG-encrypted files in git     │                              │
│     • Zero external dependencies     │──► For teams with GPG         │
│     • Transparent decryption         │                              │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start (Universal Bootstrap)

### For ANY PMOVES.AI Submodule

```bash
# From any submodule directory (PMOVES-Agent-Zero, PMOVES-Archon, etc.)
cd /path/to/submodule

# Run the universal bootstrap
source ../PMOVES.AI/pmoves/scripts/bootstrap_credentials.sh
# OR
./scripts/bootstrap_credentials.sh && source .env.bootstrap
```

The bootstrap automatically detects:
- **DOCKED MODE**: Running inside PMOVES.AI Docker stack → loads from parent only
- **STANDALONE MODE**: Independent operation → tries CHIT → git-crypt → Docker → parent

---

## Option 1: CHIT Geometry Packet (Recommended)

### What is CHIT?

CHIT (Cognitive Holographic Information Transfer) is PMOVES.AI's proprietary encoding system that transforms secrets into geometric data points. Secrets are encoded as 3D coordinates in a Geometry Packet.

**Advantages:**
- ✅ Portable across all submodules
- ✅ Traceable in git (encoded values)
- ✅ No external tools required
- ✅ Works offline
- ✅ Geometry-based (harder to accidentally expose)

### Setup

```bash
# 1. Encode your credentials into CHIT format
cd /path/to/PMOVES.AI
python3 -m pmoves.tools.chit_encode_secrets

# 2. This creates: pmoves/data/chit/env.cgp.json
#    Contains 67+ encoded secrets from env.shared

# 3. Commit the CGP file (safe to track - values are encoded)
git add pmoves/data/chit/env.cgp.json
git commit -m "feat: update CHIT credential packet"
```

### Usage in Any Submodule

```bash
# From any submodule
cd PMOVES-Agent-Zero

# Bootstrap automatically finds and decodes CHIT
source ../PMOVES.AI/pmoves/scripts/bootstrap_credentials.sh

# Credentials now available in current shell
echo $ANTHROPIC_API_KEY  # ✓ Decoded and loaded
```

### CHIT File Locations (Search Order)

The bootstrap searches these locations for `env.cgp.json`:

1. `./data/chit/env.cgp.json` - Current submodule
2. `./pmoves/data/chit/env.cgp.json` - Current repo
3. `~/.config/pmoves/chit/env.cgp.json` - User config
4. `~/.pmoves/chit/env.cgp.json` - User home
5. `../data/chit/env.cgp.json` - Parent directory
6. `../../data/chit/env.cgp.json` - Grandparent

### Adding New Secrets to CHIT

Edit `pmoves/env.shared`:

```bash
# Add your secret to env.shared
echo "NEW_SERVICE_API_KEY=sk-abc123..." >> pmoves/env.shared

# Re-encode
python3 -m pmoves.tools.chit_encode_secrets

# Commit
git add pmoves/env.shared pmoves/data/chit/env.cgp.json
git commit -m "feat: add NEW_SERVICE credentials"
```

---

## Option 2: Docker Secrets

### What are Docker Secrets?

Docker Secrets is the container-standard way to mount sensitive files at `/run/secrets/`. Works with both Docker Swarm and Docker Compose.

**Advantages:**
- ✅ Production-standard
- ✅ Automatic mounting
- ✅ Per-container permissions
- ✅ Never written to disk in layers

### Setup (Docker Compose)

Add to your `docker-compose.yml`:

```yaml
secrets:
  pmoves_openai_api_key:
    file: ./secrets/openai_api_key.txt
  pmoves_anthropic_api_key:
    file: ./secrets/anthropic_api_key.txt

services:
  your-service:
    secrets:
      - pmoves_openai_api_key
      - pmoves_anthropic_api_key
```

### Secret File Format

```bash
# ./secrets/openai_api_key.txt
sk-proj-abc123...
```

### Usage

Inside containers, secrets are mounted at:

```
/run/secrets/pmoves_openai_api_key    → OPENAI_API_KEY
/run/secrets/pmoves_anthropic_api_key → ANTHROPIC_API_KEY
```

The bootstrap automatically detects and loads these.

### Bootstrap Integration

```bash
# Inside any container
source /scripts/bootstrap_credentials.sh

# Automatically loads from /run/secrets/
```

---

## Option 3: git-crypt

### What is git-crypt?

git-crypt transparently encrypts designated files in git using GPG. Encrypted files are stored in git but only decrypted for users with the appropriate GPG key.

**Advantages:**
- ✅ Zero external runtime dependencies
- ✅ Standard GPG encryption
- ✅ Transparent after unlock
- ✅ Team-friendly (multiple GPG keys)

### Installation

```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y git-crypt

# macOS
brew install git-crypt

# Verify installation
git-crypt --version
```

### Initial Setup (One-Time)

```bash
cd /path/to/PMOVES.AI

# 1. Initialize git-crypt in the repository
git-crypt init

# 2. Add your GPG key (replace with your email)
git-crypt add-gpg-user your.email@example.com

# 3. Verify
git-crypt status
```

### Encrypted Files Configuration

Already configured in `.gitattributes`:

```
# Encrypted credentials file
pmoves/.env.enc filter=git-crypt diff=git-crypt
pmoves/.env.enc merge=git-crypt
```

### Adding Secrets

```bash
# 1. Decrypt the file (creates plaintext .env.enc)
git-crypt unlock

# 2. Edit the encrypted file
vim pmoves/.env.enc
# Add your secrets:
# NEW_API_KEY=sk-abc123...

# 3. Re-encrypt (happens automatically on commit)
git add pmoves/.env.enc
git commit -m "feat: add NEW_API_KEY to encrypted credentials"

# 4. Lock the file (remove plaintext)
git-crypt lock
```

### Sharing with Team

```bash
# Team member setup:
git clone git@github.com:POWERFULMOVES/PMOVES.AI.git
cd PMOVES.AI

# One-time GPG import (if not already in keyring)
# (Import your private GPG key first)

# Unlock repository
git-crypt unlock

# Now pmoves/.env.enc is decrypted and readable
```

### GPG Key Management

```bash
# List GPG keys with email
gpg --list-secret-keys --keyid-format LONG

# Export your public key (for sharing)
gpg --armor --export your.email@example.com > public-key.asc

# Import team member's public key
gpg --import public-key.asc

# Add team member to git-crypt
git-crypt add-gpg-user team.member@example.com
```

---

## Mode Detection

The bootstrap automatically detects its operating mode:

### DOCKED MODE (Inside PMOVES.AI Stack)

Detected when:
- `DOCKED_MODE=true` environment variable is set
- Running inside Docker container (`/.dockerenv` exists)
- Has access to parent services (`NATS_URL` or `TENSORZERO_URL` set)

**Behavior:** Loads credentials ONLY from parent PMOVES.AI

```bash
# In docked mode, parent credentials are authoritative
DOCKED_MODE=true source scripts/bootstrap_credentials.sh
# → Loads from ../PMOVES.AI/pmoves/env.shared
```

### STANDALONE MODE (Independent Operation)

Detected when:
- Not in a Docker environment
- No parent service connection

**Behavior:** Tries all credential sources in order:

1. **CHIT Geometry Packet** → Portable encoded secrets
2. **git-crypt** → Encrypted files in git
3. **Docker Secrets** → `/run/secrets/` mounting
4. **Parent PMOVES.AI** → Fallback to parent

---

## Universal Submodule Onboarding

### Adding a New Submodule

When adding a new submodule to PMOVES.AI:

```bash
# 1. Add the submodule
git submodule add https://github.com/POWERFULMOVES/NEW-SUBMODULE.git pmoves/NEW-SUBMODULE

# 2. In the new submodule, create the bootstrap symlink
cd pmoves/NEW-SUBMODULE
ln -s ../../scripts/bootstrap_credentials.sh scripts/bootstrap_credentials.sh

# 3. Create .env.shared reference
cat > env.shared << 'EOF'
# This submodule inherits credentials from parent PMOVES.AI
# Run: source ../scripts/bootstrap_credentials.sh
EOF

# 4. Done! The submodule now has universal credential access
```

### Bootstrap in New Submodule

```bash
cd pmoves/NEW-SUBMODULE

# Run bootstrap (automatically detects parent)
source ../scripts/bootstrap_credentials.sh

# ✓ Credentials loaded from parent PMOVES.AI
```

---

## Environment Files Reference

| File | Purpose | Mode | Encrypted |
|------|---------|------|-----------|
| `pmoves/env.shared` | Source for CHIT encoding | Standalone | No |
| `pmoves/.env` | Local overrides (gitignored) | Both | No |
| `pmoves/.env.enc` | git-crypt encrypted file | Standalone | Yes |
| `pmoves/.env.bootstrap` | Generated by bootstrap script | Both | No |
| `.env` | Service-specific (gitignored) | Both | No |

---

## Dependency Installation

### Required Tools

```bash
# Install all PMOVES.AI dependencies
python3 -m pmoves.tools.mini_cli deps install

# This installs:
#   - make          # Build automation
#   - jq            # JSON processing
#   - pytest        # Python testing
#   - git-crypt     # Encrypted files in git (NEW)
```

### Manual Installation

```bash
# Ubuntu/Debian
sudo apt-get install -y make jq git-crypt

# macOS
brew install make jq git-crypt

# Verify
make --version
jq --version
git-crypt --version
```

---

## Security Best Practices

### DO ✅

- ✅ Use CHIT CGP for portable, encoded secrets
- ✅ Use git-crypt for team collaboration
- ✅ Use Docker Secrets for production containers
- ✅ Keep `.env` files in `.gitignore`
- ✅ Rotate credentials regularly
- ✅ Use different keys for dev/staging/prod

### DON'T ❌

- ❌ Commit plaintext credentials to git
- ❌ Share screenshots of credential files
- ❌ Use the same key across environments
- ❌ Store credentials in code comments
- ❌ Log secret values to console output

### Secret Rotation

```bash
# 1. Update the value in env.shared
vim pmoves/env.shared
# Change: ANTHROPIC_API_KEY=sk-old-key...
# To:     ANTHROPIC_API_KEY=sk-new-key...

# 2. Re-encode CHIT
python3 -m pmoves.tools.chit_encode_secrets

# 3. Update git-crypt if using
git-crypt unlock
vim pmoves/.env.enc
git-crypt lock

# 4. Commit changes
git add pmoves/env.shared pmoves/data/chit/env.cgp.json pmoves/.env.enc
git commit -m "security: rotate ANTHROPIC_API_KEY"
```

---

## Troubleshooting

### Bootstrap Reports "0 Variables"

```bash
# Check what sources are available
ls -la pmoves/data/chit/env.cgp.json
ls -la pmoves/.env.enc
ls -la /run/secrets/

# Check mode detection
echo "DOCKED_MODE=${DOCKED_MODE:-false}"
echo "In container: $([ -f /.dockerenv ] && echo yes || echo no)"

# Manual decode test
python3 -c "
from pmoves.chit import load_cgp, decode_secret_map
cgp = load_cgp('pmoves/data/chit/env.cgp.json')
secrets = decode_secret_map(cgp)
print(f'Loaded {len(secrets)} secrets')
print(list(secrets.keys())[:5])
"
```

### git-crypt: "No GPG keys found"

```bash
# Check GPG keyring
gpg --list-secret-keys

# Import your private key if needed
gpg --import /path/to/private-key.asc

# Verify git-crypt can see your key
git-crypt status
```

### Docker Secrets Not Found

```bash
# Check secrets directory
ls -la /run/secrets/

# Verify compose configuration
docker compose config | grep -A5 secrets:

# Check service mounts
docker inspect <container> | grep -A10 Mounts
```

### CHIT Decode Failed

```bash
# Verify Python path
python3 -c "import sys; from pmoves.chit import load_cgp; print('OK')"

# Check CGP file format
python3 -c "
import json
with open('pmoves/data/chit/env.cgp.json') as f:
    cgp = json.load(f)
print(f'Version: {cgp.get(\"version\")}')
print(f'Points: {len(cgp.get(\"points\", []))}')
"
```

---

## Quick Reference Commands

```bash
# === CHIT Operations ===
python3 -m pmoves.tools.chit_encode_secrets    # Encode env.shared → CGP
python3 -c "from pmoves.chit import load_cgp, decode_secret_map; ..."

# === git-crypt Operations ===
git-crypt init                                  # Initialize in repo
git-crypt add-gpg-user user@email.com           # Add team member
git-crypt unlock                                # Decrypt files
git-crypt lock                                  # Re-encrypt files
git-crypt status                                # Check encryption status

# === Bootstrap Operations ===
source scripts/bootstrap_credentials.sh          # Run universal bootstrap
source .env.bootstrap                            # Load generated credentials

# === Dependency Operations ===
python3 -m pmoves.tools.mini_cli deps check     # Check dependencies
python3 -m pmoves.tools.mini_cli deps install   # Install missing deps

# === Verify Credentials ===
grep -c '=' .env.bootstrap                       # Count loaded variables
echo $ANTHROPIC_API_KEY                          # Check specific credential
```

---

## File Structure

```
PMOVES.AI/
├── pmoves/
│   ├── env.shared              # Source for CHIT encoding (67+ vars)
│   ├── .env.enc                # git-crypt encrypted credentials
│   ├── .env                    # Local overrides (gitignored)
│   ├── data/chit/
│   │   └── env.cgp.json        # CHIT Geometry Packet (encoded)
│   └── scripts/
│       └── bootstrap_credentials.sh    # Universal bootstrap
├── .gitattributes              # git-crypt configuration
├── .gitignore                  # Excludes .env, creds.md
└── pmoves/tools/
    ├── mini_cli.py             # Dependency management (includes git-crypt)
    └── chit_encode_secrets.py  # CHIT encoding tool
```

---

## Summary Diagram

```
                    ┌─────────────────────────┐
                    │   New Submodule Added   │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  Run Bootstrap Script   │
                    │  source ../scripts/...  │
                    └────────────┬────────────┘
                                 │
                ┌────────────────┼────────────────┐
                │                │                │
                ▼                ▼                ▼
         ┌───────────┐    ┌───────────┐    ┌───────────┐
         │   CHIT    │    │ git-crypt │    │  Docker   │
         │    CGP    │    │   .env    │    │  Secrets  │
         └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
               │                │                │
               └────────────────┼────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   .env.bootstrap        │
                    │   (67+ credentials)     │
                    └─────────────────────────┘
```

---

**Last Updated:** 2025-01-21
**Version:** 3.0 (Universal Bootstrap + git-crypt support)
