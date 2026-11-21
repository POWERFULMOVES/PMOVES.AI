"""Resolve the RECORDED commit for a fork, from PMOVES.AI's own gitlink.

WHY THIS TOOL EXISTS
--------------------
A build that resolves its source by a BRANCH NAME builds a MOVING ref. The
image it publishes is then not reproducible from the repository state: two
runs a week apart produce two different artifacts under the same tag, and
there is no commit in PMOVES.AI that names what was built.

PMOVES.AI already records the answer for every fork it tracks as a submodule:
the **gitlink**. `git ls-tree HEAD <path>` gives the exact commit the
repository pins for that submodule. `build-images.yml` already builds from
those pins (it checks out with `submodules: recursive` and builds
`github.workspace/<repo>`). `integrations-ghcr.yml` did NOT: it cloned by
branch.

This tool is the resolver the workflow calls to turn a fork URL into that
recorded commit.

HOW THE FORK IS MATCHED
-----------------------
By the `<org>/<repo>` part of the URL, case-insensitively and ignoring a
`.git` suffix, so `https://github.com/POWERFULMOVES/PMOVES-Open-Notebook.git`
and the `.gitmodules` spelling of the same URL agree.

WHEN SEVERAL SUBMODULES TRACK THE SAME FORK
--------------------------------------------
They can, and their pins can DIFFER. MEASURED 2026-11-05 in this repo:

    160000 commit 490d74bcedec73b846e10a89a7610aecfd1f601d  PMOVES-Archon
    160000 commit 8d135dabaafd090ff1da9dd966f7fd18d74da484  pmoves/integrations/archon

Both point at `PMOVES-Archon` and they pin DIFFERENT commits. The rule is
therefore: prefer the TOP-LEVEL submodule (a path with no `/`), because that is
the one `build-images.yml` builds from (`github.workspace/<repo>`). If no
single candidate wins, the tool refuses to guess.

EXIT CODES -- THE CALLER MUST HANDLE EACH ONE
---------------------------------------------
  0  resolved; the 40-character SHA is on stdout
  3  the fork is NOT tracked as a submodule: nothing is recorded, so the
     caller may build the branch (this is not an error)
  4  AMBIGUOUS: several submodules track the fork and disagree on the commit
  5  INCONSISTENT: a submodule declares the fork but the tree records no
     gitlink for it -- even when a SIBLING declaration IS recorded, because
     falling back to the sibling would publish a commit the tree does not
     record for the preferred candidate
  6  the repository state could not be read at all

4, 5 and 6 are failures the caller must NOT paper over: a build that resolves
a different commit than the one recorded is exactly the defect this tool
exists to remove.

URL SPELLINGS
-------------
The fork is matched by its `<org>/<repo>` part, so the scheme and host are
dropped, the `.git` suffix is ignored, and the SCP-LIKE form
(`git@host:org/repo`) is reduced to the same key. A URL that cannot be
reduced to `<org>/<repo>` is NOT "a fork that is not tracked" -- that answer
tells the caller to build the moving branch -- so the spellings that git
itself prints are all reduced here.

Usage:
    python pmoves/tools/resolve_recorded_pin.py --url <fork-url> [--repo-root DIR]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

EXIT_RESOLVED = 0
EXIT_NOT_TRACKED = 3
EXIT_AMBIGUOUS = 4
EXIT_INCONSISTENT = 5
EXIT_UNREADABLE = 6

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]

# The SCP-LIKE remote spelling: `git@host:org/repo`. git itself prints this
# form for an SSH remote, so it is a spelling a fork's `.gitmodules` entry can
# carry. It is matched by SHAPE, not by a prefix list, so a different host or
# a different user still reduces to `<org>/<repo>`.
_SCP_LIKE = re.compile(r"^[^/]+@[^/:]+:(?P<path>.+)$")


class ResolutionError(Exception):
    """A failure the caller must not paper over."""

    def __init__(self, exit_code: int, message: str) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.message = message


class NotTrackedError(ResolutionError):
    """The fork is not tracked as a submodule AT ALL.

    A DEDICATED class, not a bare `LookupError`. `KeyError` and `IndexError`
    are `LookupError` subclasses, so catching `LookupError` around the
    resolution would turn any stray subscript error inside it into "not
    tracked" -- and "not tracked" tells the caller to build the MOVING BRANCH.

    A failure the caller must not paper over cannot share a door with the one
    failure it is allowed to paper over.
    """

    def __init__(self, message: str) -> None:
        super().__init__(EXIT_NOT_TRACKED, message)


def _git(repo_root: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout


def normalise_url(url: str) -> str:
    """`<org>/<repo>`, lower-cased, without a `.git` suffix.

    The scheme and host are dropped: two spellings of the same fork on
    different hosts are still the same fork for our purposes, and the org is
    what distinguishes one fork from another in this fleet.

    The SCP-LIKE form (`git@host:org/repo`) -- the spelling git itself prints
    for an SSH remote -- is normalised too. That is not decoration: a URL
    this tool cannot reduce to `<org>/<repo>` looks exactly like a fork that
    is NOT tracked, and "not tracked" tells the caller to build the MOVING
    BRANCH. That is the exact defect this tool exists to remove, so a
    spelling that cannot be reduced must be REDUCED, not read as "absent".
    """
    cleaned = url.strip().rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[: -len(".git")]
    scp = _SCP_LIKE.match(cleaned)
    if scp:
        cleaned = scp.group("path")
    parts = [p for p in cleaned.split("/") if p]
    if len(parts) < 2:
        return cleaned.lower()
    return "/".join(parts[-2:]).lower()


def read_submodules(repo_root: Path) -> dict[str, list[str]]:
    """Map normalised fork URL -> the submodule paths that track it."""
    gitmodules = repo_root / ".gitmodules"
    if not gitmodules.is_file():
        raise ResolutionError(
            EXIT_UNREADABLE,
            f"no .gitmodules in {repo_root}; the fork-to-submodule map cannot be read",
        )

    rc, out = _git(
        repo_root,
        "config",
        "--file",
        str(gitmodules),
        "--get-regexp",
        r"^submodule\..+\.(url|path)$",
    )
    if rc not in (0, 1):
        raise ResolutionError(
            EXIT_UNREADABLE,
            f"could not read {gitmodules} (git config exited {rc})",
        )

    urls: dict[str, str] = {}
    paths: dict[str, str] = {}
    for line in out.splitlines():
        key, _, value = line.partition(" ")
        value = value.strip()
        if key.endswith(".url"):
            urls[key[: -len(".url")]] = value
        elif key.endswith(".path"):
            paths[key[: -len(".path")]] = value

    by_url: dict[str, list[str]] = {}
    for key, url in urls.items():
        path = paths.get(key)
        if not path:
            continue
        by_url.setdefault(normalise_url(url), []).append(path)
    return by_url


def read_gitlinks(repo_root: Path) -> dict[str, str]:
    """Map submodule path -> the commit PMOVES.AI records for it.

    The tree is read RECURSIVELY (`-r`). A plain `git ls-tree HEAD` lists
    only the top level, and this repo nests submodules INSIDE directories --
    `pmoves/integrations/archon` is one -- so the non-recursive read would
    report those as "declared but not recorded" when they are recorded.
    """
    rc, out = _git(repo_root, "ls-tree", "-r", "HEAD")
    if rc != 0:
        raise ResolutionError(
            EXIT_UNREADABLE,
            f"could not read the tree at HEAD in {repo_root} (git ls-tree exited {rc})",
        )
    links: dict[str, str] = {}
    for line in out.splitlines():
        head, _, path = line.partition("\t")
        fields = head.split()
        if len(fields) >= 3 and fields[0] == "160000":
            links[path.strip()] = fields[2]
    return links


def resolve(repo_root: Path, url: str) -> str:
    """The recorded commit for `url`, or a ResolutionError / not-tracked."""
    by_url = read_submodules(repo_root)
    links = read_gitlinks(repo_root)

    key = normalise_url(url)
    candidates = by_url.get(key)
    if not candidates:
        raise NotTrackedError(
            f"{url} is not tracked as a submodule; nothing is recorded for it"
        )

    resolved: dict[str, str] = {}
    missing: list[str] = []
    for path in candidates:
        sha = links.get(path)
        if sha is None:
            missing.append(path)
        else:
            resolved[path] = sha

    if missing:
        # ANY declared-but-unrecorded submodule makes the repository state
        # INCONSISTENT -- even when a SIBLING declaration IS recorded.
        #
        # Falling back to the sibling would publish a commit the tree does not
        # record for the PREFERRED candidate, and `build-images.yml` -- which
        # builds the top-level path -- would then disagree with this lane
        # about what is being built. The documented contract says exit 5 for a
        # declared-but-unrecorded submodule, and the contract does not carry a
        # "unless another one happens to be there" clause.
        raise ResolutionError(
            EXIT_INCONSISTENT,
            f"{url} is declared as a submodule ({', '.join(sorted(missing))}) but "
            f"the tree records no gitlink for it; the repository state is "
            f"inconsistent",
        )

    top_level = {p: s for p, s in resolved.items() if "/" not in p}
    if len(top_level) == 1:
        chosen_path, chosen_sha = next(iter(top_level.items()))
        if len(resolved) > 1:
            others = ", ".join(
                f"{p}={s[:8]}" for p, s in sorted(resolved.items()) if p != chosen_path
            )
            print(
                f"::notice::{url}: several submodules track this fork ({others}); "
                f"using the top-level one {chosen_path}={chosen_sha[:8]}",
                file=sys.stderr,
            )
        return chosen_sha

    distinct = set(resolved.values())
    if len(distinct) == 1:
        return next(iter(distinct))
    # `resolved` cannot be empty here: every candidate is either recorded or
    # missing, and a non-empty `missing` already raised above.
    raise ResolutionError(
        EXIT_AMBIGUOUS,
        f"{url} is tracked by several submodules that record DIFFERENT commits "
        f"({', '.join(f'{p}={s[:8]}' for p, s in sorted(resolved.items()))}); "
        f"refusing to guess which one this build means",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Resolve the commit PMOVES.AI records for a fork.",
    )
    parser.add_argument("--url", required=True, help="the fork's git URL")
    parser.add_argument(
        "--repo-root",
        default=str(DEFAULT_REPO_ROOT),
        help="the PMOVES.AI checkout to read (default: this file's repository)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit a JSON object instead of a bare SHA",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    try:
        sha = resolve(repo_root, args.url)
    except NotTrackedError:
        # A DEDICATED exception, not `LookupError`. `KeyError` and
        # `IndexError` are `LookupError` subclasses, so the broad catch would
        # report any stray subscript error inside the resolution as "not
        # tracked" -- and "not tracked" tells the caller to build the MOVING
        # BRANCH. That is the exact defect this tool exists to remove.
        if args.json:
            print(json.dumps({"url": args.url, "tracked": False, "sha": None}))
        print(
            f"::notice::{args.url} is not tracked as a submodule; nothing is "
            f"recorded for it",
            file=sys.stderr,
        )
        return EXIT_NOT_TRACKED
    except ResolutionError as error:
        print(f"::error::{error.message}", file=sys.stderr)
        return error.exit_code

    if args.json:
        print(json.dumps({"url": args.url, "tracked": True, "sha": sha}))
    else:
        print(sha)
    return EXIT_RESOLVED


if __name__ == "__main__":
    raise SystemExit(main())
