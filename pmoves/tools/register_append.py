#!/usr/bin/env python3
"""Append a CLAIM or RELEASE row to the AGNOTE4482 claim register, safely.

THE SANCTIONED WRITE PATH. It exists because the collision gate now REFUSES
shell writes it cannot check, and a refusal with no alternative is a deadlock,
not a gate.

That is not a hypothetical. Four delivery agents in one session had no Write
and no Edit tool -- "Write is disabled for this session, in subagents as well
as here" -- so a shell append was the only way any of them could file a row.
Denying that path without providing this one would have stopped the fleet from
claiming work at all, which is strictly worse than the unguarded path it
replaces. The deny and this tool are one change; neither is correct alone.

What this does that a heredoc cannot:

  * READS THE CLOCK. The timestamp is generated here, so it cannot be
    postdated. A sweep of the register found 41 of 404 rows (10.1%) asserting a
    time LATER than the commit that introduced them, the worst by 5h05m, and
    361 of 404 rows (89.4%) carry `:00` seconds -- hand-rounded, not read.
    Rounding explains 22 of the 41; it cannot explain the 11 over an hour. The
    register feeds TTL-lateness arithmetic, so a postdated row makes lateness
    wrong in the direction that flatters the filer.
  * CHECKS THE LANE, using the collision gate's own functions rather than a
    second implementation that would drift from it.
  * APPENDS IN O_APPEND, so the write cannot truncate or rewrite history even
    if two nodes file at once.
  * EMITS THE ROW GRAMMAR CORRECTLY -- backticked timestamp, backticked owner,
    ``branch: `x` `` where the gate can actually see it. 78 of the register's
    historical claims name no branch at all and are unenforceable as a result.

Exit codes follow this repo's doctrine (see docker_host_policy_check.py):
  0  appended
  1  refused -- the lane is held by another owner
  3  could not measure -- refused, and NOT a pass
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER = REPO_ROOT / "pmoves" / "docs" / "AGENTS" / "AGNOTE4482PHI.t1.md"
HOOK = REPO_ROOT / ".claude" / "hooks" / "governance" / "claim-collision-pre.py"

EXIT_OK, EXIT_REFUSED, EXIT_UNMEASURED = 0, 1, 3


def _load_gate():
    """Import the collision hook so this tool checks what the gate checks.

    Deliberately the hook itself and not a copy. A sanctioned path that
    implements its own idea of a collision is a second gate that will disagree
    with the first one, and the disagreement will be discovered by whoever gets
    blocked at an inconvenient moment.
    """
    spec = importlib.util.spec_from_file_location("claim_collision_pre", HOOK)
    module = importlib.util.module_from_spec(spec)
    sys.modules["claim_collision_pre"] = module
    spec.loader.exec_module(module)
    return module


def _ttl_delta(ttl: str) -> timedelta | None:
    ttl = (ttl or "").strip().lower()
    if not ttl or ttl in ("n/a", "none"):
        return None
    if ttl.endswith("h") and ttl[:-1].isdigit():
        return timedelta(hours=int(ttl[:-1]))
    if ttl.endswith("d") and ttl[:-1].isdigit():
        return timedelta(days=int(ttl[:-1]))
    raise ValueError(f"unparseable TTL {ttl!r} (use e.g. 72h, 7d, or n/a)")


def build_row(
    kind: str,
    owner: str,
    branch: str,
    scope: str,
    ttl: str = "",
    co_owners: list[str] | None = None,
    now: datetime | None = None,
) -> str:
    """Render one register row. Pure, so the tests can pin the grammar."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    now = now.replace(microsecond=0)
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    fields = [f"branch: `{branch}`"] if branch else []
    delta = _ttl_delta(ttl)
    if delta is not None:
        expires = (now + delta).strftime("%Y-%m-%dT%H:%M:%SZ")
        fields.append(f"**TTL {ttl} (expires `{expires}`)**")
    if co_owners:
        rendered = []
        for spec in co_owners:
            # `ID` or `ID:contribution note`
            ident, _, note = spec.partition(":")
            ident = ident.strip()
            note = note.strip()
            rendered.append(f"`{ident}` ({note})" if note else f"`{ident}`")
        fields.append("co-owners: " + ", ".join(rendered))

    head = f"- `{ts}` {kind} `{owner}`"
    middle = (" " + " · ".join(fields)) if fields else ""
    return f"{head}{middle} · scope: {scope}\n"


