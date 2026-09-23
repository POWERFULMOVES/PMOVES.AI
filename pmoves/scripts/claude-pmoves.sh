#!/usr/bin/env bash
# claude-pmoves — Bootstrap Claude Code with a PMOVES agent AND its MCP creds.
# ===========================================================================
# THIN DELEGATE. The real launcher is deploy/provision/claude-pmoves.sh, which
# loads pmoves/env.shared and passes the normalized MCP roster via
# --mcp-config=. This script only adds the positional-agent shorthand on top.
#
# WHY THE SPLIT EXISTED: these two files share a name but were never duplicates.
# This one selected an agent (`claude --agent`) and loaded nothing; the
# provisioning one loaded env.shared + the MCP roster and selected no agent.
# Each ended in its own `exec claude`, so they were mutually exclusive — you
# could have a PMOVES agent OR working MCP creds, never both. `make -C pmoves
# claude-pmoves` took this path, so the documented way to launch the delivery
# agent came up with every cred-dependent MCP empty.
#
# Delegating fixes that without changing either UI: the shorthand still works,
# and it now inherits env.shared + the roster.
#
# Usage: claude-pmoves [agent-name] [claude-args...]
# Default agent: node-steward (claims work, then spawns delivery agents)
# Other agents: control-agent, memory-agent, researcher, test-runner, pr-trimmer, verifier, code-review
#
# Examples:
#   claude-pmoves                          # node-steward (default)
#   claude-pmoves delivery-agent           # straight to execution
#   claude-pmoves control-agent            # review/gate agent
#   claude-pmoves memory-agent             # cipher memory agent
#   claude-pmoves test-runner --worktree   # test runner in worktree
#
# To launch with NO agent (plain Claude + PMOVES MCP), call the provisioning
# script directly: deploy/provision/claude-pmoves.sh
set -u

# ---------------------------------------------------------------------------
# REPO-ROOT RESOLUTION — keep byte-identical across the three launchers that
# carry it (deploy/provision/claude-pmoves.sh, deploy/provision/crush-pmoves.sh,
# this file). Enforced by deploy/provision/tests/test-launcher-root-resolution.sh,
# which fails if one is fixed and the others are not.
#
# WHY THE WALK: taking dirname of a PATH symlink instead of the real file makes
# ROOT=$HOME, so the delegate cannot find the real launcher and degrades to
# `claude --agent` with no creds — the silent-credless class this file exists to
# close.
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

LAUNCHER="$ROOT/deploy/provision/claude-pmoves.sh"

# DEFAULT AGENT: node-steward, not delivery-agent.
#
# The old default made every node session an execution body with no node context
# and no claim discipline. A B850 session on 2026-08-23 ran that way to
# completion -- eight PRs and three live DB mutations on the data-tier host, all
# unclaimed -- and the register recorded nobody as having been there. An agent
# that starts holding Edit will edit; the steward is denied Write/Edit and spawns
# delivery agents instead. See .claude/agents/node-steward.md.
#
# Overridable: `claude-pmoves delivery-agent` still gets the old behaviour, and
# PMOVES_DEFAULT_AGENT sets it per node without editing this file.
#
# Falls back to delivery-agent if the steward definition is absent, so a node on
# an older checkout keeps working rather than launching with --agent pointed at
# nothing.
DEFAULT_AGENT="${PMOVES_DEFAULT_AGENT:-node-steward}"
if [ ! -f "$ROOT/.claude/agents/$DEFAULT_AGENT.md" ]; then
  DEFAULT_AGENT="delivery-agent"
fi
# Only treat $1 as an agent NAME if it is not a flag. The previous form,
# AGENT="${1:-delivery-agent}", consumed anything: `claude-pmoves --print ping`
# silently launched with `--agent --print`, which claude rejects or misreads.
# A leading `-` now means "no agent named, these are claude's args".
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then
  AGENT="$1"
  shift
else
  AGENT="$DEFAULT_AGENT"
fi

