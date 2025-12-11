#!/usr/bin/env bash
set -euo pipefail

# Push secrets to GitHub using smart categorization
# Automatically determines which secrets are environment-scoped vs repository-scoped
# based on secrets_categorization.yaml

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/pmoves/env.shared}"
CATEGORIZATION_FILE="$REPO_ROOT/pmoves/chit/secrets_categorization.yaml"
REPO="POWERFULMOVES/PMOVES.AI"
ENVIRONMENT=""
DRY_RUN=0

usage() {
  cat <<'EOF'
push-categorized-secrets.sh [--env ENV] [--repo owner/name] [--file path] [--dry-run]

Intelligently pushes secrets to GitHub based on categorization rules.
Automatically determines whether secrets should be environment-scoped or repository-scoped.

Options:
  --env       GitHub environment name (Dev, Prod) - REQUIRED for environment secrets
  --repo      GitHub repo (default: POWERFULMOVES/PMOVES.AI)
  --file      Env file to read (default: pmoves/env.shared)
  --dry-run   Print actions without executing
  -h, --help  Show this help

Examples:
  # Push all Dev environment secrets
  ./pmoves/tools/push-categorized-secrets.sh --env Dev

  # Push all Prod environment secrets
  ./pmoves/tools/push-categorized-secrets.sh --env Prod

  # Push repository-level secrets only
  ./pmoves/tools/push-categorized-secrets.sh --env none

  # Dry run to see what would be pushed
  ./pmoves/tools/push-categorized-secrets.sh --env Dev --dry-run

Environment:
  ENV_FILE    Override env file path (default: pmoves/env.shared)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENVIRONMENT="$2"; shift 2;;
    --repo) REPO="$2"; shift 2;;
    --file) ENV_FILE="$2"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown option: $1" >&2; usage; exit 1;;
  esac
done

if [[ -z "$ENVIRONMENT" ]]; then
  echo "ERROR: --env is required (use 'Dev', 'Prod', or 'none' for repository secrets)" >&2
  usage
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: Env file not found: $ENV_FILE" >&2
  exit 1
fi

if [[ ! -f "$CATEGORIZATION_FILE" ]]; then
  echo "ERROR: Categorization file not found: $CATEGORIZATION_FILE" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: GitHub CLI (gh) not found" >&2
  exit 1
fi

if ! command -v yq >/dev/null 2>&1; then
  echo "WARNING: yq not found. Install it for YAML parsing." >&2
  echo "Falling back to grep-based parsing (less reliable)" >&2
  USE_YQ=0
else
  USE_YQ=1
fi

echo "================================================"
echo "Categorized GitHub Secrets Push"
echo "================================================"
echo "Repository: $REPO"
echo "Environment: $ENVIRONMENT"
echo "Env file: $ENV_FILE"
echo "Dry run: $([[ $DRY_RUN -eq 1 ]] && echo "YES" || echo "NO")"
echo ""

# Parse categorization file
if [[ $USE_YQ -eq 1 ]]; then
  # Use yq for proper YAML parsing
  ENV_SECRETS=$(yq eval '.environment_secrets[]' "$CATEGORIZATION_FILE" 2>/dev/null || echo "")
  REPO_SECRETS=$(yq eval '.repository_secrets[]' "$CATEGORIZATION_FILE" 2>/dev/null || echo "")
else
  # Fallback: grep-based parsing (fragile)
  ENV_SECRETS=$(grep -A 1000 "^environment_secrets:" "$CATEGORIZATION_FILE" | grep -B 1000 "^repository_secrets:" | grep "^  - " | sed 's/^  - //' || echo "")
  REPO_SECRETS=$(grep -A 1000 "^repository_secrets:" "$CATEGORIZATION_FILE" | grep "^  - " | sed 's/^  - //' || echo "")
fi

# Function to check if secret is in category
is_env_secret() {
  local key="$1"
  echo "$ENV_SECRETS" | grep -qx "$key"
}

is_repo_secret() {
  local key="$1"
  echo "$REPO_SECRETS" | grep -qx "$key"
}

# Counters
ENV_COUNT=0
REPO_COUNT=0
SKIPPED_COUNT=0

echo "Processing secrets from $ENV_FILE..."
echo "-------------------------------------------"

while IFS= read -r line; do
  # Skip empty lines and comments
  [[ -z "$line" ]] && continue
  [[ "$line" =~ ^[[:space:]]*# ]] && continue

  # Parse KEY=VALUE
  if [[ "$line" != *"="* ]]; then
    continue
  fi

  key=${line%%=*}
  val=${line#*=}
  key=${key//[$'\t ']/}

  [[ -z "$key" ]] && continue

  # Determine categorization
  if is_env_secret "$key"; then
    # Environment secret
    if [[ "$ENVIRONMENT" == "none" ]]; then
      echo "SKIP: $key (environment secret, but --env=none)"
      ((SKIPPED_COUNT++))
      continue
    fi

    if [[ $DRY_RUN -eq 1 ]]; then
      echo "DRY: $key → Environment: $ENVIRONMENT"
    else
      printf '%s' "$val" | gh secret set "$key" --repo "$REPO" --app actions --env "$ENVIRONMENT" >/dev/null 2>&1
      echo "SET: $key → Environment: $ENVIRONMENT"
    fi
    ((ENV_COUNT++))

  elif is_repo_secret "$key"; then
    # Repository secret
    if [[ $DRY_RUN -eq 1 ]]; then
      echo "DRY: $key → Repository (all environments)"
    else
      printf '%s' "$val" | gh secret set "$key" --repo "$REPO" --app actions >/dev/null 2>&1
      echo "SET: $key → Repository (all environments)"
    fi
    ((REPO_COUNT++))

  else
    # Not categorized
    echo "WARN: $key not in categorization file, skipping"
    ((SKIPPED_COUNT++))
  fi

done < "$ENV_FILE"

echo ""
echo "================================================"
echo "Summary"
echo "================================================"
echo "Environment secrets ($ENVIRONMENT): $ENV_COUNT"
echo "Repository secrets: $REPO_COUNT"
echo "Skipped/Uncategorized: $SKIPPED_COUNT"
echo ""

if [[ $DRY_RUN -eq 1 ]]; then
  echo "This was a dry run. No secrets were actually pushed."
  echo "Remove --dry-run to execute."
else
  echo "Secrets pushed successfully!"
  echo ""
  echo "Verify with:"
  if [[ "$ENVIRONMENT" != "none" ]]; then
    echo "  gh secret list --repo $REPO --env $ENVIRONMENT"
  fi
  echo "  gh secret list --repo $REPO"
fi
echo ""
