#!/usr/bin/env bash
# pmoves-cipher.sh — POSIX launcher for the pmoves-cipher CLI.
# ===========================================================================
# WHY THIS FILE: pmoves-cipher is a single front-end (pmoves/tools/cipher_cli.py)
# over a family of chit_* tools and the live cipher API health endpoint. Each
# subcommand dispatches to one underlying tool; this wrapper does the same
# three things every PMOVES launcher does:
#
#   1. resolve the repo root (NOT the symlink target — see install-… below),
#   2. source pmoves/env.shared into the process env if it exists, and
#   3. exec cipher_cli.py under the discovered python interpreter.
#
# The wrapper is INTENTIONALLY THIN: no roster normalization, no identity
# resolver, no fail-closed gates. claude-pmoves.sh owns that machinery because
# it alone carries the MCP roster. pmoves-cipher hits the cipher API directly
# via the bearer in env.shared, which is exactly the same bearer .claude/mcp.json
# uses — so the launcher surface mirrors the MCP surface, minus the roster.
#
# USAGE:  pmoves-cipher <subcommand> [args...]
#         (or `bash pmoves-cipher.sh` if not on PATH)
#
# Subcommands: register | verify | decode | encode | bundle | health
# See cipher_cli.py --help for the full grammar.
#
# Provenance: deploy/provision/pmoves-cipher.{sh,ps1,cmd} are the launcher
# trio for this CLI. Mirrors deploy/provision/claude-pmoves.{sh,ps1,cmd}
# (PR #3092 template, see pmoves/docs/AGENTS/pmoves_launcher_generator_LEARNINGS.md).
set -u

