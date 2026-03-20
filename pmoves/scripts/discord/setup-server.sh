#!/usr/bin/env bash
set -euo pipefail
# ═══════════════════════════════════════════════════════════════
# DARKXSIDE's School of POWERFUL MOVES — Discord Server Setup
# ═══════════════════════════════════════════════════════════════
#
# Creates the full channel structure, roles, and webhooks for a
# PMOVES Discord server using the Discord REST API.
#
# Prerequisites:
#   1. Create server in Discord client
#   2. Create bot at https://discord.com/developers/applications
#   3. Invite bot with: Administrator permission
#   4. Set DISCORD_BOT_TOKEN and GUILD_ID below or in env
#
# Usage:
#   DISCORD_BOT_TOKEN=xxx GUILD_ID=yyy bash setup-server.sh
# ═══════════════════════════════════════════════════════════════

DISCORD_BOT_TOKEN="${DISCORD_BOT_TOKEN:?Set DISCORD_BOT_TOKEN}"
GUILD_ID="${GUILD_ID:?Set GUILD_ID}"
API="https://discord.com/api/v10"
AUTH="Bot ${DISCORD_BOT_TOKEN}"

# ── Helpers ───────────────────────────────────────────────────

discord() {
  local method="$1" endpoint="$2"
  shift 2
  curl -sS -X "$method" "${API}${endpoint}" \
    -H "Authorization: ${AUTH}" \
    -H "Content-Type: application/json" \
    "$@"
}

create_category() {
  local name="$1"
  local resp id
  resp=$(discord POST "/guilds/${GUILD_ID}/channels" \
    -d "{\"name\": \"$name\", \"type\": 4}")
  id=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
  if [ -z "$id" ]; then
    echo "ERROR: Failed to create category '$name': $resp" >&2
    return 1
  fi
  echo "$id"
}

create_channel() {
  local name="$1" parent_id="$2" topic="${3:-}"
  local payload="{\"name\": \"$name\", \"type\": 0, \"parent_id\": \"$parent_id\""
  if [ -n "$topic" ]; then
    payload="${payload}, \"topic\": \"$topic\""
  fi
  payload="${payload}}"
  local resp id
  resp=$(discord POST "/guilds/${GUILD_ID}/channels" -d "$payload")
  id=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
  if [ -z "$id" ]; then
    echo "ERROR: Failed to create channel '$name': $resp" >&2
    return 1
  fi
  echo "$id"
}

create_voice_channel() {
  local name="$1" parent_id="$2"
  local resp id
  resp=$(discord POST "/guilds/${GUILD_ID}/channels" \
    -d "{\"name\": \"$name\", \"type\": 2, \"parent_id\": \"$parent_id\"}")
  id=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
  if [ -z "$id" ]; then
    echo "ERROR: Failed to create voice channel '$name': $resp" >&2
    return 1
  fi
  echo "$id"
}

