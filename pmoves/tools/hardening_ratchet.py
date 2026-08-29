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

import yaml
from pathlib import Path
from typing import Dict, List, Set

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


def load_baseline() -> Dict[str, str]:
    """`KIND|path` -> reason (empty string when none was given).

    Two entry forms are accepted, because the older one is still correct for a
    gap whose only story is "not fixed yet":

        - "NO_USER|path/Dockerfile"                     bare, no reason
        - entry: "NO_USER|path/Dockerfile"              with the story attached
          reason: >-
            nginx drops worker privileges internally ...

    The reason belongs HERE and not in a PR description. The file's own header
    has always said adding an entry "should require saying why", but there was
    nowhere to say it, so the why lived in a commit message nobody reads when
    they meet the entry two months later. A ratchet entry without a reason is
    an allowlist with extra steps.
    """
    if not BASELINE.is_file():
        return {}
    doc = yaml.safe_load(BASELINE.read_text(encoding="utf-8")) or {}
    out: Dict[str, str] = {}
    for item in (doc.get("known_gaps") or []):
        if isinstance(item, str):
            out[item] = ""
        elif isinstance(item, dict) and item.get("entry"):
            out[str(item["entry"])] = str(item.get("reason") or "").strip()
    return out


def load_reasonless_allowance() -> int:
    if not BASELINE.is_file():
        return 0
    doc = yaml.safe_load(BASELINE.read_text(encoding="utf-8")) or {}
    try:
        return int(doc.get(REASONLESS_ALLOWANCE_KEY, 0))
    except (TypeError, ValueError):
        return 0


def write_baseline(findings: List[dict]) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Baselined container-hardening gaps — hardening_ratchet.py",
        "#",
        "# Each entry is a tracked Dockerfile that runs as root: either it declares",
        "# no USER at all, or its last USER directive is root. They are recorded so",
        "# `hardening-validation` can be enforced today without turning main red in",
        "# a single step. They are NOT approved, and none of them is 'expected'.",
        "#",
        "# The list may shrink and must never silently grow. Removing an entry is",
        "# the goal; adding one should require saying why in the PR. A Dockerfile",
        "# that is fixed but still listed here fails the gate as a STALE entry, so",
        "# the count only goes down.",
        "#",
        "# Regenerate: python pmoves/tools/hardening_ratchet.py --write-baseline",
        "known_gaps:",
    ]
    for k in sorted({_key(f) for f in findings}):
        lines.append(f'  - "{k}"')
    BASELINE.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
