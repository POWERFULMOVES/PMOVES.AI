#!/usr/bin/env python3
"""Preflight: every compose bind-mount source that lives in a submodule must exist.

This is the check specified by `pmoves/docs/operations/SUBMODULE_BUILD_AND_MOUNT_GAP.md`
(see its closing section): *"on `up`, assert that every declared bind source of file
kind is a file on disk. That catches Class B at the moment it matters, needs no
submodule checkout in CI, and is a handful of `test -f` calls."*

Why it is needed at all
-----------------------
**Docker does not error when a bind source is missing — it creates it, as a
directory.** So in a checkout where `git submodule update --init` has not run
(most commonly a **git worktree**), a mount declared as a *file* silently becomes a
mount of an empty *directory*, and the container then fails on its own config. The
error names the application, never the submodule:

    supabase-vector           Configuration error. error=Is a directory (os error 21)
    supabase-edge-functions   could not find an appropriate entrypoint

Worse, Docker's auto-created stubs make the submodule directory **non-empty**, so a
later `git submodule update --init` refuses to clone into it — the failure protects
itself.

Neither CI ratchet catches this: `validate-composes-ratchet` and
`validate-dockerfile-paths-ratchet` both check out without submodules, and the
dockerfile ratchet explicitly holds sibling-submodule paths out of scope as external
repos it cannot statically reason about. That is a defensible split. It leaves this
gap for a runtime check, which is what this file is.

What it checks
--------------
For every bind mount declared in the scanned compose files whose source resolves
into a **registered submodule** (read from `.gitmodules`, not guessed from a `../`
prefix):

  1. the source exists on disk — if not, the submodule is unpopulated;
  2. if the declaration looks like a file (its last segment has a suffix), the path
     on disk is a file and *not* a directory — a directory there is the exact
     signature of Docker having auto-created it on a previous `up`.

Resolving the first segment against `.gitmodules` rather than matching a `../`
shape is deliberate. `pmoves/compose/docker-compose.core.yml` sits one directory
deeper and reaches n8n as `../../PMOVES-n8n`, so a single-`../` scan misses it;
and `pmoves/docker-compose/hf-mcp-server.yml` uses `../../pmoves/services/...`,
which resolves back *inside* this repository and is not a submodule at all.

Run:   python pmoves/tools/check_bind_sources.py
       python pmoves/tools/check_bind_sources.py --json
Exit:  0 = every submodule-backed bind source present and of the right kind
       1 = at least one missing or wrong-kind (the message names the submodule)
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

# Compose files to scan. Globs, resolved relative to the repository root.
COMPOSE_GLOBS = [
    "pmoves/docker-compose.yml",
    "pmoves/docker-compose.*.yml",
    "pmoves/compose/docker-compose.*.yml",
]

SUBMODULE_PATH_RE = re.compile(r"^\s*path\s*=\s*(.+?)\s*$", re.MULTILINE)


class ComposeLoader(yaml.SafeLoader):
    """SafeLoader that tolerates Compose-spec tags such as `!reset` and `!override`.

    These are real Compose syntax (they control how an override file merges with the
    base) and pyyaml's SafeLoader rejects them outright. We only read `volumes`, so
    resolving an unknown tag to None is sufficient — and far better than refusing to
    parse the file, which would silently drop it from coverage.
    """


ComposeLoader.add_multi_constructor("", lambda loader, suffix, node: None)


def registered_submodules(root: Path) -> set[str]:
    """Submodule paths as declared in .gitmodules, repo-root-relative, posix."""
    gitmodules = root / ".gitmodules"
    if not gitmodules.is_file():
        print("FAIL: no .gitmodules at the repository root", file=sys.stderr)
        sys.exit(1)
    text = io.open(gitmodules, encoding="utf-8").read()
    return {m.group(1).replace("\\", "/").strip("/") for m in SUBMODULE_PATH_RE.finditer(text)}


def iter_binds(compose_path: Path):
    """Yield (service, raw_source) for every bind mount in one compose file.

    Handles both the short string form ("src:dst:ro") and the long mapping form
    ({type: bind, source: ...}). Named volumes are skipped: in the short form they
    are the entries whose source has no path separator and no leading dot.
    """
    try:
        doc = yaml.load(io.open(compose_path, encoding="utf-8"), Loader=ComposeLoader) or {}
    except yaml.YAMLError as exc:
        print(f"FAIL: {compose_path} is not valid YAML: {exc}", file=sys.stderr)
        sys.exit(1)

    for service, spec in (doc.get("services") or {}).items():
        if not isinstance(spec, dict):
            continue
        for vol in spec.get("volumes") or []:
            if isinstance(vol, str):
                # "src:dst" / "src:dst:ro" -- but Windows-style absolute sources are
                # not used here, so a plain split on ":" is safe for this repo.
                src = vol.split(":", 1)[0]
                if "/" not in src and not src.startswith("."):
                    continue  # named volume
                yield service, src
            elif isinstance(vol, dict) and vol.get("type") == "bind":
                src = vol.get("source")
                if isinstance(src, str):
                    yield service, src


def owning_submodule(resolved: Path, submodules: set[str], root: Path) -> str | None:
    """The registered submodule this resolved path lives in, if any."""
    try:
        rel = resolved.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None  # outside the repo entirely
    for sub in submodules:
        if rel == sub or rel.startswith(sub + "/"):
            return sub
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="repository root to check (default: the checkout this file lives in). "
             "Point it at the main checkout to verify a populated tree passes.",
    )
    args = ap.parse_args()
    root = args.root.resolve()

    submodules = registered_submodules(root)

    compose_files: list[Path] = []
    for pattern in COMPOSE_GLOBS:
        compose_files.extend(sorted(root.glob(pattern)))
    compose_files = [p for p in dict.fromkeys(compose_files) if p.is_file()]

    checked: list[dict] = []
    problems: list[dict] = []

    for compose in compose_files:
        for service, raw in iter_binds(compose):
            resolved = (compose.parent / raw).resolve()
            sub = owning_submodule(resolved, submodules, root)
            if sub is None:
                continue  # first-party path, named volume, or absolute -- not our gap

            looks_like_file = bool(Path(raw).suffix)
            rel_compose = compose.relative_to(root).as_posix()
            entry = {
                "compose": rel_compose,
                "service": service,
                "source": raw,
                "submodule": sub,
                "kind": "file" if looks_like_file else "directory",
            }
            checked.append(entry)

            if not resolved.exists():
                problems.append({
                    **entry,
                    "problem": "missing",
                    "detail": (
                        f"submodule '{sub}' is not populated in this checkout. Docker will "
                        f"CREATE this path as an empty directory on `up`, the container will "
                        f"fail on its own config, and the stub will then block "
                        f"`git submodule update --init`."
                    ),
                })
            elif looks_like_file and resolved.is_dir():
                problems.append({
                    **entry,
                    "problem": "directory-where-file-expected",
                    "detail": (
                        f"this is the signature of a previous `up` having auto-created the "
                        f"mount. Remove the stub, then populate '{sub}'."
                    ),
                })

    if args.json:
        print(json.dumps({"checked": checked, "problems": problems}, indent=2))
        return 1 if problems else 0

    if problems:
        print(
            f"FAIL: {len(problems)} of {len(checked)} submodule-backed bind sources "
            f"are missing or the wrong kind.\n",
            file=sys.stderr,
        )
        for p in problems:
            print(
                f"  {p['compose']} :: {p['service']}\n"
                f"    source   {p['source']}  ({p['kind']} expected)\n"
                f"    problem  {p['problem']}\n"
                f"    {p['detail']}\n",
                file=sys.stderr,
            )
        subs = sorted({p["submodule"] for p in problems})
        print(
            "Fix, from the repository root:\n"
            f"  git submodule update --init {' '.join(subs)}\n\n"
            "If that refuses because the directory is non-empty, Docker already stubbed it —\n"
            "remove the stub first. Full diagnosis: "
            "pmoves/docs/operations/SUBMODULE_BUILD_AND_MOUNT_GAP.md",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: {len(checked)} submodule-backed bind sources present and of the expected kind "
        f"(across {len(compose_files)} compose files)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
