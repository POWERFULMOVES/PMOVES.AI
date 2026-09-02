#!/usr/bin/env python3
"""Is the submodule this build road is about to compile the commit `main` records?

WHY THIS EXISTS
---------------
`make -C pmoves up-cipher` runs ``docker compose up -d --build cipher-api``, and
that service's ``build.context`` is ``../Pmoves-cipher`` -- the submodule
WORKTREE. Docker reads the files on disk. It has no idea a gitlink exists.

So when the worktree drifts from the recorded gitlink, the road faithfully
builds the wrong commit and prints ``✔ Cipher Memory ready``.

Measured on B850, 2026-09-01. `main` had pinned Pmoves-cipher at ``d5c4045e``
since PR #2366; that commit contains ``c69adb43``, which fixes cipher's MCP
transport by mounting the ``/mcp`` router BEFORE ``express.json()`` so the SDK's
``handlePostMessage()`` still has a readable body stream. The checked-out
worktree was four commits behind at ``986e6e2f``. The image built from it on
2026-08-16 answered every ``initialize`` with

    HTTP 400  InternalServerError: stream is not readable

for two weeks, while the fix sat on `main` and the container healthcheck --
``GET /health``, which works on every build -- read "healthy" throughout.

A fresh clone was always fine. That is exactly what made it expensive: the
defect was invisible to CI, invisible to review, and invisible to anyone
reading the repo. It lived only in one node's checkout.

WHY NOT submodule_integrity.py
------------------------------
It already detects this -- the ``+`` prefix in ``git submodule status`` means
worktree != gitlink, and it fails on it. Two reasons it cannot serve here:

  1. It is not on any build road. It is a repo-hygiene gate.
  2. It is all-or-nothing. On B850 it reports 25 drifted submodules at once,
     most of them irrelevant to any given build. A road that refused to build
     cipher because PMOVES-Wealth is drifted would be turned off within a day.

This check takes the submodules ONE road actually consumes, so its answer is
about that road and a red result is always actionable.

WHY A GATE AND NOT AN AUTO-SYNC
-------------------------------
Deliberate. A drifted worktree is sometimes a developer mid-change, and
silently running ``git submodule update --checkout`` under someone's build
would discard uncommitted work to make a check pass. This REPORTS and refuses,
and prints the exact command to run. The human decides whether the worktree or
the pin is the thing that is wrong.

Blast radius, measured: of 19 distinct ``build.context`` values in
``pmoves/docker-compose.yml``, 7 are rooted in a submodule -- PMOVES-Archon,
PMOVES-OpenRoom, PMOVES-llama-throughput-lab, PMOVES-transcribe-and-fetch,
PMOVES.YT, Pmoves-cipher, and PMOVES-ToKenism-Multi/pmoves-nextjs. Every one of
them can build a commit that is on nobody's main.

REFUSING TO GUESS
-----------------
If a submodule is uninitialized, or git cannot be run, or the path names no
gitlink, that is exit 3 -- could not measure, NOT a pass. A gate that returns
"clean" because it read nothing is worse than no gate, and is the failure this
whole check exists to stop.

Usage:
  python3 pmoves/tools/submodule_build_pin_check.py Pmoves-cipher
  python3 pmoves/tools/submodule_build_pin_check.py Pmoves-cipher --json

Exit codes:
  0  every named submodule's worktree HEAD == its recorded gitlink
  1  drift -- the build would compile a commit the superproject does not record
  3  could not measure -- NOT a pass
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

def _repo_root() -> Path | None:
    """The working tree we are checking -- anchored on CWD, not on __file__.

    Deliberate. `docker compose` resolves ``build.context: ../Pmoves-cipher``
    relative to the compose file, i.e. relative to where the road is being run
    from -- so the tree docker will read is the tree the CALLER is standing in.
    Anchoring on the script's own location would let a checkout of this tool in
    one worktree report "clean" about a submodule in a different worktree, which
    is the same class of mistake the check exists to catch.
    """
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return Path(proc.stdout.strip())


REPO_ROOT = _repo_root()


def run_git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def recorded_gitlink(path: str) -> str | None:
    """The commit the superproject's HEAD tree records for `path`, or None.

    `git ls-tree HEAD <path>` is the pin. `git submodule status` is NOT -- it
    prints the WORKTREE sha with a `+` when the two disagree, which is the
    misreading that hid this defect in the first place.
    """
    proc = run_git("ls-tree", "HEAD", path)
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    fields = proc.stdout.split()
    # "<mode> <type> <sha>\t<path>" -- mode 160000 / type commit is a gitlink.
    if len(fields) < 3 or fields[0] != "160000" or fields[1] != "commit":
        return None
    return fields[2]


def worktree_head(path: str) -> str | None:
    """The commit actually checked out on disk -- what docker build will read."""
    sub = REPO_ROOT / path
    if not (sub / ".git").exists():
        return None
    proc = run_git("rev-parse", "HEAD", cwd=sub)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def check(paths: list[str]) -> tuple[int, list[dict]]:
    findings: list[dict] = []
    unmeasured = False

    for path in paths:
        pin = recorded_gitlink(path)
        head = worktree_head(path)

        if pin is None:
            findings.append({
                "path": path,
                "status": "unmeasured",
                "detail": "no gitlink recorded at this path in HEAD",
            })
            unmeasured = True
            continue

        if head is None:
            findings.append({
                "path": path,
                "status": "unmeasured",
                "detail": "submodule not initialized (or git unreadable) -- "
                          "run: git submodule update --init " + path,
            })
            unmeasured = True
            continue

        findings.append({
            "path": path,
            "status": "clean" if head == pin else "drift",
            "gitlink": pin,
            "worktree": head,
        })

    if unmeasured:
        return 3, findings
    if any(f["status"] == "drift" for f in findings):
        return 1, findings
    return 0, findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail when a build road would compile a submodule commit "
                    "the superproject does not record.",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="submodule paths, relative to the repo root (e.g. Pmoves-cipher)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    if REPO_ROOT is None:
        print("submodule build pins: COULD NOT MEASURE -- not inside a git "
              "working tree; refusing to report a pass", file=sys.stderr)
        return 3

    code, findings = check(args.paths)

    if args.json:
        print(json.dumps({"exit": code, "findings": findings}, indent=2))
        return code

    for f in findings:
        if f["status"] == "clean":
            print(f"  ok        {f['path']} @ {f['gitlink'][:12]}")
        elif f["status"] == "drift":
            print(f"  DRIFT     {f['path']}")
            print(f"              recorded gitlink : {f['gitlink']}")
            print(f"              checked out      : {f['worktree']}")
            print("              docker build reads the CHECKED OUT tree, so this")
            print("              road would ship a commit that is on nobody's main.")
            print(f"              fix: git -C {f['path']} fetch && "
                  f"git submodule update --checkout {f['path']}")
        else:
            print(f"  UNMEASURED {f['path']}: {f['detail']}")

    if code == 0:
        print("submodule build pins: clean")
    elif code == 1:
        print("submodule build pins: DRIFT -- refusing to build a stale commit")
    else:
        print("submodule build pins: COULD NOT MEASURE -- this is not a pass")
    return code


if __name__ == "__main__":
    sys.exit(main())
