#!/usr/bin/env bash
set -euo pipefail

echo "PMOVES First-Run Wizard (bash)"

ENV_FILE=".env.local"
cp -n .env.example "$ENV_FILE" || true

read -r -p "Stack mode: [1] Full  [2] Minimal (no n8n/yt/comfy)  > " MODE
read -r -p "Use external Supabase? (y/N) > " EXT_S
read -r -p "Use external Neo4j?    (y/N) > " EXT_N
read -r -p "Use external Meili?     (y/N) > " EXT_M
read -r -p "Use external Qdrant?    (y/N) > " EXT_Q
read -r -p "Enable GPU profile now? (y/N) > " GPU

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

echo "Starting stack…"
if [ "${GPU:-n}" = y ]; then
  make up-gpu
else
  make up
fi

if [ "${MODE:-1}" = "1" ]; then
  make up-n8n || true
  make up-yt || true
  make up-comfy || true
fi

echo "Running flight-check…"
make flight-check || true
echo "Wizard complete."
