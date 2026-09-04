#!/usr/bin/env bash
# firefly_automint.sh — automatically mint a Firefly III API PAT and land it in env.shared
# as FIREFLY_ACCESS_TOKEN (the fleet convention that wealth-mcp + integration-auth-setup read).
#
# Why this exists: Firefly is configured with remote_user_guard (SSO forward-auth), so web
# /register is disabled (500) and there is no user:create artisan. The API needs a passport
# OAuth PAT (the `correction:access-tokens` CLI token returns 401 on /api/v1). This script is
# the wger-style automation Firefly lacked:
#   1. ensure a passport personal-access client (idempotent)
#   2. provision the user by hitting a web route with the trusted Remote-User header
#      (TRUSTED_PROXIES=** honors it; the guard auto-creates the user)
#   3. mint an API PAT via firefly_mkpat.php ($user->createToken → plaintext JWT, once)
#   4. land it in env.shared via bootstrap_env.py (the token is NEVER echoed)
#
# The PAT never touches stdout/chat — it flows container -> env.shared inside the script.
#
# Usage: bash pmoves/scripts/firefly_automint.sh   (env overrides below)
set -euo pipefail

EMAIL="${FIREFLY_ADMIN_EMAIL:-pmoves@pmoves.ai}"
CONTAINER="${FIREFLY_CONTAINER:-pmoves-firefly}"
TOKEN_NAME="${FIREFLY_PAT_NAME:-wealth-mcp-automint}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Clear any PMOVES-family secrets inherited from an interactive shell BEFORE we
# touch the secrets pipeline. The secrets-funnel (step 4c) regenerates every tier
# env file; if it inherits a stale exported value (e.g. an old FIREFLY_ACCESS_TOKEN
# left over from `source with-env.sh`) it bakes that into the tier — the exact
# shell-shadow failure mode that made the funnel re-emit a dead 977-char token over
# the freshly-minted one. Config was already captured above, so this is safe.
while IFS= read -r _v; do unset "$_v" 2>/dev/null || true; done < <(
  env | grep -iE '^(NATS_|SUPABASE_|POSTGRES_|PG|ANON_KEY|SERVICE_ROLE_KEY|JWT_|KONG_|DASHBOARD_|CIPHER_|FIREFLY_ACCESS|FIREFLY_PAT|GOTRUE_|MINIO_|QDRANT_|NEO4J_|REDIS_|GRAFANA_|SECRET_KEY|VAULT_|SEALED)=' | sed 's/=.*//'
)

echo "[firefly-automint] container=$CONTAINER user=$EMAIL"

# 1. Ensure the passport personal-access client (idempotent; harmless if it already exists).
docker exec "$CONTAINER" php artisan passport:client --personal --no-interaction >/dev/null 2>&1 || true

# 2. Provision the user via the trusted Remote-User header (web guard auto-creates them).
code=$(docker exec "$CONTAINER" curl -s -o /dev/null -w '%{http_code}' \
  -H "Remote-User: ${EMAIL}" http://localhost:8080/ || true)
echo "[firefly-automint] user provision (Remote-User) -> HTTP ${code}"

# 3+4. Mint the PAT inside the container and read it back in ONE exec (base64-inject the
# helper to avoid docker-cp path quirks). php diagnostics go to /dev/null so stdout is the
# PAT alone; captured into $PAT here — never echoed.
B64="$(base64 -w0 "${SCRIPT_DIR}/firefly_mkpat.php" 2>/dev/null || base64 "${SCRIPT_DIR}/firefly_mkpat.php" | tr -d '\n')"
PAT="$(docker exec "$CONTAINER" sh -c "echo '${B64}' | base64 -d > /tmp/firefly_mkpat.php && PAT_EMAIL='${EMAIL}' PAT_NAME='${TOKEN_NAME}' php /tmp/firefly_mkpat.php >/dev/null 2>&1 && cat /tmp/pmoves_pat")"
# Windows/MSYS `docker exec` can append a CR to the stream — strip ALL CR/LF so the JWT is
# clean before it reaches bootstrap_env (which rejects \r) and env.shared (line-based).
PAT="$(printf '%s' "$PAT" | tr -d '\r\n')"
if [ -z "$PAT" ]; then echo "[firefly-automint] ERROR: no PAT produced" >&2; exit 1; fi

# Verify it works before persisting.
verify=$(docker exec "$CONTAINER" curl -s -o /dev/null -w '%{http_code}' \
  -H "Authorization: Bearer ${PAT}" -H 'Accept: application/vnd.api+json' \
  http://localhost:8080/api/v1/about || true)
if [ "$verify" != "200" ]; then echo "[firefly-automint] ERROR: minted PAT failed /api/v1/about (HTTP ${verify})" >&2; exit 1; fi
echo "[firefly-automint] PAT verified against /api/v1/about -> 200"

# Land + propagate through the CANONICAL secrets flow — do NOT hand-roll it. The
# `secrets-rotate` make target is the one sanctioned path: it runs
#   bootstrap_env --rotate (env.shared, surgical) -> chit-export FORCE (CGP bundle)
#   -> secrets-funnel (materialize every tier env file).
# PMOVES_ROTATE_VALUE feeds --value-env, so the JWT never passes through argv/make
# expansion (shell-safe). The funnel is the load-bearing step whose absence 401'd
# wealth-mcp: --rotate writes env.shared only, but FIREFLY_ACCESS_TOKEN is funneled
# into env.tier-agent (wealth-mcp's tier), which compose loads AFTER env.shared
# (last-writer-wins) — so the tier's stale copy won until the funnel rewrote it.
# The shadow-unset at the top keeps the funnel materializing from the bundle only.
export PMOVES_ROTATE_VALUE="$PAT"
if make -C "$ROOT_DIR" secrets-rotate KEY=FIREFLY_ACCESS_TOKEN >/dev/null 2>&1; then
  echo "[firefly-automint] secrets-rotate OK — env.shared + CGP bundle + tier env files all carry the new PAT"
else
  unset PMOVES_ROTATE_VALUE
  echo "[firefly-automint] ERROR: secrets-rotate failed — token NOT landed. Run: PMOVES_ROTATE_VALUE=<pat> make -C pmoves secrets-rotate KEY=FIREFLY_ACCESS_TOKEN" >&2
  exit 1
fi
unset PMOVES_ROTATE_VALUE

# 4b. Round-trip verify: read the token back through the env pipeline and test it — this
# catches any env-file write/read transform (e.g. the CR contamination that bit us).
LANDED="$(bash "${SCRIPT_DIR}/with-env.sh" bash -c 'printf "%s" "${FIREFLY_ACCESS_TOKEN:-}"' 2>/dev/null | tr -d '\r\n')"
rt=$(docker exec "$CONTAINER" curl -s -o /dev/null -w '%{http_code}' \
  -H "Authorization: Bearer ${LANDED}" -H 'Accept: application/vnd.api+json' \
  http://localhost:8080/api/v1/about || true)
if [ "$rt" = "200" ]; then
  echo "[firefly-automint] round-trip OK: env.shared token -> /api/v1/about 200"
else
  echo "[firefly-automint] ERROR: env.shared token round-trip FAILED (HTTP ${rt}) — the landed value differs from the minted PAT" >&2
  exit 1
fi

# 5. Scrub the in-container temp files (no rm -f needed; truncate).
docker exec "$CONTAINER" sh -c ': > /tmp/pmoves_pat 2>/dev/null; : > /tmp/firefly_mkpat.php 2>/dev/null' || true

echo "[firefly-automint] done. Next: make -C pmoves recreate-svc SVC=wealth-mcp (or chit-export for durability)."