# ---------------------------------------------------------------------------
# NODE IDENTITY — the half the agent selection above does not answer.
#
# `--agent node-steward` says what this session DOES. It says nothing about
# which node it is on or which registered agent it IS, so every session began
# by rediscovering both. `topology.node_affinity` in agent_registry.yaml was
# written for exactly this and nothing read it.
#
# Resolution is declared, not inferred: eight registry agents claim the 4090
# under one spelling or another, so "the agent whose affinity matches" would be
# a guess wearing a resolver's clothes. See pmoves/tools/node_identity.py.
#
# FAIL-OPEN, LOUDLY. Every failure here -- no python, no config, unknown node,
# identity declared but not yet registered -- leaves the session launching
# exactly as it did before, and prints why. An identity is a convenience;
# losing it must never cost you the launch. Losing it SILENTLY is the defect
# this file keeps having to fix, so the reason is always printed.
# ---------------------------------------------------------------------------
# Resolution moved to the shared fragment (2026-09-16). It was ~35 lines here and
# again in crush-pmoves, and nowhere in the other seven launchers -- the same
# shape pm-python.sh and pm-cipher-identity.sh were extracted for. The behaviour
# is unchanged: same tool, same --harness, same settings.local.json read, same
# fail-open-loudly rule. See pmoves/scripts/pm-node-identity.sh.
# shellcheck source=./pm-node-identity.sh
. "$ROOT/pmoves/scripts/pm-node-identity.sh"
pm_node_identity "$ROOT" claude-code claude-pmoves || true
IDENT_PY=(${PM_IDENT_PY[@]+"${PM_IDENT_PY[@]}"})
echo "${PM_IDENT_LINE}" >&2
# Cipher refuses every call without an `agentId`, and refuses a wrong one under
# token enforcement, so a session that is not told the spelling cannot use
# persistent memory at all. It rides in the same accumulated prompt -- a fourth
# flag would have cancelled the three above it.
if [ -n "${PM_IDENT_CIPHER_ID:-}" ]; then
  pm_ident_append "When calling the Cipher MCP tools, pass agentId '${PM_IDENT_CIPHER_ID}'. It is REQUIRED on every call and is the signing-card spelling from pmoves/config/signing_identity_cards.yaml -- not your registry identity, which cipher refuses."
else
  pm_ident_append "You have NO declared Cipher agentId this session. Cipher requires one on every call, so declare it per call and say that you are doing so. Reason: ${PM_IDENT_CIPHER_WHY:-not measured}"
fi

if [ "${PM_IDENT_OK:-0}" = "1" ]; then
  # Put it where the session can actually READ it. Exported variables do not
  # reach the model's context; an appended system prompt does. This is the
  # difference between the identity existing and the identity working.
  pm_ident_append "You are running on PMOVES node '${PMOVES_NODE}'. Your registered identity in pmoves/config/agent_registry.yaml is '${PMOVES_NODE_IDENTITY}'. Disclose it at session start rather than rediscovering it. Your selected role for this session is the '${AGENT}' agent."
fi

# CIPHER TOKEN BIND — the handoff the carry check could only report as missing.
#
# pm-cipher-identity.sh measures which agent_id writes will carry; until the
# minted per-agent token is bound into the session env, the answer stays
# 'bootstrap' no matter what the model declares. Bind BEFORE the preflight and
# the carry measurement so both report the post-bind reality, and export the
# agentId so the inner launcher (deploy/provision/claude-pmoves.sh) can re-bind
# after it sources env.shared — which would otherwise clobber this with the
# node bootstrap token before the roster is normalized.
if [ -f "$ROOT/pmoves/scripts/pm-cipher-token-bind.sh" ]; then
  # shellcheck source=./pm-cipher-token-bind.sh
  . "$ROOT/pmoves/scripts/pm-cipher-token-bind.sh"
  pm_cipher_token_bind "$ROOT" "${PM_IDENT_CIPHER_ID:-}" || true
  echo "[claude-pmoves] ${PM_CARRY_BIND_LINE}" >&2
  export PM_IDENT_CIPHER_ID
fi

