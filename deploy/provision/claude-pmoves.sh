#!/usr/bin/env bash
# claude-pmoves.sh — launch Claude Code with pmoves/env.shared loaded so the MCP
# servers in .claude/mcp.json get their creds.
# ===========================================================================
# WHY: mcp.json entries reference ${TAILSCALE_API_KEY}, ${HOSTINGER_API_KEY}, etc.,
# which Claude Code substitutes from ITS OWN process env at launch. Nothing sources
# env.shared into that env, so cred-dependent MCPs start empty and their tools never
# surface — the CLI ends up without "access to all". This wrapper loads env.shared
# first, then exec's claude, so every ${VAR} resolves and all tools come online.
#
# env.shared is the single source of truth, kept fresh by the secrets-hydration lane
# (`make -C pmoves secrets-runtime-hydrate` / `ensure-env-shared`). This is the last mile.
#
# Usage: run this instead of `claude` (alias it: alias claude=/path/to/claude-pmoves.sh).
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/../.." && pwd)"
ENVF="${PMOVES_ENV_SHARED:-$ROOT/pmoves/env.shared}"

if [ -f "$ENVF" ]; then
  # Parse env_file format (KEY=VALUE) safely — do NOT `source` it: env.shared is
  # Docker Compose env_file format with unquoted values that would break `. file`.
  n=0
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|\#*) continue;; esac
    key=${line%%=*}
    val=${line#*=}
    # trim surrounding whitespace on the key; leave the value verbatim
    key=$(printf '%s' "$key" | tr -d '[:space:]')
    [ -z "$key" ] && continue
    export "$key=$val" 2>/dev/null && n=$((n+1))
  done < "$ENVF"
  echo "[claude-pmoves] loaded $n vars from $ENVF" >&2
else
  echo "[claude-pmoves] WARN: $ENVF not found — MCP creds may be missing." >&2
  echo "[claude-pmoves]       run: make -C pmoves ensure-env-shared" >&2
fi

exec claude "$@"
