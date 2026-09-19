#!/usr/bin/env bash
# mavis_sdk_env.sh - Mavis SDK env-strip helper, sourced by every PMOVES
# launcher that needs to scrub Mavis SDK env vars before exec'ing its binary.
#
# ===========================================================================
# WHY THIS FILE EXISTS
# ===========================================================================
#
# The Mavis SDK puts env vars in the process environment via the
# `env` block of `~/.claude/settings.json` (ANTHROPIC_BASE_URL,
# ANTHROPIC_AUTH_TOKEN, ANTHROPIC_MODEL, MCP_TIMEOUT, API_TIMEOUT_MS,
# CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC, ...).  Every PMOVES launcher
# inherits those vars from the parent process.  Without this scrub, every
# downstream CLI (claude, kilo, codex, kimi, hermes, pmoves-mini) starts with
# Mavis's provider config baked in - claude-pmoves talks to api.minimax.io
# instead of the operator's intended Anthropic endpoint, kilo-pmoves gets an
# ANTHROPIC_BASE_URL it does not understand, etc.
#
# The operator's framing ("claude-pmoves to load the claude-code settings")
# is the load-bearing requirement.  The check is a NEED check against the SDK:
# for each Mavis SDK var in the shell env, ask "does this CLI consume it?".
# If yes, leave it.  If no, preserve its value under `PMOVES_MAVIS_SDK_<NAME>`
# and unset it, then WARN the operator what was caught.
#
# ===========================================================================
# WHY A REGISTRY, NOT A BLANKET BLOCKLIST
# ===========================================================================
#
# A blanket blocklist ("strip every Mavis SDK var") is wrong because:
#   * claude-pmoves consumers MAY want to keep ANTHROPIC_BASE_URL if they
#     actually use Mavis's API as their Claude Code provider.  The check is
#     per-CLI, not per-process.
#   * kilo-pmoves consumers want zero Mavis SDK vars (kilo talks to Z.AI/GLM
#     on its own config), but new Mavis SDK vars (e.g. ANTHROPIC_BETAS,
#     future fields) need to be considered for kilo too.  Per-CLI needs list
#     is the registry that makes "consider every CLI when adding a new var"
#     a single-place change.
#
# ===========================================================================
# HOW THE REGISTRY IS STRUCTURED
# ===========================================================================
#
# Two pieces of data, kept in sync with `pmoves/configs/cli_tools.yaml`:
#
#   MAVIS_SDK_ENV_NAMES:   every env var the Mavis SDK puts in process env.
#                          A new entry here is a CONTRACT change: any CLI
#                          whose `MAVIS_SDK_NEEDS_BY_TOOL` lacks an explicit
#                          answer for that var WILL strip it.
#
#   MAVIS_SDK_NEEDS_BY_TOOL: per-CLI list of "this var IS needed by THIS
#                          CLI's SDK, do not strip".  Keys match the CLI
#                          name in `pmoves/configs/cli_tools.yaml`.  The
#                          special value `["*"]` means "consume every Mavis
#                          SDK var" (used by pmoves-mini, which IS the
#                          Mavis agent).  An empty list means "strip them
#                          all, this CLI does not consume any".
#
# The two share a keys contract: when you add a var to MAVIS_SDK_ENV_NAMES,
# every key in MAVIS_SDK_NEEDS_BY_TOOL gets either a corresponding entry or
# stays empty - both are valid answers, just explicit ones.
#
# ===========================================================================
# USAGE
# ===========================================================================
#
#   source pmoves/scripts/mavis_sdk_env.sh
#
#   # Strip Mavis SDK vars NOT needed by claude, preserve the rest under prefix.
#   mavis_sdk_strip_env_for "claude"
#
#   # Inspect what was stripped (after the call):
#   echo "PMOVES_MAVIS_SDK_STRIPPED=${PMOVES_MAVIS_SDK_STRIPPED:-}"
#
# ---------------------------------------------------------------------------
# Test pin: pmoves/tests/test_mavis_sdk_env.py pins the registry shape, the
# strip behavior, the preservation under PMOVES_MAVIS_SDK_<NAME>, the WARN
# line emission, the "all-needed" pass-through (every var in needs list is
# kept, every var not in needs list is stripped), and the "*" wildcard.  Do
# not change a behavior without a matching test mutation-kill.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Resolve this file's directory once, so it works when sourced from any CWD.
# ---------------------------------------------------------------------------
_MAVIS_SDK_ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# ---------------------------------------------------------------------------
# Registry: Mavis SDK env vars (the env block of ~/.claude/settings.json).
#
# Add a NEW Mavis SDK env var HERE, then verify every entry in
# MAVIS_SDK_NEEDS_BY_TOOL explicitly handles it (either listed or omitted).
# Leaving the per-CLI decision implicit means a new var silently passes
# through to every CLI - the exact leak this file exists to prevent.
# ---------------------------------------------------------------------------
MAVIS_SDK_ENV_NAMES=(
  # Billing / provider routing (force a specific API host + token)
  ANTHROPIC_API_KEY
  ANTHROPIC_AUTH_TOKEN
  ANTHROPIC_BASE_URL
  # Model picker forcing (forces claude --model to a specific variant)
  ANTHROPIC_MODEL
  ANTHROPIC_DEFAULT_SONNET_MODEL
  ANTHROPIC_DEFAULT_OPUS_MODEL
  ANTHROPIC_DEFAULT_HAIKU_MODEL
  # PMOVES-internal runtime config (not part of Claude Code or kilo)
  API_TIMEOUT_MS
  MCP_TIMEOUT
  # Claude Code session / telemetry (NOT consumed by kilo/codex/kimi/hermes)
  CLAUDECODE
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC
  CLAUDE_CODE_AUTO_COMPACT_WINDOW
  # Glob patterns - matched via shell case against the live env
  "CLAUDE_CODE_*"
  "CLAUDE_SESSION_*"
)

