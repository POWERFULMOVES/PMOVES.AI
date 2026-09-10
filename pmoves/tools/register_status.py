#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
#
# DECLARED HERE TOO, for the reason `register_append.py` declares it: this tool
# imports the collision hook, which needs PyYAML to read
# `identity_vocabulary.yaml`. Without it the hook folds no owner spellings, and
# this tool would report a lane as free because the RELEASE that closed it was
# spelled differently from the CLAIM that opened it. `register_append.py` can
# survive that degradation -- it fails CLOSED, it blocks. A READ cannot: it
# would fail OPEN, quietly, by answering "free". So this tool refuses to answer
# at all when the vocabulary is missing. See `_require_measurable()`.
"""Report what the claim register says is OPEN. Read-only.

THE SANCTIONED READ PATH, and the missing half of #2879.

That PR made the Bash gate fail closed on the register, correctly: six
interpreter write-shapes (`python3 -c`, `node -e`, `ruby -e`, `ed`, truncation,
`git checkout --ours`) had all been reaching an append-only ledger at exit 0.
The allowlist that closed them enumerates what is positively recognised as a
read, and an interpreter naming the register is not on it -- it cannot be,
because a `-c` that opens the file for writing and a `-c` that prints it are
the same shape at the shell level.

The cost was that `open_claims_in()` -- which the register itself names as the
authority on what is open -- became unreachable. Every sanctioned path the
refusal named was a WRITE (`register-claim`, `register-release`,
`register-amend`). An agent could file a claim but could not ask whether the
lane was free. This is the answer to that refusal, not a hole in it.

WHY THIS IS NOT A SECOND PARSER. Every judgement below is delegated:

  * `open_claims_in()`  -- what is open, and who holds it (the hook)
  * `canonical_owner()` -- which spellings are one identity (the hook)
  * `evaluate_claims()` -- whether a lane is free FOR YOU (the hook)
  * `build_row()`       -- the row grammar the probe is phrased in
                           (`register_append.py`, which writes it)
  * `_ttl_delta()`      -- what `72h` means (`register_append.py`, which
                           computed the `expires` values already in the file)
  * `ROW_RE` / `parse_ts()` -- how a row's own timestamp is read
                           (`register_postdate_check.py`)

Two parsers is how this register acquired 20 spellings of one owner and three
lanes with more releases than claims. A read path that computed its own answer
would disagree with the gate, and the disagreement would be discovered by
whoever got blocked after being told they were clear.

Exit codes follow this repo's doctrine (see `docker_host_policy_check.py`,
`mcp_toolkit_preflight.py`):

  0  clean            -- lane is free / nothing open has expired
  1  findings         -- lane is held (or needs a decision), or an open claim's
                         TTL has expired and it was never released
  3  could not measure -- and that is NOT a pass

`make` collapses 1 and 3 into its own exit 2, so invoke this file directly when
you need to tell them apart.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER = REPO_ROOT / "pmoves" / "docs" / "AGENTS" / "AGNOTE4482PHI.t1.md"
TOOLS = REPO_ROOT / "pmoves" / "tools"

EXIT_CLEAN, EXIT_FINDINGS, EXIT_UNMEASURED = 0, 1, 3

# An owner string for a probe filed by nobody. It is only ever passed to
# `evaluate_claims()` as the claimant, never written, and the parenthetical is
# deliberately unspellable so `canonical_owner()` cannot fold it onto a real
# node and turn "somebody else holds this" into "you hold this".
ANONYMOUS_PROBE = "REGISTER-STATUS-PROBE (no OWNER given)"


def _load_siblings():
    """Import the gate and the two tools that already own this grammar."""
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    import register_append
    import register_postdate_check

    return register_append._load_gate(), register_append, register_postdate_check


def _require_measurable(gate) -> None:
    """Refuse to answer when owner-folding is unavailable.

    THE ASYMMETRY IS THE POINT. When `identity_vocabulary.yaml` cannot be read,
    `canonical_owner()` falls back to exact string comparison -- documented in
    the hook as fail-safe, and it is, *for a gate*: unfolded spellings make the
    gate see two identities where there is one, so it BLOCKS more, not less.

    Run backwards through a read, the same degradation inverts. A RELEASE
    spelled `B850-CLAUDE (Opus 5)` stops closing a CLAIM opened as
    `B850-CLAUDE (Knuckles)`, so the claim stays in `open_claims_in()` and this
    tool over-reports open lanes -- and, worse, a lane genuinely held under one
    spelling can be reported free to a claimant asking under another. That is a
    read that fails open. Could-not-measure is not a pass, so it is refused.

    The remedy is one line and it is printed, because a refusal with no route
    is the whole defect this lane exists to fix.
    """
    if gate._load_lineage() is None:
        sys.stderr.write(
            "register-status: NOT MEASURED - the identity vocabulary could not "
            "be loaded, so owner spellings are not folded. A RELEASE filed "
            "under one spelling would not close a CLAIM opened under another, "
            "and this tool would report a held lane as free. Refusing to "
            "answer rather than answering wrongly.\n"
            "  Remedy: `make -C pmoves register-status`, which picks an "
            "interpreter that has PyYAML, or `uv run --script "
            "pmoves/tools/register_status.py`.\n"
        )
        sys.exit(EXIT_UNMEASURED)


# --------------------------------------------------------------------------
# TTL
# --------------------------------------------------------------------------
#
# Two shapes exist in the live file and both are load-bearing:
#
#   1. `**TTL 24h (expires ...)**` -- what `build_row()` emits. The expiry is
#      stated, so it is read, not computed.
#   2. `..., TTL 72h.` -- prose, hand-written before the sanctioned path
#      existed. Measured on the live register: 3 of 22 open claims. The expiry
#      has to be derived from the row's own timestamp.
#
# 15 of 22 open claims name no TTL at all. That is reported as a count, not as
# a finding -- an exit code that is non-zero 68% of the time is one nobody
# reads.

TTL_FIELD_RE = re.compile(r"\bTTL\b[:\s]+([^\s.,;)`*]+)", re.IGNORECASE)
EXPIRES_RE = re.compile(r"\bexpires\s+`([^`]+)`", re.IGNORECASE)


class Expiry:
    """What a row says about its own lifetime.

    state: "none" (no TTL) | "live" | "expired" | "unmeasured"
    """

    __slots__ = ("state", "ttl", "expires", "why")

    def __init__(self, state, ttl="", expires=None, why=""):
        self.state = state
        self.ttl = ttl
        self.expires = expires
        self.why = why


def row_expiry(row: str, append_mod, postdate_mod, now: datetime) -> Expiry:
    """Read one row's TTL. Never raises; an unreadable TTL is `unmeasured`."""
    field = TTL_FIELD_RE.search(row)
    if not field:
        return Expiry("none")
    ttl = field.group(1).strip().strip("*")

    stated = EXPIRES_RE.search(row)
    if stated:
        # The row states its own expiry. `parse_ts` is the postdate check's
        # reader, so a timestamp this tool accepts is one that tool accepts.
        when = postdate_mod.parse_ts(stated.group(1))
        if when is None:
            return Expiry("unmeasured", ttl,
                          why="the stated `expires` timestamp did not parse")
        return Expiry("expired" if when <= now else "live", ttl, when)

    # Derived: row timestamp + the TTL that `register_append` would have used.
    try:
        delta = append_mod._ttl_delta(ttl)
    except ValueError as exc:
        return Expiry("unmeasured", ttl, why=str(exc))
    if delta is None:  # `n/a`, `none`
        return Expiry("none", ttl)

    m = postdate_mod.ROW_RE.match(row)
    started = postdate_mod.parse_ts(m.group("ts")) if m else None
    if started is None:
        return Expiry("unmeasured", ttl,
                      why="the row states a TTL but its own timestamp did not "
                          "parse, so the expiry cannot be derived")
    when = started + delta
    return Expiry("expired" if when <= now else "live", ttl, when)


