#!/usr/bin/env bash
# sso-create-user.sh — create a CONFIRMED Supabase (GoTrue) email/password user so
# DARKXSIDE can sign in at https://auth.pmoves.ai/login.
#
# Why this exists: the login page's "Sign in with GitHub" button is a dead internal
# link and GoTrue has no GitHub provider wired (see
# docs/handoffs / memory project_sso_auth_architecture_decision). Email/password is the
# interim path while Tailscale-identity SSO + Google Workspace get set up. GoTrue has no
# SMTP configured and MAILER_AUTOCONFIRM=false, so a self-service signup creates a user
# that can never confirm and thus can never log in. This uses the GoTrue ADMIN API with
# email_confirm:true, which creates an already-confirmed user without sending any mail.
#
# Security: the service_role key and the password NEVER appear in argv / `ps` /
# docker inspect / chat. The key rides a curl -K config file (chmod 600) and the JSON
# body (with the password) rides --data @file (chmod 600); both temp files are removed
# on exit. The password is read interactively (hidden) and confirmed.
#
# Usage (through the secrets pipeline so SUPABASE_SERVICE_ROLE_KEY is present):
#   bash pmoves/scripts/with-env.sh bash pmoves/scripts/sso-create-user.sh
# or the make target:
#   make -C pmoves sso-create-user
#
# Env:
#   SUPABASE_SERVICE_ROLE_KEY (or SERVICE_ROLE_KEY)  required — Kong apikey + GoTrue admin bearer
#   KONG_URL   default http://localhost:8000   (Supabase Kong on this node; /auth/v1 -> GoTrue)
set -euo pipefail

KONG_URL="${KONG_URL:-http://localhost:8000}"
KEY="${SUPABASE_SERVICE_ROLE_KEY:-${SERVICE_ROLE_KEY:-}}"

if [ -z "$KEY" ]; then
  echo "ERROR: SUPABASE_SERVICE_ROLE_KEY (or SERVICE_ROLE_KEY) is not in the environment." >&2
  echo "Run it through the pipeline so the key is loaded from the env tier:" >&2
  echo "  bash pmoves/scripts/with-env.sh bash pmoves/scripts/sso-create-user.sh" >&2
  exit 1
fi
command -v jq >/dev/null 2>&1 || { echo "ERROR: jq is required (safe JSON build without argv exposure)." >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "ERROR: curl is required." >&2; exit 1; }

# --- Preflight: Kong -> GoTrue reachable? (key is a header, via a 600 config file) ---
pre_cfg="$(mktemp)"; chmod 600 "$pre_cfg"
trap 'rm -f "$pre_cfg"' EXIT
printf 'header = "apikey: %s"\n' "$KEY" > "$pre_cfg"
pre=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 -K "$pre_cfg" "$KONG_URL/auth/v1/settings" || echo 000)
if [ "$pre" != "200" ]; then
  echo "ERROR: GoTrue not reachable via $KONG_URL/auth/v1 (settings -> HTTP $pre)." >&2
  echo "Is the supabase stack up on this node? (docker ps | grep supabase-kong)" >&2
  exit 1
fi

# --- Collect credentials interactively (password never echoed, never in argv) ---
read -r -p "Email for the new SSO user: " EMAIL
[ -n "$EMAIL" ] || { echo "Email required." >&2; exit 1; }
read -r -s -p "Password (hidden): " PW; echo
read -r -s -p "Confirm password:  " PW2; echo
[ "$PW" = "$PW2" ] || { echo "ERROR: passwords do not match." >&2; exit 1; }
[ "${#PW}" -ge 8 ] || { echo "ERROR: password must be at least 8 characters." >&2; exit 1; }

# --- Build request: JSON body via env (not --arg, which would hit ps) into a 600 file ---
body_file="$(mktemp)"; chmod 600 "$body_file"
cfg="$(mktemp)"; chmod 600 "$cfg"
trap 'rm -f "$pre_cfg" "$body_file" "$cfg"' EXIT
EMAIL="$EMAIL" PW="$PW" jq -n '{email: env.EMAIL, password: env.PW, email_confirm: true}' > "$body_file"
{
  printf 'header = "apikey: %s"\n' "$KEY"
  printf 'header = "Authorization: Bearer %s"\n' "$KEY"
  printf 'header = "Content-Type: application/json"\n'
} > "$cfg"
unset PW PW2

# --- Create the user ---
resp_file="$(mktemp)"
trap 'rm -f "$pre_cfg" "$body_file" "$cfg" "$resp_file"' EXIT
http=$(curl -sS -o "$resp_file" -w '%{http_code}' -X POST "$KONG_URL/auth/v1/admin/users" -K "$cfg" --data @"$body_file")

case "$http" in
  200|201)
    uid=$(jq -r '.id // .user.id // "?"' "$resp_file" 2>/dev/null || echo "?")
    echo "✔ Created confirmed user: $EMAIL  (id=$uid)"
    echo "  Sign in at https://auth.pmoves.ai/login (email/password)."
    ;;
  422)
    echo "• User already exists ($EMAIL). Nothing changed."
    echo "  To reset the password, use the admin API (PUT /auth/v1/admin/users/<id>) — not this script."
    ;;
  *)
    echo "ERROR: create failed (HTTP $http):" >&2
    jq -r '.msg // .message // .error // .' "$resp_file" 2>/dev/null >&2 || cat "$resp_file" >&2
    exit 1
    ;;
esac
