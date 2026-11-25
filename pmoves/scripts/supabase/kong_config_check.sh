#!/bin/sh
# Pre-boot validation of the Supabase Kong declarative config.
#
# Runs INSIDE a throwaway supabase-kong container (see `make kong-config-check`),
# so it sees exactly the environment, mounts and image the real service gets.
# It renders kong.yml the same way kong-entrypoint.sh does, then asks Kong to
# parse it WITHOUT starting the gateway.
#
# Why: every known Kong crash-loop so far came from per-node env drift that
# nothing flagged before boot. Kong exits on a bad declarative config, Docker
# restarts it, and the loop runs silently (3,924 restarts on z890 2026-08-18,
# 1,266 in 22h on the 4090 2026-11-25). See
# docs/handoffs/supabase-kong-declarative-config-boot-failure-2026-08-18.md.
#
# Exit 0 = Kong will accept the config. Exit 1 = it will not; the message says why.

ENTRYPOINT=/home/kong/kong-entrypoint.sh
fail=0

say_fail() { echo "  ✗ $*" >&2; fail=1; }

echo "=== Kong: pre-boot declarative config check ==="

# --- Fault 1: empty dashboard password -------------------------------------
# kong.yml declares basicauth password '$DASHBOARD_PASSWORD'; Kong refuses an
# empty one ("in 'password': length must be at least 1").
if [ -z "${DASHBOARD_PASSWORD:-}" ]; then
  say_fail "DASHBOARD_PASSWORD is empty on this node. Kong rejects an empty basic-auth password."
  echo "    fix: make -C pmoves secrets-rotate KEY=DASHBOARD_PASSWORD LEN=32" >&2
fi

# --- Fault 3: new-format keys aliased to the legacy JWTs --------------------
# Each consumer declares both a legacy and a new key slot. Kong requires
# keyauth_credentials.key to be globally unique, so a copy is a hard refusal.
# Upstream's intended state for unmigrated installs is EMPTY (the entrypoint
# strips blank `- key:` lines).
dup_key() {
  # $1 new-name  $2 new-value  $3 legacy-name  $4 legacy-value
  if [ -n "$2" ] && [ "$2" = "$4" ]; then
    say_fail "$1 is a copy of $3. Kong rejects duplicate keyauth keys (uniqueness violation)."
    echo "    fix: set $1= (empty) in env.shared, then make -C pmoves secrets-funnel" >&2
  fi
}
dup_key SUPABASE_PUBLISHABLE_KEY "${SUPABASE_PUBLISHABLE_KEY:-}" SUPABASE_ANON_KEY "${SUPABASE_ANON_KEY:-}"
dup_key SUPABASE_SECRET_KEY "${SUPABASE_SECRET_KEY:-}" SUPABASE_SERVICE_KEY "${SUPABASE_SERVICE_KEY:-}"

# --- CRLF line endings (Windows checkouts) ----------------------------------
# PMOVES-supabase ships no .gitattributes, so core.autocrlf=true checks the
# entrypoint out with CRLF and `#!/bin/sh\r` cannot exec. The compose
# entrypoint now strips CRs before running it, so this is a warning only.
cr=$(printf '\r')
if grep -q "$cr" "$ENTRYPOINT" 2>/dev/null; then
  echo "  ! $ENTRYPOINT has CRLF line endings (Windows checkout). Compose strips them," >&2
  echo "    but re-check out the submodule with core.autocrlf=false to clear this." >&2
fi

# --- Render + parse ---------------------------------------------------------
# Same render as the real boot, with the final `exec ... kong docker-start`
# swapped for a no-op so the gateway never starts here.
if [ ! -r "$ENTRYPOINT" ] || [ ! -r /home/kong/temp.yml ]; then
  say_fail "kong.yml / kong-entrypoint.sh are not mounted. Is the PMOVES-supabase submodule populated?"
  echo "    fix: git submodule update --init PMOVES-supabase" >&2
  exit 1
fi

tr -d '\r' < "$ENTRYPOINT" \
  | sed 's|^exec /entrypoint.sh kong docker-start.*$|: # kong-config-check: start suppressed|' \
  > /tmp/kong-render.sh
if grep -q 'kong docker-start' /tmp/kong-render.sh; then
  say_fail "kong-entrypoint.sh no longer ends in 'exec /entrypoint.sh kong docker-start'; upstream changed it. Update this check."
  exit 1
fi

if ! sh /tmp/kong-render.sh; then
  say_fail "rendering kong.yml failed (see output above)"
  exit 1
fi

if kong config parse "$KONG_DECLARATIVE_CONFIG"; then
  echo "  ✓ Kong parses the rendered declarative config"
else
  say_fail "Kong refused the rendered declarative config (error above). It would crash-loop on boot."
fi

if [ "$fail" -ne 0 ]; then
  echo "✗ kong-config-check failed; not starting supabase-kong." >&2
  exit 1
fi
echo "✓ kong-config-check passed"
