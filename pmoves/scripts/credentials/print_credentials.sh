#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMOVES_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${PMOVES_ROOT}/.env.local"
SHARED_FILE="${PMOVES_ROOT}/env.shared"
SHARED_TEMPLATE="${PMOVES_ROOT}/env.shared.example"

load_value() {
  local key="$1" file="$2"
  if [ -f "$file" ]; then
    grep -E "^${key}=" "$file" | tail -n1 | cut -d'=' -f2-
  fi
}

get_env() {
  local key="$1"
  load_value "$key" "$ENV_FILE"
}

get_shared() {
  local key="$1"
  local value
  value=$(load_value "$key" "$SHARED_FILE")
  if [ -z "${value:-}" ]; then
    value=$(load_value "$key" "$SHARED_TEMPLATE")
  fi
  printf '%s' "${value:-}"
}

default_if_empty() {
  local value="$1" fallback="$2"
  if [ -z "$value" ]; then
    printf '%s' "$fallback"
  else
    printf '%s' "$value"
  fi
}

cat <<'HEADER'
PMOVES Provisioned Services — Default Login Summary
---------------------------------------------------
HEADER

wger_url=$(default_if_empty "$(get_shared WGER_BASE_URL)" "http://localhost:8000")
firefly_url=$(default_if_empty "$(get_shared FIREFLY_BASE_URL)" "http://localhost:8082")
jellyfin_url=$(default_if_empty "$(get_shared JELLYFIN_PUBLISHED_URL)" "http://localhost:8096")
jellyfin_api=$(default_if_empty "$(get_shared JELLYFIN_API_KEY)" "<not set>")
supa_rest=$(default_if_empty "$(get_shared SUPABASE_URL)" "http://localhost:3000")
supa_anon=$(default_if_empty "$(get_shared SUPABASE_ANON_KEY)" "<not set>")
supa_service=$(default_if_empty "$(get_shared SUPABASE_SERVICE_ROLE_KEY)" "<not set>")
minio_endpoint=$(default_if_empty "$(get_env MINIO_ENDPOINT)" "http://localhost:9000")
discord_webhook=$(default_if_empty "$(get_shared DISCORD_WEBHOOK_URL)" "<not set>")

cat <<EOF
Wger         : URL=${wger_url} | admin / adminadmin
Firefly III  : URL=${firefly_url} | First user you register becomes admin
Jellyfin     : URL=${jellyfin_url} | Set on first run; API key: ${jellyfin_api}
Supabase     : REST=${supa_rest} | anon=${supa_anon} service=${supa_service}
MinIO        : URL=${minio_endpoint} | minioadmin / minioadmin
Discord Webhook: ${discord_webhook}
EOF