# ---------------------------------------------------------------------------
# Per-CLI needs registry.
#
# KEYS MUST MATCH pmoves/configs/cli_tools.yaml CLI names (the registry
# the operator pointed at - "check PMOVES-Registry for existing tooling").
# A new CLI in cli_tools.yaml that is absent from this dict falls through
# the "no entry" branch, which behaves as needs=[] (strip everything).  That
# is the SAFE default for a new CLI - the alternative (silently inherit
# Mavis config) is the bug this file exists to prevent.
#
# Special value `["*"]` means "consume every Mavis SDK var" - reserved for
# PMOVES-internal CLIs that ARE the Mavis agent (pmoves-mini).
# ---------------------------------------------------------------------------
MAVIS_SDK_NEEDS_BY_TOOL_claude=(
  ANTHROPIC_BASE_URL
  ANTHROPIC_AUTH_TOKEN
  ANTHROPIC_API_KEY
)
MAVIS_SDK_NEEDS_BY_TOOL_kilo=()
MAVIS_SDK_NEEDS_BY_TOOL_codex=()
MAVIS_SDK_NEEDS_BY_TOOL_kimi=()
MAVIS_SDK_NEEDS_BY_TOOL_hermes=()
MAVIS_SDK_NEEDS_BY_TOOL_crush=()
MAVIS_SDK_NEEDS_BY_TOOL_pmoves_mini=(
  "*"
)

# ---------------------------------------------------------------------------
# mavis_sdk_needs_for <cli_name>
#
# Echoes the needs list for a CLI, one element per line.  Caller pipes it
# into the strip.  Echoes an empty string for an unknown CLI (which behaves
# as needs=[], stripping everything - the safe default).
# ---------------------------------------------------------------------------
mavis_sdk_needs_for() {
  local cli="$1"
  case "$cli" in
    claude) printf '%s\n' "${MAVIS_SDK_NEEDS_BY_TOOL_claude[@]}";;
    kilo)   printf '%s\n' "${MAVIS_SDK_NEEDS_BY_TOOL_kilo[@]}";;
    codex)  printf '%s\n' "${MAVIS_SDK_NEEDS_BY_TOOL_codex[@]}";;
    kimi)   printf '%s\n' "${MAVIS_SDK_NEEDS_BY_TOOL_kimi[@]}";;
    hermes) printf '%s\n' "${MAVIS_SDK_NEEDS_BY_TOOL_hermes[@]}";;
    crush)  printf '%s\n' "${MAVIS_SDK_NEEDS_BY_TOOL_crush[@]}";;
    pmoves-mini) printf '%s\n' "${MAVIS_SDK_NEEDS_BY_TOOL_pmoves_mini[@]}";;
    *)      return 0;;
  esac
}

