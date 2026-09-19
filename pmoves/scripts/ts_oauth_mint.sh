#!/usr/bin/env bash
# Mint a Tailscale API access token from the OAuth client (client credentials).
#
# WHY THIS EXISTS: the fleet's static TAILSCALE_API_KEY was revoked upstream while
# remaining shape-valid, so the funnel kept delivering a dead credential (same
# failure class as the E2B e2b_/42-char delivery defect: the funnel validates
# shape, not liveness). The OAuth client (#3054) is the durable answer: mint a
# fresh token at sync time instead of storing a long-lived key at all.
#
# Official contract (accessed 2026-09-15):
#   POST https://api.tailscale.com/api/v2/oauth/token
#   body: client_id=...&client_secret=...   (form-encoded)
#   resp:  {"access_token": "...", "token_type": "Bearer", "expires_in": ...}
#   use:   Authorization: Bearer <access_token>
#   docs:  https://tailscale.com/kb/1215/oauth-clients
#
# Env: TAILSCALE_OAUTH_CLIENT_ID, TAILSCALE_OAUTH_CLIENT_SECRET (required).
# Prints the token on stdout ( callers MUST mask it ). Exit 0 only on a token.
set -euo pipefail

ID="${TAILSCALE_OAUTH_CLIENT_ID:-}"
SEC="${TAILSCALE_OAUTH_CLIENT_SECRET:-}"
if [ -z "$ID" ] || [ -z "$SEC" ]; then
  echo "ts_oauth_mint: TAILSCALE_OAUTH_CLIENT_ID/SECRET not set - cannot mint" >&2
  exit 3
fi

resp="$(curl -fsS --max-time 20 -X POST \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "client_id=$ID" \
  --data-urlencode "client_secret=$SEC" \
  https://api.tailscale.com/api/v2/oauth/token)" || {
    echo "ts_oauth_mint: token endpoint request failed" >&2
    exit 3
}

token="$(printf '%s' "$resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))')"
if [ -z "$token" ]; then
  echo "ts_oauth_mint: response carried no access_token" >&2
  exit 3
fi
printf '%s' "$token"
