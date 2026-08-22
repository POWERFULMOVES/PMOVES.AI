#!/usr/bin/env python3
"""agent_zero_pin_check.py - stop our overlay from overriding the fork's pins.

WHY THIS EXISTS
---------------
The agent-zero image installs dependencies TWICE into the SAME virtualenv:

  stage 1   uv pip install -r <fork>/requirements.txt
  stage 2   uv pip install --constraint requirements.lock -r requirements.txt

Stage 2 wins. So every package named in our lock is a version we impose on top
of whatever the fork already resolved - including packages the fork pins for
stated security reasons.

That went wrong silently (found 2026-08-22). The fork pins

    starlette==1.0.1  # security fix: Host header validation bypass GHSA-...

and our lock carried starlette==0.50.0, because we declared `fastapi`, fastapi
caps starlette, and we install second. The fork's pin was intact in the fork's
file the whole time; the running image had something else. Nothing compared the
two files, so nothing noticed.

WHAT IT CHECKS
  1. UNSATISFIED CONSTRAINT - a package in our lock whose version violates the
     specifier the fork declares for it. This is the failure above.

  2. DUPLICATE DECLARATION - a package declared in BOTH requirements files.
     The rule is: if the fork needs it too, declare it in the FORK, so it is
     resolved once. Declaring it in both means we resolve it separately and
     then install over the top, which is how (1) happens in the first place.

  3. LOCK PROVENANCE - the lock must have been produced by
     `make -C pmoves agent-zero-lock` and nothing else.

     Two flags are load-bearing and neither is obvious:

       --upgrade         `uv pip compile` treats an existing output file as
                         PREFERENCES and holds packages at their current
                         versions where still valid. Regenerating in place
                         carries a stale resolution forward while showing a
                         clean diff - which is exactly how the vulnerable
                         starlette survived a full regeneration of the lock.

       --python-platform linux
                         the image is Linux and this repo is worked on from
                         Windows; compiling on the host silently produced a
                         Windows-flavoured resolution.

     We cannot check for those flags directly: uv does not record `--upgrade`
     in the header, because it is a resolution mode rather than part of the
     reproducible command. So the make target sets UV_CUSTOM_COMPILE_COMMAND,
     and the header records the TARGET instead. A hand-run of `uv pip compile`
     writes its own command line there and fails this check.

  4. LOCK COVERAGE - a package declared in our requirements.txt but absent from
     the lock. `python-jose` was in that state: declared, imported by our auth
     code, never pinned or hashed.

WHAT IT DELIBERATELY DOES NOT CHECK
  Whether the gitlink matches the fork's branch head. That is
  submodule_freshness_check.py's job. This tool compares against the gitlink so
  its result is deterministic in CI.

EXIT CODES
  0  clean
  1  findings, or the inputs could not be read

Every finding is blocking. There is no advisory tier on purpose: each one means
the image installs something other than what a file says it does.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

try:
    from packaging.requirements import Requirement
    from packaging.version import Version
except ImportError:  # pragma: no cover
    sys.stderr.write("packaging required: uv run --with packaging python <this file>\n")
    raise SystemExit(1)

SUBMODULE = "PMOVES-Agent-Zero"
RAW = "https://raw.githubusercontent.com/POWERFULMOVES/PMOVES-Agent-Zero/{ref}/requirements.txt"

# Which ref the image builds is READ from the Dockerfiles, never hard-coded.
#
# The PUBLISHED pmoves-agent-zero image is built from Dockerfile.multiarch
# (.github/workflows/integrations-ghcr.matrix.json), and the auto-bump workflow
# rewrites `ARG AGENT_ZERO_REF=` in THAT file only
# (agent-zero-upstream-check.yml:19,163). So a constant here would keep checking
# PMOVES.AI-Edition-Hardened the moment a bump lands a version tag -- the gate
# would approve a lock against a tree the published image does not contain.
# That is the same wrong-tree approval this tool was just fixed to prevent, one
# level up: correct today, silently wrong after the next routine bump.
_REF_ARG = re.compile(r"^ARG\s+AGENT_ZERO_REF=(.+?)\s*$", re.M)
REF_API = "https://api.github.com/repos/POWERFULMOVES/PMOVES-Agent-Zero/git/ref/{kind}/{ref}"


def dockerfile_ref(path):
    """The AGENT_ZERO_REF a build definition declares, or None."""
    try:
        m = _REF_ARG.search(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    return m.group(1).strip() if m else None

# The only sanctioned way to regenerate the lock. The make target sets this as
# UV_CUSTOM_COMPILE_COMMAND so the header records it instead of a raw uv line.
LOCK_COMMAND = "make -C pmoves agent-zero-lock"

PIN_RE = re.compile(r"^([A-Za-z0-9._-]+)==([A-Za-z0-9._+!-]+)", re.M)

LABELS = (
    "INPUT MISSING",
    "UNSATISFIED CONSTRAINT",
    "DUPLICATE DECLARATION",
    "LOCK PROVENANCE",
    "LOCK COVERAGE",
)


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pmoves" / "services" / "agent-zero").is_dir():
            return parent
    return Path.cwd()


ROOT = repo_root()
OURS_TXT = ROOT / "pmoves" / "services" / "agent-zero" / "requirements.txt"
OURS_LOCK = ROOT / "pmoves" / "services" / "agent-zero" / "requirements.lock"

# Defined after ROOT; see the AGENT_ZERO_REF note above.
PUBLISHED_DOCKERFILE = ROOT / "pmoves" / "services" / "agent-zero" / "Dockerfile.multiarch"
COMPOSE_DOCKERFILE = ROOT / "pmoves" / "services" / "agent-zero" / "Dockerfile"


_SEPARATORS = re.compile(r"[-_.]+")


def norm(name: str) -> str:
    """PEP 503 canonical form: runs of `-`, `_` and `.` are ALL equivalent.

    This used to replace `_` only, so `zope.interface` and `zope-interface`
    produced different keys. Python packaging treats them as the same
    distribution, so the fork could constrain one spelling, our overlay could
    override the other, and both the constraint lookup and the
    duplicate-declaration intersection would miss it -- the check passing on a
    real override is exactly the outcome it exists to prevent.

    Ref: https://peps.python.org/pep-0503/#normalized-names
    """
    return _SEPARATORS.sub("-", name).lower()


def resolve_ref_sha(ref):
    """Resolve a branch OR tag name to a sha, the way `git clone --branch` would.

    `--branch` accepts either, and the auto-bump workflow writes version TAGS, so
    resolving only heads/ would start returning None after a routine bump -- which
    (before this was fail-closed) meant falling back to the gitlink.
    """
    if not ref:
        return None
    for kind in ("heads", "tags"):
        try:
            url = REF_API.format(kind=kind, ref=ref)
            with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310 - fixed https host
                obj = json.load(r)["object"]
                # An annotated tag points at a tag object; deref to the commit.
                return obj["sha"]
        except Exception:  # noqa: BLE001
            continue
    return None


def gitlink_sha():
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-tree", "HEAD", SUBMODULE],
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.split()
        return out[2] if len(out) >= 3 else None
    except Exception:  # noqa: BLE001
        return None


def read_fork_requirements(ref, problems):
    """Prefer the checked-out submodule; fall back to fetching the pinned SHA.

    Never returns empty-but-successful. If neither source works the caller gets
    None and the run FAILS. A check that silently compares against nothing is
    worse than no check, because it reports green.
    """
    # Which revision to compare against is the whole correctness question.
    #
    # This used to prefer the local checkout, then the GITLINK. The image builds
    # NEITHER: both Dockerfiles clone `--branch ${AGENT_ZERO_REF}`, i.e. the ref
    # TIP. So whenever that advanced past the gitlink -- the normal state, since
    # the Dockerfile even cache-busts on the tip moving -- this gate validated a
    # tree that is not the one shipped.
    #
    # FAIL CLOSED when the tip cannot be resolved. An earlier version fell back
    # to the gitlink with a stderr WARNING, but the merge gate reads the exit
    # STATUS, not stderr. So a rate-limited API (unauthenticated, and
    # raw.githubusercontent.com stays reachable) would silently restore the exact
    # wrong-tree approval this function exists to prevent. A gate that downgrades
    # to a weaker check under load is a gate that fails when it matters most.
    sha = ref
    if sha is None:
        published_ref = dockerfile_ref(PUBLISHED_DOCKERFILE)
        if not published_ref:
            problems.append(
                "cannot read ARG AGENT_ZERO_REF from {} -- that file defines the "
                "PUBLISHED image, so without it there is nothing to validate "
                "against".format(PUBLISHED_DOCKERFILE.name)
            )
            return None

        # Both build definitions must agree, or one of them ships a tree this
        # check never looked at.
        compose_ref = dockerfile_ref(COMPOSE_DOCKERFILE)
        if compose_ref and compose_ref != published_ref:
            problems.append(
                "build definitions disagree: {} pins {!r} but {} pins {!r}. One of "
                "them ships a tree this check does not validate.".format(
                    PUBLISHED_DOCKERFILE.name, published_ref,
                    COMPOSE_DOCKERFILE.name, compose_ref,
                )
            )
            return None

        sha = resolve_ref_sha(published_ref)
        if sha is None:
            problems.append(
                "could not resolve {!r} (from {}) to a sha. Refusing to fall back "
                "to the gitlink: the gate is read by exit status, so a quiet "
                "downgrade to a weaker check is indistinguishable from success. "
                "Retry, or pass --ref explicitly.".format(
                    published_ref, PUBLISHED_DOCKERFILE.name
                )
            )
            return None

        gl = gitlink_sha()
        if gl and sha != gl:
            print(
                "note: comparing against {} tip {} -- that is what the image "
                "builds. The gitlink is {}, so the submodule pointer does NOT "
                "describe the shipped tree.".format(published_ref, sha[:12], gl[:12]),
                file=sys.stderr,
            )
    url = RAW.format(ref=sha)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310 - fixed https host
            return r.read().decode("utf-8")
    except Exception as e:  # noqa: BLE001
        problems.append(
            "could not read the fork's requirements.txt at {} ({}). "
            "Run `git submodule update --init {}` or pass --ref.".format(
                sha[:12], e, SUBMODULE
            )
        )
        return None


def parse_requirements(text):
    out = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        try:
            req = Requirement(line)
        except Exception:  # noqa: BLE001 - markers and oddities are not our business
            continue
        out[norm(req.name)] = req
    return out


def parse_lock(text):
    return {norm(n): v for n, v in PIN_RE.findall(text)}


def report(problems, checked=0, fork_n=0):
    if not problems:
        print(
            "agent-zero pin check: clean ({} locked packages checked "
            "against {} fork declarations)".format(checked, fork_n)
        )
        return
    print("agent-zero pin check: {} problem(s)".format(len(problems)))
    for label in LABELS:
        items = [m for lbl, m in problems if lbl == label]
        if items:
            print("")
            print("{} ({}):".format(label, len(items)))
            for it in items:
                print("  - {}".format(it))


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--ref",
        help="fork revision to compare against (default: the AGENT_ZERO_REF "
             "declared by Dockerfile.multiarch, which builds the published "
             "image -- NOT the gitlink)",
    )
    # Overridable so the checks can be exercised against fixtures. A check that
    # has never been shown to FAIL is indistinguishable from one that measures
    # nothing, and the real lock cannot be mutated to prove it.
    ap.add_argument("--requirements", type=Path, default=OURS_TXT, help="override our requirements.txt")
    ap.add_argument("--lock", type=Path, default=OURS_LOCK, help="override our requirements.lock")
    a = ap.parse_args()

    ours_txt, ours_lock = a.requirements, a.lock
    problems = []

    missing = [p for p in (ours_txt, ours_lock) if not p.is_file()]
    if missing:
        for p in missing:
            problems.append(("INPUT MISSING", str(p)))
        report(problems)
        return 1

    fork_errors = []
    fork_raw = read_fork_requirements(a.ref, fork_errors)
    for msg in fork_errors:
        problems.append(("INPUT MISSING", msg))
    if fork_raw is None:
        report(problems)
        return 1

    fork = parse_requirements(fork_raw)
    ours = parse_requirements(ours_txt.read_text(encoding="utf-8"))
    lock_text = ours_lock.read_text(encoding="utf-8")
    lock = parse_lock(lock_text)

    # 1. our lock must satisfy every constraint the fork declares
    for name, version in sorted(lock.items()):
        req = fork.get(name)
        if req is None or not str(req.specifier):
            continue
        if not req.specifier.contains(Version(version), prereleases=True):
            problems.append(
                (
                    "UNSATISFIED CONSTRAINT",
                    "{}: fork declares `{}`, our lock pins {} - the image installs OUR "
                    "version second, so the fork's constraint is not what runs".format(
                        name, req, version
                    ),
                )
            )

    # 2. declared in both files
    for name in sorted(set(ours) & set(fork)):
        problems.append(
            (
                "DUPLICATE DECLARATION",
                "{} is declared in BOTH requirements files. Declare it only in the fork, "
                "so it is resolved once instead of resolved twice and installed over "
                "the top.".format(name),
            )
        )

    # 3. lock provenance - see the module docstring for why this is indirect
    header = "\n".join(lock_text.splitlines()[:4])
    if LOCK_COMMAND not in header:
        recorded = next(
            (ln.strip("# ").strip() for ln in lock_text.splitlines()[:4] if ln.startswith("#    ")),
            "(no command recorded)",
        )
        problems.append(
            (
                "LOCK PROVENANCE",
                "the lock was not produced by `{}` - it records `{}`. That target sets "
                "--upgrade (without which uv reuses this file as PREFERENCES and carries a "
                "stale resolution forward while showing no diff) and --python-platform linux "
                "(the image is Linux; this repo is worked on from Windows). Regenerate with "
                "`{}`.".format(LOCK_COMMAND, recorded, LOCK_COMMAND),
            )
        )

    # 4. everything we declare must actually be locked
    for name in sorted(ours):
        if name not in lock:
            problems.append(
                (
                    "LOCK COVERAGE",
                    "{} is declared in our requirements.txt but absent from the lock - "
                    "it installs unpinned and unhashed".format(name),
                )
            )

    report(problems, checked=len(lock), fork_n=len(fork))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
