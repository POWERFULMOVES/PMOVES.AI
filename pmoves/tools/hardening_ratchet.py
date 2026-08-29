#!/usr/bin/env python3
"""Assert every tracked Dockerfile drops root, as a ratchet.

Why this exists
---------------
The `hardening-validation` job is a REQUIRED status check on `main`. Until this
tool, it ran:

    grep -r 'USER' pmoves/services/*/Dockerfile 2>/dev/null | head -10 \
      || echo 'No USER directives found'

Three separate defects, each enough on its own to make the check meaningless:

  1. `|| echo` guarantees exit 0. The job could not fail.
  2. Even on a match it only *prints*. Nothing is asserted, so a match and a
     non-match are the same outcome.
  3. It looks only at `pmoves/services/*/Dockerfile`. Of 99 tracked Dockerfiles
     in this repository that glob sees 76, and 10 of the 12 non-compliant files
     live outside it.

And the check was not merely unable to fail — it measured the wrong property.
`pmoves/images/jellyfin/Dockerfile` declares a non-root `USER` and then switches
back with a later `USER root`. A substring search for `USER` scores that as
compliant. It is the worst case in the repository.

What is asserted
----------------
For every Dockerfile tracked by git:

  NO_FROM    the file declares no `FROM`, so it has no build stage and cannot
             build at all. Checked first and short-circuiting: a truncated
             fragment whose only line is `USER pmoves` otherwise scores
             COMPLIANT under the last-USER rule below.
  NO_USER    the file declares no `USER` directive at all, so the image runs as
             root by default.
  ROOT_USER  the *last* `USER` directive is `root` or `0`. Order matters: it is
             normal and correct to `USER root` for an install step and drop back
             afterwards. Only the final directive decides what the container
             runs as, so only the final directive is judged.

Discovery is `git ls-files`, deliberately, not a filesystem walk. A walk from the
repository root descends into populated submodules and into the git worktrees
this fleet keeps beside the repo, and would judge other projects' Dockerfiles as
if they were ours. `git ls-files` returns exactly the files this repository is
responsible for. (The pytest ratchet records the same hazard from the other
direction — see the `--write-baseline` note in its baseline file.)

Ratchet semantics — identical to pmoves/tools/pytest_ratchet.py:

  new findings    not in the baseline                    -> fail
  stale entries   in the baseline, now compliant, and the
                  file IS tracked in this tree           -> fail
  not-in-tree     in the baseline, file not tracked here -> report, do not fail

Stale entries fail on purpose. Without that, a baseline silently becomes a
permanent allowlist: someone fixes a Dockerfile, the entry stays, and the count
never goes down. The list may shrink and must never quietly grow.

Run:   python pmoves/tools/hardening_ratchet.py
       python pmoves/tools/hardening_ratchet.py --json
       python pmoves/tools/hardening_ratchet.py --write-baseline
Exit:  0 = no new findings and no stale entries
       1 = new finding(s) and/or stale baseline entry(ies)
       2 = discovered no Dockerfiles at all (wrong repo root / not a git checkout)
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Set

REPO_ROOT = Path(__file__).resolve().parents[2]
PMOVES = REPO_ROOT / "pmoves"
BASELINE = PMOVES / "configs" / "hardening_ratchet" / "_known_gaps.yaml"

# `Dockerfile`, `Dockerfile.cipher`, `service.Dockerfile` all count.
DOCKERFILE_RE = re.compile(r"(^|/)(Dockerfile(\..+)?|.+\.Dockerfile)$")
USER_RE = re.compile(r"^\s*USER\s+(\S+)", re.IGNORECASE)
FROM_RE = re.compile(r"^\s*FROM\s+\S+", re.IGNORECASE)
ROOT_USERS = {"root", "0"}


def discover_dockerfiles() -> List[str]:
    """Tracked Dockerfiles, repo-relative, sorted. Never leaves this repository."""
    try:
        # Bytes, not text=True. `text=True` decodes with the *locale* encoding,
        # which on Windows is cp1252, and this repository tracks paths holding
        # bytes cp1252 cannot represent — `git ls-files` then dies with
        # UnicodeDecodeError before the gate has judged a single file. `-z`
        # keeps git from quoting those paths, and surrogateescape lets an
        # undecodable byte survive the round trip to the filesystem call.
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8", errors="surrogateescape")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return sorted(p for p in out.split("\0") if p and DOCKERFILE_RE.search(p))


def effective_user(path: str) -> str | None:
    """The last USER directive, or None if the file declares none.

    Read with errors='replace' rather than strict: a Dockerfile with a stray
    non-UTF-8 byte should be judged on its USER directives, not crash the gate.
    """
    full = REPO_ROOT / path
    try:
        text = io.open(full, encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    users = [m.group(1) for line in text.splitlines() if (m := USER_RE.match(line))]
    return users[-1] if users else None


def has_build_stage(path: str) -> bool:
    """True when the file declares at least one FROM.

    A Dockerfile with no FROM has no build stage: `docker build` fails with
    "no build stage in current context". It also cannot be judged on its USER
    directive, because there is no image for that USER to apply to.
    """
    full = REPO_ROOT / path
    try:
        text = io.open(full, encoding="utf-8", errors="replace").read()
    except OSError:
        return False
    return any(FROM_RE.match(line) for line in text.splitlines())


def scan() -> List[dict]:
    findings: List[dict] = []
    for path in discover_dockerfiles():
        # NO_FROM is checked FIRST and short-circuits, because a fragment with no
        # build stage would otherwise be scored *compliant*: its lone `USER pmoves`
        # is non-root, so the last-USER rule passes it. That is not hypothetical --
        # #2285's hardening pass truncated 9 tracked Dockerfiles down to their USER
        # tails, `main` could not build them, and this gate stayed green through it
        # (#2604). A gate that greens a file which cannot build is asserting a
        # property nobody asked about.
        if not has_build_stage(path):
            findings.append({"kind": "NO_FROM", "where": path, "detail": ""})
            continue
        user = effective_user(path)
        if user is None:
            findings.append({"kind": "NO_USER", "where": path, "detail": ""})
        elif user.strip("\"'").lower() in ROOT_USERS:
            findings.append({"kind": "ROOT_USER", "where": path, "detail": user})
    return findings


def _key(f: dict) -> str:
    """`KIND|path` — same shape as the other ratchets in this repo.

    The offending USER value is deliberately excluded from the key: rewriting
    `USER 0` as `USER root` is the same defect and must not read as a new one.
    """
    return f"{f['kind']}|{f['where']}"


# How many baselined entries are allowed to carry no reason. These are the
# entries that predate the reason field; the number may only go DOWN. A new
# entry without a reason pushes the count over the allowance and fails the
# gate, which is what makes "say why" enforceable instead of aspirational.
REASONLESS_ALLOWANCE_KEY = "reasonless_allowance"

# What KIND of baselined entry this is. The distinction matters because the
# headline count is read as "how much hardening debt we carry", and only one of
# these is debt:
#
#   debt              not fixed yet. The number that should shrink.
#   handled-elsewhere the Dockerfile runs as root, and something ELSE already
#                     constrains it -- `user:` in docker-compose.hardened.yml,
#                     or an image that drops privileges internally the way
#                     nginx spawns workers as `nginx`.
#   deliberate        root is required and chosen, with the reason recorded.
#   not-deployed      not a deployable image: a documentation example, a
#                     fragment, a template nothing builds.
#
# Lumping them together overstates risk and makes progress unmeasurable: work
# off three real gaps and the number barely moves, because most of what it
# counts was never debt.
KINDS = ("debt", "handled-elsewhere", "deliberate", "not-deployed")
DEFAULT_KIND = "debt"


# Both quote styles, so an entry may be written either way.
_QUOTES = chr(34) + chr(39)


class BaselineEntry(NamedTuple):
    """One recorded gap: what it is, why, and what kind of thing it is."""
    ident: str
    kind: str
    reason: str


def _parse_baseline():
    """Read the baseline WITHOUT PyYAML.

    `hardening-validation` runs this with no pip install -- the job says so
    outright: "the ratchet is stdlib-only ... it needs the checkout and nothing
    else". Importing yaml for the richer entry form broke that, and the gate
    died with ModuleNotFoundError before judging a single file. The format is
    small and entirely under this repo's control, so it is parsed here rather
    than trading a deliberate no-dependency property for convenience.

    Handles exactly two entry shapes and one scalar:

        - "KIND|path"
        - entry: "KIND|path"
          kind: not-deployed
          reason: >-
            folded text, continued on more-indented lines
        reasonless_allowance: 6
    """
    if not BASELINE.is_file():
        return [], 0
    entries = []
    allowance = 0
    state = {"ident": "", "kind": "", "reason": [], "in_reason": False}

    def flush():
        if state["ident"]:
            entries.append(BaselineEntry(
                state["ident"],
                state["kind"] or DEFAULT_KIND,
                " ".join(state["reason"]).strip(),
            ))
        state.update(ident="", kind="", reason=[], in_reason=False)

    for raw in BASELINE.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if (state["in_reason"] and raw.startswith("      ") and s
                and not s.startswith("#")
                and not re.match(r"^(entry|kind|reason):", s)):
            state["reason"].append(s)
            continue
        if not s or s.startswith("#"):
            continue
        if s.startswith("- entry:"):
            flush()
            state["ident"] = s.split(":", 1)[1].strip().strip(_QUOTES)
        elif s[:3] in ("- " + chr(34), "- " + chr(39)):
            flush()
            state["ident"] = s[2:].strip().strip(_QUOTES)
        elif s.startswith("kind:") and state["ident"]:
            state["kind"] = s.split(":", 1)[1].strip().strip(_QUOTES)
        elif s.startswith("reason:") and state["ident"]:
            rest = s.split(":", 1)[1].strip()
            state["in_reason"] = True
            if rest and rest not in (">-", ">", "|", "|-"):
                state["reason"].append(rest.strip(_QUOTES))
        elif s.startswith(REASONLESS_ALLOWANCE_KEY + ":"):
            flush()
            try:
                allowance = int(s.split(":", 1)[1].strip())
            except ValueError:
                allowance = 0
    flush()
    return entries, allowance


def load_kinds() -> Dict[str, str]:
    """`KIND|path` -> classification. Absent or unknown reads as `debt`.

    Defaulting to `debt` is deliberate: an unclassified entry should count
    AGAINST us, never be quietly excused. The safe direction for a gate that
    cannot tell is to assume the worse case.
    """
    return {
        e.ident: (e.kind if e.kind in KINDS else DEFAULT_KIND)
        for e in _parse_baseline()[0]
    }


def load_baseline() -> Dict[str, str]:
    """`KIND|path` -> reason (empty string when none was given).

    Two entry forms are accepted, because the older one is still right for a
    gap whose only story is "not fixed yet". The reason belongs HERE and not in
    a PR description: the file's header has always said adding an entry should
    require saying why, but there was nowhere to say it, so the why lived in a
    commit message nobody reads on meeting the entry months later.
    """
    return {e.ident: e.reason for e in _parse_baseline()[0]}


def load_reasonless_allowance() -> int:
    return _parse_baseline()[1]


def write_baseline(findings: List[dict]) -> None:
    """Regenerate, MERGING rather than replacing.

    The old implementation wrote only the current tree's findings, as bare
    strings. Running it therefore deleted every entry belonging to a branch
    this checkout does not carry, and every `kind` and `reason` besides -- so
    the documented regeneration command silently undid the two properties this
    file exists to hold, and the next run on the branch that owns those
    Dockerfiles reported them as NEW and failed.

    What is kept, and why:

      not tracked here      KEPT verbatim. Another branch owns it; this
                            checkout has no standing to judge it.
      tracked and failing   KEPT, with its kind and reason.
      tracked and fixed     DROPPED. That is what regeneration is for.
      newly failing         ADDED, bare -- a reason has to be written by a
                            human, and `reasonless_allowance` will require it.
    """
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    existing = _parse_baseline()[0]
    tracked = set(discover_dockerfiles())
    current = {_key(f) for f in findings}

    keep: Dict[str, BaselineEntry] = {}
    for entry in existing:
        path = entry.ident.split("|", 1)[-1]
        if path not in tracked or entry.ident in current:
            keep[entry.ident] = entry
    for ident in current:
        keep.setdefault(ident, BaselineEntry(ident, DEFAULT_KIND, ""))

    reasonless = sum(1 for e in keep.values() if not e.reason)
    lines = [
        "# Baselined container-hardening gaps -- hardening_ratchet.py",
        "#",
        "# Each entry is a tracked Dockerfile that runs as root: either it declares",
        "# no USER at all, or its last USER directive is root. They are recorded so",
        "# `hardening-validation` can be enforced today without turning main red in",
        "# a single step. They are NOT approved, and none of them is 'expected'.",
        "#",
        "# The list may shrink and must never silently grow. A Dockerfile that is",
        "# fixed but still listed here fails the gate as a STALE entry.",
        "#",
        "# Two forms. Use the second whenever the story is anything other than",
        "# 'not fixed yet' -- an entry without a reason is an allowlist with extra",
        "# steps, because nobody meeting it later can tell whether it was judged",
        "# or merely tolerated:",
        "#",
        '#   - "KIND|path"',
        '#   - entry: "KIND|path"',
        "#     kind: debt | handled-elsewhere | deliberate | not-deployed",
        "#     reason: >-",
        "#       what makes this acceptable, or what it is waiting on",
        "#",
        "# Regenerating MERGES: entries for files this checkout does not track are",
        "# kept verbatim, because another branch owns them.",
        "#",
        "# Regenerate: python pmoves/tools/hardening_ratchet.py --write-baseline",
        "known_gaps:",
    ]
    for ident in sorted(keep):
        entry = keep[ident]
        if entry.reason or entry.kind != DEFAULT_KIND:
            lines.append('  - entry: "' + ident + '"')
            if entry.kind != DEFAULT_KIND:
                lines.append("    kind: " + entry.kind)
            if entry.reason:
                lines.append("    reason: >-")
                lines.append("      " + entry.reason)
        else:
            lines.append('  - "' + ident + '"')
    lines += [
        "",
        "# How many entries above may carry no `reason`. These are grandfathered,",
        "# not approved, and the number may only go DOWN: add one without a reason",
        "# and it exceeds this, and the gate fails.",
        REASONLESS_ALLOWANCE_KEY + ": " + str(reasonless),
    ]
    BASELINE.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Container-hardening ratchet.")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument(
        "--write-baseline",
        action="store_true",
        help="record the current findings as the baseline",
    )
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    files = discover_dockerfiles()
    if not files:
        print(
            "ERROR: no tracked Dockerfiles discovered — wrong repo root, or this "
            "is not a git checkout.",
            file=sys.stderr,
        )
        return 2

    findings = scan()

    if args.write_baseline:
        write_baseline(findings)
        print(f"Wrote {len({_key(f) for f in findings})} entries to {BASELINE}")
        return 0

    reasons = load_baseline()
    baseline = set(reasons)
    found = {_key(f) for f in findings}

    # "Say why" was already this file's stated rule; it just had nowhere to be
    # said, so it could not be checked. Now it can: entries with no reason are
    # counted, and the count may only go DOWN. Adding one without a reason
    # pushes it past the recorded allowance and fails.
    kinds = load_kinds()
    by_kind: Dict[str, int] = {}
    for k in baseline:
        by_kind[kinds.get(k, DEFAULT_KIND)] = by_kind.get(kinds.get(k, DEFAULT_KIND), 0) + 1
    debt = sorted(k for k in baseline if kinds.get(k, DEFAULT_KIND) == "debt")

    reasonless = sorted(k for k in baseline if not reasons.get(k))
    allowance = load_reasonless_allowance()
    over_allowance = max(0, len(reasonless) - allowance)
    new = sorted(found - baseline)
    detail: Dict[str, str] = {_key(f): f["detail"] for f in findings}

    # A baselined entry can be absent from `found` for TWO unrelated reasons,
    # and only one of them is a defect:
    #
    #   the file is in this tree and no longer fails  -> STALE. Fail, so a
    #       baseline cannot rot into a permanent allowlist.
    #   the file is not in this tree at all           -> NOT APPLICABLE. This
    #       branch simply does not carry it.
    #
    # Treating both as stale makes ONE baseline unusable across branches whose
    # file sets differ, which is not hypothetical: `PMOVES.AI-Edition-Hardened`
    # carries CATACLYSM Dockerfiles main has never had. Baseline them and main
    # goes red with stale entries; leave them out and hardened goes red with new
    # ones. The ratchet became unsatisfiable on both branches at once, and the
    # only escape was to stop running it on one of them.
    #
    # Splitting the two restores the ratchet's actual promise -- no silent
    # allowlist -- while letting the same baseline serve trees that legitimately
    # differ. Not-applicable entries are REPORTED, never silently dropped: an
    # entry no branch carries any more is real rot and should be visible.
    tracked = set(files)
    absent = sorted(baseline - found)
    stale = [entry for entry in absent if entry.split("|", 1)[-1] in tracked]
    not_in_tree = [entry for entry in absent if entry.split("|", 1)[-1] not in tracked]

    if args.json:
        print(
            json.dumps(
                {
                    "scanned": len(files),
                    "findings": len(found),
                    "baselined": len(baseline),
                    "new": new,
                    "stale": stale,
                    "not_in_tree": not_in_tree,
                    "debt": debt,
                    "by_kind": by_kind,
                    "reasonless": reasonless,
                    "reasonless_allowance": allowance,
                },
                indent=2,
            )
        )
        return 1 if (new or stale or over_allowance) else 0

    print(f"Scanned {len(files)} tracked Dockerfiles.")
    # "Findings", not "Root-running": NO_FROM is not a root-privilege problem,
    # and a summary line that mislabels what it counted is how a gate ends up
    # trusted for a property it never checked.
    print(f"Findings: {len(found)} ({len(baseline)} baselined, {len(new)} new)")
    if by_kind:
        # Split, because the total is read as "how much debt we carry" and most
        # of it may not be debt. A number that conflates a documentation
        # example with an unhardened service cannot be worked off.
        summary = "  ".join(f"{k}={by_kind[k]}" for k in KINDS if k in by_kind)
        print(f"Baselined by kind: {summary}")
        print(f"Actual hardening debt: {len(debt)}")

    if new:
        print("\nNEW - not in the baseline:")
        for k in new:
            kind, path = k.split("|", 1)
            extra = f" (last USER: {detail[k]})" if detail.get(k) else ""
            print(f"  {kind:<10} {path}{extra}")
        if any(k.startswith("NO_FROM|") for k in new):
            print("\nNO_FROM = no build stage; docker build fails outright.\n  Restore the file content. Do NOT baseline it.")
        if any(not k.startswith("NO_FROM|") for k in new):
            print("\nNO_USER / ROOT_USER: add a non-root USER as the final USER directive,\n  or record it deliberately:\n  python pmoves/tools/hardening_ratchet.py --write-baseline")

    if stale:
        print("\nSTALE — baselined but now compliant. Remove these entries:")
        for k in stale:
            kind, path = k.split("|", 1)
            print(f"  {kind:<10} {path}")
        print(
            "\nA fixed Dockerfile still listed here would let the baseline become "
            "a permanent allowlist. Delete the line."
        )

    if not_in_tree:
        # Reported, never silently dropped. These do not fail the gate -- this
        # branch does not carry the files -- but an entry that NO branch carries
        # any more is real rot, and it can only be seen if it is printed.
        print(
            f"\nNOT IN THIS TREE -- {len(not_in_tree)} baselined "
            f"{'entry' if len(not_in_tree) == 1 else 'entries'} for files this "
            f"branch does not track:"
        )
        for k in not_in_tree:
            kind, path = k.split("|", 1)
            print(f"  {kind:<10} {path}")
        print(
            "\nNot a failure: branches legitimately carry different files, and"
            " one baseline serves them all. Do check that each of these still"
            " exists SOMEWHERE -- an entry no branch carries is stale for real."
        )

    if over_allowance:
        print(
            f"\nNO REASON GIVEN -- {len(reasonless)} baselined entries carry"
            f" no `reason`, and only {allowance} are grandfathered:"
        )
        for k in reasonless:
            kind, path = k.split("|", 1)
            print(f"  {kind:<10} {path}")
        print(
            "\nRecord WHY on the entry itself, not in a PR description:\n"
            "    - entry: \"KIND|path\"\n"
            "      reason: >-\n"
            "        what makes this acceptable, or what it waits on\n"
            "\n  Then lower `reasonless_allowance`. An entry with no reason is an"
            " allowlist with extra steps: nobody meeting it later can tell"
            " whether it was judged or merely tolerated."
        )

    if not new and not stale and not over_allowance:
        print("\nOK — no new root-running Dockerfiles, no stale baseline entries.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