def _humanise(delta: timedelta) -> str:
    secs = int(abs(delta).total_seconds())
    days, secs = divmod(secs, 86400)
    hours, secs = divmod(secs, 3600)
    mins = secs // 60
    if days:
        return f"{days}d{hours}h"
    if hours:
        return f"{hours}h{mins:02d}m"
    return f"{mins}m"


def _iso(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# THE QUESTIONS
# --------------------------------------------------------------------------


class OpenLane:
    __slots__ = ("owner_key", "owner", "lineno", "lanes", "participants",
                 "expiry")

    def __init__(self, owner_key, owner, lineno, lanes, participants, expiry):
        self.owner_key = owner_key
        self.owner = owner
        self.lineno = lineno
        self.lanes = lanes
        self.participants = participants
        self.expiry = expiry

    def as_dict(self):
        return {
            "owner": self.owner,
            "owner_key": self.owner_key,
            "line": self.lineno,
            "lanes": sorted(self.lanes),
            "participants": sorted(self.participants),
            "ttl": self.expiry.ttl,
            "ttl_state": self.expiry.state,
            "expires": _iso(self.expiry.expires) if self.expiry.expires else None,
            "ttl_why": self.expiry.why,
        }


def collect(text: str, gate, append_mod, postdate_mod, now: datetime):
    """Every open claim, with its expiry resolved. Sorted by line number."""
    # `split`, NOT `splitlines`, and for the reason `open_claims_in` documents
    # at length: this file carries vertical tabs and form feeds that
    # `splitlines` breaks on and no editor, grep or sed counts as a line. The
    # line numbers here come FROM `open_claims_in`, so indexing back into the
    # text with different line semantics would fetch the wrong row -- and the
    # wrong row is the one whose TTL gets reported.
    lines = text.split("\n")
    out = []
    for owner_key, rows in gate.open_claims_in(text).items():
        for lineno, lanes, as_written, participants in rows:
            row = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
            out.append(OpenLane(
                owner_key, as_written, lineno, lanes, participants,
                row_expiry(row, append_mod, postdate_mod, now),
            ))
    out.sort(key=lambda o: o.lineno)
    return out


def probe_branch(text: str, branch: str, owner: str, gate, append_mod):
    """Ask the GATE what it would do if `owner` claimed `branch` right now.

    Not "is any open row's branch string equal to this one". The gate's answer
    is the only one that matters, and it is more subtle than equality: the same
    identity re-naming its own lane is not a collision, an incumbent who
    declared you as a co-owner is a SHARED lane and allowed, and a one-sided
    declaration is neither -- it is an `ask`. Reimplementing that here would
    produce a second opinion, and the second opinion would be wrong first.

    The probe row is built by `build_row()`, so it is phrased in exactly the
    grammar the write path emits. A probe the gate reads differently from a
    real claim is not a probe. It is never appended anywhere.
    """
    probe = append_mod.build_row(
        "CLAIM", owner, branch,
        "register-status probe -- rendered in memory, never appended",
        ttl="n/a",
    )
    return gate.evaluate_claims(probe, gate.open_claims_in(text))


# --------------------------------------------------------------------------
# REPORTING
# --------------------------------------------------------------------------


def _lane_label(lane: OpenLane) -> str:
    return ", ".join(sorted(lane.lanes)) if lane.lanes else "(no branch named)"


def _expiry_label(exp: Expiry, now: datetime) -> str:
    if exp.state == "none":
        return "no TTL"
    if exp.state == "unmeasured":
        return f"TTL {exp.ttl} - NOT MEASURED ({exp.why})"
    rel = _humanise(exp.expires - now)
    if exp.state == "expired":
        return f"TTL {exp.ttl} EXPIRED {rel} ago ({_iso(exp.expires)})"
    return f"TTL {exp.ttl} live, {rel} left ({_iso(exp.expires)})"


def report_listing(lanes, register, now, out) -> int:
    expired = [x for x in lanes if x.expiry.state == "expired"]
    unmeasured = [x for x in lanes if x.expiry.state == "unmeasured"]
    no_ttl = [x for x in lanes if x.expiry.state == "none"]
    owners = {x.owner_key for x in lanes}

    out.write(f"claim register: {register}\n")
    out.write(f"read at {_iso(now)} - {len(lanes)} open claim rows held by "
              f"{len(owners)} {'identity' if len(owners) == 1 else 'identities'}\n\n")

    if not lanes:
        out.write("OPEN LANES: none. Every CLAIM in this file has a later "
                  "RELEASE from the same identity.\n")
        return EXIT_CLEAN

    out.write("OPEN LANES\n")
    for lane in lanes:
        out.write(f"  line {lane.lineno:>5}  {_lane_label(lane)}\n")
        out.write(f"{'':>15}owner: {lane.owner}\n")
        out.write(f"{'':>15}{_expiry_label(lane.expiry, now)}\n")
        extra = sorted(lane.participants - {lane.owner_key})
        if extra:
            out.write(f"{'':>15}co-owners: {', '.join(extra)}\n")

    if expired:
        out.write(f"\nEXPIRED AND NOT RELEASED ({len(expired)})\n")
        out.write("  A TTL is a promise to release by a time. These rows are "
                  "past it, so each\n  still blocks a claimant while nobody "
                  "has said they are still on it.\n")
        for lane in expired:
            out.write(f"  line {lane.lineno:>5}  {_lane_label(lane)}  - "
                      f"{lane.owner}\n")

    if unmeasured:
        out.write(f"\nTTL NOT MEASURED ({len(unmeasured)})\n")
        for lane in unmeasured:
            out.write(f"  line {lane.lineno:>5}  {_lane_label(lane)}  - "
                      f"{lane.expiry.why}\n")

    out.write(f"\nWITHOUT A TTL: {len(no_ttl)} of {len(lanes)} open claims name "
              "no TTL, so they cannot\n  expire and nothing will ever prompt "
              "their release. Pass TTL= to\n  `make -C pmoves register-claim` "
              "to avoid adding to that number.\n")
    out.write("\n  Times here are as the rows ASSERT them. Whether a row's "
              "asserted time precedes\n  the commit that added it is a "
              "different question: `make -C pmoves\n  "
              "register-postdate-check`.\n")

    if unmeasured:
        return EXIT_UNMEASURED
    if expired:
        return EXIT_FINDINGS
    return EXIT_CLEAN


def _matching(lanes, branch):
    """Every open row that names `branch`. One definition, because the report
    and the JSON have to be talking about the same rows -- a second copy of
    this expression is how the exit code and the payload drift apart."""
    return [x for x in lanes if branch in x.lanes]


def report_branch(verdict, branch, owner_given, lanes, now, out) -> int:
    """Render the gate's verdict on one lane."""
    matching = _matching(lanes, branch)
    out.write(f"lane `{branch}`\n")
    if not owner_given:
        out.write("  asked anonymously (no OWNER=), so a lane YOU already hold "
                  "reads as held by\n  someone else. Pass OWNER= for the answer "
                  "`register-claim` would give you.\n")

    if verdict.collisions:
        for _lane, holder, lineno in verdict.collisions:
            out.write(f"  HELD by `{holder}` (line {lineno})\n")
        out.write("  `register-claim` would refuse this lane.\n")
    elif verdict.one_sided:
        for _o, _lane, holder, lineno, witnesses in verdict.one_sided:
            out.write(f"  DECLARED ONE-SIDED with `{holder}` (line {lineno}) "
                      f"via {', '.join(witnesses)}\n")
        out.write("  The incumbent's row does not name you back. That is "
                  "attribution, not a handoff:\n  the gate would ASK, not "
                  "allow. Have them run `register-amend`.\n")
    elif verdict.shared:
        for _lane, holder, lineno in verdict.shared:
            out.write(f"  SHARED with `{holder}` (line {lineno}), who declared "
                      "you on their own row\n")
    elif matching:
        # Held, but by the identity that asked. The gate allows this and says
        # nothing about it; a status report has to say it out loud, or "free"
        # gets read as "nobody is on it".
        for lane in matching:
            out.write(f"  HELD BY YOU (line {lane.lineno}, as `{lane.owner}`)\n")
    else:
        out.write("  FREE - no open claim names it\n")

    for lane in matching:
        out.write(f"  line {lane.lineno}: {_expiry_label(lane.expiry, now)}\n")

    # A SHARED LANE DOES NOT SUSPEND THE TTL. The expiry check used to sit
    # behind `not verdict.shared`, so a reciprocated lane whose open row had
    # already expired printed `TTL 24h - EXPIRED` and returned 0. This tool's
    # documented contract is that an expired unreleased claim is a FINDING, and
    # the whole-file report already exits 1 on exactly that row; branch mode
    # disagreeing with it meant automation could read a stale co-held lane as
    # clean -- the fail-open this file exists to prevent, printed in full and
    # then contradicted by the exit code.
    #
    # The relationship still reports as SHARED above. Co-holding a lane is a
    # deliberate feature and the register must keep naming everyone who worked
    # it; what is not a feature is a promise-to-release, broken, reported, and
    # scored as a pass.
    stale = [x for x in matching if x.expiry.state == "expired"]
    if stale:
        out.write("  The open row(s) above are past a TTL nobody released. "
                  "That is a finding, not a\n  free lane: `register-release` "
                  "closes it, or `register-claim` re-states the TTL.\n")

    if verdict.collisions or verdict.one_sided:
        return EXIT_FINDINGS
    if any(x.expiry.state == "unmeasured" for x in matching):
        return EXIT_UNMEASURED
    if stale:
        return EXIT_FINDINGS
    if matching and not verdict.shared:
        return EXIT_FINDINGS  # held by you: not free, so not clean
    return EXIT_CLEAN


def _json_payload(lanes, register, now, branch, verdict, code):
    payload = {
        "register": str(register),
        "read_at": _iso(now),
        "open_claims": [x.as_dict() for x in lanes],
        "counts": {
            "open": len(lanes),
            "identities": len({x.owner_key for x in lanes}),
            "expired": sum(1 for x in lanes if x.expiry.state == "expired"),
            "no_ttl": sum(1 for x in lanes if x.expiry.state == "none"),
            "ttl_unmeasured": sum(1 for x in lanes
                                  if x.expiry.state == "unmeasured"),
        },
        "exit_code": code,
    }
    if branch:
        payload["branch"] = {
            "name": branch,
            "collisions": [
                {"lane": lane, "holder": holder, "line": lineno}
                for lane, holder, lineno in verdict.collisions
            ],
            "shared": [
                {"lane": lane, "holder": holder, "line": lineno}
                for lane, holder, lineno in verdict.shared
            ],
            "one_sided": [
                {"lane": lane, "holder": holder, "line": lineno,
                 "witnesses": witnesses}
                for _o, lane, holder, lineno, witnesses in verdict.one_sided
            ],
            # Named here because a consumer reading only `branch` should not
            # have to re-derive from `open_claims` the one fact that turns this
            # lane's exit code from 0 into 1.
            "expired": [
                {"lane": branch, "holder": x.owner, "line": x.lineno,
                 "expires": _iso(x.expiry.expires) if x.expiry.expires else None}
                for x in _matching(lanes, branch) if x.expiry.state == "expired"
            ],
        }
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="register_status.py",
        description="Report what the AGNOTE4482 claim register says is open. "
                    "Read-only.",
    )
    parser.add_argument(
        "--branch", default=os.environ.get("REGISTER_BRANCH", ""),
        help="ask whether ONE lane is free (or set REGISTER_BRANCH)")
    parser.add_argument(
        "--owner", default=os.environ.get("REGISTER_OWNER", ""),
        help="who is asking, so a lane you already hold is not reported as "
             "someone else's (or set REGISTER_OWNER)")
    parser.add_argument("--json", action="store_true",
                        help="machine-readable output on stdout")
    parser.add_argument("--register", default=None,
                        help="read a different register file (for tests)")
    parser.add_argument("--now", default=None,
                        help="evaluate expiry against this ISO instant (tests)")
    args = parser.parse_args(argv)

    register = Path(args.register) if args.register else REGISTER

    try:
        gate, append_mod, postdate_mod = _load_siblings()
    except Exception as exc:  # noqa: BLE001 -- the message matters more
        sys.stderr.write(
            "register-status: NOT MEASURED - the collision gate could not be "
            f"imported ({exc}), so nothing was read. This tool deliberately "
            "has no fallback parser: a second opinion about what is open is "
            "how the register acquired lanes with more releases than claims.\n"
        )
        return EXIT_UNMEASURED

    _require_measurable(gate)

    try:
        text = register.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        sys.stderr.write("register-status: NOT MEASURED - the register could "
                         f"not be read ({exc}).\n")
        return EXIT_UNMEASURED

    if args.now:
        now = postdate_mod.parse_ts(args.now)
        if now is None:
            sys.stderr.write(f"register-status: NOT MEASURED - --now "
                             f"{args.now!r} did not parse as an ISO instant.\n")
            return EXIT_UNMEASURED
    else:
        now = datetime.now(timezone.utc).replace(microsecond=0)

    lanes = collect(text, gate, append_mod, postdate_mod, now)

    # With --json the human report goes to stderr so stdout stays parseable.
    prose = sys.stderr if args.json else sys.stdout

    verdict = None
    if args.branch:
        owner = args.owner or ANONYMOUS_PROBE
        verdict = probe_branch(text, args.branch, owner, gate, append_mod)
        code = report_branch(verdict, args.branch, bool(args.owner), lanes,
                             now, prose)
    else:
        code = report_listing(lanes, register, now, prose)

    if args.json:
        json.dump(_json_payload(lanes, register, now, args.branch, verdict,
                                code), sys.stdout, indent=2)
        sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
