#!/usr/bin/env bash
set -euo pipefail

echo "PMOVES First-Run Wizard (bash)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMOVES_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${PMOVES_ROOT}/.env.local"
BASE_ENV="${PMOVES_ROOT}/.env.example"

if [ ! -f "$BASE_ENV" ]; then
  echo "Missing base env template at $BASE_ENV" >&2
  exit 1
fi

mkdir -p "${PMOVES_ROOT}/scripts/install"
cp -n "$BASE_ENV" "$ENV_FILE" || true

run_make() {
  (cd "$PMOVES_ROOT" && make "$@")
}

read -r -p "Stack mode: [1] Full  [2] Minimal (no n8n/yt/comfy)  > " MODE
read -r -p "Use external Supabase? (y/N) > " EXT_S
read -r -p "Use external Neo4j?    (y/N) > " EXT_N
read -r -p "Use external Meili?     (y/N) > " EXT_M
read -r -p "Use external Qdrant?    (y/N) > " EXT_Q
read -r -p "Enable GPU profile now? (y/N) > " GPU
read -r -p "Enable Glancer add-on?  (y/N) > " GLANCER

echo "Configuring $ENV_FILE…"
sed -i.bak "s/^EXTERNAL_SUPABASE=.*/EXTERNAL_SUPABASE=$([ "${EXT_S:-n}" = y ] && echo true || echo false)/" "$ENV_FILE"
sed -i.bak "s/^EXTERNAL_NEO4J=.*/EXTERNAL_NEO4J=$([ "${EXT_N:-n}" = y ] && echo true || echo false)/" "$ENV_FILE"
sed -i.bak "s/^EXTERNAL_MEILI=.*/EXTERNAL_MEILI=$([ "${EXT_M:-n}" = y ] && echo true || echo false)/" "$ENV_FILE"
sed -i.bak "s/^EXTERNAL_QDRANT=.*/EXTERNAL_QDRANT=$([ "${EXT_Q:-n}" = y ] && echo true || echo false)/" "$ENV_FILE"
rm -f "$ENV_FILE.bak"

echo "Optional Discord webhook (for publisher):"
read -r -p "DISCORD_WEBHOOK_URL (empty to skip): " DURL
if [ -n "$DURL" ]; then
  awk -v v="$DURL" '/^DISCORD_WEBHOOK_URL=/{ $0="DISCORD_WEBHOOK_URL="v }1' "$ENV_FILE" > "$ENV_FILE.tmp" && mv "$ENV_FILE.tmp" "$ENV_FILE"
fi

if [ "${GLANCER:-n}" = y ]; then
  GLANCER_PATCH="${PMOVES_ROOT}/../pmoves_provisioning_addon_bundle/addons/install_glancer.sh"
  if [ -x "$GLANCER_PATCH" ]; then
    (cd "${PMOVES_ROOT}/.." && "$GLANCER_PATCH") || true
  elif [ -f "$GLANCER_PATCH" ]; then
    (cd "${PMOVES_ROOT}/.." && bash "$GLANCER_PATCH") || true
  else
    echo "Glancer installer not found at $GLANCER_PATCH; skipping." >&2
  fi
fi

echo "Starting stack…"
if [ "${GPU:-n}" = y ]; then
  run_make up-gpu || true
else
  run_make up || true
fi

if [ "${MODE:-1}" = "1" ]; then
  run_make up-n8n || true
  run_make up-yt || true
  run_make up-comfy || true
fi

echo "Running flight-check…"
run_make flight-check || true
echo "Wizard complete."
