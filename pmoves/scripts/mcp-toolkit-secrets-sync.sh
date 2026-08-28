#!/usr/bin/env bash
# Headless secrets bridge: populate Docker MCP Toolkit's keychain from the PMOVES
# secrets pipeline (env.tier-* files produced by the canonical secrets-funnel).
#
# Handles the API-key style secrets stored under the `docker-pass` provider.
# Does NOT handle OAuth-mediated secrets (Cloudflare suite) — those require a
# one-time interactive `docker mcp oauth authorize <server>` per node and are
# documented in pmoves/docs/operations/MCP_TOOLKIT.md § 5.
#
# Idempotent — re-running with the same env.tier-shared values is a no-op.
# Re-running with changed values overwrites the keychain entry.
#
# Usage:
#   # Default: read pmoves/env.shared (the canonical aggregate the secrets-funnel produces)
#   bash pmoves/scripts/mcp-toolkit-secrets-sync.sh
#
#   # Tier-specific override (e.g. for agent-tier-only sync):
#   PMOVES_TIER_FILE=pmoves/env.tier-agent bash pmoves/scripts/mcp-toolkit-secrets-sync.sh
#
# Make target: make -C pmoves mcp-toolkit-secrets-sync

set -euo pipefail

# Resolve the canonical default relative to this script's location, not the
# caller's cwd. `make -C pmoves` and direct invocation from repo root both work.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMOVES_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_TIER_FILE="${PMOVES_DIR}/env.shared"

TIER_FILE="${PMOVES_TIER_FILE:-${DEFAULT_TIER_FILE}}"
DRY_RUN="${PMOVES_MCP_DRY_RUN:-0}"

color() { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
info() { color "1;34" "[mcp-secrets] $*"; }
warn() { color "1;33" "[mcp-secrets] WARN: $*" >&2; }
fail() { color "1;31" "[mcp-secrets] FAIL: $*" >&2; exit 1; }

if [ ! -f "${TIER_FILE}" ]; then
  fail "Tier file not found: ${TIER_FILE}. Run the PMOVES secrets-funnel first (see pmoves/Makefile for the canonical target)."
fi

if ! command -v docker >/dev/null 2>&1 || ! docker mcp version >/dev/null 2>&1; then
  fail "Docker MCP Toolkit not available. Run: make mcp-toolkit-bootstrap"
fi

# Source-of-truth mapping: PMOVES env name → Toolkit secret name (under docker-pass).
# To add a new server's API key to the bridge:
#   1. Confirm the secret name with `docker mcp profile show <profile> | grep -A2 secrets:`
#   2. Add the mapping below.
#   3. Ensure the PMOVES env var is populated by the secrets-funnel.
declare -A SECRET_MAP=(
  [HOSTINGER_API_KEY]="hostinger-mcp-server.api_token"
  [GITHUB_PAT]="github.personal_access_token"
  [GITHUB_TOKEN]="github.personal_access_token"
  [DOCKERHUB_PAT]="dockerhub.pat_token"
  [DOCKERHUB_TOKEN]="dockerhub.pat_token"
  [DISCORD_TOKEN]="discord.token"
  # `postman.postman-api-key`, NOT `postman.api_key`. Verified against
  # `docker mcp profile show` on 2026-08-28: the field really is doubled.
  # The short form wrote a secret under a name no server reads -- the sync
  # reported success and postman still started unauthenticated.
  [POSTMAN_API_KEY]="postman.postman-api-key"
)

info "Reading tier file: ${TIER_FILE}"
# Load the tier file into the current shell so $VAR expansion sees its contents.
# Tier files are plain KEY=VALUE per PMOVES convention.
set -a
# shellcheck disable=SC1090
. "${TIER_FILE}"
set +a

# Returns 0 only when a value was actually set (or would be set in dry-run).
# Returns 1 when the source env var is empty so the caller doesn't mark the
# toolkit secret name as written and another env alias gets a chance.
set_secret() {
  local env_name="$1"
  local toolkit_name="$2"
  local value="${!env_name:-}"
  if [ -z "${value}" ]; then
    return 1
  fi
  if [ "${DRY_RUN}" = "1" ]; then
    info "[dry-run] would set: docker mcp secret set ${toolkit_name} (value from ${env_name}, ${#value} bytes)"
    return 0
  fi
  info "setting: ${toolkit_name} (source env: ${env_name})"
  # STDIN redirection is the canonical headless path per `docker mcp secret --help`.
  printf '%s' "${value}" | docker mcp secret set "${toolkit_name}" >/dev/null
  return 0
}

# Track which Toolkit secret names we've successfully set, to avoid double-
# writing when two env aliases map to the same target (e.g. GITHUB_PAT and
# GITHUB_TOKEN both → github.personal_access_token). The flag is set ONLY
# after a successful write so empty aliases don't shadow populated ones.
declare -A WRITTEN=()
for env_name in "${!SECRET_MAP[@]}"; do
  toolkit_name="${SECRET_MAP[$env_name]}"
  if [ -n "${WRITTEN[$toolkit_name]:-}" ]; then
    continue
  fi
  if set_secret "${env_name}" "${toolkit_name}"; then
    WRITTEN[$toolkit_name]=1
  fi
done

# Summarize unwritten toolkit secrets. Build a unique-sorted list of mapped
# targets, then print the ones that weren't successfully set.
mapfile -t ALL_TOOLKIT_NAMES < <(printf '%s\n' "${SECRET_MAP[@]}" | sort -u)
for toolkit_name in "${ALL_TOOLKIT_NAMES[@]}"; do
  if [ -z "${WRITTEN[$toolkit_name]:-}" ]; then
    # Show which env vars would have populated this target.
    aliases=""
    for env_name in "${!SECRET_MAP[@]}"; do
      if [ "${SECRET_MAP[$env_name]}" = "${toolkit_name}" ]; then
        aliases="${aliases} ${env_name}"
      fi
    done
    warn "no source env found for ${toolkit_name} (tried any of:${aliases})"
  fi
done

info "Secrets sync complete."
echo
echo "Verify with: docker mcp secret ls"
echo
echo "OAuth-mediated Cloudflare servers (13 of 25 in pmoves_5090_web) are NOT"
echo "covered by this bridge. For each Cloudflare server you need:"
echo "  docker mcp oauth authorize cloudflare-<service>"
echo "See pmoves/docs/operations/MCP_TOOLKIT.md § 5 for the full list."
