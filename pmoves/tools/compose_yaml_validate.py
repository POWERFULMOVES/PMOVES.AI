#!/usr/bin/env python3
"""compose_yaml_validate.py - assert every tracked compose file actually parses.

WHY THIS EXISTS
---------------
The merge gate had a job named `docker-build-validation` whose entire body was:

    pip install pyyaml
    python -c "import yaml; yaml.safe_load(open('pmoves/docker-compose.yml'))" \\
        2>/dev/null || echo 'Compose validation skipped'

Three things at once:

  * it parsed ONE file out of 55 tracked compose files;
  * `2>/dev/null` discarded the error that would have told anyone;
  * `|| echo` meant the step exited 0 no matter what.

It could not fail. It sat in merge-decision's `needs` supplying a guaranteed
green vote under a name that reads, in the checks list, as though Docker builds
were being validated. This file is the same shape as the `merge-gate` job that
was previously removed from that workflow for exactly this reason.

THE TRAP THAT MAKES THE OBVIOUS FIX WRONG
Parsing all 55 files with a plain `yaml.safe_load` fails on two of them:

    pmoves/docker-compose.amd-voice.yml   -> unknown tag '!reset'
    pmoves/docker-compose.hardened.yml    -> unknown tag '!override'

Those are not broken files. `!reset` and `!override` are Compose's own
merge-behaviour tags for overlay files. A validator that rejected them would be
wrong about valid input, which is the fastest way to get a check disabled. They
are registered below and carry their argument through unchanged - this tool
judges syntax, not merge semantics.

WHAT IT CHECKS
  1. every tracked compose file parses as YAML
  2. every one of them is a mapping at the top level (a file that parses to a
     bare string or None is not a compose file, and would sail through a naive
     "did it raise?" check)
  3. at least one file was found. A glob that silently matches nothing is the
     failure this whole tool exists to stop: zero files parsed cleanly is not
     the same as success, though it reports identically.

EXIT CODES
  0  every file parsed
  1  a file failed to parse, or the file list came back empty
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("PyYAML required: uv run --with pyyaml python <this file>\n")
    raise SystemExit(1)

PATTERNS = ("pmoves/docker-compose*.yml", "pmoves/docker-compose*.yaml")

# Compose overlay merge tags. Registered so valid overlay files parse; the value
# is passed through untouched because this tool judges syntax only.
COMPOSE_TAGS = ("!reset", "!override")


class ComposeLoader(yaml.SafeLoader):
    """SafeLoader that understands Compose's overlay tags.

    Using `yaml.load(..., Loader=ComposeLoader)` rather than `yaml.safe_load`
    looks alarming, and a security linter flags it on sight. It is safe here for
    one specific reason: this derives from SafeLoader, so it inherits SafeLoader's
    constructor table and the `!!python/*` constructors are simply not in it.

    Verified rather than asserted - all three refused with ConstructorError:

        !!python/object/apply:os.system ["echo PWNED"]
        !!python/name:os.system
        !!python/object/apply:subprocess.Popen [["echo","PWNED"]]

    and `any('python' in str(k) for k in ComposeLoader.yaml_constructors)` is
    False. The only tags added are the two Compose ones below.

    If you ever need a tag whose constructor builds a Python object rather than
    passing data through, stop: that is the point where this becomes unsafe.
    """


def _passthrough(loader, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_mapping(node, deep=True)


for _tag in COMPOSE_TAGS:
    ComposeLoader.add_constructor(_tag, _passthrough)


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pmoves").is_dir() and (parent / ".git").exists():
            return parent
    return Path.cwd()


def tracked_files(root: Path, patterns):
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", *patterns],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if out.returncode != 0:
        sys.stderr.write("git ls-files failed: {}\n".format(out.stderr.strip()))
        return None
    return [root / line for line in out.stdout.split() if line]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    # Overridable so the checks can be exercised against fixtures. A validator
    # never shown rejecting anything is indistinguishable from one that always
    # says yes, and the real compose files cannot be broken to prove it.
    ap.add_argument("--root", type=Path, default=None, help="repo root to scan")
    ap.add_argument("--pattern", action="append", default=None, help="git ls-files pattern (repeatable)")
    a = ap.parse_args()

    root = a.root.resolve() if a.root else repo_root()
    patterns = a.pattern or list(PATTERNS)
    files = tracked_files(root, patterns)
    if files is None:
        return 1
    if not files:
        print(
            "compose yaml validate: NO FILES MATCHED {} - refusing to report success "
            "on an empty set".format(" ".join(patterns))
        )
        return 1

    problems = []
    for f in files:
        try:
            doc = yaml.load(f.read_text(encoding="utf-8"), Loader=ComposeLoader)  # noqa: S506 - ComposeLoader derives from SafeLoader
        except Exception as e:  # noqa: BLE001 - any parse failure is a finding
            problems.append((f, "{}: {}".format(type(e).__name__, str(e).splitlines()[0])))
            continue
        if not isinstance(doc, dict):
            problems.append((f, "parsed to {}, not a mapping".format(type(doc).__name__)))

    rel = lambda p: p.relative_to(root).as_posix()  # noqa: E731
    if problems:
        print("compose yaml validate: {} of {} file(s) failed".format(len(problems), len(files)))
        for f, err in problems:
            print("  - {}: {}".format(rel(f), err))
        return 1

    print("compose yaml validate: clean ({} compose files parsed)".format(len(files)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
