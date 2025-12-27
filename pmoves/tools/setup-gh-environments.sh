#!/usr/bin/env bash
set -euo pipefail

# Setup GitHub environments for PMOVES.AI
# This script creates Dev and Prod environments with appropriate protection rules

REPO="POWERFULMOVES/PMOVES.AI"

usage() {
  cat <<'EOF'
setup-gh-environments.sh [--repo owner/name] [--dry-run]

Creates Dev and Prod GitHub environments for the repository.

Options:
  --repo      GitHub repo in owner/name form (default: POWERFULMOVES/PMOVES.AI)
  --dry-run   Print API calls instead of executing them
  -h, --help  Show this help message

Examples:
  ./pmoves/tools/setup-gh-environments.sh
  ./pmoves/tools/setup-gh-environments.sh --repo POWERFULMOVES/PMOVES.AI --dry-run
EOF
}

DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown option: $1" >&2; usage; exit 1;;
  esac
done

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: GitHub CLI (gh) not found. Install it first." >&2
  echo "Visit: https://cli.github.com/" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "WARNING: jq not found. Output formatting will be limited." >&2
fi

echo "================================================"
echo "GitHub Environment Setup for PMOVES.AI"
echo "================================================"
echo "Repository: $REPO"
echo "Dry run: $([[ $DRY_RUN -eq 1 ]] && echo "YES" || echo "NO")"
echo ""

# Check authentication
if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: Not authenticated with GitHub CLI" >&2
  echo "Run: gh auth login" >&2
  exit 1
fi

echo "Step 1: Checking existing environments..."
echo "-------------------------------------------"

if command -v jq >/dev/null 2>&1; then
  EXISTING=$(gh api repos/$REPO/environments 2>/dev/null | jq -r '.environments[].name' || echo "")
else
  EXISTING=$(gh api repos/$REPO/environments 2>/dev/null || echo "")
fi

echo "Current environments:"
if [[ -n "$EXISTING" ]]; then
  echo "$EXISTING"
else
  echo "(none)"
fi
echo ""

# Function to create environment
create_environment() {
  local env_name="$1"
  local wait_timer="${2:-0}"
  local prevent_self_review="${3:-false}"

  echo "Creating '$env_name' environment..."

  if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY-RUN: Would create environment '$env_name' with:"
    echo "  - wait_timer: $wait_timer"
    echo "  - prevent_self_review: $prevent_self_review"
    return 0
  fi

  # Create environment with protection rules
  if [[ "$wait_timer" -eq 0 && "$prevent_self_review" == "false" ]]; then
    # Simple environment without protection
    gh api --method PUT \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "/repos/$REPO/environments/$env_name" \
      >/dev/null 2>&1
  else
    # Environment with protection rules
    gh api --method PUT \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "/repos/$REPO/environments/$env_name" \
      -f wait_timer="$wait_timer" \
      -F prevent_self_review="$prevent_self_review" \
      >/dev/null 2>&1
  fi

  if [[ $? -eq 0 ]]; then
    echo "  ✓ '$env_name' created successfully"
  else
    echo "  ✗ Failed to create '$env_name'" >&2
    return 1
  fi
}

echo "Step 2: Creating environments..."
echo "-------------------------------------------"

# Create Dev environment (no protection rules)
if echo "$EXISTING" | grep -q "^Dev$"; then
  echo "Dev environment already exists, skipping..."
else
  create_environment "Dev" 0 "false"
fi

echo ""

# Create Prod environment (with protection rules)
if echo "$EXISTING" | grep -q "^Prod$"; then
  echo "Prod environment already exists, skipping..."
else
  echo "Creating Prod environment with protection rules:"
  echo "  - Wait timer: 30 minutes"
  echo "  - Prevent self-review: enabled"
  create_environment "Prod" 30 "true"
fi

echo ""
echo "Step 3: Verifying environment creation..."
echo "-------------------------------------------"

if [[ $DRY_RUN -eq 0 ]]; then
  if command -v jq >/dev/null 2>&1; then
    ENVS=$(gh api repos/$REPO/environments 2>/dev/null | jq -r '.environments[] | "  - \(.name) (created: \(.created_at))"')
    echo "Environments in $REPO:"
    echo "$ENVS"
  else
    echo "Listing environments:"
    gh api repos/$REPO/environments 2>/dev/null || echo "Failed to list environments"
  fi
else
  echo "Skipped (dry-run mode)"
fi

echo ""
echo "================================================"
echo "Setup Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Push secrets to Dev environment:"
echo "   ./pmoves/tools/push-gh-secrets.sh --env Dev --file pmoves/env.shared"
echo ""
echo "2. Push secrets to Prod environment:"
echo "   ./pmoves/tools/push-gh-secrets.sh --env Prod --file pmoves/env.shared"
echo ""
echo "3. (Optional) Push only specific secrets:"
echo "   ./pmoves/tools/push-gh-secrets.sh --env Prod \\"
echo "     --only SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY,POSTGRES_HOSTNAME"
echo ""
echo "4. Verify secrets were created:"
echo "   gh secret list --repo $REPO --env Dev"
echo "   gh secret list --repo $REPO --env Prod"
echo ""
echo "5. Update GitHub Actions workflows to use environments:"
echo "   jobs:"
echo "     deploy:"
echo "       environment: Dev  # or Prod"
echo ""
echo "For detailed documentation, see:"
echo "  docs/github-environment-setup.md"
echo ""
