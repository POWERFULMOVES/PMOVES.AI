#!/usr/bin/env bash
# PMOVES Tier Environment Files Seeder
#
# Creates tier env files from their .example counterparts.
# This is the 6-tier hardened architecture replacement for legacy .env setup.
#
# Usage:
#   bash scripts/seed-tier-envs.sh              # interactive prompts
#   bash scripts/seed-tier-envs.sh -y           # non-interactive; create all from examples
#   bash scripts/seed-tier-envs.sh --force      # overwrite existing files
#
# Tier Files (created in pmoves/ folder):
#   - env.tier-data   (postgres, minio, qdrant, neo4j, meilisearch)
#   - env.tier-api    (postgrest, presign, retrieval-eval)
#   - env.tier-llm    (all LLM provider API keys)
#   - env.tier-media  (ffmepg-whisper, media analyzers, youtube)
#   - env.tier-agent  (agent-zero, archon, deepresearch, supaserch)
#   - env.tier-ui     (frontends: pmoves-ui, wger, firefly, open-notebook, jellyfin)
#   - env.tier-worker (extract-worker, langextract, notebook-sync)

set -euo pipefail

# Script location: pmoves/scripts/seed-tier-envs.sh
# We need to work in the pmoves folder
cd "$(dirname "$0")/.." || exit 1

# All tier env files (in order of loading)
TIERS=(
  "data"
  "api"
  "llm"
  "media"
  "agent"
  "worker"
  "ui"
)

force=0
yes=0
verbose=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--force) force=1; shift ;;
    -y|--yes) yes=1; shift ;;
    -v|--verbose) verbose=1; shift ;;
    -h|--help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Creates tier environment files from .example templates."
      echo ""
      echo "Options:"
      echo "  -y, --yes     Non-interactive mode (auto-confirm all)"
      echo "  -f, --force   Overwrite existing files"
      echo "  -v, --verbose Show detailed output"
      echo "  -h, --help    Show this help message"
      echo ""
      echo "Tier files created in pmoves/:"
      echo "  env.tier-data   - Data storage credentials (postgres, minio, qdrant, neo4j, meilisearch)"
      echo "  env.tier-api    - API tier URLs and internal service credentials"
      echo "  env.tier-llm    - LLM provider API keys (openai, anthropic, etc.)"
      echo "  env.tier-media  - Media processing services (whisper, youtube, etc.)"
      echo "  env.tier-agent  - Agent services (agent-zero, archon, deepresearch)"
      echo "  env.tier-worker - Background workers (extract, langextract)"
      echo "  env.tier-ui     - Frontend UI service URLs and credentials"
      exit 0
      ;;
    *) shift ;;
  esac
done

echo "== PMOVES Tier Environment Seeder =="
echo "Working directory: $(pwd)"
echo ""

created=0
skipped=0
errors=0

for tier in "${TIERS[@]}"; do
  example_file="env.tier-$tier.example"
  target_file="env.tier-$tier"

  if [[ ! -f "$example_file" ]]; then
    echo "❌ ERROR: $example_file not found"
    errors=$((errors + 1))
    continue
  fi

  if [[ -f "$target_file" ]]; then
    if [[ $force -eq 1 ]]; then
      if [[ $verbose -eq 1 ]]; then
        echo "📝 Overwriting $target_file (force mode)"
      fi
    else
      echo "⏭️  Skipping $target_file (already exists)"
      skipped=$((skipped + 1))
      continue
    fi
  fi

  # Interactive prompt for non-yes mode
  if [[ $yes -eq 0 ]]; then
    read -p "Create $target_file from $example_file? [Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ -n "$REPLY" ]]; then
      echo "⏭️  Skipping $target_file"
      skipped=$((skipped + 1))
      continue
    fi
  fi

  # Copy the example file
  if cp "$example_file" "$target_file"; then
    echo "✓ Created $target_file"
    created=$((created + 1))
  else
    echo "❌ ERROR: Failed to create $target_file"
    errors=$((errors + 1))
  fi
done

echo ""
echo "=== Summary ==="
echo "Created: $created"
echo "Skipped: $skipped"
echo "Errors:  $errors"

if [[ $created -gt 0 ]]; then
  echo ""
  echo "📝 Next steps:"
  echo "  1. Edit the tier env files with your actual values"
  echo "  2. Run: source scripts/with-env.sh  # Load environment variables"
  echo "  3. Run: make up                     # Start services"
fi

if [[ $errors -gt 0 ]]; then
  exit 1
fi
