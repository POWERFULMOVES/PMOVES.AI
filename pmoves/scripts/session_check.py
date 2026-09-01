#!/usr/bin/env python3
"""Report whether THIS session can actually authenticate its MCP roster.

WHY THIS EXISTS, and why `launcher-check` does not cover it.

`launcher-check` (added 2026-08-30, PR #2846) asks "does `claude-pmoves`
resolve on this host". That is a question about the INSTALLER. It cannot see
the failure it was written to prevent, because a launcher can be perfectly
installed and simply not used -- you start `claude` out of habit, or a tool
spawns it, or you reattach to a shell that predates the install.

Measured on Z890, 2026-08-31, both at the same moment:

    launcher-check           OK - <userprofile>/.local/bin/claude-pmoves.bat
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

TWO THINGS THIS DELIBERATELY DOES NOT DO ITS OWN WAY, both from Codex review
of the first draft:

  1. It does not implement its own ${VAR} expansion. `mcp_roster_normalize`
     already does exactly this for the launcher, with balanced-brace matching,
     nested `${A:-${B}}` defaults, and a tested refusal of the dangerous
     `${A-B}` spelling. A second implementation would drift, and the drift
     would be invisible: this tool exists to report on what the launcher
     loads, so any disagreement between the two is a wrong answer by
     construction. The first draft's regex could not parse the roster's own
     `${SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_SERVICE_KEY}}`.

  2. It does not assume the working tree is the roster. The launchers load
     `origin/main:.claude/mcp.json` unless PMOVES_ROSTER_FROM_TREE is set --
     PR #2847, after a wip branch on the 4090 served 14 servers where main has
     19. Reporting on the tree while Claude loads main's copy is the same
     class of defect as PRECHECK_PY probing one interpreter while make ran
     another: an instrument reporting on something other than what runs.

WHAT IT DOES NOT DO AT ALL. It does not read the shared env file, contact any
service, or print a single value. It reports NAMES and set/unset, nothing else
-- the whole point is that it must be safe to run inside an agent transcript,
which is exactly where the failure shows up.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[2]
sys.path.insert(0, str(_ROOT / "pmoves" / "tools"))

# `expand` is the launcher's own expander (public). `_match_brace` is private,
# and importing it is deliberate rather than sloppy: re-deriving brace matching
# here is precisely the divergence the reuse is meant to prevent, and a local
# copy would be the second implementation this module's docstring argues
# against. tests/test_session_check.py pins both behaviours so a change there
# cannot silently alter what this reports.
from mcp_roster_normalize import _match_brace, expand  # noqa: E402

# Roster fields that actually carry credentials or endpoints. Matches the
# normalizer's own _DROP_FIELDS + _WARN_FIELDS, plus the launch fields, so a
# reference buried in prose does not become a finding.
_SCAN_FIELDS = ("url", "headers", "env", "command", "args")


def _iter_refs(text: str):
    """Yield each literal ``${...}`` span in *text*, brace-balanced."""
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "$" and text[i + 1 : i + 2] == "{":
            end = _match_brace(text, i + 1)
            if end == -1:
                yield text[i:]
                return
            yield text[i : end + 1]
            i = end + 1
        else:
            i += 1


def _strings(node):
    """Every string in an arbitrary JSON subtree, skipping `_`-prefixed prose."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str) and k.startswith("_"):
                continue
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)


def classify(server: dict, environ) -> tuple[list[str], list[str]]:
    """Return (hard, soft) variable names for one server entry.

    hard -- the reference cannot resolve at all, so Claude Code warns and puts
            the literal ``${VAR}`` text on the wire.
    soft -- it resolves, but to the EMPTY string (``${VAR:-}``). The request is
            then made unauthenticated: accepted by a service with no token
            configured, 401 by one that has a token. Node-dependent, which is
            exactly why the 4090 and Z890 disagree about the same roster.

    The split matters because the remedies differ, and because `expand` alone
    cannot make it: a `:-` default that renders empty is a successful
    expansion by its rules, and correctly so -- for the launcher, which only
    needs to know whether to DROP the server.
    """
    scanned = []
    for field in _SCAN_FIELDS:
        if field in server:
            scanned.extend(_strings(server[field]))

    hard: list[str] = []
    soft: list[str] = []
    for text in scanned:
        for ref in _iter_refs(text):
            missing: list[str] = []
            value = expand(ref, environ, missing)
            if missing:
                for name in missing:
                    if name not in hard:
                        hard.append(name)
            elif value == "":
                # Name the outermost variable: that is the one an operator sets.
                inner = ref[2:-1].split(":-", 1)[0].strip()
                if inner and inner not in soft:
                    soft.append(inner)
    return sorted(hard), sorted(soft)


