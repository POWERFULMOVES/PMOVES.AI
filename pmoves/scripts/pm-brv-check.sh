#!/usr/bin/env bash
# pm-brv-check.sh — say, loudly and once, when the ByteRover CLI is missing.
# ===========================================================================
# WHY THIS EXISTS
# ---------------
# `brv` (npm package `byterover-cli`, the upstream of the Pmoves-cipher fork)
# is the context-tree memory CLI: `brv-query` / `brv-curate` operate on the
# per-repo context tree (pmoves/docs/TAC/TAC_CIPHER.md, "Memory data model
# (upstream)"). Measured 2026-10-08 on knuckles: `command -v brv` printed
# nothing, and no launcher said so. A session on that node had no context-tree
# memory and nothing in its output distinguished that from "the tree is empty"
# -- the same silent-absence shape the cipher preflight exists to end.
#
# THE CONTRACT
# ------------
# pm_brv_check
#
#   ALWAYS returns 0. A missing brv costs the context tree, not the session,
#   so this is fail-open (same doctrine as pm-node-identity.sh: "losing it
#   must never cost you the launch"). Loud, never silent.
#
# On return, ALWAYS set:
#   PM_BRV_OK      1 when `brv` resolves on PATH, else 0
#   PM_BRV_LINE    one line for stderr, already prefixed by the caller
#   PM_BRV_PROMPT  a sentence for the session prompt when brv is MISSING,
#                  empty otherwise. stderr scrolls away before the TUI paints,
#                  so the caller should hand this to pm_ident_append too --
#                  the prompt is the channel the model actually reads.
#
# INSTALL ROUTE
# -------------
# Kept identical to `host_clis.brv.install.linux` in pmoves/configs/cli_tools.yaml
# (pmoves/tests/test_pm_brv_check.py pins the two together). It is a USER-level
# npm global -- under fnm/nvm the prefix is in $HOME, so no sudo -- and the
# version is not checked here: `make -C pmoves cli-check` reports versions.

PM_BRV_INSTALL_HINT="npm install -g byterover-cli"

pm_brv_check() {
  PM_BRV_OK=0
  PM_BRV_LINE=""
  PM_BRV_PROMPT=""

  local brv_path
  brv_path="$(command -v brv 2>/dev/null)" || brv_path=""

  if [ -n "$brv_path" ]; then
    PM_BRV_OK=1
    PM_BRV_LINE="brv=present (${brv_path})"
    return 0
  fi

  PM_BRV_LINE="WARN: brv=MISSING -- ByteRover CLI not on PATH, so this session has NO context-tree memory (brv-query/brv-curate). Install (user-level, no sudo): ${PM_BRV_INSTALL_HINT}  then: make -C pmoves cli-check"
  PM_BRV_PROMPT="The ByteRover CLI (brv) is NOT installed on this node, so context-tree memory (brv-query / brv-curate) is unavailable this session. Say so at session start rather than reporting an empty tree. Install route: ${PM_BRV_INSTALL_HINT} (user-level npm global, no sudo)."
  return 0
}