# CIPHER — persistent memory. Same reasoning as the identity block above: the
# agent has to be TOLD, in context, whether it has memory. An MCP server that
# never connects contributes no tools, so a session with no memory looks exactly
# like a session with memory and nothing to recall. That is the silent failure
# this check exists to end.
#
# It reports WHICH endpoint answered, not merely that one did. The roster
# carries a fleet cipher (${TS_Z890}) and a local one, and #2792 exists because
# it once carried only the fleet entry -- "memory that silently wasn't there"
# whenever Z890 was unreachable. "Memory is up" must not quietly mean "someone
# else's memory is up".
#
# NEVER blocks: a session without memory is degraded, not unusable, and refusing
# to launch would be worse than launching informed.
CIPHER_TOOL="$ROOT/pmoves/tools/cipher_preflight.py"
if [ -f "$CIPHER_TOOL" ] && [ ${#IDENT_PY[@]} -gt 0 ]; then
  CIPHER_OUT=""
  set +e
  CIPHER_OUT="$("${IDENT_PY[@]}" "$CIPHER_TOOL" 2>&1)"
  cipher_rc=$?
  set -e
  case "$cipher_rc" in
    0)
      CIPHER_WHICH="$(printf '%s\n' "$CIPHER_OUT" | awk '/^cipher OK/ {print $3; exit}')"
      echo "[claude-pmoves] cipher=up (${CIPHER_WHICH:-unknown endpoint})" >&2
      pm_ident_append "Persistent memory IS available this session via the Cipher MCP server '${CIPHER_WHICH:-unknown}'. Use it for recall and for writes; do not fall back to the auto-memory directory while it is up."
      ;;
    1)
      # FINDINGS: something ANSWERED and was not usable. Cipher is UP either
      # way, so "no persistent memory, Cipher is down" stays wrong here -- that
      # false negative is what the wildcard branch used to emit for every
      # non-zero code, and it sends the operator to restart a healthy service.
      #
      # But exit 1 is NOT synonymous with 401. `http_error` (a 404) and
      # `redirect` (a refused 302) also land on 1, and hardcoding "bind
      # CIPHER_API_TOKEN" tells an operator staring at a 404 to fix a
      # credential that was never the problem -- the same collapse of distinct
      # verdicts into one remedy, just moved up a layer.
      #
      # So branch on the verdict the tool actually reported. The second token
      # of each row IS the verdict class (OK / UNAUTHORIZED / ANSWERED / DOWN),
      # emitted from `row["verdict"]` in cipher_preflight.py. Matched with
      # `case`, not `grep`: errexit is live from the `set -e` above and a pipe
      # into `grep -q` can also lose to SIGPIPE.
      case "$CIPHER_OUT" in
        *"cipher UNAUTHORIZED"*)
          echo "[claude-pmoves] cipher=UNAUTHORIZED (exit 1) — service is UP, credential not accepted" >&2
          pm_ident_append "Cipher ANSWERED this session but refused the credential (preflight exit 1, verdict unauthorized), so persistent memory is not usable right now. The service is UP -- this is an access problem, not an outage, so do NOT report Cipher as down and do not restart it. Use the file-based auto-memory directory meanwhile and say which of the two it is. Remedy: bind CIPHER_API_TOKEN into the roster. Recovery: pmoves/docs/operations/MCP_TOOLKIT.md."
          ;;
        *)
          echo "[claude-pmoves] cipher=ANSWERED-UNUSABLE (exit 1) — something is listening; see the status below" >&2
          pm_ident_append "Cipher ANSWERED this session but not usably (preflight exit 1, and NOT a 401/403 -- read the status printed above, e.g. an HTTP error or a refused redirect), so persistent memory is not usable right now. Something IS listening on that endpoint, so do NOT report Cipher as simply down, and do NOT assume the credential is at fault -- the preflight would have said unauthorized if it were. Use the file-based auto-memory directory meanwhile and say which of the two it is. Recovery: pmoves/docs/operations/MCP_TOOLKIT.md."
          ;;
      esac
      printf '%s\n' "$CIPHER_OUT" >&2
      ;;
    *)
      # 3 = could not measure: no cipher entry in the roster, nothing
      # resolvable, nothing reachable at all, or the check itself crashed.
      # This is the only case where "you have no memory" is a true statement.
      #
      # A crash belongs HERE and not in the exit-1 branch above. Python exits 1
      # on an uncaught exception, so before cipher_preflight.py grew its own
      # backstop, a schemeless roster url or a failed import landed on "the
      # service is UP, do not restart it" -- a health assertion from a run that
      # contacted nothing.
      echo "[claude-pmoves] cipher=DOWN (exit ${cipher_rc}) — session has no persistent memory" >&2
      printf '%s\n' "$CIPHER_OUT" >&2
      pm_ident_append "Cipher is NOT reachable this session (preflight exit ${cipher_rc}), so you have NO persistent memory. Say so at session start rather than recalling nothing silently, and use the file-based auto-memory directory instead. Recovery: pmoves/docs/operations/MCP_TOOLKIT.md."
      ;;
  esac
