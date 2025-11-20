#!/usr/bin/env bash
set -euo pipefail

# Create or rotate the Supabase boot operator using the CLI stack or remote URL.
# Writes credentials into env.shared, .env.local, and pmoves/.env.local

EMAIL="${SUPABASE_BOOT_USER_EMAIL:-operator@pmoves.local}"
NAME="${SUPABASE_BOOT_USER_NAME:-PMOVES Operator}"

# Prefer explicit SUPABASE_SERVICE_URL, then SUPABASE_URL, then CLI default
SUPA_URL="${SUPABASE_SERVICE_URL:-${SUPABASE_URL:-${NEXT_PUBLIC_SUPABASE_URL:-http://127.0.0.1:65421}}}"
SUPA_URL="${SUPA_URL%/}"

echo "→ Provisioning Supabase boot user at ${SUPA_URL} for ${EMAIL}"

# Basic readiness check (auth health or settings when service key is present)
READY=0
if [[ -n "${SUPABASE_SERVICE_ROLE_KEY:-}" ]]; then
  for _ in $(seq 1 20); do
    if curl -fsS -m 3 -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
      "${SUPA_URL}/auth/v1/settings" >/dev/null 2>&1; then READY=1; break; fi
    sleep 1
  done
else
  for _ in $(seq 1 20); do
    if curl -fsS -m 3 "${SUPA_URL}/auth/v1/health" >/dev/null 2>&1; then READY=1; break; fi
    sleep 1
  done
fi

if [[ "$READY" != "1" ]]; then
  echo "✖ Supabase auth not reachable at ${SUPA_URL}. Start CLI: make -C pmoves supa-start"
  exit 1
fi

## Resolve service role key via Supabase CLI if not exported
if [[ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]]; then
  TMP_OUT="$(mktemp)" || true
  # Supabase CLI is invoked at repo root (two levels above this script)
  ( cd "${SCRIPT_DIR}/../.." && supabase start --network-id pmoves-net ) >"$TMP_OUT" 2>&1 || true
  SRK=$(awk '/Secret key:/{print $3}' "$TMP_OUT" | tail -n1)
  rm -f "$TMP_OUT" || true
  if [[ -n "$SRK" ]]; then
    export SUPABASE_SERVICE_ROLE_KEY="$SRK"
  fi
fi

if [[ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]]; then
  echo "Supabase service role key missing. Export SUPABASE_SERVICE_ROLE_KEY before running."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export SUPABASE_SERVICE_URL="${SUPA_URL}"
python "${SCRIPT_DIR}/create_supabase_boot_user.py" "${EMAIL}" \
  --name "${NAME}" \
  --rotate-password \
  --json \
  --write-env env.shared \
  --write-env .env.local \
  --write-env pmoves/.env.local

echo "✔ Boot user ensured and env files updated."
