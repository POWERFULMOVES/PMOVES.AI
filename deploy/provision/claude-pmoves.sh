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
  # Blocklist: vars that control Claude SDK/session behavior and should NEVER be
  # sourced by the launcher. These are user's personal billing/config, not fleet MCP creds.
  # Sourcing them forces API billing (ANTHROPIC_API_KEY) or clobbers session state.
  blocklist='^(ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN|ANTHROPIC_BASE_URL|CLAUDECODE|CLAUDE_CODE_|CLAUDE_SESSION_)$'

  # env.shared is Docker Compose env_file format: unquoted values, and some are
  # ALIAS lines like SUPABASE_SERVICE_ROLE_KEY=${SERVICE_ROLE_KEY}. Two hazards:
  #   1. We can't `source` it raw — unquoted values break `. file`.
  #   2. We must NOT export values verbatim — that leaks the literal string
  #      "${SERVICE_ROLE_KEY}" into the MCP --apiKey, so an alias-backed MCP
  #      starts unauthorized even though the canonical key is present (Codex #1987 P2).
  # Mirror pmoves/scripts/with-env.sh: build a sanitized assignment file
  # (single-quote plain values; pass ${...}-bearing lines through for shell
  # expansion), then source it with auto-export so aliases resolve against the
  # canonical keys defined earlier in the same file.
  set +H 2>/dev/null || true   # tolerate '!' in values (no history expansion)
  tmpf=$(mktemp)
  n=0
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"                       # normalize CRLF
    case "$line" in ''|\#*) continue;; esac
    case "$line" in *=*) : ;; *) continue;; esac
    key=${line%%=*}
    val=${line#*=}
    key=$(printf '%s' "$key" | tr -d '[:space:]')
    [ -z "$key" ] && continue
    # Skip blocklisted keys (these control Claude SDK/session, not MCP)
    if [[ "$key" =~ $blocklist ]]; then
      continue
    fi
    val="${val#"${val%%[![:space:]]*}"}"       # trim leading whitespace on value
    if [ "${val#*'${'}" != "$val" ]; then
      printf '%s=%s\n' "$key" "$val" >> "$tmpf" # let the shell expand ${...}
    else
      esc="${val//\'/\'\\\'\'}"                 # escape single quotes: ' -> '\''
      printf "%s='%s'\n" "$key" "$esc" >> "$tmpf"
    fi
    n=$((n+1))
  done < "$ENVF"
  set -a; set +u                               # auto-export; tolerate forward refs
  # shellcheck source=/dev/null
  . "$tmpf"
  set +a; set -u
  rm -f "$tmpf"
  set -H 2>/dev/null || true
  echo "[claude-pmoves] loaded $n vars from $ENVF" >&2
else
  echo "[claude-pmoves] WARN: $ENVF not found — MCP creds may be missing." >&2
  echo "[claude-pmoves]       run: make -C pmoves ensure-env-shared" >&2
fi

# Point Claude Code at the tracked PMOVES MCP roster. Claude Code only reads
# `.mcp.json` at the repo root (project scope), `~/.claude.json` (user/local),
# or an explicit `--mcp-config` — it does NOT read `.claude/mcp.json`. Without
# this flag every server defined there stays dark and the env vars loaded above
# have nothing to resolve into, which is exactly the "no access to all tools"
# symptom this wrapper was written to fix.
#
# NOT --strict-mcp-config: we want a MERGE, so the per-node `.mcp.json` written
# by `make -C pmoves mcp-toolkit-connect` (the Docker MCP gateway entry) stays
# live alongside the tracked roster.
MCP_ROSTER="$ROOT/.claude/mcp.json"
if [ -f "$MCP_ROSTER" ]; then
  exec claude --mcp-config "$MCP_ROSTER" "$@"
else
  echo "[claude-pmoves] WARN: $MCP_ROSTER not found — PMOVES MCP servers will not load." >&2
  exec claude "$@"
fi
