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

# Resolve through symlinks before deriving ROOT. install-claude-pmoves-command.sh
# drops a ~/.local/bin/claude-pmoves symlink on PATH as the route for shells that
# don't source the rc function. Taking dirname of the SYMLINK made ROOT=$HOME, so
# env.shared and .claude/mcp.json both missed and every cred-dependent MCP started
# empty — silently, with only a WARN. Same failure class as #2484, other entrypoint.
SELF="${BASH_SOURCE[0]:-$0}"
while [ -L "$SELF" ]; do
  link_dir="$(cd -P "$(dirname "$SELF")" && pwd)"
  SELF="$(readlink "$SELF")"
  case "$SELF" in /*) ;; *) SELF="$link_dir/$SELF" ;; esac
done
if [ -n "${PMOVES_REPO_ROOT:-}" ]; then
  ROOT="$PMOVES_REPO_ROOT"
else
  ROOT="$(cd "$(dirname "$SELF")/../.." && pwd)"
fi

# Validate the derived ROOT the way the sibling launchers already do — crush-pmoves
# tests `$candidate/pmoves/Makefile`, pmoves-mini tests `$candidate/pmoves/tools/
# mini_cli.py`, and both reject a candidate that fails. This script computed ROOT and
# trusted it, so a wrong answer degraded into two WARNs and a session with every
# cred-dependent MCP dark. A launcher whose whole job is loading repo-relative config
# must not proceed when it cannot find the repo.
if [ ! -f "$ROOT/pmoves/Makefile" ]; then
  echo "[claude-pmoves] ERROR: derived repo root has no pmoves/Makefile: $ROOT" >&2
  echo "[claude-pmoves]        (resolved from: $SELF)" >&2
  echo "[claude-pmoves]        Fix: re-run deploy/provision/install-claude-pmoves-command.sh," >&2
  echo "[claude-pmoves]             or set PMOVES_REPO_ROOT=/path/to/PMOVES.AI" >&2
  exit 1
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
  # (Codex #2243). The transform needs JSON parsing; python3 is present on PMOVES
  # nodes. If it is missing we fall back to the raw roster (previous behavior).
  RESOLVED="${TMPDIR:-/tmp}/claude-pmoves-mcp-roster.$(id -u).json"
  resolved_ok=0
  if command -v python3 >/dev/null 2>&1; then
    if PM_ROOT="$ROOT" python3 - "$MCP_ROSTER" "$RESOLVED" <<'PY'
import json, os, sys
root = os.environ["PM_ROOT"]
src, dst = sys.argv[1], sys.argv[2]
def resolve(p):
    return os.path.join(root, p[2:]) if isinstance(p, str) and p.startswith("./") else p
with open(src) as fh:
    data = json.load(fh)
clean = {}
for name, cfg in (data.get("mcpServers") or {}).items():
    if name.startswith("_"):          # disabled-in-name-only — exclude
        continue
    if isinstance(cfg, dict):
        if isinstance(cfg.get("command"), str):
            cfg["command"] = resolve(cfg["command"])
        if isinstance(cfg.get("args"), list):
            cfg["args"] = [resolve(a) for a in cfg["args"]]
    clean[name] = cfg
data["mcpServers"] = clean
with open(dst, "w") as fh:
    json.dump(data, fh)
PY
    then
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