# ---------------------------------------------------------------------------
# mavis_sdk_strip_env_for <cli_name>
#
# The load-bearing call.  For each Mavis SDK var in the SHELL env:
#   - if the var's value matches a NEED for this CLI, leave it
#   - else preserve it under PMOVES_MAVIS_SDK_<NAME> and unset the original
#   - record the stripped names in PMOVES_MAVIS_SDK_STRIPPED (newline-separated)
#   - emit ONE WARN line summarizing what was caught, on stderr
#
# Glob patterns in MAVIS_SDK_ENV_NAMES (e.g. CLAUDE_CODE_*) are matched against
# the live env via `compgen -v` (POSIX) or an equivalent list.  A match
# under a glob pattern uses the same preserve+unset path.
#
# Special case: needs=["*"] (used by pmoves-mini) means strip NOTHING.  This
# is the Mavis agent itself - it consumes the full Mavis SDK env by design.
#
# Side effects:
#   * Sets PMOVES_MAVIS_SDK_<NAME> for every stripped var
#   * Unsets the original var
#   * Sets PMOVES_MAVIS_SDK_STRIPPED (newline-separated names)
#   * Prints "[mavis-sdk] stripped N Mavis SDK vars from <cli> env: <names>"
#     on stderr when N > 0.  Silent when N == 0 (nothing to do).
# ---------------------------------------------------------------------------
mavis_sdk_strip_env_for() {
  local cli="$1"
  local needs_list=""
  local all_pass=0
  needs_list="$(mavis_sdk_needs_for "$cli" 2>/dev/null || true)"

  # "*" wildcard: pmoves-mini and other Mavis-internal CLIs that consume
  # every Mavis SDK var.  A bare "*" line in the needs list is the signal.
  if [ "$needs_list" = "*" ]; then
    all_pass=1
  fi

  local stripped=""
  local n_stripped=0
  local name val live_value
  local -a live_names

  # Enumerate the current shell's variable names.  `compgen -v` is a bash
  # builtin that lists set variable names - POSIX equivalent of `set` without
  # the values.  Filter to those whose NAME matches a Mavis SDK var OR a
  # Mavis SDK glob pattern.
  if [ -n "${ZSH_VERSION:-}" ]; then
    live_names=("${(k)parameters[@]}")
  else
    # bash
    mapfile -t live_names < <(compgen -v)
  fi

  for name in "${live_names[@]}"; do
    # Match against the registry.
    local matched=0
    for pat in "${MAVIS_SDK_ENV_NAMES[@]}"; do
      if [[ "$pat" == *"*"* ]]; then
        # Glob pattern - unquoted $pat on the RHS lets the * act as a glob
        # match against $name (e.g. pat='CLAUDE_CODE_*' matches the live var
        # CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC).
        # shellcheck disable=SC2053  # intentional: glob match on $name
        if [[ "$name" == $pat ]]; then
          matched=1
          break
        fi
      else
        if [ "$name" = "$pat" ]; then
          matched=1
          break
        fi
      fi
    done
    [ "$matched" -eq 1 ] || continue

    if [ "$all_pass" -eq 1 ]; then
      # Consume everything - skip the strip.
      continue
    fi

    # Is this var in the CLI's needs list?
    local needed=0
    if [ -n "$needs_list" ]; then
      while IFS= read -r needed_name; do
        if [ "$name" = "$needed_name" ]; then
          needed=1
          break
        fi
      done <<<"$needs_list"
    fi
    [ "$needed" -eq 1 ] && continue

    # Capture current value, preserve under prefix, unset the original.
    live_value="${!name:-}"
    if [ -n "$live_value" ]; then
      # PMOVES_MAVIS_SDK_<NAME> in upper-case, dashes/underscores preserved.
      # `declare -g` makes the export survive into the caller's scope.
      declare -g "PMOVES_MAVIS_SDK_${name}=${live_value}"
    fi
    unset "$name"
    if [ -z "$stripped" ]; then
      stripped="$name"
    else
      stripped="${stripped}"$'\n'"${name}"
    fi
    n_stripped=$((n_stripped + 1))
  done

  # Export the stripped list for downstream introspection (e.g.
  # `make -C pmoves session-check`).
  if [ -n "$stripped" ]; then
    PMOVES_MAVIS_SDK_STRIPPED="$stripped"
    export PMOVES_MAVIS_SDK_STRIPPED
    # One WARN line, all names on one line so the operator can grep it.
    # Newline-joined names flatten to spaces here for readability.
    local one_line
    one_line="$(printf '%s' "$stripped" | tr '\n' ' ')"
    echo "[mavis-sdk] stripped $n_stripped Mavis SDK vars from $cli env: $one_line" >&2
    echo "[mavis-sdk]   preserved under PMOVES_MAVIS_SDK_<NAME>; original vars unset." >&2
  else
    PMOVES_MAVIS_SDK_STRIPPED=""
    unset PMOVES_MAVIS_SDK_STRIPPED 2>/dev/null || true
  fi

  # Marker for downstream "this session was scrubbed" assertions.
  PMOVES_MAVIS_SDK_CLI="$cli"
  export PMOVES_MAVIS_SDK_CLI
  return 0
}

# Make the function available to subshells (e.g. when the caller does
# `( source ...; mavis_sdk_strip_env_for ... )`).  Bash exports functions
# when called with `export -f`, which works on Linux but historically not on
# macOS bash 3.2; the wrappers in claude-pmoves.sh / kilo-pmoves.sh source
# this file directly so the function is in scope.
if [ -n "${BASH_VERSION:-}" ]; then
  export -f mavis_sdk_strip_env_for 2>/dev/null || true
  export -f mavis_sdk_needs_for 2>/dev/null || true
fi
