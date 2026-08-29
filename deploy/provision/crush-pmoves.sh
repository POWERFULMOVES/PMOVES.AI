#!/usr/bin/env bash
# crush-pmoves.sh — launch Charm Crush with pmoves/env.shared loaded so the MCP
# servers in ~/.config/crush/crush.json get their creds.
# ===========================================================================
# WHY: crush.json entries reference ${SUPABASE_SERVICE_KEY}, ${CIPHER_API_TOKEN},
# ${TS_Z890}, etc., which Crush substitutes from ITS OWN process env at launch.
# Nothing sources env.shared into that env, so cred-dependent MCPs start empty
# (or fail URL parsing — see AGNOTE4482PHI.t1.md SPARK Crush Awakening lane).
# This wrapper loads env.shared first, then exec's crush, so every ${VAR}
# resolves and all tools come online. Mirrors deploy/provision/claude-pmoves.sh.
#
# env.shared is the single source of truth, kept fresh by the secrets-hydration
# lane (`make -C pmoves secrets-runtime-hydrate` / `ensure-env-shared`).
#
# Usage:
#   deploy/provision/crush-pmoves.sh            # plain launch
#   alias crush=.../crush-pmoves.sh             # permanent
#
# Optional env overrides:
#   PMOVES_ENV_SHARED   path to env.shared (default: $REPO/pmoves/env.shared)
set -u

# ---------------------------------------------------------------------------
# REPO-ROOT RESOLUTION — keep byte-identical across the three launchers that
# carry it (claude-pmoves.sh, this file, pmoves/scripts/claude-pmoves.sh).
# Enforced by deploy/provision/tests/test-launcher-root-resolution.sh, which
# fails if one is fixed and the others are not — the drift that produced this
# bug in the first place.
#
# WHY THE WALK: an install script may drop a ~/.local/bin/<name> symlink on PATH
# for shells that don't source the rc function. Taking dirname of the SYMLINK
# makes ROOT=$HOME, so env.shared misses and every cred-dependent MCP starts
# empty — silently, with only a WARN.
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
# pmoves/services/creator-operator/config.py.
if [ -n "${PMOVES_LAUNCHER_ROOT:-}" ]; then
  ROOT="$PMOVES_LAUNCHER_ROOT"
else
  ROOT="$(CDPATH='' cd -P -- "$SELF_DIR/../.." && pwd)" || ROOT=""
fi

if [ ! -f "${ROOT:-/nonexistent}/pmoves/Makefile" ]; then
  if [ -n "${PMOVES_ENV_SHARED:-}" ] && [ -f "$PMOVES_ENV_SHARED" ]; then
    echo "[crush-pmoves] WARN: repo root not found (${ROOT:-<unresolved>}); using PMOVES_ENV_SHARED." >&2
  else
    echo "[crush-pmoves] ERROR: no pmoves/Makefile under repo root: ${ROOT:-<unresolved>}" >&2
    echo "[crush-pmoves]        (resolved from: $SELF)" >&2
    echo "[crush-pmoves]        Fix: set PMOVES_LAUNCHER_ROOT=/path/to/PMOVES.AI," >&2
    echo "[crush-pmoves]             or PMOVES_ENV_SHARED=/path/to/env.shared" >&2
    exit 1
  fi
fi

ENVF="${PMOVES_ENV_SHARED:-$ROOT/pmoves/env.shared}"

if [ -f "$ENVF" ]; then
  # Blocklist: vars that control Crush SDK/session behavior and should NEVER be
  # sourced by the launcher. These are user's personal billing/config, not fleet
  # MCP creds. Sourcing ANTHROPIC_API_KEY forces API billing even when the user
  # wants the Z.AI Coding Plan path.
  blocklist='^(ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN|ANTHROPIC_BASE_URL|CRUSH_|OPENAI_API_KEY)$'

  # env.shared is Docker Compose env_file format: unquoted values, and some are
  # ALIAS lines like SUPABASE_SERVICE_ROLE_KEY=${SERVICE_ROLE_KEY}. Two hazards:
  #   1. We can't `source` it raw — unquoted values break `. file`.
  #   2. We must NOT export values verbatim — that leaks the literal string
  #      "${SERVICE_ROLE_KEY}" into the MCP --apiKey, so an alias-backed MCP
  #      starts unauthorized even though the canonical key is present.
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
    # Skip blocklisted keys (these control Crush SDK/session, not MCP)
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
  echo "[crush-pmoves] loaded $n vars from $ENVF" >&2
else
  echo "[crush-pmoves] WARN: $ENVF not found — MCP creds may be missing." >&2
  echo "[crush-pmoves]       run: make -C pmoves ensure-env-shared" >&2
fi

# --- name bridge: PMOVES calls it Z_AI_API_KEY, Crush reads ZAI_API_KEY -------
# Crush's own README documents the Z.ai variable as `ZAI_API_KEY`; the funnel and
# the GitHub secret both spell it `Z_AI_API_KEY` (102 references across the repo).
# One underscore apart, so Crush could never pick up the key env.shared already
# carries -- which is why an operator had to paste one into ~/.config/crush/crush.json
# by hand, where it sits in plaintext and cannot rotate.
#
# Aliasing here rather than renaming either side: the PMOVES name is load-bearing
# in 102 places, and the upstream name is not ours to change. Only set when unset,
# so an explicitly-exported ZAI_API_KEY still wins.
if [ -z "${ZAI_API_KEY:-}" ] && [ -n "${Z_AI_API_KEY:-}" ]; then
  export ZAI_API_KEY="$Z_AI_API_KEY"
  echo "[crush-pmoves] ZAI_API_KEY <- Z_AI_API_KEY (upstream/PMOVES name bridge)" >&2
fi

exec crush "$@"
