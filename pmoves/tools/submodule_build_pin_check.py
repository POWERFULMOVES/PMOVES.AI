#!/usr/bin/env python3
"""Will this build road compile the submodule commit -- and the files -- this checkout records?

WHY THIS EXISTS
---------------
`make -C pmoves up-cipher` runs ``docker compose up -d --build cipher-api``, and
that service's ``build.context`` is ``../Pmoves-cipher`` -- the submodule
WORKTREE. Docker reads the files on disk. It has no idea a gitlink exists.

So when the worktree drifts from the recorded gitlink, the road faithfully
builds the wrong commit and prints ``✔ Cipher Memory ready``.

Measured on B850, 2026-09-01. `main` pinned Pmoves-cipher at ``d5c4045e``
(promote ``4ffb56dcb`` / PR #2366, 2026-08-03); the fix itself, ``c69adb43``,
had already been pinned earlier by promote ``96cfa3311`` on 2026-07-30. It
mounts the ``/mcp`` router BEFORE ``express.json()`` so the SDK's
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

WHAT IS COMPARED, EXACTLY
-------------------------
``git ls-tree HEAD <path>`` -- the gitlink recorded in THIS CHECKOUT's HEAD.
Not ``origin/main``'s, and the tool does not claim otherwise anywhere in its
output. That is the right reference for the docker question: a legitimate
promote branch has the worktree moved and the gitlink bumped to match, and it
should read clean. The claim is deliberately the small one -- "the commit this
checkout records" -- because that is the only one this comparison supports.

AND THE FILES, NOT JUST THE COMMIT (review F1, 2026-09-02)
----------------------------------------------------------
HEAD matching the pin does not make a build reproducible. Docker reads FILES.
A worktree sitting exactly on the pin with an uncommitted edit under ``src/``
compiles that edit into the image, and ``git submodule status`` shows no ``+``
for it -- so the entire ``+``-prefix family is blind to the single most common
real drift, a developer mid-change.

So a submodule whose HEAD matches the pin but whose build inputs are modified
is ``dirty``, and dirty blocks (exit 1) exactly like drift. ``CIPHER_BUILD_PIN=warn``
is the documented way to build mid-change on purpose.

"Build inputs" is narrowed to what the Dockerfile actually copies FROM THE
CONTEXT, when the caller names one (``Pmoves-cipher:Dockerfile.pmoves``).
Cipher's copies ``package.json``, ``package-lock.json``, ``tsconfig.json``,
``src/`` and ``packages/`` -- and the real B850 worktree carries an untracked
``data/`` that no COPY reads. Blocking on ``data/`` would get this gate switched
off inside a day with ``CIPHER_BUILD_PIN=warn``, which is precisely the
all-or-nothing failure this file objects to in submodule_integrity.py above.
The narrowing is derived from the Dockerfile rather than duplicated from it, so
adding a ``COPY`` widens the gate automatically instead of blinding it.

Name no Dockerfile and the whole worktree is watched -- the conservative answer
for a road that did not say what it reads. Name one that cannot be read or that
copies nothing from the context, and that is exit 3, not a narrower pass.

``.dockerignore`` is NOT subtracted (Pmoves-cipher has none). If one appears,
this over-reports rather than under-reports, which is the safe direction.

WHY A GATE AND NOT AN AUTO-SYNC
-------------------------------
Deliberate. A drifted worktree is sometimes a developer mid-change, and
silently running ``git submodule update --checkout`` under someone's build
would discard uncommitted work to make a check pass. This REPORTS and refuses,
and prints the exact command to run. The human decides whether the worktree or
the pin is the thing that is wrong.

Which puts the whole weight of the recovery on that printed command, so it is
anchored absolutely rather than relatively -- see ``_abs()``. Every road into
this gate is ``make -C pmoves ...``, so the operator reading a block is standing
in ``pmoves/``, and ``Pmoves-cipher`` is a SIBLING of that directory, not a
child. A root-relative remediation is wrong on 100% of real invocations, which
are the only ones anybody ever sees (Codex P2, comment 3910500690, 2026-09-02).

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

Usage (paths are relative to the repo ROOT, and so is this invocation; the
Makefile runs it from ``pmoves/`` as ``tools/submodule_build_pin_check.py``,
which is why everything it PRINTS is absolute instead):
  python3 pmoves/tools/submodule_build_pin_check.py Pmoves-cipher
  python3 pmoves/tools/submodule_build_pin_check.py Pmoves-cipher:Dockerfile.pmoves
  python3 pmoves/tools/submodule_build_pin_check.py Pmoves-cipher --json

An argument is ``<submodule-path>`` or ``<submodule-path>:<dockerfile>``, where
the dockerfile is relative to the submodule and names the build's Dockerfile.

Exit codes:
  0  worktree HEAD == the recorded gitlink AND no build input is modified
  1  drift or dirty -- the build would compile something this checkout does
     not record
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


def _abs(*parts: str) -> str:
    """An absolute path under the repo root, for strings a human will paste.

    Every remediation this tool prints is anchored with ``git -C <absolute>``
    rather than a root-relative path, because the tool does not run from the
    root. The canonical road is ``make -C pmoves up-cipher``, so the process --
    and the operator reading its output -- stands in ``pmoves/``, where
    ``git -C Pmoves-cipher fetch`` is ``fatal: cannot change to 'Pmoves-cipher'``
    and ``git submodule update --checkout Pmoves-cipher`` is ``error: pathspec
    ... did not match``. The submodule is a SIBLING of ``pmoves``, not a child.

    That is worth more than its cosmetic weight, because these strings are only
    ever read by an operator the gate has just blocked. A recovery command that
    fails when pasted is how a correct gate gets switched off with
    ``CIPHER_BUILD_PIN=warn`` by a frustrated human -- and the whole point of the
    gate is that it is the only thing between them and a stale image.

    ``REPO_ROOT`` is already absolute (``git rev-parse --show-toplevel``), so
    ``-C`` makes each string correct from ANY directory rather than from exactly
    one. Both halves need it: anchoring the submodule half and leaving the
    superproject half relative is the original defect
    (Codex P2, review comment 3910500690, 2026-09-02).
    """
    base = REPO_ROOT if REPO_ROOT is not None else Path(".")
    return str(base.joinpath(*parts))


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


# The Dockerfile parse below returns this when a COPY reads the whole context
# (``COPY . /app``). It is not a path; it means "watch everything".
WHOLE_CONTEXT = object()


def _logical_lines(text: str) -> list[str]:
    """Dockerfile lines with backslash continuations joined and comments dropped."""
    lines: list[str] = []
    buf = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if not buf and (not stripped or stripped.startswith("#")):
            continue
        if stripped.endswith("\\"):
            buf += stripped[:-1] + " "
            continue
        lines.append((buf + stripped).strip())
        buf = ""
    if buf.strip():
        lines.append(buf.strip())
    return lines


def context_paths(dockerfile: Path) -> set | None:
    """Paths a Dockerfile copies FROM THE BUILD CONTEXT, or None if unreadable.

    ``COPY --from=<stage>`` reads a previous stage, not the context, so it is
    excluded -- cipher's runtime stage copies ``/app/dist`` and
    ``/app/node_modules`` from the builder and neither is a worktree file.

    Returns ``{WHOLE_CONTEXT}`` for ``COPY . .`` and friends. Returns None when
    the file cannot be read or when nothing is copied from the context at all;
    both mean "cannot say which files docker reads", which is exit 3, never a
    narrower pass.
    """
    try:
        text = dockerfile.read_text(encoding="utf-8")
    except OSError:
        return None

    sources: set = set()
    for line in _logical_lines(text):
        parts = line.split(None, 1)
        if len(parts) < 2 or parts[0].upper() not in ("COPY", "ADD"):
            continue
        rest = parts[1]

        args: list[str] = []
        from_stage = False
        # Flags come first: --from=, --chown=, --chmod=, --link ...
        while rest.startswith("--"):
            flag, _, rest = rest.partition(" ")
            if flag.startswith("--from="):
                from_stage = True
            rest = rest.lstrip()
        if from_stage:
            continue

        if rest.startswith("["):
            try:
                args = [str(x) for x in json.loads(rest)]
            except (ValueError, TypeError):
                return None  # exec-form we cannot read -> refuse to guess
        else:
            args = rest.split()

        if len(args) < 2:
            return None  # malformed COPY -> refuse to guess
        for src in args[:-1]:
            src = src.strip().rstrip("/")
            if src in ("", ".", "./", "*"):
                return {WHOLE_CONTEXT}
            sources.add(src.lstrip("./"))

    return sources or None


def dirty_build_inputs(path: str, watched: set | None) -> list[str] | None:
    """Modified/untracked build inputs in the submodule worktree, or None on error.

    `git status --porcelain` and not `git submodule status`: the latter prints
    `+` only when HEAD differs from the gitlink, so it is silent on exactly the
    case this catches. Gitignored files are excluded by git's own default, which
    is what keeps `dist/` and `node_modules/` out of the answer.
    """
    sub = REPO_ROOT / path
    args = ["status", "--porcelain", "--untracked-files=all"]
    if watched is not None and WHOLE_CONTEXT not in watched:
        args += ["--", *sorted(watched)]
    proc = run_git(*args, cwd=sub)
    if proc.returncode != 0:
        return None
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def _remediation(status: str, path: str) -> list[str]:
    """The commands printed to an operator this gate has just blocked.

    Every entry must survive being pasted verbatim from ANY directory -- see
    ``_abs()``. They are stored on the finding rather than formatted at print
    time so that the strings a test executes are the identical objects the
    operator sees; a parallel copy would let the two drift apart, which is the
    same class of defect as the one this function fixes.

    Nothing here is a mutation the human did not ask for. Drift gets the sync
    command because the tool already knows the answer (the checkout is wrong).
    Dirty deliberately does NOT get an automatic ``git stash -u``: the dirt may
    be work in progress, and on the real Pmoves-cipher an ``--include-untracked``
    stash would also sweep the runtime ``data/`` directory. It gets a read-only
    inspect command instead and leaves the decision where this file's
    "WHY A GATE AND NOT AN AUTO-SYNC" section puts it -- with the human.
    """
    if status == "drift":
        return [
            "git -C %s fetch && git -C %s submodule update --checkout %s"
            % (_abs(path), _abs(), path),
        ]
    if status == "dirty":
        return ["git -C %s status --short" % _abs(path)]
    return []


def check(specs: list[str]) -> tuple[int, list[dict]]:
    """Answer for each ``<path>`` or ``<path>:<dockerfile>`` spec.

    Precedence when more than one thing is wrong: unmeasured (3) beats drift and
    dirty (1) beats clean (0). A submodule we could not read never vouches for
    one we could, and a clean sibling never vouches for an unreadable one.
    """
    findings: list[dict] = []
    unmeasured = False

    for spec in specs:
        path, _, dockerfile = spec.partition(":")
        pin = recorded_gitlink(path)
        head = worktree_head(path)

        if pin is None:
            findings.append({
                "path": path,
                "status": "unmeasured",
                "detail": "no gitlink recorded at this path in HEAD",
                "remediation_verb": "inspect",
                "remediation": [
                    "git -C %s ls-tree HEAD %s" % (_abs(), path),
                ],
            })
            unmeasured = True
            continue

        if head is None:
            findings.append({
                "path": path,
                "status": "unmeasured",
                "detail": "submodule not initialized (or git unreadable)",
                "remediation_verb": "run",
                "remediation": [
                    "git -C %s submodule update --init %s" % (_abs(), path),
                ],
            })
            unmeasured = True
            continue

        # Which files docker will read. None means "could not narrow", and when
        # a Dockerfile was NAMED that is a measurement failure, not a licence to
        # check nothing. With no Dockerfile named we watch the whole worktree.
        watched: set | None = None
        if dockerfile:
            watched = context_paths(REPO_ROOT / path / dockerfile)
            if watched is None:
                findings.append({
                    "path": path,
                    "status": "unmeasured",
                    "detail": "cannot read the build inputs from %s -- "
                              "missing, unparseable, or it copies nothing from "
                              "the build context" % _abs(path, dockerfile),
                    "remediation_verb": "inspect",
                    "remediation": [
                        "cat %s" % _abs(path, dockerfile),
                    ],
                })
                unmeasured = True
                continue

        dirt = dirty_build_inputs(path, watched)
        if dirt is None:
            findings.append({
                "path": path,
                "status": "unmeasured",
                "detail": "git status failed in %s -- cannot tell whether the "
                          "build inputs are modified" % _abs(path),
                "remediation_verb": "inspect",
                "remediation": [
                    "git -C %s status --porcelain" % _abs(path),
                ],
            })
            unmeasured = True
            continue

        if head != pin:
            # Drift is the larger claim; record the dirt alongside rather than
            # letting one mask the other.
            status = "drift"
        elif dirt:
            status = "dirty"
        else:
            status = "clean"

        findings.append({
            "path": path,
            "status": status,
            "gitlink": pin,
            "worktree": head,
            "dirty": bool(dirt),
            "dirty_entries": dirt[:20],
            "watched": ("<whole worktree>" if watched is None
                        else "<whole build context>" if WHOLE_CONTEXT in watched
                        else sorted(watched)),
            "remediation": _remediation(status, path),
        })

    if unmeasured:
        return 3, findings
    if any(f["status"] in ("drift", "dirty") for f in findings):
        return 1, findings
    return 0, findings


def _print_dirt(f: dict) -> None:
    for entry in f["dirty_entries"]:
        print("                " + entry)
    if f["watched"] != "<whole worktree>":
        print("              (build inputs watched: %s)" % (f["watched"],))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail when a build road would compile a submodule commit "
                    "the superproject does not record.",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="submodule path relative to the repo root, optionally "
             "<path>:<dockerfile> to narrow the modified-build-input check "
             "to what that Dockerfile copies from the build context "
             "(e.g. Pmoves-cipher:Dockerfile.pmoves)",
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
            print("              docker build reads the CHECKED OUT tree, so this road")
            print("              would ship a commit this checkout does not record.")
            if f["dirty"]:
                print("              and its build inputs are modified on top:")
                _print_dirt(f)
            for cmd in f["remediation"]:
                print(f"              fix: {cmd}")
        elif f["status"] == "dirty":
            print(f"  DIRTY     {f['path']} @ {f['gitlink'][:12]}")
            print("              HEAD matches the pin, but docker reads FILES, and")
            print("              these build inputs are not the recorded ones:")
            _print_dirt(f)
            print("              `git submodule status` shows no `+` for this state.")
            print(f"              fix: commit or stash the changes in {_abs(f['path'])}")
            for cmd in f["remediation"]:
                print(f"              inspect: {cmd}")
            print("              or set CIPHER_BUILD_PIN=warn to build mid-change on")
            print("              purpose (an env var -- correct from any directory).")
        else:
            print(f"  UNMEASURED {f['path']}: {f['detail']}")
            # "run" = executing this clears the block. "inspect" = this is a
            # read to tell you WHICH of the causes in `detail` you have; it may
            # legitimately exit non-zero (a `cat` of a genuinely missing file),
            # and that is an answer, not the wrong-directory failure this
            # anchoring fixes. Both must RESOLVE from any cwd.
            verb = f.get("remediation_verb", "run")
            for cmd in f.get("remediation", []):
                print(f"              {verb}: {cmd}")

    if code == 0:
        print("submodule build pins: clean")
    elif code == 1:
        print("submodule build pins: DRIFT/DIRTY -- refusing to build something "
              "this checkout does not record")
    else:
        print("submodule build pins: COULD NOT MEASURE -- this is not a pass")
    return code


if __name__ == "__main__":
    sys.exit(main())
