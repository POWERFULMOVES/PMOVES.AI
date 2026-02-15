#!/usr/bin/env python3
"""
Check GitHub self-hosted runner availability for PMOVES CI lanes.

By default this reports status in warning mode (always exit 0). Use --strict to
exit non-zero when required runner label groups are not online.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_GROUPS = (
    "self-hosted,vps",
    "self-hosted,ai-lab,gpu",
)
RUNS_ON_LIST_RE = re.compile(r"runs-on:\s*\[([^\]]+)\]", re.IGNORECASE)
RUNS_ON_SINGLE_RE = re.compile(r"runs-on:\s*([A-Za-z0-9_-]+)", re.IGNORECASE)


@dataclass
class Runner:
    name: str
    status: str
    busy: bool
    labels: set[str]

    @property
    def online(self) -> bool:
        return self.status.lower() == "online"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check GitHub Actions runner availability for required label groups."
    )
    parser.add_argument(
        "--repo",
        default=os.getenv("GITHUB_REPOSITORY", "POWERFULMOVES/PMOVES.AI"),
        help="GitHub repository in OWNER/REPO format (default: %(default)s).",
    )
    parser.add_argument(
        "--group",
        action="append",
        dest="groups",
        help=(
            "Required runner labels as a comma-separated group. "
            "Repeat for multiple groups."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when required groups are missing or query fails.",
    )
    parser.add_argument(
        "--discover-workflow-groups",
        action="store_true",
        help=(
            "Discover self-hosted runner label groups from local workflow files "
            "(.github/workflows/*.yml) and include them in the check."
        ),
    )
    parser.add_argument(
        "--workflows-dir",
        default=".github/workflows",
        help="Workflow directory for --discover-workflow-groups (default: %(default)s).",
    )
    return parser.parse_args()


def _normalize_group(raw: str) -> tuple[str, ...]:
    labels = tuple(sorted({part.strip() for part in raw.split(",") if part.strip()}))
    if not labels:
        raise ValueError(f"Empty label group: {raw!r}")
    return labels


def _extract_groups_from_workflow(path: Path) -> list[tuple[str, ...]]:
    groups: list[tuple[str, ...]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return groups

    for match in RUNS_ON_LIST_RE.finditer(text):
        parts = [part.strip().strip("'\"") for part in match.group(1).split(",")]
        labels = {part for part in parts if part}
        if "self-hosted" in labels:
            groups.append(tuple(sorted(labels)))

    for match in RUNS_ON_SINGLE_RE.finditer(text):
        label = match.group(1).strip().strip("'\"")
        if label == "self-hosted":
            groups.append(("self-hosted",))
    return groups


def discover_groups(workflows_dir: Path) -> list[tuple[str, ...]]:
    if not workflows_dir.exists():
        return []

    groups: set[tuple[str, ...]] = set()
    for path in sorted(workflows_dir.glob("*.yml")):
        for group in _extract_groups_from_workflow(path):
            groups.add(group)
    return sorted(groups)


def load_runners(repo: str) -> list[Runner]:
    cmd = [
        "gh",
        "api",
        f"repos/{repo}/actions/runners?per_page=100",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip() or "unknown gh api error"
        raise RuntimeError(err)

    payload = json.loads(proc.stdout)
    runners: list[Runner] = []
    for item in payload.get("runners", []):
        labels = {label.get("name", "") for label in item.get("labels", [])}
        runners.append(
            Runner(
                name=item.get("name", "unknown"),
                status=item.get("status", "unknown"),
                busy=bool(item.get("busy", False)),
                labels={l for l in labels if l},
            )
        )
    return runners


def main() -> int:
    args = parse_args()
    raw_groups = args.groups if args.groups else list(DEFAULT_GROUPS)
    try:
        groups = [_normalize_group(group) for group in raw_groups]
    except ValueError as exc:
        print(f"runner-check: invalid --group value: {exc}")
        return 2

    if args.discover_workflow_groups:
        discovered = discover_groups(Path(args.workflows_dir))
        if discovered:
            merged = {group for group in groups}
            merged.update(discovered)
            groups = sorted(merged)
        print(
            "runner-check: discovered groups from workflows: "
            f"{len(discovered)}"
        )

    print(f"runner-check: repo={args.repo}")
    print("runner-check: required groups:")
    for group in groups:
        print(f"  - {', '.join(group)}")

    try:
        runners = load_runners(args.repo)
    except Exception as exc:  # noqa: BLE001
        msg = f"runner-check: unable to query GitHub runners ({exc})"
        if args.strict:
            print(f"ERROR: {msg}")
            return 2
        print(f"WARN: {msg}")
        return 0

    if not runners:
        msg = "runner-check: no runners registered for repository"
        if args.strict:
            print(f"ERROR: {msg}")
            return 2
        print(f"WARN: {msg}")
        return 0

    print("runner-check: discovered runners:")
    for runner in sorted(runners, key=lambda r: r.name.lower()):
        state = "online" if runner.online else "offline"
        busy = "busy" if runner.busy else "idle"
        labels = ",".join(sorted(runner.labels))
        print(f"  - {runner.name}: {state}/{busy} [{labels}]")

    missing: list[tuple[str, ...]] = []
    for group in groups:
        matches = [
            runner
            for runner in runners
            if set(group).issubset(runner.labels) and runner.online
        ]
        if matches:
            names = ", ".join(sorted(r.name for r in matches))
            print(f"OK: {', '.join(group)} -> {names}")
        else:
            missing.append(group)
            print(f"MISSING: {', '.join(group)}")

    if missing:
        if args.strict:
            print("ERROR: required runner lanes are offline/missing.")
            return 2
        print("WARN: one or more runner lanes are unavailable (non-strict mode).")
    else:
        print("runner-check: all required runner lanes available.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
