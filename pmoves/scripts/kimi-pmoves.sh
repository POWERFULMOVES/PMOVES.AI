#!/usr/bin/env bash
# kimi-pmoves — Bootstrap Kimi with PMOVES project context
# Usage: kimi-pmoves [kimi-args...]
#
# Two different programs answer to `kimi`, and this launcher serves both:
#   - Kimi Code (>= 2.x, ~/.kimi-code/bin/kimi): takes NO config-file flags.
#     It reads <KIMI_CODE_HOME>/config.toml and mcp.json, plus the project
#     layer it finds from the working directory (<git root>/.mcp.json,
#     <cwd>/.kimi-code/mcp.json, AGENTS.md). Passing --config-file made it
#     exit with "error: unknown option '--config-file'" before any session.
#   - legacy kimi-cli (uv tool): takes --config-file / --mcp-config-file,
#     which load .kimi/config.toml and .kimi/mcp.json.
# The flag set is chosen by asking `kimi --help`, not by version-guessing.
#
# Either way the session is bound to THIS checkout (see the cwd block below).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# ---------------------------------------------------------------------------
# NODE IDENTITY + CIPHER CARRY -- added 2026-09-16.
#
# This launcher previously told its agent NOTHING: not which node it was on, not
# which registered identity it wears, and not whether cipher would record its
# memories as itself. Measured across the nine launchers that day, only the two
# CLAUDE ones carried the full set. Cipher is shared by every agent on a node --
# auth.ts files an uncarried write under `bootstrap`, "shared with every other
# agent on the node, attributed to none" (crush-pmoves) -- so an unwired harness
# does not merely lose its own attribution, it pollutes everyone's.
#
# Both measurements are SHARED FRAGMENTS, never copied blocks: that is the rule
# pm-python.sh and pm-cipher-identity.sh were extracted under, and copying into
# eight files is named there as the cause of this family's last three defects.
#
# FAIL-OPEN, ALWAYS LOUD. Neither call can cost the launch, and every path prints
# its reason -- an unbound session is degraded, not broken, but never silent.
# ---------------------------------------------------------------------------
if [ -f "$PROJECT_ROOT/pmoves/scripts/pm-node-identity.sh" ]; then
  # shellcheck source=./pm-node-identity.sh
  . "$PROJECT_ROOT/pmoves/scripts/pm-node-identity.sh"
  pm_node_identity "$PROJECT_ROOT" kimi kimi-pmoves || true
  echo "${PM_IDENT_LINE}" >&2
  # CIPHER TOKEN BIND + TS_ RESOLUTION. .kimi/mcp.json addresses cipher as
  # ${TS_Z890} and authenticates with ${CIPHER_API_TOKEN}; this launcher loads
  # neither, so every reference went out literal and cipher never connected.
  # Bind the minted per-agent token for the declared agentId BEFORE the carry
  # measurement so the verdict reports the post-bind reality.
  TS_HELPER="$PROJECT_ROOT/pmoves/scripts/tailscale-node-ips.sh"
  if [ -f "$TS_HELPER" ]; then
    # shellcheck source=./tailscale-node-ips.sh
    . "$TS_HELPER"
  fi
  if [ -f "$PROJECT_ROOT/pmoves/scripts/pm-cipher-token-bind.sh" ]; then
    # shellcheck source=./pm-cipher-token-bind.sh
    . "$PROJECT_ROOT/pmoves/scripts/pm-cipher-token-bind.sh"
    pm_cipher_token_bind "$PROJECT_ROOT" "${PM_IDENT_CIPHER_ID:-}" || true
    echo "[kimi-pmoves] ${PM_CARRY_BIND_LINE}" >&2
  fi
  if [ -f "$PROJECT_ROOT/pmoves/scripts/pm-cipher-identity.sh" ]; then
    # shellcheck source=./pm-cipher-identity.sh
    . "$PROJECT_ROOT/pmoves/scripts/pm-cipher-identity.sh"
    pm_cipher_identity "$PROJECT_ROOT" "${PM_IDENT_CIPHER_ID:-${PMOVES_NODE_IDENTITY:-}}" ${PM_IDENT_PY[@]+"${PM_IDENT_PY[@]}"} || true
    echo "[kimi-pmoves] ${PM_CARRY_LINE}" >&2
  fi