def append_row(row: str, register: Path | None = None) -> None:
    """Append one row. O_APPEND, so it cannot truncate and cannot interleave.

    `register=None` and resolved at CALL time, deliberately. It was a default
    argument bound to the module global, which python evaluates once at import.
    A caller that redirected `REGISTER` -- the test suite, and anything else
    pointing this tool at a different register -- still wrote to the ORIGINAL
    path, so the first run of these tests appended three junk rows to the live
    fleet register. A late-binding bug in the one function whose entire job is
    "write to the right file".

    `os.open` with O_APPEND rather than a plain `open(..., "a")` because the
    flag is the point: every write is positioned at end-of-file by the kernel
    at write time, so a concurrent filer on another node cannot land inside an
    existing row. The register is append-only; this makes that a property of
    the syscall rather than of everyone's good intentions.
    """
    if not row.endswith("\n"):
        row += "\n"
    target = REGISTER if register is None else register
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    fd = os.open(target, flags, 0o644)
    try:
        os.write(fd, row.encode("utf-8"))
    finally:
        os.close(fd)


def _ledger_rows(text: str) -> list[str]:
    """Every CLAIM/RELEASE-shaped row, in order. The thing that must not move."""
    return [
        line for line in text.split("\n")
        if re.match(r"^\s*[-*]\s+`[0-9]{4}-[0-9]{2}-[0-9]{2}", line)
    ]


def insert_docs(anchor: str, block: str, register: Path | None = None) -> int:
    """Insert prose immediately BEFORE `anchor`, provably without touching rows.

    WHY THIS EXISTS. The collision gate now refuses shell writes to the register
    it cannot check -- which is correct for rows and has a cost: it also refuses
    a shell edit to the file's own DOCUMENTATION, because a PreToolUse hook
    cannot see what a mid-file rewrite will produce. An agent with no Write tool
    could therefore file rows and not maintain the prose describing how.

    The answer is the same one the append path uses: do it in validated code.
    The new content is built as a pure INSERTION into the original string, so
    deletion is structurally impossible rather than merely checked for, and the
    ledger rows are then compared before and after as a belt-and-braces
    assertion that the operation did what its shape says it did.
    """
    target = REGISTER if register is None else register
    original = target.read_text(encoding="utf-8")
    if anchor not in original:
        print(f"register-append: NOT MEASURED - anchor {anchor!r} not found in "
              "the register, so nothing was inserted.", file=sys.stderr)
        return EXIT_UNMEASURED
    if original.count(anchor) > 1:
        print(f"register-append: NOT MEASURED - anchor {anchor!r} occurs "
              f"{original.count(anchor)} times; it must be unique to place the "
              "insertion unambiguously.", file=sys.stderr)
        return EXIT_UNMEASURED

    idx = original.index(anchor)
    updated = original[:idx] + block + original[idx:]

    # Structural: the write IS the original with one insertion, nothing else.
    if updated.replace(block, "", 1) != original:
        print("register-append: NOT MEASURED - the rendered file is not the "
              "original plus one insertion. Refusing.", file=sys.stderr)
        return EXIT_UNMEASURED
    before, after = _ledger_rows(original), _ledger_rows(updated)
    if before != after:
        print(f"register-append: refusing - the ledger changed "
              f"({len(before)} rows before, {len(after)} after). The register "
              "is append-only; prose edits must not touch rows.",
              file=sys.stderr)
        return EXIT_REFUSED

    target.write_text(updated, encoding="utf-8")
    print(f"register-append: inserted {len(block.splitlines())} line(s) before "
          f"{anchor!r}; {len(after)} ledger rows unchanged.", file=sys.stderr)
    return EXIT_OK