# ---------------------------------------------------------------------------
# REPO-ROOT RESOLUTION — byte-identical across the three launchers. Enforced
# by deploy/provision/tests/test-launcher-root-resolution.sh. The walk fixes
# the symlink-pickup bug (install-pmoves-cipher-command.sh drops a
# ~/.local/bin/pmoves-cipher symlink on PATH; `dirname $0` on a symlink
# resolves to $HOME, not the repo).
# ---------------------------------------------------------------------------
SELF="${BASH_SOURCE[0]:-$0}"
while [ -L "$SELF" ]; do
  link_dir="$(CDPATH='' cd -P -- "$(dirname -- "$SELF")" && pwd)"
  SELF="$(readlink -- "$SELF")"
  case "$SELF" in /*) ;; *) SELF="$link_dir/$SELF" ;; esac
done
SELF_DIR="$(CDPATH='' cd -P -- "$(dirname -- "$SELF")" && pwd)"

# PMOVES_LAUNCHER_ROOT, not PMOVES_REPO_ROOT: the latter is consumed by other
# PMOVES services (see pmoves/services/creator-operator/config.py), so reusing
# it would let a shell exported for that service silently redirect this launcher.
if [ -n "${PMOVES_LAUNCHER_ROOT:-}" ]; then
  ROOT="$PMOVES_LAUNCHER_ROOT"
else
  ROOT="$(CDPATH='' cd -P -- "$SELF_DIR/../.." && pwd)" || ROOT=""
fi

# Validate ROOT. Mirrors claude-pmoves.sh: a launcher whose whole job is
# loading repo-relative config must not proceed silently when it cannot find
# the repo.
if [ ! -f "${ROOT:-/nonexistent}/pmoves/Makefile" ]; then
  if [ -n "${PMOVES_ENV_SHARED:-}" ] && [ -f "$PMOVES_ENV_SHARED" ]; then
    echo "[pmoves-cipher] WARN: repo root not found (${ROOT:-<unresolved>}); using PMOVES_ENV_SHARED." >&2
    echo "[pmoves-cipher]       cipher_cli.py is repo-relative and will be skipped." >&2
  else
    echo "[pmoves-cipher] ERROR: no pmoves/Makefile under repo root: ${ROOT:-<unresolved>}" >&2
    echo "[pmoves-cipher]        (resolved from: $SELF)" >&2
    echo "[pmoves-cipher]        Fix: re-run deploy/provision/install-pmoves-cipher-command.sh," >&2
    echo "[pmoves-cipher]             set PMOVES_LAUNCHER_ROOT=/path/to/PMOVES.AI," >&2
    echo "[pmoves-cipher]             or set PMOVES_ENV_SHARED=/path/to/env.shared" >&2
    exit 1
  fi
fi

ENVF="${PMOVES_ENV_SHARED:-$ROOT/pmoves/env.shared}"

# ---------------------------------------------------------------------------
# env.shared loader — strictly the subset the cipher CLI actually needs.
#
# pmoves-cipher does NOT want the full env.shared: claude-pmoves.sh blocklists
# ANTHROPIC_API_KEY etc. because sourcing them forces API billing. The cipher
# CLI only needs CIPHER_API_TOKEN (bearer for the cipher API) and possibly a
# handful of NATS creds for downstream tools. Sourcing the whole file would
# pollute the launcher's child env with ANTHROPIC_* / CLAUDE_CODE_* keys when
# the launcher is invoked from a CI step or a hook script, which is the
# documented class of bug.
#
# So: source ONLY the keys listed in PMOVES_CIPHER_REQUIRED_KEYS (default:
# CIPHER_API_TOKEN). If you need more, set PMOVES_CIPHER_REQUIRED_KEYS to a
# space-separated list. The loader deliberately does NOT support regex or
# glob — "what keys does this launcher need" is a closed question answered by
# the launcher, not by the env file.
# ---------------------------------------------------------------------------
required_keys="${PMOVES_CIPHER_REQUIRED_KEYS:-CIPHER_API_TOKEN}"

if [ -f "$ENVF" ]; then
  set +H 2>/dev/null || true   # tolerate '!' in values
  n=0
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"                       # normalize CRLF
    case "$line" in ''|\#*) continue;; esac    # comment / blank
    case "$line" in *=*) : ;; *) continue;; esac
    key=${line%%=*}
    val=${line#*=}
    key=$(printf '%s' "$key" | tr -d '[:space:]')
    [ -z "$key" ] && continue
    # Match against the allow-list.
    wanted=false
    for k in $required_keys; do
      if [ "$key" = "$k" ]; then wanted=true; break; fi
    done
    [ "$wanted" = false ] && continue
    # Resolve ${VAR} / ${VAR:-default} against the env we have already loaded
    # from earlier lines in the same file. We iterate bounded passes so that
    # A=${B} -> B=${C} -> ${C:-fallback} converges (stop when a pass makes
    # no substitution). Aliases that resolve to another alias-not-yet-loaded
    # stay as literal ${VAR} text, exactly the same semantics as the shell's
    # `source` in claude-pmoves.sh. Self-reference (KEY=${KEY:-default}) and
    # chained-alias resolution both fall out of the iteration naturally.
    #
    # The allow-list means we ONLY resolve references whose name is also in
    # the allow-list -- ${SUPABASE_SERVICE_ROLE_KEY} in a CIPHER_API_TOKEN
    # line is left alone because SUPABASE isn't loaded here.
    for _pass in 1 2 3 4 5; do
      changed=false
      resolved=$val
      # Walk the references left-to-right; for each ${X} or ${X:-default},
      # substitute from the in-launcher map if X is allowed AND loaded.
      rest=$resolved
      new_rest=
      while [ -n "$rest" ]; do
        case "$rest" in
          *'${'*)
            prefix=${rest%%'${'*}
            ref=${rest#*'$'{*}
            ref=${ref%%'}'*}
            suffix=${rest#*'}'}
            # `${X:-default}` form -- extract the default.
            default=
            case "$ref" in
              *:-*)    name=${ref%%:-*}; default=${ref#*-:} ;;
              *)       name=$ref ;;
            esac
            # Allowed?
            allowed_ref=false
            for k in $required_keys; do
              if [ "$name" = "$k" ]; then allowed_ref=true; break; fi
            done
            if [ "$allowed_ref" = true ] && [ -n "${!name:-}" ]; then
              new_rest="${new_rest}${prefix}${!name}"
              changed=true
            elif [ "$allowed_ref" = true ] && [ -n "$default" ]; then
              new_rest="${new_rest}${prefix}${default}"
              changed=true
            else
              new_rest="${new_rest}${prefix}\${${ref}}"
            fi
            rest=$suffix
            ;;
          *)
            new_rest="${new_rest}${rest}"
            rest=
            ;;
        esac
      done
      val=$new_rest
      [ "$changed" = false ] && break
    done
    export "$key=$val"
    n=$((n+1))
  done < "$ENVF"
  echo "[pmoves-cipher] loaded $n vars from $ENVF" >&2
else
  echo "[pmoves-cipher] WARN: $ENVF not found — running without env.shared." >&2
  echo "[pmoves-cipher]       Subcommands that need CIPHER_API_TOKEN (none do directly) will still work, but any MCP client using this launcher's env will be unauthenticated." >&2
fi

# ---------------------------------------------------------------------------
# Python interpreter discovery — defer to the canonical pm-python.sh.
# pm-python.sh is the ONE python discovery; every PMOVES launcher that needs
# an interpreter sources it. See pmoves/scripts/pm-python.sh for the ladder
# (canonical venv, then platform launchers) and the explicit "PRESENCE IS
# NOT RUNNABILITY" guarantee that rejects the Microsoft Store stub.
# ---------------------------------------------------------------------------
PM_PY_SCRIPT="$ROOT/pmoves/scripts/pm-python.sh"
if [ -f "$PM_PY_SCRIPT" ]; then
  # shellcheck disable=SC1090
  . "$PM_PY_SCRIPT"
else
  echo "[pmoves-cipher] ERROR: $PM_PY_SCRIPT not found." >&2
  echo "[pmoves-cipher]        This launcher requires pm-python.sh for interpreter discovery." >&2
  echo "[pmoves-cipher]        Verify the repo is intact (pmoves/scripts/pm-python.sh should exist)." >&2
  exit 1
fi

if ! pm_pick_python; then
  echo "[pmoves-cipher] ERROR: no usable python interpreter." >&2
  echo "[pmoves-cipher]        Tried: \$PMOVES_PYTHON, $ROOT/pmoves/.venv-pmoves/bin/python," >&2
  echo "[pmoves-cipher]        $ROOT/pmoves/.venv-pmoves/Scripts/python.exe, python, python3, py -3." >&2
  echo "[pmoves-cipher]        Each candidate was RUN, so a Microsoft Store python.exe stub counts as absent." >&2
  echo "[pmoves-cipher]        Fix: run \`make -C pmoves preflight\` or set PMOVES_PYTHON=/path/to/python.exe." >&2
  exit 1
fi

CIPHER_CLI="$ROOT/pmoves/tools/cipher_cli.py"
if [ ! -f "$CIPHER_CLI" ]; then
  echo "[pmoves-cipher] ERROR: $CIPHER_CLI not found." >&2
  exit 1
fi

# Leave the same launcher-session marker claude-pmoves.sh leaves, so a
# downstream process can tell whether the env it sees came through a launcher.
# Format mirrors the ps1 twin so downstream checks do not need to know which
# launcher produced the env.
export PMOVES_LAUNCHER_SESSION="pmoves-cipher.sh (loaded $n vars)"

exec "${PM_PY[@]}" "$CIPHER_CLI" "$@"