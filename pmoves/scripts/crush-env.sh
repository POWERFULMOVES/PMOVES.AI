#!/usr/bin/env bash
# crush-env.sh — resolve PMOVES tier env files and export vars for Crush MCP servers.
# Sources env.tier-* files in dependency order, resolving ${VAR} references.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${1:-${BASH_SOURCE[0]:-${0}}}")" 2>/dev/null && pwd)"
if [ -z "$SCRIPT_DIR" ]; then
  # Fallback: derive from repo root if we're being sourced from the repo
  SCRIPT_DIR="$(git rev-parse --show-toplevel 2>/dev/null)/pmoves/scripts"
fi
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PMOVES_DIR="${REPO_ROOT}/pmoves"

# Collect all key=value pairs from tier files (skip comments and blanks)
declare -A ENV_MAP

# Load tier files in order (later files can reference earlier ones)
for tier_file in \
  "${PMOVES_DIR}/env.tier-data" \
  "${PMOVES_DIR}/env.tier-api" \
  "${PMOVES_DIR}/env.tier-llm" \
  "${PMOVES_DIR}/env.tier-supabase" \
  "${PMOVES_DIR}/env.tier-worker" \
  "${PMOVES_DIR}/env.tier-media" \
  "${PMOVES_DIR}/env.tier-agent"; do
  if [ -f "$tier_file" ]; then
    while IFS='=' read -r key val || [ -n "$key" ]; do
      [[ "$key" =~ ^[[:space:]]*# ]] && continue
      [ -z "$key" ] && continue
      val="${val%${val##*[![:space:]]}}"  # rtrim
      # Resolve ${VAR} references from already-collected map
      while [[ "$val" =~ \$\{([a-zA-Z_][a-zA-Z0-9_]*)\} ]]; do
        ref="${BASH_REMATCH[1]}"
        refval="${ENV_MAP[$ref]:-}"
        val="${val//\$\{${ref}\}/${refval}}"
      done
      ENV_MAP["$key"]="$val"
    done < "$tier_file"
  fi
done

# Also try env.shared for any remaining gaps
if [ -f "${PMOVES_DIR}/env.shared" ]; then
  while IFS='=' read -r key val || [ -n "$key" ]; do
    [[ "$key" =~ ^[[:space:]]*# ]] && continue
    [ -z "$key" ] && continue
    val="${val%${val##*[![:space:]]}}"
    while [[ "$val" =~ \$\{([a-zA-Z_][a-zA-Z0-9_]*)\} ]]; do
      ref="${BASH_REMATCH[1]}"
      refval="${ENV_MAP[$ref]:-}"
      val="${val//\$\{${ref}\}/${refval}}"
    done
    [ -z "${ENV_MAP[$key]:-}" ] && ENV_MAP["$key"]="$val"
  done < "${PMOVES_DIR}/env.shared"
fi

# Export vars that Crush MCP servers need
for var in \
  SUPABASE_SERVICE_KEY \
  SUPABASE_SERVICE_ROLE_KEY \
  SUPABASE_URL \
  SUPABASE_ANON_KEY \
  N8N_API_KEY \
  NATS_URL \
  CIPHER_API_TOKEN \
  CHIT_PASSPHRASE \
  HF_TOKEN \
  OLLAMA_BASE_URL; do
  if [ -n "${ENV_MAP[$var]:-}" ] && [ -z "${!var:-}" ]; then
    export "$var"="${ENV_MAP[$var]}"
  fi
done

# Override Docker-internal URLs to localhost for Crush (host-side)
export SUPABASE_URL="${SUPABASE_URL:-http://localhost:8000}"
if [[ "${SUPABASE_URL}" == *"supabase-kong"* ]]; then
  export SUPABASE_URL="http://localhost:8000"
fi
