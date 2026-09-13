#!/usr/bin/env bash
# pm-cipher-identity.sh — the ONE identity-carry measurement, sourced by every
# PMOVES launcher that puts an agent in front of cipher memory.
#
# WHY A SHARED FRAGMENT AND NOT A COPIED BLOCK
# --------------------------------------------
# The carry verdict shipped in claude-pmoves.sh as 36 inline lines. There are
# eight launchers on this fleet -- claude, crush, kimi, kilo, codex, hermes, plus
# the deploy/provision delegates and their .ps1/.cmd twins -- and copying a block
# into eight files is how the launcher family got its last three defects:
#
#   * three conventions for "find python", two of them in ONE file (#2769)
#   * a root-resolution walk fixed in one launcher and not the others, which is
#     why deploy/provision/tests/test-launcher-root-resolution.sh exists
#   * a pm_pick_python fix landed for crush-pmoves (#2763) that claude-pmoves
#     then still carried in the broken form
#
# pm-python.sh is the answer the repo already reached for that class. This is
# the same shape, for the same reason. A node's agent should not learn whether
# its memories are its own based on which harness it happened to launch.
#
# THE CONTRACT
# ------------
# pm_cipher_identity <repo_root> <agent_id> [python argv...]
#
#   returns 0  a verdict was measured; PM_CARRY_* are set
#   returns 1  could not measure; PM_CARRY_LINE says WHY, and the caller must
#              still print it
#
# On return, ALWAYS set:
#   PM_CARRY_LINE    one line for stderr, already prefixed by the caller's name
#   PM_CARRY_WHY     the reason, verbatim from the tool or from the skip
#   PM_CARRY_ID      the agent_id writes will carry ('' if unmeasurable)
#   PM_CARRY_PROMPT  context text for harnesses that can append one ('' if none)
#   PM_CARRY_OK      1 when the carry is intact, 0 otherwise
#
# NEVER: prints, exports, logs, or reads past the prefix of a bearer token. The
# tool it calls is pure; this wrapper adds no I/O of its own beyond the verdict.
#
# ALWAYS LOUD ON SKIP. The inline version guarded on three conditions with no
# else, so a node with no PyYAML, or an unresolved identity, produced NOTHING --
# indistinguishable from a node whose carry is fine. That is precisely the defect
# the block was written to end, reintroduced by the block itself. Every path out
# of this function sets PM_CARRY_LINE.

pm_cipher_identity() {
  local root="${1:-}" agent="${2:-}"
  shift 2 2>/dev/null || true
  local py=("$@")

  PM_CARRY_LINE=""
  PM_CARRY_WHY=""
  PM_CARRY_ID=""
  PM_CARRY_PROMPT=""
  PM_CARRY_OK=0

  local tool="$root/pmoves/tools/cipher_identity.py"

  if [ ! -f "$tool" ]; then
    # A checkout too old to contain the tool cannot report the carry. Say the
    # version, not just the absence: "protection is inversely correlated with
    # drift" is only actionable if the operator learns which side they are on.
    PM_CARRY_WHY="cipher_identity.py not present in this checkout (pull main)"
    PM_CARRY_LINE="cipher identity=unmeasured — ${PM_CARRY_WHY}"
    return 1
  fi
  if [ ${#py[@]} -eq 0 ]; then
    PM_CARRY_WHY="no usable python (pm_pick_python yaml found none)"
    PM_CARRY_LINE="cipher identity=unmeasured — ${PM_CARRY_WHY}"
    return 1
  fi
  if [ -z "$agent" ]; then
    PM_CARRY_WHY="node identity unresolved, so there is nothing to compare the token against"
    PM_CARRY_LINE="cipher identity=unmeasured — ${PM_CARRY_WHY}"
    return 1
  fi

  # `|| rc=$?` rather than a set +e/set -e sandwich: the launchers run under
  # `set -u` and NOT `set -e`, so a bare `set -e` would enable errexit for
  # everything after the call. A `||` list reads the code under either setting.
  local out="" rc=0
  out="$("${py[@]}" "$tool" --agent "$agent" --shell 2>/dev/null)" || rc=$?

  if [ -z "$out" ]; then
    PM_CARRY_WHY="cipher_identity.py produced no output (exit ${rc})"
    PM_CARRY_LINE="cipher identity=unmeasured — ${PM_CARRY_WHY}"
    return 1
  fi

  eval "$out"
  PM_CARRY_ID="${PMOVES_CIPHER_EFFECTIVE_ID:-}"
  PM_CARRY_WHY="${PMOVES_CIPHER_WHY:-no reason emitted}"

  if [ "$rc" = "0" ]; then
    PM_CARRY_OK=1
    PM_CARRY_LINE="cipher identity=${PM_CARRY_ID} (carry intact)"
    PM_CARRY_PROMPT="Your cipher memory writes are attributed to agent_id '${PM_CARRY_ID}', which matches your registered identity. Recall and writes are yours."
  else
    PM_CARRY_OK=0
    PM_CARRY_LINE="cipher identity=${PM_CARRY_ID:-advisory} — CARRY GAP: ${PM_CARRY_WHY}"
    PM_CARRY_PROMPT="IDENTITY CARRY GAP: you are '${agent}', but cipher will attribute your memory writes to '${PM_CARRY_ID:-an advisory id you declare per call}' — not to you. Reason: ${PM_CARRY_WHY} Treat anything you recall as possibly another agent's, say so when it matters, and do not claim a memory as your own on the strength of finding it. Road to close it: make -C pmoves cipher-identity."
  fi
  return 0
}
