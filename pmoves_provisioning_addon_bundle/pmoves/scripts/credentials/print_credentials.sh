#!/usr/bin/env bash
set -euo pipefail
ENV_FILE="pmoves/.env.local"
SHARED_FILE="pmoves/env.shared"

getv() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -n1 | cut -d'=' -f2-; }
getsv(){ grep -E "^$1=" "$SHARED_FILE" 2>/dev/null | tail -n1 | cut -d'=' -f2-; }

echo "PMOVES Provisioned Services — Default Login Summary"
echo "---------------------------------------------------"
echo "Wger         : URL=$(getsv WGER_BASE_URL || echo http://localhost:8000) | admin / adminadmin"
echo "Firefly III  : URL=$(getsv FIREFLY_BASE_URL || echo http://localhost:8082) | First user you register becomes admin"
echo "Jellyfin     : URL=$(getsv JELLYFIN_PUBLISHED_URL || echo http://localhost:8096) | Set on first run; API key: $(getsv JELLYFIN_API_KEY || echo '<not set>')"
echo "Supabase     : REST=$(getsv SUPABASE_URL || echo http://localhost:3000) | anon=$(getsv SUPABASE_ANON_KEY || echo '<not set>') service=$(getsv SUPABASE_SERVICE_ROLE_KEY || echo '<not set>')"
echo "MinIO        : URL=$(getv MINIO_ENDPOINT || echo http://localhost:9000) | minioadmin / minioadmin"
echo "Discord Webhook: $(getsv DISCORD_WEBHOOK_URL || echo '<not set>')"
