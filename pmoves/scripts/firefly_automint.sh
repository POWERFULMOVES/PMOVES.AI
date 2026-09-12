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
#   4. land it via the canonical secrets flow (`make secrets-rotate`) — the token is NEVER echoed
#   5. after the landed token round-trips, revoke the superseded PATs of the same name
#
# The PAT never touches stdout/chat — it flows container -> env.shared inside the script.
# Every exit path (success or failure) scrubs the in-container temp files; a failure after
# the mint also revokes the token it just created, so a failed run leaves no live credential.
#
# Refuses to run when this node carries a CI-pulled CHIT bundle (<bundle>.provenance):
# `secrets-rotate` replaces that bundle with a local env.shared export, which silently
# drops prod-only keys from every tier file. Re-pull first (make secrets-pull), or set
# FIREFLY_AUTOMINT_ALLOW_BUNDLE_REPLACE=1 to accept that trade knowingly.
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
  # Prefix match needs the trailing [A-Za-z0-9_]*: `^(NATS_|...)=` only matches a
  # variable literally named NATS_, so the earlier form unset nothing and a stale
  # FIREFLY_ACCESS_TOKEN exported in the shell still won compose interpolation.
  env | grep -iE '^(NATS_|SUPABASE_|POSTGRES_|PG|ANON_KEY|SERVICE_ROLE_KEY|JWT_|KONG_|DASHBOARD_|CIPHER_|FIREFLY_|GOTRUE_|MINIO_|QDRANT_|NEO4J_|REDIS_|GRAFANA_|SECRET_KEY|VAULT_|SEALED)[A-Za-z0-9_]*=' | sed 's/=.*//'
)

echo "[firefly-automint] container=$CONTAINER user=$EMAIL"

# 0. Production-bundle guard. secrets-rotate forces a local chit-export over whatever
# bundle is present; on a node fed by sync-secrets-local.yml that bundle carries
# prod-only keys env.shared does not, and they vanish from the tier files on the next
# funnel. Refuse that state instead of hiding the target's warning behind a redirect.
BUNDLE="$(make -C "$ROOT_DIR" -s --eval='__chit_path: ; @echo $(CHIT_EXPORT_PATH)' __chit_path 2>/dev/null | tail -1 | tr -d '
')"
if [ -n "$BUNDLE" ] && [ -f "${BUNDLE}.provenance" ] && [ "${FIREFLY_AUTOMINT_ALLOW_BUNDLE_REPLACE:-0}" != "1" ]; then
  echo "[firefly-automint] REFUSED: this node runs on a CI-pulled CHIT bundle (${BUNDLE}.provenance present)." >&2
  echo "  secrets-rotate would replace it with a local export and drop prod-only keys from the tier files." >&2
  echo "  Either re-pull after minting (PMOVES_NODE=<node> make -C pmoves secrets-pull) and re-run with" >&2
  echo "  FIREFLY_AUTOMINT_ALLOW_BUNDLE_REPLACE=1, or mint on the node that owns the bundle." >&2
  exit 3
