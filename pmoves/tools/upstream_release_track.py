#!/usr/bin/env python3
"""Resolve the newest upstream release for a tracked fork and check that the
PMOVES hardened branch already contains it.

Images follow upstream RELEASES, not a hand-bumped pin. This is the single
resolver the make targets (archon-build-latest, a0-release-resolve) and any
release-triggered workflow share, so "what is latest" has one answer.

    python3 tools/upstream_release_track.py archon            # shell KEY=VALUE lines
    python3 tools/upstream_release_track.py agent-zero --format json

Exit codes (fleet doctrine):
    0  the fork's hardened branch contains the latest upstream release
    1  finding: it does not (sync the fork first -- fleet-fork-sync road)
    3  could not measure (gh missing/unauthenticated, API error, bad data)

Every value printed is validated against a strict pattern before it is
emitted, because make targets eval this output.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys

COMPONENTS = {
    "archon": {
        "upstream": "coleam00/Archon",
        "fork": "POWERFULMOVES/PMOVES-Archon",
        "branch": "PMOVES.AI-Edition-Hardened",
    },
    "agent-zero": {
        "upstream": "agent0ai/agent-zero",
        "fork": "POWERFULMOVES/PMOVES-Agent-Zero",
        "branch": "PMOVES.AI-Edition-Hardened",
    },
}

SAFE = re.compile(r"^[A-Za-z0-9._/-]{1,128}$")
SHA = re.compile(r"^[0-9a-f]{40}$")


class CouldNotMeasure(Exception):
    pass


def gh(path: str, jq: str) -> str:
    try:
        out = subprocess.run(
            ["gh", "api", path, "--jq", jq],
            check=True, capture_output=True, text=True, timeout=60,
        )
    except subprocess.CalledProcessError as exc:
        raise CouldNotMeasure(f"gh api {path}: {exc.stderr.strip()[:300]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise CouldNotMeasure(f"gh api {path}: timeout") from exc
    return out.stdout.strip()


def resolve(component: str) -> dict:
    cfg = COMPONENTS[component]
    tag = gh(f"repos/{cfg['upstream']}/releases/latest", ".tag_name")
    if not SAFE.match(tag):
        raise CouldNotMeasure(f"unexpected release tag {tag!r}")
    tag_sha = gh(f"repos/{cfg['upstream']}/commits/{tag}", ".sha")
    fork_sha = gh(f"repos/{cfg['fork']}/git/ref/heads/{cfg['branch']}", ".object.sha")
    for name, val in (("tag_sha", tag_sha), ("fork_sha", fork_sha)):
        if not SHA.match(val):
            raise CouldNotMeasure(f"unexpected {name} {val!r}")
    # Forks share the upstream object network, so the fork can compare against
    # the release commit. "ahead"/"identical" == the branch contains the release.
    status = gh(f"repos/{cfg['fork']}/compare/{tag_sha}...{fork_sha}", ".status")
    if status not in {"ahead", "identical", "behind", "diverged"}:
        raise CouldNotMeasure(f"unexpected compare status {status!r}")
    version = tag[1:] if tag.startswith("v") else tag
    return {
        "COMPONENT": component,
        "UPSTREAM": cfg["upstream"],
        "FORK": cfg["fork"],
        "FORK_BRANCH": cfg["branch"],
        "RELEASE_TAG": tag,
        "RELEASE_VERSION": version,
        "RELEASE_SHA": tag_sha,
        "FORK_SHA": fork_sha,
        "FORK_SHA8": fork_sha[:8],
        "COMPARE": status,
        "CONTAINS_RELEASE": "yes" if status in {"ahead", "identical"} else "no",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("component", choices=sorted(COMPONENTS))
    ap.add_argument("--format", choices=("shell", "json"), default="shell")
    args = ap.parse_args()
    if not shutil.which("gh"):
        print("COULD-NOT-MEASURE: gh CLI not found", file=sys.stderr)
        return 3
    try:
        info = resolve(args.component)
    except CouldNotMeasure as exc:
        print(f"COULD-NOT-MEASURE: {exc}", file=sys.stderr)
        return 3
    if args.format == "json":
        print(json.dumps(info, indent=2))
    else:
        for key, val in info.items():
            if not SAFE.match(val):
                print(f"COULD-NOT-MEASURE: unsafe value for {key}", file=sys.stderr)
                return 3
            print(f"{key}={val}")
    if info["CONTAINS_RELEASE"] != "yes":
        print(
            f"FINDING: {info['FORK']}@{info['FORK_BRANCH']} ({info['FORK_SHA8']}) does not "
            f"contain upstream {info['RELEASE_TAG']} (compare={info['COMPARE']}). "
            "Sync the fork first (fleet-fork-sync road).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
