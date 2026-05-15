#!/usr/bin/env python3
"""known-roads-enforcer.py — PreToolUse (Bash matcher) governance hook.

Nudges users toward PMOVES "Known Roads" Make targets when they reach for
raw `docker compose up|restart|down`. The Make wrappers (e.g. `make -C pmoves
up-<tier>`) layer tier-aware env loading, profile selection, and audit
breadcrumbs that the raw compose verbs skip.

OPT-IN: not wired by default. Operator activates via PreToolUse "Bash"
matcher in .claude/settings.json.

Exit codes:
  0  allow
  2  block (stderr fed back to Claude)
"""

import json
import re
import sys

# Raw `docker compose <verb>` — only the lifecycle-changing verbs.
RAW_COMPOSE = re.compile(r'docker[\s]+compose[\s]+(up|restart|down)\b')
# If the command is wrapped by `make -C pmoves ...`, the Make layer is in charge — allow.
MAKE_WRAPPER = re.compile(r'make[\s]+-C[\s]+pmoves\b')


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)  # never block on malformed harness input

    if payload.get("tool_name") != "Bash":
        sys.exit(0)
    command = (payload.get("tool_input") or {}).get("command", "") or ""

    if RAW_COMPOSE.search(command) and not MAKE_WRAPPER.search(command):
        sys.stderr.write(
            "known-roads-enforcer: raw `docker compose up|restart|down` detected.\n"
            "Use `make -C pmoves up-<tier>` (or the matching tier target) instead — "
            "see .claude/PATTERNS.md \xa7 Known Roads.\n"
        )
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
