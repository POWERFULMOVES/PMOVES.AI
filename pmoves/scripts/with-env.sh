#!/usr/bin/env bash
# Unified env loader for PMOVES scripts.
# Loads, in order: env.shared* → tier env files → .env* overlays.
# This mirrors compose layering so tier/runtime values override shared defaults.
# Existing exported vars are preserved unless files set them explicitly.
set -euo pipefail
# Get to the repo root from pmoves/scripts/with-env.sh
# Handle both sourced and executed cases
SCRIPT_FILE="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_FILE")" && pwd)"
# From pmoves/scripts/ -> repo root
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

load_env_file() {
  local f="$1"
  [ -f "$f" ] || return 0
  # shellcheck disable=SC2046
  set +H 2>/dev/null || true  # disable history expansion to tolerate '!'
  tmpfile=$(mktemp)
  # Build a sanitized assignment file.
  #
  # Performance note: this loop is on the hot path — it runs once per tier
  # file per Make invocation. Earlier versions forked `sed` three times per
  # input line for whitespace trim + quote escape; on Windows/MSYS2 that was
  # ~100ms/line × ~500 lines × 10+ files = minutes of overhead per Make target.
  # We replace every sed call with pure-bash parameter expansion so the whole
  # loop stays in-process. Drops z890 env-setup from ~108s to <2s per file.
  while IFS= read -r line || [ -n "$line" ]; do
    # Normalize CRLF when running on Windows/WSL.
    line="${line%$'\r'}"
    # ignore comments/blank
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*[[:space:]]*=.*$ ]]; then
      key=${line%%=*}
      val=${line#*=}
      # Trim trailing whitespace from key (leading stripped by regex anchor).
      # The %%/## idiom: `${key##*[![:space:]]}` matches everything through the
      # last non-whitespace char, leaving only trailing whitespace; stripping
      # that suffix gives the trimmed key. Pure-bash, no fork.
      key="${key%"${key##*[![:space:]]}"}"
      # Trim leading whitespace from val (trailing kept — callers may need it).
      val="${val#"${val%%[![:space:]]*}"}"
      val="${val%$'\r'}"
      # If value contains ${ for variable expansion, output line directly for shell evaluation
      # Otherwise wrap in single quotes to handle spaces and special characters
      if [[ "$val" =~ \$\{ ]]; then
        printf "%s\n" "$line" >> "$tmpfile"
      else
        # Escape single quotes: ' -> '\''  (pure-bash substitution)
        esc="${val//\'/\'\\\'\'}"
        printf "%s='%s'\n" "$key" "$esc" >> "$tmpfile"
      fi
    fi
  done < "$f"
  set -a
  # Allow forward references like SUPABASE_ANON_KEY=${ANON_KEY} while loading.
  set +u
  # shellcheck source=/dev/null
  . "$tmpfile"
  set -u
  set +a
  rm -f "$tmpfile"
  set -H 2>/dev/null || true
}

# Base/shared defaults first.
load_env_file "$ROOT_DIR/env.shared.generated"
load_env_file "$ROOT_DIR/env.shared"

# Hardened 6-tier architecture overlays.
load_env_file "$ROOT_DIR/env.tier-data"
load_env_file "$ROOT_DIR/env.tier-supabase"
load_env_file "$ROOT_DIR/env.tier-api"
load_env_file "$ROOT_DIR/env.tier-llm"
load_env_file "$ROOT_DIR/env.tier-media"
load_env_file "$ROOT_DIR/env.tier-agent"
load_env_file "$ROOT_DIR/env.tier-worker"
load_env_file "$ROOT_DIR/env.tier-ui"

# URL-encoded credential overlay (passwords with @/:  for asyncpg/DSN-safe URLs)
load_env_file "$ROOT_DIR/env.tier-supabase.urlencoded"

# Local/runtime overlays last.
load_env_file "$ROOT_DIR/.env.generated"
load_env_file "$ROOT_DIR/.env.local"

# Supabase runtime overlay is generated from CLI status output.
# Only apply it when running in CLI mode to avoid stale overrides in compose mode.
if [ "${SUPABASE_RUNTIME:-compose}" = "cli" ]; then
  load_env_file "$ROOT_DIR/env.supa.runtime"
fi

# Back-compat: some docs/manifests use MINIO_USER/MINIO_PASSWORD. Services use MINIO_ACCESS_KEY/MINIO_SECRET_KEY.
if [ -z "${MINIO_ACCESS_KEY:-}" ] && [ -n "${MINIO_USER:-}" ]; then
  export MINIO_ACCESS_KEY="$MINIO_USER"
fi
if [ -z "${MINIO_SECRET_KEY:-}" ] && [ -n "${MINIO_PASSWORD:-}" ]; then
  export MINIO_SECRET_KEY="$MINIO_PASSWORD"
fi

# Local MinIO defaults:
# If only the unified S3 creds (MINIO_ACCESS_KEY/MINIO_SECRET_KEY) are configured,
# mirror them into MINIO_ROOT_USER/MINIO_ROOT_PASSWORD so the optional local MinIO service can boot.
if [ -z "${MINIO_ROOT_USER:-}" ] && [ -n "${MINIO_ACCESS_KEY:-}" ]; then
  export MINIO_ROOT_USER="$MINIO_ACCESS_KEY"
fi
if [ -z "${MINIO_ROOT_PASSWORD:-}" ] && [ -n "${MINIO_SECRET_KEY:-}" ]; then
  export MINIO_ROOT_PASSWORD="$MINIO_SECRET_KEY"
fi

# Supabase alias normalization:
# env.shared can contain forward refs (e.g. SUPABASE_ANON_KEY=${ANON_KEY})
# before ANON_KEY/SERVICE_ROLE_KEY are defined. Normalize here after all files load.
if [ -z "${SUPABASE_ANON_KEY:-}" ] && [ -n "${ANON_KEY:-}" ]; then
  export SUPABASE_ANON_KEY="$ANON_KEY"
fi
if [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ] && [ -n "${SERVICE_ROLE_KEY:-}" ]; then
  export SUPABASE_SERVICE_ROLE_KEY="$SERVICE_ROLE_KEY"
fi
# Do NOT back-fill SUPABASE_PUBLISHABLE_KEY / SUPABASE_SECRET_KEY from the
# legacy JWT keys. They are the NEW opaque API-key model (sb_publishable_*/
# sb_secret_*): Kong's declarative config registers all four as distinct
# keyauth credentials, so aliasing them to the legacy values is a uniqueness
# violation that crash-loops Kong at init. Empty = legacy-only mode (the
# kong-entrypoint strips the empty credential lines).

export PMOVES_ENV_LOADER=1

# Execute any remaining arguments as a command with the loaded environment.
# This enables the pattern: bash scripts/with-env.sh <command> <args>
# When sourced (no arguments), the env is simply exported and control returns.
if [ $# -gt 0 ]; then
  exec "$@"
fi
