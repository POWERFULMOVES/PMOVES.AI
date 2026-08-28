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
# WHY `CDPATH='' cd -P --`: dirname yields a bare relative path when the script is
# invoked relatively; `cd` consults CDPATH for such arguments, which both jumps
# elsewhere AND echoes the destination, embedding a newline in the captured path.
# ---------------------------------------------------------------------------
SELF="${BASH_SOURCE[0]:-$0}"
while [ -L "$SELF" ]; do
  link_dir="$(CDPATH='' cd -P -- "$(dirname -- "$SELF")" && pwd)"
  SELF="$(readlink -- "$SELF")"
  case "$SELF" in /*) ;; *) SELF="$link_dir/$SELF" ;; esac
done
SELF_DIR="$(CDPATH='' cd -P -- "$(dirname -- "$SELF")" && pwd)"

# PMOVES_LAUNCHER_ROOT, not PMOVES_REPO_ROOT: the latter is already consumed by
# pmoves/services/creator-operator/config.py, so reusing it would let a shell
# exported for that service silently redirect this launcher.
if [ -n "${PMOVES_LAUNCHER_ROOT:-}" ]; then
  ROOT="$PMOVES_LAUNCHER_ROOT"
else
  ROOT="$(CDPATH='' cd -P -- "$SELF_DIR/../.." && pwd)" || ROOT=""
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
    # shellcheck disable=SC2016  # the literal '${' is what is being matched
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
  # The tool PRINTS the path it wrote; it is not a name we pick. The old fixed
  # name (…-roster.$(id -u).json) is squattable in a world-writable /tmp, and
  # since the file now holds expanded bearer tokens, losing that race would both
  # fail the write AND silently fall back to the raw roster -- reinstating the
  # literal-${TS_Z890} failure on demand.
  NORMALIZER="$ROOT/pmoves/tools/mcp_roster_normalize.py"
  RESOLVED=""
  resolved_ok=0
  why=""
  # Shared discovery (pm-python.sh) — the third python convention this file
  # grew (scalar python in the identity twin, bare python3 here, inline chain
  # in crush-pmoves) was the pair-review finding: unify, don't re-add. No
  # probe: the normalizer needs only the stdlib (json/os/re).
  # shellcheck source=../../pmoves/scripts/pm-python.sh
  . "$ROOT/pmoves/scripts/pm-python.sh"
  # FOUR causes used to collapse into one guess: "(python3 missing?)". Keep them
  # apart. The operator's next command differs for each, and a message that names
  # the wrong cause sends them to fix the wrong thing — which is how this path
  # stayed broken: it blamed a missing interpreter for a whitespace-valued
  # PMOVES_PYTHON that made pm_pick_python return success with an EMPTY PM_PY,
  # so `"${PM_PY[@]}" "$NORMALIZER"` ran the .py file as the command.
  if [ ! -f "$NORMALIZER" ]; then
    why="the normalizer is missing: $NORMALIZER"
  # The empty probe is explicit, not an omission: the normalizer imports only
  # json/os/re, so any interpreter will do — but it still has to RUN.
  elif ! pm_pick_python ""; then
    why="no usable python interpreter (tried \$PMOVES_PYTHON, $ROOT/pmoves/.venv-pmoves, python3, py -3, python)"
  else
    RESOLVED="$("${PM_PY[@]}" "$NORMALIZER" "$MCP_ROSTER" \
                 --root "$ROOT" --label claude-pmoves)"
    norm_rc=$?
    if [ "$norm_rc" -ne 0 ]; then
      why="the normalizer exited $norm_rc under '${PM_PY[*]}' (its own stderr is above)"
    elif [ -z "$RESOLVED" ]; then
      why="the normalizer exited 0 but printed no roster path — nothing was written"
    else
      resolved_ok=1
    fi
  fi

  # Pass the config with `--mcp-config=<file>` (the `=` form): `--mcp-config` is a
  # variadic option (`<configs...>`), so the space form would swallow a trailing
  # positional prompt as another config value (Codex #2243 P1). The `=` binds
  # exactly one value and leaves "$@" as separate arguments.
  if [ "$resolved_ok" -eq 1 ]; then
    exec claude --mcp-config="$RESOLVED" "$@"
  fi

  # -------------------------------------------------------------------------
  # FAIL CLOSED when the raw roster would carry literal ${VAR}s.
  #
  # The old behaviour warned once and launched anyway. What that produces is a
  # session whose MCP servers are present, look configured, and cannot
  # authenticate: Claude Code's documented response to an unresolvable reference
  # is to warn and then use the unexpanded "${VAR}" text AS THE VALUE. So
  # `Bearer ${CIPHER_API_TOKEN}` goes on the wire as that literal string (a
  # measured 401 against our own cipher shim) and `http://${TS_Z890}:8105/…` is
  # used as a hostname. Nothing inside the session can tell that apart from
  # "cipher is down", the single stderr line has scrolled away before the TUI
  # paints, and every subsequent session on that node repeats it.
  #
  # This is deliberately NOT the fail-open doctrine of the identity twin
  # (pmoves/scripts/claude-pmoves.sh: "an identity is a convenience; losing it
  # must never cost you the launch"), nor the "a lane is a ledger entry, not a
  # lock" position. Both were settled about things that cost you a NAME. This
  # costs credentials, and a credential that is silently a placeholder is worse
  # than an absent one because it reports success. The refusal is bounded: the
  # override is printed in the refusal itself, so it is one command rather than
  # a lockout, and `claude` is still on PATH unwrapped.
  #
  # PROPORTIONATE. If no unexpanded ${…} remains, the raw file authenticates
  # exactly as the normalized one would; that case warns about what it actually
  # loses (P2 disabled-duplicate dropping, P3 ./-path rewriting) and launches.
  # Refusing there would be a lock with nothing behind it.
  # -------------------------------------------------------------------------
  echo "[claude-pmoves] ERROR: could not normalize the MCP roster." >&2
  echo "[claude-pmoves]        cause: $why" >&2
  # -F: match the two characters literally; this is a placeholder check, not a
  # regex, and SC2016 is exactly backwards here — non-expansion is the point.
  # shellcheck disable=SC2016
  if grep -qF '${' "$MCP_ROSTER" 2>/dev/null; then
    echo "[claude-pmoves]        LOST: $MCP_ROSTER still contains \${VAR} references." >&2
    echo "[claude-pmoves]              Claude Code sends an unresolvable reference as the" >&2
    echo "[claude-pmoves]              LITERAL text, so bearer tokens would go out as" >&2
    echo "[claude-pmoves]              'Bearer \${CIPHER_API_TOKEN}' and cross-node URLs as" >&2
    echo "[claude-pmoves]              'http://\${TS_Z890}:8105/...'. Those servers load," >&2
    echo "[claude-pmoves]              look configured, and never authenticate." >&2
    if [ -z "${PMOVES_ALLOW_RAW_ROSTER:-}" ]; then
      echo "[claude-pmoves]        Refusing to start a session whose MCP credentials are" >&2
      echo "[claude-pmoves]        placeholders. Fix one of:" >&2
      echo "[claude-pmoves]          make -C pmoves preflight      # provisions pmoves/.venv-pmoves" >&2
      echo "[claude-pmoves]          PMOVES_PYTHON=/path/to/python # pin an interpreter explicitly" >&2
      echo "[claude-pmoves]        Or accept a credential-less session on purpose, this once:" >&2
      echo "[claude-pmoves]          PMOVES_ALLOW_RAW_ROSTER=1 <your usual command>" >&2
      exit 1
    fi
    echo "[claude-pmoves]        PMOVES_ALLOW_RAW_ROSTER=1 is set — launching anyway." >&2
  else
    echo "[claude-pmoves] WARN: launching with the RAW roster $MCP_ROSTER." >&2
    echo "[claude-pmoves]       No \${VAR} references remain, so credentials are intact." >&2
    echo "[claude-pmoves]       Lost: '_'-prefixed disabled duplicates are NOT dropped, and" >&2
    echo "[claude-pmoves]       ./ paths stay relative to your CWD instead of the repo root." >&2
  fi
  exec claude --mcp-config="$MCP_ROSTER" "$@"
else
  echo "[claude-pmoves] WARN: $MCP_ROSTER not found — PMOVES MCP servers will not load." >&2
  exec claude "$@"
fi
