#!/usr/bin/env python3
"""Report whether THIS session can actually authenticate its MCP roster.

WHY THIS EXISTS, and why `launcher-check` does not cover it.

`launcher-check` (added 2026-08-30, PR #2846) asks "does `claude-pmoves`
resolve on this host". That is a question about the INSTALLER. It cannot see
the failure it was written to prevent, because a launcher can be perfectly
installed and simply not used -- you start `claude` out of habit, or a tool
spawns it, or you reattach to a shell that predates the install.

Measured on Z890, 2026-08-31, both at the same moment:

    launcher-check           OK - C:\\Users\\...\\.local\\bin\\claude-pmoves.bat
    session process env      CIPHER_API_TOKEN unset, SUPABASE_SERVICE_KEY unset,
                             POSTGRES_PASSWORD unset, GROQ_API_KEY unset
    cipher /mcp/sse          Bearer ''  -> 401     (container HAS a token set)

So the check passed and the roster was dark anyway. The two questions are
different and only one of them is about this session.

WHAT MAKES THIS NEWLY LOAD-BEARING. Until a node's cipher container has a
token configured, an empty bearer is ACCEPTED (measured 200 on the 4090), so a
launcher-less session degrades invisibly but still works. Once the token is
set -- which is the correct posture, and now the posture on Z890 -- the same
empty bearer is REJECTED. Hardening a node converts a silent degradation into
a hard 401. That is the right trade, but it means "did this session load the
environment" stops being cosmetic.

WHAT THIS DOES NOT DO. It does not read the shared env file, contact any
service, or print a single value. It reports NAMES and set/unset, nothing else
-- the whole point is that it must be safe to run inside an agent transcript,
which is exactly where the failure shows up.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ${VAR} and ${VAR:-fallback}. The second group is present only when a default
# was supplied, which is the distinction that decides severity below.
_REF = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(:-[^}]*)?\}")

# Not a credential, and not supplied the way the others are. Listing it as
# "missing" would bury the real rows in noise.
_IGNORE = {"VAR"}


def _refs(node) -> set:
    """Collect (var, has_default) over an arbitrary JSON subtree."""
    found = set()
    if isinstance(node, str):
        for m in _REF.finditer(node):
            if m.group(1) not in _IGNORE:
                found.add((m.group(1), m.group(2) is not None))
    elif isinstance(node, dict):
        for k, v in node.items():
            # Skip prose. `_note` fields in this roster are long-form measurement
            # records that quote ${VAR} spellings as EXAMPLES; counting those as
            # live references would invent dependencies that do not exist.
            if isinstance(k, str) and k.startswith("_"):
                continue
            found |= _refs(v)
    elif isinstance(node, list):
        for v in node:
            found |= _refs(v)
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description="MCP roster session preflight")
    ap.add_argument("--roster", default=None, help="path to mcp.json")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero when any server would start unauthenticated",
    )
    args = ap.parse_args()

    # Emit ASCII only. A previous tool in this repo died with UnicodeEncodeError
    # on a cp1252 console; a diagnostic that crashes on the platform it
    # diagnoses is worse than no diagnostic.
    try:
        sys.stdout.reconfigure(errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    root = Path(__file__).resolve().parents[2]
    roster = Path(args.roster) if args.roster else root / ".claude" / "mcp.json"

    print("session-check: can THIS process authenticate the MCP roster?")
    print()

    marker = os.environ.get("PMOVES_LAUNCHER_SESSION")
    if marker:
        print("  launcher   this session came through: %s" % marker)
    else:
        print("  launcher   NO MARKER - this session did not come through claude-pmoves")
        print("             (a launcher can be installed and still not be used;")
        print("              'make -C pmoves launcher-check' cannot see this)")
    print()

    if not roster.is_file():
        print("  roster     NOT FOUND at %s" % roster)
        print("             nothing to check; pass --roster if it lives elsewhere")
        return 0

    try:
        data = json.loads(roster.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print("  roster     UNREADABLE at %s: %s" % (roster, exc))
        return 0

    servers = data.get("mcpServers", {})
    if not isinstance(servers, dict) or not servers:
        print("  roster     no mcpServers declared in %s" % roster)
        return 0

    hard = []
    soft = []
    ok = []

    # A `_`-prefixed key under mcpServers is a DISABLED entry, not a live one --
    # the roster's existing convention for retiring a server without deleting
    # its configuration (`_pmoves-cipher-legacy-python-wrapper` is the current
    # instance). Reporting one as degraded would tell an operator to go supply
    # credentials for something deliberately switched off.
    #
    # Caught by testing, not by reading: the first version counted 20 servers
    # where PR #2846 measured 19, and the difference was exactly this key. The
    # `_` skip inside _refs() does not cover it, because that guard walks the
    # values and this loop names the servers.
    names = [n for n in sorted(servers) if not n.startswith("_")]

    for name in names:
        needed = _refs(servers[name])
        if not needed:
            ok.append(name)
            continue
        missing_hard = sorted(v for v, d in needed if not d and not os.environ.get(v))
        missing_soft = sorted(v for v, d in needed if d and not os.environ.get(v))
        if missing_hard:
            hard.append((name, missing_hard))
        elif missing_soft:
            soft.append((name, missing_soft))
        else:
            ok.append(name)

    print("  roster     %s" % roster)
    print("             %d servers declared" % len(names))
    print()

    if hard:
        print("  UNSET, no fallback -- the literal '${VAR}' text goes on the wire.")
        print("  Claude Code substitutes nothing and warns; the server sees garbage.")
        for name, vs in hard:
            print("    x %-28s %s" % (name, ", ".join(vs)))
        print()

    if soft:
        print("  UNSET, ':-' fallback -- expands EMPTY, so the request is made")
        print("  unauthenticated. Accepted by a service with no token configured,")
        print("  rejected (401) by one that has a token. Node-dependent.")
        for name, vs in soft:
            print("    ! %-28s %s" % (name, ", ".join(vs)))
        print()

    if not hard and not soft:
        print("  OK         every declared server has the variables it references.")
        print()
        return 0

    print("  %d server(s) need no environment and are unaffected." % len(ok))
    print()
    print("  Remedy: start the session through the launcher, which loads the")
    print("  shared env file into the process environment:")
    print("      claude-pmoves            (install: make -C pmoves launcher-install)")
    print("  Restarting the session is required -- a child shell cannot")
    print("  retroactively add variables to an already-running parent process.")

    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
