#!/usr/bin/env bash
# Unified env loader for PMOVES scripts.
# Loads, in order: env.shared.generated → env.shared → .env.generated → .env.local
# Existing exported vars are preserved unless files set them explicitly.
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

load_env_file() {
  local f="$1"
  [ -f "$f" ] || return 0
  # shellcheck disable=SC2046
  set +H 2>/dev/null || true  # disable history expansion to tolerate '!'
  tmpfile=$(mktemp)
  # Build a sanitized assignment file: trim spaces around '=', always single-quote value, escape single quotes
  while IFS= read -r line; do
    # ignore comments/blank
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*[[:space:]]*=.*$ ]]; then
      key=${line%%=*}
      val=${line#*=}
      key=$(echo "$key" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')
      # trim leading spaces on value
      val=$(echo "$val" | sed -E 's/^[[:space:]]+//')
      # escape single quotes in value for POSIX sh style
      esc=${val//"'"/"'\\''"}
      printf "%s='%s'\n" "$key" "$esc" >> "$tmpfile"
    fi
  done < "$f"
  set -a
  # shellcheck source=/dev/null
  . "$tmpfile"
  set +a
  rm -f "$tmpfile"
  set -H 2>/dev/null || true
}

load_env_file "$ROOT_DIR/env.shared.generated"
load_env_file "$ROOT_DIR/env.shared"
load_env_file "$ROOT_DIR/.env.generated"
load_env_file "$ROOT_DIR/.env.local"

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

export PMOVES_ENV_LOADER=1