fi

# Bind the session to this checkout. Kimi Code finds its project layer
# (<git root>/.mcp.json, AGENTS.md) and keys "continue" by cwd, so a launch from a sibling
# checkout ran against THAT checkout's files. A cwd inside this checkout
# (including .claude/worktrees/*) is kept; PMOVES_LAUNCH_KEEP_CWD=1 keeps any.
# pm-cwd-bind: this block is an inline TWIN of the one in kilo-pmoves.sh --
# deliberately not a sourced fragment, so the binding holds on a checkout with
# no fragments at all. test_kimi_kilo_launchers.py asserts the two blocks are
# byte-identical modulo the launcher tag; edit both or the test fails.
ROOT_P="$(CDPATH='' cd -P -- "$PROJECT_ROOT" && pwd)" || exit 1
HERE_P="$(pwd -P)"
case "$HERE_P/" in
  "$ROOT_P"/*) ;;
  *)
    if [ -z "${PMOVES_LAUNCH_KEEP_CWD:-}" ]; then
      cd -- "$ROOT_P" || exit 1
      echo "[kimi-pmoves] cwd=$ROOT_P (was $HERE_P, outside this checkout; PMOVES_LAUNCH_KEEP_CWD=1 keeps it)" >&2
    fi
    ;;
esac

if ! command -v kimi >/dev/null 2>&1; then
  echo "[!] kimi not found on PATH. Install Kimi Code (https://moonshotai.github.io/kimi-code/)."
  exit 127
fi

CONFIG="$PROJECT_ROOT/.kimi/config.toml"
MCP_CONFIG="$PROJECT_ROOT/.kimi/mcp.json"

# Which program is this? Ask its --help ONCE and keep the answer. The match is
# anchored to a flag-DEFINITION line (`--config-file` at the start of a line,
# optionally after a short flag), not to the string appearing anywhere: a
# deprecation note or an example mentioning the flag must not flip this to the
# legacy path and resurrect `unknown option '--config-file'`. Empty or failed
# --help is an explicit refusal, not a silent fall-through into either branch.
KIMI_HELP="$(kimi --help 2>&1 || true)"
if [ -z "$KIMI_HELP" ]; then
  echo "[!] 'kimi --help' printed nothing, so this launcher cannot tell Kimi Code from the legacy kimi-cli ($(command -v kimi)). Not guessing: run 'kimi --help' yourself and fix the install." >&2
  exit 1
fi
if ! printf '%s\n' "$KIMI_HELP" | grep -Eq -- '^[[:space:]]*(-[A-Za-z][[:space:]]*,[[:space:]]*)?--config-file([[:space:]=,]|$)'; then
  # Kimi Code. Its config is user-level; the .kimi/ files are kimi-cli
  # formats it does not read, so say where config really comes from.
  echo "[kimi-pmoves] $(command -v kimi): Kimi Code -- config from ${KIMI_CODE_HOME:-$HOME/.kimi-code}/{config.toml,mcp.json} + $PROJECT_ROOT/.mcp.json; .kimi/config.toml and .kimi/mcp.json are legacy kimi-cli files and are not loaded" >&2
  exec kimi "$@"
fi

if [ ! -f "$CONFIG" ]; then
  echo "[!] Kimi config not found: $CONFIG"
  echo "    Run 'make -C pmoves env-setup' to generate it."
  exit 1
fi

if [ -f "$MCP_CONFIG" ]; then
  exec kimi --config-file "$CONFIG" --mcp-config-file "$MCP_CONFIG" "$@"
else
  echo "[!] Warning: $MCP_CONFIG not found; launching Kimi without MCP config."
  echo "    Cipher and Agent Zero MCP servers will not be available."
  exec kimi --config-file "$CONFIG" "$@"
fi
