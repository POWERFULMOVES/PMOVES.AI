# shellcheck shell=bash
# pm-launch-cwd.sh -- bind a harness session to the launcher's own checkout.
#
# Sourced by pmoves/scripts/{kimi,kilo}-pmoves.sh. Not executable on its own.
#
# WHY: kimi and kilo resolve their project layer from the WORKING DIRECTORY,
# not from any flag -- Kimi Code reads <git root>/.mcp.json and
# <cwd>/.kimi-code/, kilo reads <git root>/kilo.json, and both key their
# session history ("continue the previous session") by cwd. The launchers
# never changed directory, so a session started from a sibling checkout ran
# against THAT checkout's files while the launcher's banner described this
# one. A stale sibling checkout far behind main is exactly what SPARK-KIMI
# was found running against.
#
# RULE: a cwd inside the launcher's checkout (including its
# .claude/worktrees/*) is kept, so subdirectory and worktree work is
# unchanged. A cwd anywhere else is replaced by the checkout root, loudly.
# PMOVES_LAUNCH_KEEP_CWD=1 keeps the caller's cwd regardless.
#
# Sets PM_LAUNCH_CWD_LINE. Returns non-zero only if the root cannot be entered.

pm_launch_cwd() {
  local root="$1" tag="$2" here root_p
  here="$(pwd -P)"
  if ! root_p="$(CDPATH='' cd -P -- "$root" 2>/dev/null && pwd)"; then
    PM_LAUNCH_CWD_LINE="[$tag] ERROR: cannot enter checkout root: $root"
    return 1
  fi
  if [ -n "${PMOVES_LAUNCH_KEEP_CWD:-}" ]; then
    PM_LAUNCH_CWD_LINE="[$tag] cwd=$here (kept: PMOVES_LAUNCH_KEEP_CWD is set)"
    return 0
  fi
  case "$here/" in
    "$root_p"/*)
      PM_LAUNCH_CWD_LINE="[$tag] cwd=$here"
      return 0
      ;;
  esac
  cd -- "$root_p" || {
    PM_LAUNCH_CWD_LINE="[$tag] ERROR: cannot enter checkout root: $root_p"
    return 1
  }
  PM_LAUNCH_CWD_LINE="[$tag] cwd=$root_p (was $here -- outside this checkout; set PMOVES_LAUNCH_KEEP_CWD=1 to keep it)"
}
