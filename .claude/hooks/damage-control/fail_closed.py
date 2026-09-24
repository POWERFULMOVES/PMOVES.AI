"""Top-level fail-closed runner for the four damage-control hook entry points.

    if __name__ == "__main__":
        from fail_closed import run_fail_closed
        run_fail_closed(main, "PreToolUse")      # or "PostToolUse"

WHY (review of #3174, F1, confirmed): a corrupt grant-state cache made
known_roads raise OverflowError / RecursionError, the hook exited 1, and a
PreToolUse exit code other than 2 is NON-BLOCKING -- the protected edit went
ahead and no trail row was written. A guard that crashes open is the defect the
PR exists to remove, so no exception may leave a hook with any code but 0 or 2.

EXIT CODES, per Claude Code hook event
--------------------------------------
  PreToolUse    0  proceed (stdout JSON, e.g. permissionDecision "ask", is honoured)
                2  BLOCK; stderr is shown to the model; stdout JSON is ignored
                other  non-blocking error: the tool call PROCEEDS  <- fail-open
  PostToolUse   0  fine (stdout JSON honoured)
                2  the tool already ran, so nothing is blocked; stderr is FED BACK
                   to the model -- the loudest channel this event has
                other  non-blocking; stderr is shown to the user only

So for both events the fail-closed code is 2. For PreToolUse that blocks the
call. For PostToolUse (effect_check) it cannot un-run the command; it tells the
model that the command's effect on protected paths was NOT checked, which is the
most a post-hoc check can do. The message is worded for each event so neither
reader mistakes one for the other.

Deliberate exits keep their meaning: SystemExit(0) and SystemExit(2) pass through
unchanged. Any OTHER exit code -- including the pre-existing `sys.exit(1)` on
unreadable hook input in the three PreToolUse guards -- is itself a fail-open,
and is converted to 2 here rather than by editing each guard body.

RESIDUAL, stated: an exception raised while the hook MODULE IS IMPORTED (e.g. a
syntax error in known_roads.py) happens before this runner exists and still
exits 1. Covering that needs the harness command itself to map codes.

The message names the exception TYPE and the innermost file:line, never the
exception text: that text can carry file contents (a decode error quotes bytes).
"""
from __future__ import annotations

import os
import sys
import traceback
from typing import Callable, Optional


def _where(exc: BaseException) -> str:
    tb = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ else []
    if not tb:
        return "?"
    frame = tb[-1]
    return "%s:%s" % (os.path.basename(frame.filename), frame.lineno)


def _message(event: str, what: str) -> str:
    if event == "PostToolUse":
        return ("EFFECT-CHECK GUARD ERROR, refusing to report clean: %s. This "
                "command's effect on protected paths was NOT checked -- treat it as "
                "unverified and disclose it. See .claude/skills/known-roads/SKILL.md."
                % what)
    return ("SECURITY: damage-control guard error, refusing: %s. The guard could not "
            "decide, so the call is blocked (fail-closed). Report this; do not work "
            "around it." % what)


def run_fail_closed(main: Callable[[], Optional[int]], event: str) -> None:
    """Run `main`; exit 0 or 2 only. Never returns normally."""
    try:
        rc = main()
    except SystemExit as exc:
        code = exc.code
        if code in (None, 0):
            sys.exit(0)
        if code == 2:
            sys.exit(2)
        print(_message(event, "exited with code %r" % (code,)), file=sys.stderr)
        sys.exit(2)
    except BaseException as exc:  # noqa: BLE001 -- the whole point: nothing escapes open
        print(_message(event, "%s at %s" % (type(exc).__name__, _where(exc))),
              file=sys.stderr)
        sys.exit(2)
    sys.exit(0 if rc in (None, 0) else 2)