def resolve_roster(explicit: str | None, root: Path) -> tuple[bytes | None, str, str]:
    """Mirror the launcher's roster selection.

    Returns ``(content, display, source)``. Content is returned as BYTES rather
    than a path because the origin/main copy has no path -- an earlier version
    staged it under ``.git/``, which is a FILE in a worktree, not a directory.
    The resulting NotADirectoryError is an OSError, so it was swallowed by the
    same handler as a genuine read failure and reported as "origin/main
    unreadable -- offline?" on a machine that was neither offline nor unable to
    read it. Same defect the launcher's own comment warns about: four causes
    collapsing into one wrong guess. Not writing a file removes the cause.

    Precedence, highest first:
      --roster                 an operator overriding on purpose
      $PMOVES_MCP_ROSTER       the path the launcher actually handed to Claude
      origin/main              what the launcher would pick (PR #2847)
      working tree             the launcher's own documented fallback
    """

    def _read(p: Path, source: str) -> tuple[bytes | None, str, str]:
        try:
            return p.read_bytes(), str(p), source
        except OSError as exc:
            return None, str(p), f"{source} -- unreadable: {exc}"

    if explicit:
        return _read(Path(explicit), "--roster (explicit)")

    from_launcher = os.environ.get("PMOVES_MCP_ROSTER")
    if from_launcher and Path(from_launcher).is_file():
        src = os.environ.get("PMOVES_MCP_ROSTER_SOURCE", "unspecified")
        return _read(Path(from_launcher), "the launcher's own roster (%s)" % src)

    tree = root / ".claude" / "mcp.json"

    if os.environ.get("PMOVES_ROSTER_FROM_TREE"):
        return _read(tree, "working tree (PMOVES_ROSTER_FROM_TREE set)")

    try:
        out = subprocess.run(
            ["git", "-C", str(root), "show", "origin/main:.claude/mcp.json"],
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return _read(tree, "working tree (git unavailable: %s)" % exc)

    if out.returncode == 0 and out.stdout.strip():
        return out.stdout, "origin/main:.claude/mcp.json", "origin/main (what the launcher loads)"

    why = out.stderr.decode("utf-8", "replace").strip().splitlines()
    return _read(tree, "working tree (origin/main unreadable: %s)" % (why[0] if why else "no such ref"))


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

    content, display, source = resolve_roster(args.roster, _ROOT)

    if content is None:
        print("  roster     NOT READ: %s" % display)
        print("             source: %s" % source)
        return 0

    try:
        data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print("  roster     UNPARSEABLE at %s: %s" % (display, exc))
        print("             source: %s" % source)
        return 0

    servers = data.get("mcpServers", {})
    if not isinstance(servers, dict) or not servers:
        print("  roster     no mcpServers declared in %s" % display)
        return 0

    # A `_`-prefixed key under mcpServers is a DISABLED entry, not a live one --
    # the roster's convention for retiring a server without deleting its
    # configuration (`_pmoves-cipher-legacy-python-wrapper` is the current
    # instance), and the launcher's normalizer drops exactly these. Reporting
    # one as degraded would tell an operator to go supply credentials for
    # something deliberately switched off.
    #
    # Caught by testing, not by reading: the first version counted 20 servers
    # where PR #2846 measured 19, and the difference was exactly this key.
    names = [n for n in sorted(servers) if not n.startswith("_")]

    hard: list[tuple[str, list[str]]] = []
    soft: list[tuple[str, list[str]]] = []
    ok: list[str] = []

    for name in names:
        h, s = classify(servers[name], os.environ)
        if h:
            hard.append((name, h))
        elif s:
            soft.append((name, s))
        else:
            ok.append(name)

    print("  roster     %s" % display)
    print("             source: %s" % source)
    print("             %d servers declared" % len(names))
    print()

    if hard:
        print("  UNRESOLVABLE -- the literal '${VAR}' text goes on the wire.")
        print("  Claude Code substitutes nothing and warns; the server sees garbage.")
        for name, vs in hard:
            print("    x %-28s %s" % (name, ", ".join(vs)))
        print()

    if soft:
        print("  RESOLVES TO EMPTY -- the request is made unauthenticated.")
        print("  Accepted by a service with no token configured, rejected (401)")
        print("  by one that has a token. Node-dependent.")
        for name, vs in soft:
            print("    ! %-28s %s" % (name, ", ".join(vs)))
        print()

    if not hard and not soft:
        print("  OK         every declared server resolves to a usable value.")
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
