#!/usr/bin/env bash
# tailscale-node-ips.sh — resolve TS_<NODE> variables from the live tailnet.
# ===========================================================================
# SOURCE this file; do not execute it. It exports, so a subshell is useless.
#
# WHY IT EXISTS: .claude/mcp.json and Crush's roster both address cross-node
# MCP servers as ${TS_Z890}, ${TS_SPARK}, and friends. Those names had exactly
# ONE definition in the repo — an inline block in pmoves/scripts/crush-env.sh —
# and that file is sourced only by the Crush launcher. Claude's launcher loads
# the shared env file, which does not carry them, so the same roster resolved
# under Crush and stayed literal under Claude: `http://${TS_Z890}:8105/mcp/sse`
# was handed to Claude Code as a hostname and cipher never connected.
#
# The addresses are 100.64/10 CGNAT and MUST stay runtime-derived. Baking one
# into the repo would leak topology into a public tree (there is a hook that
# blocks it) and would rot the moment a node re-registers.
#
# BEHAVIOUR NOTE: an already-set TS_* wins. The inline block this replaces
# exported unconditionally, clobbering an operator's explicit value. Nothing in
# the tree exports these before sourcing, so the normal path is unchanged; the
# difference is that a node without the tailscale CLI can now pre-set them, and
# the tests can drive this without a tailnet.
#
# THE KNOWN GAP RECORDED HERE IS NOW CLOSED, and this is that change. The case
# below read `pmoves-laptop`, which no peer has ever registered as — the 4090
# announces itself as `pmoves-4090` — so TS_4090 resolved to EMPTY on every node
# in the fleet.
#
# The previous author deferred it correctly: "correcting it changes which host
# an MCP server dials and belongs in its own change." This is that change.
#
# What made it expensive to leave: nothing failed. Consumers carry `:-` literal
# fallbacks (pmoves/config/profiles/z890-coordinator.yaml:57), so an empty
# TS_4090 silently became a hardcoded address instead of an error. A variable
# that resolves to a stale literal is worse than one that resolves to nothing —
# the second announces itself.
#
# Verified against the live tailnet, not inferred: `pmoves-laptop` does not
# resolve and appears in zero DNSNames; `pmoves-4090` resolves and answers.
# ===========================================================================

# Set VAR=value only when VAR is unset or empty.
_pm_ts_set() {
  local var="$1" val="$2"
  [ -n "$val" ] || return 0
  [ -n "${!var:-}" ] && return 0
  export "$var"="$val"
}

pmoves_resolve_tailscale_node_ips() {
  command -v tailscale >/dev/null 2>&1 || return 0
  local ip host
  while IFS=' ' read -r ip host; do
    case "$host" in
      pmoves-z890)     _pm_ts_set TS_Z890   "$ip" ;;
      pmoves-5090)     _pm_ts_set TS_5090   "$ip" ;;
      pmoves-4090)     _pm_ts_set TS_4090   "$ip" ;;
      pmoves-spark)    _pm_ts_set TS_SPARK  "$ip" ;;
      pmoves-b850-*)   _pm_ts_set TS_B850   "$ip" ;;
      pmoves-kvm4-1)   _pm_ts_set TS_KVM4_1 "$ip" ;;
      pmoves-kvm4-2)   _pm_ts_set TS_KVM4_2 "$ip" ;;
      pmoves-kvm2)     _pm_ts_set TS_KVM2   "$ip" ;;
    esac
  done < <(tailscale status 2>/dev/null | awk '{print $1" "$2}')
  return 0
}

pmoves_resolve_tailscale_node_ips