fi

# IDENTITY CARRY — the join the two blocks above never made.
#
# The identity block tells the model it is 'z890-claude'. The cipher block tells
# it memory is up. Neither says which agent_id those memories are FILED under,
# and the answer has been 'bootstrap' on every node since per-agent tokens
# shipped: auth.ts:46 @ e24f1323 forks on a 'cipher_' prefix and nothing in this
# repo ever checked it. So a session is told it is one agent and writes as
# another, with no line of output disagreeing.
#
# bootstrap is not an agent. It is the single-token launch path whose whole
# purpose is to hand off to a minted one, and the handoff has never been wired.
# This does not wire it — a token cannot be minted from a launcher without
# putting a secret through a shell. It ENDS THE SILENCE.
#
# The measurement lives in pm-cipher-identity.sh, not inline here, so the other
# seven launchers get the same sentence instead of seven drifting copies. See
# that file's header for why (same reason pm-python.sh exists).
# shellcheck source=./pm-cipher-identity.sh
. "$ROOT/pmoves/scripts/pm-cipher-identity.sh"
# PM_IDENT_CIPHER_ID, not PMOVES_NODE_IDENTITY: cipher keys on the signing-card
# spelling, and handing it the registry one made this very check report `signing
# card: no` on every node. It falls back to the registry identity where no
# agentId is declared, so nothing that measures today stops measuring.
pm_cipher_identity "$ROOT" "${PM_IDENT_CIPHER_ID:-${PMOVES_NODE_IDENTITY:-}}" ${IDENT_PY[@]+"${IDENT_PY[@]}"} || true
# Printed on EVERY path, including the ones that could not measure: a node with
# no PyYAML must not look identical to a node whose carry is fine.
echo "[claude-pmoves] ${PM_CARRY_LINE}" >&2
if [ -n "${PM_CARRY_PROMPT:-}" ]; then
  pm_ident_append "$PM_CARRY_PROMPT"
fi

# ONE FLAG, COMPOSED ONCE. Every block above called pm_ident_append, which
# concatenates; none of them pushed a flag of its own. `claude
# --append-system-prompt` keeps only its LAST occurrence, so the multi-flag form
# this file used to build handed the model the cipher-carry sentence and
# silently discarded the node identity resolved a hundred lines earlier. See
# pm-node-identity.sh for the measurement.
pm_ident_prompt_args
IDENTITY_ARGS=(${PM_IDENT_PROMPT_ARGS[@]+"${PM_IDENT_PROMPT_ARGS[@]}"})

if [ ! -f "$LAUNCHER" ]; then
  # Degrade to the pre-delegation behavior rather than failing: the agent still
  # loads, MCP creds do not. Warn so the missing half is visible, not silent.
  echo "[claude-pmoves] WARN: $LAUNCHER not found — launching without env.shared or the MCP roster." >&2
  exec claude --agent "$AGENT" ${IDENTITY_ARGS[@]+"${IDENTITY_ARGS[@]}"} "$@"
fi

# The launcher forwards "$@" straight to claude after --mcp-config=, so --agent
# rides through unchanged.
exec bash "$LAUNCHER" --agent "$AGENT" ${IDENTITY_ARGS[@]+"${IDENTITY_ARGS[@]}"} "$@"
