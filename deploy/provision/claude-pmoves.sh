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

# ---------------------------------------------------------------------------
# REPO-ROOT RESOLUTION — keep byte-identical across the three launchers that
# carry it (this file, crush-pmoves.sh, pmoves/scripts/claude-pmoves.sh).
# Enforced by deploy/provision/tests/test-launcher-root-resolution.sh, which
# fails if one is fixed and the others are not — the drift that produced this
# bug in the first place.
#
# WHY THE WALK: install-claude-pmoves-command.sh drops a ~/.local/bin/<name>
# symlink on PATH for shells that don't source the rc function. Taking dirname
# of the SYMLINK made ROOT=$HOME, so env.shared and .claude/mcp.json both missed
# and every cred-dependent MCP started empty — silently, with only a WARN.
#
# WHY `CDPATH= cd -P --`: dirname yields a bare relative path when the script is
# invoked relatively; `cd` consults CDPATH for such arguments, which both jumps
# elsewhere AND echoes the destination, embedding a newline in the captured path.
# ---------------------------------------------------------------------------
SELF="${BASH_SOURCE[0]:-$0}"
while [ -L "$SELF" ]; do
  link_dir="$(CDPATH= cd -P -- "$(dirname -- "$SELF")" && pwd)"
  SELF="$(readlink -- "$SELF")"
  case "$SELF" in /*) ;; *) SELF="$link_dir/$SELF" ;; esac
done
SELF_DIR="$(CDPATH= cd -P -- "$(dirname -- "$SELF")" && pwd)"

# PMOVES_LAUNCHER_ROOT, not PMOVES_REPO_ROOT: the latter is already consumed by
# pmoves/services/creator-operator/config.py, so reusing it would let a shell
# exported for that service silently redirect this launcher.
if [ -n "${PMOVES_LAUNCHER_ROOT:-}" ]; then
  ROOT="$PMOVES_LAUNCHER_ROOT"
else
  ROOT="$(CDPATH= cd -P -- "$SELF_DIR/../.." && pwd)" || ROOT=""
fi

# Validate the derived ROOT the way the sibling launchers do (marker-file check)
# rather than trusting the computation. A launcher whose whole job is loading
# repo-relative config must not proceed silently when it cannot find the repo.
#
# EXCEPTION: an explicit, existing PMOVES_ENV_SHARED means the operator has
# pinned the creds themselves — the documented "alias claude=..." path from a
# non-repo copy. Honour it and warn about the roster instead of hard-failing,
# which would make `claude` itself unusable on that node.
if [ ! -f "${ROOT:-/nonexistent}/pmoves/Makefile" ]; then
  if [ -n "${PMOVES_ENV_SHARED:-}" ] && [ -f "$PMOVES_ENV_SHARED" ]; then
    echo "[claude-pmoves] WARN: repo root not found (${ROOT:-<unresolved>}); using PMOVES_ENV_SHARED." >&2
    echo "[claude-pmoves]       The MCP roster is repo-relative and will be skipped." >&2
  else
    echo "[claude-pmoves] ERROR: no pmoves/Makefile under repo root: ${ROOT:-<unresolved>}" >&2
    echo "[claude-pmoves]        (resolved from: $SELF)" >&2
    echo "[claude-pmoves]        Fix: re-run deploy/provision/install-claude-pmoves-command.sh," >&2
    echo "[claude-pmoves]             set PMOVES_LAUNCHER_ROOT=/path/to/PMOVES.AI," >&2
    echo "[claude-pmoves]             or set PMOVES_ENV_SHARED=/path/to/env.shared" >&2
    exit 1
  fi
fi

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

# Resolve ${TS_<NODE>} for the cross-node MCP servers in the roster.
#
# .claude/mcp.json addresses cipher, agent-zero and archon as ${TS_Z890}. That
# name had exactly one definition in the repo -- an inline block in
# pmoves/scripts/crush-env.sh -- and only the Crush launcher sourced it. Same
# roster, two launchers, one of them blind: Claude got the literal string as a
# hostname and cipher never connected. The helper is shared, not copied.
#
# Best-effort: a node without the tailscale CLI just leaves them unset, and the
# normalizer below turns that into a named WARN instead of a silent 404.
TS_HELPER="$ROOT/pmoves/scripts/tailscale-node-ips.sh"
if [ -f "$TS_HELPER" ]; then
  # shellcheck source=../../pmoves/scripts/tailscale-node-ips.sh
  . "$TS_HELPER"
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
  # Normalize the roster before handing it to Claude:
  #   P2 — drop servers whose key starts with "_" (disabled-in-name-only, e.g.
  #        `_pmoves-cipher-legacy-python-wrapper`; `_disabled` is metadata, not a
  #        real MCP off-switch, so Claude would otherwise launch the broken dupe).
  #   P3 — rewrite repo-relative ("./…") command/arg paths to absolute $ROOT paths
  #        so `uv --directory ./pmoves-nats-mcp` launches from any caller CWD.
  #   P4 — expand ${VAR} in url/headers/env, and DROP any server whose variables
  #        are unset. Claude Code's documented behaviour for an unresolvable
  #        reference is to warn and then use the literal ${VAR} text as-is, so an
  #        unresolvable server looked well-formed and failed where nobody could
  #        see it. Announced-and-dropped is recoverable; silently-404ing is not.
  #
  # (Codex #2243 for P2/P3.) The transform used to be a heredoc right here, which
  # is why P4 was missing for so long: a heredoc cannot be tested. It now lives in
  # pmoves/tools/mcp_roster_normalize.py with pmoves/tests/test_mcp_roster_normalize.py
  # on it. If python3 or the tool is absent we fall back to the raw roster.
  RESOLVED="${TMPDIR:-/tmp}/claude-pmoves-mcp-roster.$(id -u).json"
  NORMALIZER="$ROOT/pmoves/tools/mcp_roster_normalize.py"
  resolved_ok=0
  if command -v python3 >/dev/null 2>&1 && [ -f "$NORMALIZER" ]; then
    if python3 "$NORMALIZER" "$MCP_ROSTER" "$RESOLVED" \
         --root "$ROOT" --label claude-pmoves; then
      resolved_ok=1
    fi
  fi

  # Pass the config with `--mcp-config=<file>` (the `=` form): `--mcp-config` is a
  # variadic option (`<configs...>`), so the space form would swallow a trailing
  # positional prompt as another config value (Codex #2243 P1). The `=` binds
  # exactly one value and leaves "$@" as separate arguments.
  if [ "$resolved_ok" -eq 1 ]; then
    exec claude --mcp-config="$RESOLVED" "$@"
  else
    echo "[claude-pmoves] WARN: could not normalize roster (python3 missing?); using raw $MCP_ROSTER" >&2
    exec claude --mcp-config="$MCP_ROSTER" "$@"
  fi
else
  echo "[claude-pmoves] WARN: $MCP_ROSTER not found — PMOVES MCP servers will not load." >&2
  exec claude "$@"
fi