def _render_co_owners(specs):
    """`ID` or `ID:contribution note` -> the register's own rendering."""
    out = []
    for spec in specs:
        ident, _, note = spec.partition(":")
        ident, note = ident.strip(), note.strip()
        out.append(f"`{ident}` ({note})" if note else f"`{ident}`")
    return ", ".join(out)


def amend_co_owners(owner, branch, co_owners, register=None, gate=None):
    """Add `co-owners:` to the caller's OWN open CLAIM row, in validated code.

    THE NEXT DEADLOCK INSTANCE, closed. The collision gate refuses shell writes
    to the register it cannot check. That is correct for rows, and it left the
    three-way co-owner workflow with no door: reciprocation requires the
    INCUMBENT to add `co-owners:` to a row they already filed, which is an
    in-place edit of one line. `sed -i` and `perl -pi` are refused (rightly --
    a PreToolUse hook cannot see what a mid-file rewrite produces),
    `register-claim` only appends, and `register-docs` refuses anything that
    changes a ledger row. So the field that SUPPRESSES a collision could only be
    set by the one tool nobody in this fleet has had for five sessions.

    Same answer as the append path: do it in validated code, and make the
    dangerous outcome structurally impossible rather than merely checked for.

      * YOUR OWN ROW ONLY. The row is located through the gate's own
        `open_claims_in`, keyed on the CANONICAL identity, and a row whose owner
        does not fold to the caller is not amendable. Attribution and authority
        are different powers -- you may declare who worked WITH you, never edit
        someone else's declaration of who worked with them.
      * ONE OPEN ROW, or nothing. Two open claims by the same identity on the
        same lane is ambiguous, and guessing which to amend is how a gate starts
        editing rows nobody asked it to.
      * PURE INSERTION. The new row is the old row with one substring added, and
        that is asserted by removing the substring again and comparing. Every
        other ledger row must be byte-identical, and the row COUNT must not move.
    """
    target = REGISTER if register is None else register
    original = target.read_text(encoding="utf-8")
    gate = gate or _load_gate()

    key = gate.canonical_owner(owner)
    mine = [c for c in gate.open_claims_in(original).get(key, [])
            if branch in c[1]]
    if not mine:
        print(f"register-append: refusing - no OPEN CLAIM by `{owner}` naming "
              f"branch `{branch}`. You may only amend a row you filed and have "
              "not released. To declare co-owners on a NEW lane, use "
              "`make -C pmoves register-claim CO_OWNER=...`.", file=sys.stderr)
        return EXIT_REFUSED
    if len(mine) > 1:
        print(f"register-append: NOT MEASURED - `{owner}` has {len(mine)} open "
              f"CLAIM rows naming branch `{branch}` (lines "
              f"{', '.join(str(c[0]) for c in mine)}). Which one to amend is "
              "ambiguous, so nothing was changed.", file=sys.stderr)
        return EXIT_UNMEASURED

    lineno = mine[0][0]
    lines = original.split("\n")
    row = lines[lineno - 1]
    rendered = _render_co_owners(co_owners)
    if not rendered:
        print("register-append: amend needs at least one --co-owner.",
              file=sys.stderr)
        return EXIT_UNMEASURED

    if "co-owners:" in row:
        inserted = rendered + ", "
        new_row = re.sub(r"(co-owners:\s*)", lambda m: m.group(1) + inserted,
                         row, count=1)
    else:
        # THE ROW GRAMMAR IS NOT UNIFORM AND THE TOOL MUST NOT ASSUME IT IS.
        # `build_row` emits ` \xb7 scope:`, and the first cut of this function
        # keyed on that -- which works for 18 of the register's 264 CLAIM rows
        # and refuses the other 246, every one of them filed by hand before this
        # tool existed. Those are precisely the rows an incumbent would need to
        # amend. Found by running the amend against a copy of the LIVE register
        # rather than a fixture built to the grammar the tool writes.
        mid = " " + chr(183) + " "
        canonical = mid + "scope:"
        if canonical in row:
            inserted = mid + "co-owners: " + rendered
            new_row = row.replace(canonical, inserted + canonical, 1)
        elif "scope:" in row:
            idx = row.index("scope:")
            inserted = chr(183) + " co-owners: " + rendered + " " + chr(183) + " "
            new_row = row[:idx] + inserted + row[idx:]
        else:
            # A row with no scope field at all (1 of 264). Appending keeps the
            # insertion pure, which is the property the checks below assert.
            inserted = mid + "co-owners: " + rendered
            new_row = row.rstrip() + inserted

    if new_row.replace(inserted, "", 1) != row:
        print("register-append: NOT MEASURED - the amended row is not the "
              "original plus one insertion. Refusing.", file=sys.stderr)
        return EXIT_UNMEASURED

    lines[lineno - 1] = new_row
    updated = "\n".join(lines)
    before, after = _ledger_rows(original), _ledger_rows(updated)
    if len(before) != len(after):
        print(f"register-append: refusing - the ledger changed length "
              f"({len(before)} rows before, {len(after)} after).",
              file=sys.stderr)
        return EXIT_REFUSED
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    if changed != [before.index(row)] or len(changed) != 1:
        print(f"register-append: refusing - {len(changed)} ledger rows changed; "
              "an amend must touch exactly one.", file=sys.stderr)
        return EXIT_REFUSED

    target.write_text(updated, encoding="utf-8")
    print(new_row)
    print(f"register-append: amended line {lineno}; {len(after)} ledger rows, "
          "one row changed by insertion only.", file=sys.stderr)
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("kind", choices=["claim", "release", "docs", "amend"],
                        help="CLAIM opens a lane, RELEASE closes it, "
                             "docs inserts prose without touching rows, "
                             "amend adds co-owners to YOUR OWN open row")
    parser.add_argument("--anchor", default="",
                        help="docs mode: unique line to insert BEFORE")
    parser.add_argument("--text-file", default="",
                        help="docs mode: file holding the prose to insert")
    parser.add_argument("--owner", default=os.environ.get("REGISTER_OWNER", ""),
                        help="owner ID exactly as the register spells it, "
                             "e.g. 'B850-CLAUDE (Knuckles)' "
                             "(or set REGISTER_OWNER)")
    parser.add_argument("--branch", default="",
                        help="the lane. A claim naming no branch cannot be "
                             "checked by the collision gate, so this is "
                             "REQUIRED for a claim.")
    parser.add_argument("--scope", default=os.environ.get("REGISTER_SCOPE", ""),
                        help="what this lane covers (or set REGISTER_SCOPE). "
                             "PREFER THE ENVIRONMENT for prose: a register row "
                             "is full of backticks, and any layer that hands "
                             "the text to a shell will command-substitute "
                             "them. Discovered by filing a real RELEASE "
                             "through `make`, which re-parses its own "
                             "variables -- the row came back with its code "
                             "spans executed and deleted.")
    parser.add_argument("--ttl", default="",
                        help="e.g. 72h, 7d, or n/a")
    parser.add_argument("--co-owner", action="append",
                        default=[c for c in
                                 os.environ.get("REGISTER_CO_OWNERS", "").split("\n")
                                 if c.strip()],
                        metavar="ID[:note]",
                        help="another body that worked this lane; repeatable")
    parser.add_argument("--scope-file", default="",
                        help="read the scope prose from a FILE. The most "
                             "robust option and the one to reach for with long "
                             "rows: prose never becomes part of a command "
                             "string, so nothing downstream can expand, "
                             "substitute or pattern-match against it. "
                             "(A register row quoting an ordinary path fragment "
                             "was refused by the damage-control hook, which "
                             "matches literal strings anywhere in a command -- "
                             "including inside prose.)")
    parser.add_argument(
        "--i-have-coordinated", action="store_true",
        help="proceed with a UNILATERAL co-owner declaration -- a lane whose "
             "incumbent has NOT named you back. The hook asks a human at this "
             "point; a CLI has nobody to ask, so it refuses unless you say so "
             "here. Without this flag the sanctioned path would be the one "
             "route that skips the question, which is how a gate becomes "
             "theatre.")
    parser.add_argument("--dry-run", action="store_true",
                        help="render and check the row, write nothing")
    args = parser.parse_args(argv)

    if args.kind == "docs":
        if not args.anchor or not args.text_file:
            print("register-append: docs mode needs --anchor and --text-file",
                  file=sys.stderr)
            return EXIT_UNMEASURED
        return insert_docs(args.anchor, Path(args.text_file).read_text(encoding="utf-8"))

    if args.kind == "amend":
        if not args.branch or not args.co_owner:
            print("register-append: amend needs --branch and at least one "
                  "--co-owner (or CO_OWNER= via make).", file=sys.stderr)
            return EXIT_UNMEASURED
        if not args.owner:
            print("register-append: amend needs --owner or REGISTER_OWNER: it "
                  "only ever edits a row filed by that identity.",
                  file=sys.stderr)
            return EXIT_UNMEASURED
        if not REGISTER.is_file():
            print(f"register-append: NOT MEASURED - no register at {REGISTER}",
                  file=sys.stderr)
            return EXIT_UNMEASURED
        try:
            gate = _load_gate()
        except Exception as exc:  # noqa: BLE001 -- report, never guess
            print("register-append: NOT MEASURED - the collision gate could not "
                  f"be loaded ({exc}); the row could not be located.",
                  file=sys.stderr)
            return EXIT_UNMEASURED
        return amend_co_owners(args.owner, args.branch, args.co_owner, gate=gate)

    if args.scope_file:
        args.scope = Path(args.scope_file).read_text(encoding="utf-8").strip()

    if not args.owner:
        print("register-append: no --owner and no REGISTER_OWNER. The row must "
              "say who filed it.", file=sys.stderr)
        return EXIT_UNMEASURED
    if not args.scope.strip():
        print("register-append: --scope is required. A row that records no "
              "scope records nothing.", file=sys.stderr)
        return EXIT_UNMEASURED
    if args.kind == "claim" and not args.branch:
        print("register-append: a CLAIM must name --branch. Without a lane the "
              "collision gate has nothing to compare, and the claim is "
              "unenforceable -- 78 rows in this register are already in that "
              "state.", file=sys.stderr)
        return EXIT_UNMEASURED

    try:
        row = build_row(
            kind=args.kind.upper(),
            owner=args.owner,
            branch=args.branch,
            scope=args.scope.strip(),
            ttl=args.ttl,
            co_owners=args.co_owner,
        )
    except ValueError as exc:
        print(f"register-append: {exc}", file=sys.stderr)
        return EXIT_UNMEASURED

    if not REGISTER.is_file():
        print(f"register-append: NOT MEASURED - no register at {REGISTER}",
              file=sys.stderr)
        return EXIT_UNMEASURED

    try:
        gate = _load_gate()
    except Exception as exc:  # noqa: BLE001 -- report, never guess
        print("register-append: NOT MEASURED - the collision gate could not be "
              f"loaded ({exc}), so this row was NOT checked against the open "
              "lanes. Refusing rather than appending unchecked.", file=sys.stderr)
        return EXIT_UNMEASURED

    existing = REGISTER.read_text(encoding="utf-8", errors="replace")
    # WRAPPED, and the wrapping is the fix for a defect this tool shipped.
    # `evaluate_claims` used to be called bare. When the gate's return type
    # widened from 2 categories to a verdict object, this line raised
    # `ValueError: too many values to unpack` -- an UNCAUGHT traceback, exit 1.
    # Exit 1 in this tool's own doctrine means "refused: the lane is held by
    # another owner", so a crash was indistinguishable from a legitimate refusal
    # by exit code alone, in the one tool the fleet has when the Bash path
    # denies and there is no Write tool. A crash must never be able to wear a
    # refusal's exit code; could-not-measure (3) is what it is.
    try:
        verdict = gate.evaluate_claims(row, gate.open_claims_in(existing))
    except Exception as exc:  # noqa: BLE001 -- report, never guess
        print("register-append: NOT MEASURED - the collision gate raised "
              f"{type(exc).__name__}: {exc}. The row was NOT checked against "
              "the open lanes and was NOT written. This is a crash, not a "
              "refusal -- exit 3, never 1.", file=sys.stderr)
        return EXIT_UNMEASURED

    if verdict.collisions:
        print("register-append: refusing to add a CLAIM for a lane another "
              "owner holds.", file=sys.stderr)
        for lane, other, lineno in verdict.collisions:
            print(f"  - lane `{lane}` is already claimed by `{other}` "
                  f"(open CLAIM at line {lineno})", file=sys.stderr)
        print("Either coordinate a handoff, wait for their RELEASE, or pick a "
              "different branch (see Village Rule in AGNOTE4482PHI.t1.md).",
              file=sys.stderr)
        return EXIT_REFUSED

    # A CONSENTED SHARE IS ALLOWED AND ANNOUNCED. An allow that prints nothing
    # cannot be told apart from a gate that did not run.
    for lane, other, lineno in verdict.shared:
        print(f"register-append: SHARED LANE - `{lane}` is held by `{other}` "
              f"(open CLAIM at line {lineno}), whose own row declares this "
              "claimant as a co-owner. Allowing: the incumbent declared it.",
              file=sys.stderr)

    # UNILATERAL. The hook emits `permissionDecision: "ask"` here and a human
    # answers. This tool has nobody to ask, so it refuses and names the flag
    # that answers the question -- rather than being the one path on which the
    # question is never put.
    if verdict.one_sided and not args.i_have_coordinated:
        print("register-append: refusing - this row does not collide only "
              "because of something IT declares. Nobody on the other side has "
              "said so:", file=sys.stderr)
        for owner, lane, other, lineno, witnesses in verdict.one_sided:
            print(f"  - `{owner}` claims lane `{lane}`, held by `{other}` "
                  f"(open CLAIM at line {lineno}); `{other}`'s open row does "
                  f"not declare `{owner}` back, so the sharing is UNILATERAL "
                  f"(shared participants: {', '.join(witnesses)}).",
                  file=sys.stderr)
        print("If you have coordinated -- or the incumbent is offline and you "
              "are picking the lane up -- re-run with --i-have-coordinated. "
              "The incumbent's own reciprocation is "
              "`make -C pmoves register-amend`.", file=sys.stderr)
        return EXIT_REFUSED

    if verdict.unreadable_co_owners:
        print("register-append: NOT MEASURED - this row declares `co-owners:` "
              "and names none the parser can read, so the shared-lane check ran "
              "WITHOUT them. Write each ID in backticks.", file=sys.stderr)
        return EXIT_UNMEASURED

    if verdict.unkeyed:
        for owner in verdict.unkeyed:
            print(f"register-append: NOT MEASURED - CLAIM by `{owner}` names no "
                  "branch the gate can read, so no lane was compared.",
                  file=sys.stderr)
        return EXIT_UNMEASURED

    if args.dry_run:
        sys.stdout.write(row)
        print("register-append: dry run - checked, not written.", file=sys.stderr)
        return EXIT_OK

    append_row(row, REGISTER)
    print(row.rstrip("\n"))
    try:
        where = REGISTER.relative_to(REPO_ROOT)
    except ValueError:
        where = REGISTER
    print(f"register-append: appended to {where}", file=sys.stderr)
    return EXIT_OK


def _guarded(argv=None) -> int:
    """Run main(), and never let an unexpected exception exit 1.

    The exit codes are a CONTRACT here -- 0 appended / 1 the lane is held / 3
    could not measure -- and python's default for an uncaught exception is 1.
    That collapses "this tool crashed" into "another owner holds your lane",
    which is the fleet's signature defect appearing inside the tool built to
    prevent it. A traceback is could-not-measure, and it is printed in full.
    """
    try:
        return main(argv)
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 -- the whole point is to not exit 1
        import traceback
        traceback.print_exc()
        print("register-append: NOT MEASURED - this tool crashed (traceback "
              "above). Nothing was written. Exit 3, NOT 1: a crash must not be "
              "indistinguishable from 'refused, the lane is held'.",
              file=sys.stderr)
        return EXIT_UNMEASURED


if __name__ == "__main__":
    sys.exit(_guarded())