create_role() {
  local name="$1" color="$2"
  local id
  id=$(discord POST "/guilds/${GUILD_ID}/roles" \
    -d "{\"name\": \"$name\", \"color\": $color, \"mentionable\": true}" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  echo "  Role: $name ($id)"
}

create_webhook() {
  local channel_id="$1" name="$2"
  local url
  url=$(discord POST "/channels/${channel_id}/webhooks" \
    -d "{\"name\": \"$name\"}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('url','ERROR'))")
  echo "$url"
}

# ── Roles ─────────────────────────────────────────────────────

echo "═══ Creating Roles ═══"
create_role "Student"    "3447003"   # #348ABB blue
create_role "Builder"    "3066993"   # #2ECC71 green
create_role "Enterprise" "15105570"  # #E67E22 orange
create_role "Investor"   "10181046"  # #9B59B6 purple

# ── Categories & Channels ─────────────────────────────────────

echo ""
echo "═══ Creating Categories & Channels ═══"

# WELCOME
echo "→ WELCOME"
CAT_WELCOME=$(create_category "WELCOME")
CH_WELCOME=$(create_channel "welcome" "$CAT_WELCOME" "Welcome to DARKXSIDE's School of POWERFUL MOVES")
CH_WAITLIST=$(create_channel "waitlist" "$CAT_WELCOME" "Join the waitlist — Supabase-backed signup")
CH_ANNOUNCE=$(create_channel "announcements" "$CAT_WELCOME" "Platform updates and new content")

# AGENTS
echo "→ AGENTS"
CAT_AGENTS=$(create_category "AGENTS")
CH_TRAILS=$(create_channel "agent-trails" "$CAT_AGENTS" "Graphiti signed trail feed")
CH_CARDS=$(create_channel "agent-cards" "$CAT_AGENTS" "ComfyUI-rendered agent identity cards")
CH_CHAT=$(create_channel "agent-chat" "$CAT_AGENTS" "Interactive voice/text agent — RAG-aware")
CH_STATUS=$(create_channel "agent-status" "$CAT_AGENTS" "Service health feed")

# CREATIVE
echo "→ CREATIVE"
CAT_CREATIVE=$(create_category "CREATIVE")
CH_BEATS=$(create_channel "beats-lab" "$CAT_CREATIVE" "Audio upload → analysis → CGP envelope")
CH_RENDER=$(create_channel "render-lab" "$CAT_CREATIVE" "ComfyUI trigger + results feed")
CH_VOICE=$(create_channel "voice-lab" "$CAT_CREATIVE" "TTS demos via Flute Gateway")
CH_SONG=$(create_channel "song-lab" "$CAT_CREATIVE" "Music creation → beats analysis → indexing")

# RESEARCH
echo "→ RESEARCH"
CAT_RESEARCH=$(create_category "RESEARCH")
CH_DEEP=$(create_channel "deep-research" "$CAT_RESEARCH" "DeepResearch results feed")
CH_KB=$(create_channel "knowledge-base" "$CAT_RESEARCH" "Hi-RAG query bot — !ask your question")
CH_CIPHER=$(create_channel "cipher-memory" "$CAT_RESEARCH" "Agent memory queries via Cipher")

# BUILDERS
echo "→ BUILDERS"
CAT_BUILDERS=$(create_category "BUILDERS")
CH_DEV=$(create_channel "dev-updates" "$CAT_BUILDERS" "CI/CD notifications, PR merges")
CH_PINOKIO=$(create_channel "pinokio-apps" "$CAT_BUILDERS" "App discovery and launcher links")
CH_DOCKER=$(create_channel "docker-status" "$CAT_BUILDERS" "Container health and compose profiles")

# VOICE CHANNELS
echo "→ VOICE CHANNELS"
CAT_VC=$(create_category "VOICE CHANNELS")
create_voice_channel "Agent Voice" "$CAT_VC"
create_voice_channel "Beats Room" "$CAT_VC"
create_voice_channel "Research Lab" "$CAT_VC"

# ── Webhooks for NATS-fed channels ────────────────────────────

echo ""
echo "═══ Creating Webhooks ═══"
echo "  agent-trails:"
WH_TRAILS=$(create_webhook "$CH_TRAILS" "PMOVES Agent Trails")
echo "    $WH_TRAILS"

echo "  announcements:"
WH_ANNOUNCE=$(create_webhook "$CH_ANNOUNCE" "PMOVES Publisher")
echo "    $WH_ANNOUNCE"

echo "  deep-research:"
WH_DEEP=$(create_webhook "$CH_DEEP" "PMOVES DeepResearch")
echo "    $WH_DEEP"

echo "  dev-updates:"
WH_DEV=$(create_webhook "$CH_DEV" "PMOVES CI")
echo "    $WH_DEV"

echo "  beats-lab:"
WH_BEATS=$(create_webhook "$CH_BEATS" "PMOVES Audio Analysis")
echo "    $WH_BEATS"

echo "  render-lab:"
WH_RENDER=$(create_webhook "$CH_RENDER" "PMOVES ComfyUI")
echo "    $WH_RENDER"

# ── Summary ───────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Server setup complete!"
echo ""
echo "  Add these to env.shared (docker-compose expects DISCORD_WEBHOOK_URL):"
echo "    DISCORD_WEBHOOK_URL=$WH_TRAILS"
echo ""
echo "  Per-channel webhooks for publisher-discord config:"
echo "    DISCORD_WEBHOOK_TRAILS=$WH_TRAILS"
echo "    DISCORD_WEBHOOK_ANNOUNCE=$WH_ANNOUNCE"
echo "    DISCORD_WEBHOOK_RESEARCH=$WH_DEEP"
echo "    DISCORD_WEBHOOK_CI=$WH_DEV"
echo "    DISCORD_WEBHOOK_BEATS=$WH_BEATS"
echo "    DISCORD_WEBHOOK_RENDER=$WH_RENDER"
echo "═══════════════════════════════════════════════════════════"