fi

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
NEW_ID=""; PERSISTED=0
# Run the helper in revoke mode: $1 = "PAT_ONLY_ID=<id>" or "PAT_KEEP_ID=<id>". Re-injects the
# helper so it works even after the temp files were scrubbed.
revoke_pat() {
  docker exec "$CONTAINER" sh -c "echo '${B64}' | base64 -d > /tmp/firefly_mkpat.php && PAT_MODE=revoke $1 PAT_EMAIL='${EMAIL}' PAT_NAME='${TOKEN_NAME}' php /tmp/firefly_mkpat.php 2>/dev/null" | tr -d '
'
}
# EXIT trap, armed BEFORE the mint so no error path can leave the plaintext PAT in the
# container or a freshly minted token alive after a failed run.
cleanup() {
  local rc=$?
  if [ "$rc" -ne 0 ] && [ -n "$NEW_ID" ] && [ "$PERSISTED" != 1 ]; then
    echo "[firefly-automint] run failed after mint — revoking the just-minted token id=${NEW_ID}" >&2
    revoke_pat "PAT_ONLY_ID=${NEW_ID}" >&2 || echo "[firefly-automint] WARNING: could not revoke token id=${NEW_ID}; revoke it in Firefly (Profile → OAuth)" >&2
  fi
  docker exec "$CONTAINER" sh -c ': > /tmp/pmoves_pat 2>/dev/null; : > /tmp/pmoves_pat_id 2>/dev/null; : > /tmp/firefly_mkpat.php 2>/dev/null' >/dev/null 2>&1 || true
  exit "$rc"
}
trap cleanup EXIT
PAT="$(docker exec "$CONTAINER" sh -c "echo '${B64}' | base64 -d > /tmp/firefly_mkpat.php && PAT_EMAIL='${EMAIL}' PAT_NAME='${TOKEN_NAME}' php /tmp/firefly_mkpat.php >/dev/null 2>&1 && cat /tmp/pmoves_pat")"
NEW_ID="$(docker exec "$CONTAINER" sh -c 'cat /tmp/pmoves_pat_id 2>/dev/null' | tr -d '
')"
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
# Output is NOT suppressed: the target prints its own recovery warnings (bundle
# replacement, off-box copies, revoke-at-source) and those must reach the operator.
# The target's exit code is recorded but does NOT decide success: the tier write
# happens early in secrets-funnel, while its trailing secrets-audit / tooling-audit
# walk the whole checkout and can run for a very long time on a big node. The
# round-trip check below is the truth about whether the token landed; a rotate
# failure after a successful round-trip is reported as DEGRADED (exit 2), never
# as a reason to revoke a token that is already in the env files.
# Output goes to a file, not a pipe: when `timeout` kills make, its native
# (Windows) python children survive and would hold a pipe's write end open, so a
# `| sed` reader never sees EOF and the script hangs *after* the timeout fired.
ROTATE_LOG="$(mktemp "${TMPDIR:-/tmp}/firefly-automint-rotate.XXXXXX")"
export PMOVES_ROTATE_VALUE="$PAT"
set +e
timeout "${FIREFLY_AUTOMINT_ROTATE_TIMEOUT:-900}" make -C "$ROOT_DIR" secrets-rotate KEY=FIREFLY_ACCESS_TOKEN >"$ROTATE_LOG" 2>&1
ROTATE_RC=$?
set -e
unset PMOVES_ROTATE_VALUE
sed 's/^/[secrets-rotate] /' "$ROTATE_LOG"; : > "$ROTATE_LOG"
if [ "$ROTATE_RC" -eq 0 ]; then
  echo "[firefly-automint] secrets-rotate OK — env.shared + CGP bundle + tier env files all carry the new PAT"
elif [ "$ROTATE_RC" -eq 124 ]; then
  echo "[firefly-automint] WARNING: secrets-rotate exceeded ${FIREFLY_AUTOMINT_ROTATE_TIMEOUT:-900}s (its trailing audits are slow on this node) — checking whether the token landed anyway" >&2
else
  echo "[firefly-automint] WARNING: secrets-rotate exited ${ROTATE_RC} — checking whether the token landed anyway" >&2
fi

# 4b. Round-trip verify: read the token back through the env pipeline and test it — this
# catches any env-file write/read transform (e.g. the CR contamination that bit us).
LANDED="$(bash "${SCRIPT_DIR}/with-env.sh" bash -c 'printf "%s" "${FIREFLY_ACCESS_TOKEN:-}"' 2>/dev/null | tr -d '\r\n')"
rt=$(docker exec "$CONTAINER" curl -s -o /dev/null -w '%{http_code}' \
  -H "Authorization: Bearer ${LANDED}" -H 'Accept: application/vnd.api+json' \
  http://localhost:8080/api/v1/about || true)
if [ "$rt" = "200" ]; then
  echo "[firefly-automint] round-trip OK: env.shared token -> /api/v1/about 200"
  PERSISTED=1
else
  echo "[firefly-automint] ERROR: env.shared token round-trip FAILED (HTTP ${rt}) — the token did NOT land (secrets-rotate rc=${ROTATE_RC}). Run: PMOVES_ROTATE_VALUE=<pat> make -C pmoves secrets-rotate KEY=FIREFLY_ACCESS_TOKEN" >&2
  exit 1
fi

# 5. The landed token works, so the previous baseline PAT(s) of this name are superseded:
# revoke them at the source now rather than leaving a dead-but-valid bearer credential behind.
# Only tokens named ${TOKEN_NAME} are touched; per-tenant PATs minted in the UI are untouched.
echo "[firefly-automint] $(revoke_pat "PAT_KEEP_ID=${NEW_ID}" || echo 'WARNING: superseded-token revoke failed — revoke older '"${TOKEN_NAME}"' tokens in Firefly (Profile → OAuth)')"

# 6. Temp files are scrubbed by the EXIT trap (every path, not just this one).
if [ "$ROTATE_RC" -ne 0 ]; then
  echo "[firefly-automint] DEGRADED: the PAT is landed, round-tripped and superseded the old ones, but secrets-rotate's trailing steps did not complete (rc=${ROTATE_RC}). Re-run them: make -C pmoves secrets-audit tooling-audit" >&2
  echo "[firefly-automint] Next: make -C pmoves recreate-svc SVC=wealth-mcp (consumers cache env at creation)."
  exit 2
fi
echo "[firefly-automint] done. Next: make -C pmoves recreate-svc SVC=wealth-mcp (consumers cache env at creation)."
