#!/usr/bin/env python3
"""Deterministic submodule integrity gate for local/CI checks."""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GITMODULES = REPO_ROOT / ".gitmodules"


def normalize_path(path: str) -> str:
    """Normalize git paths for cross-platform integrity comparisons."""
    value = path.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    if os.name == "nt":
        value = value.lower()
    return value


@dataclass
class SubmoduleStatus:
    prefix: str
    commit: str
    path: str
    detail: str


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def parse_status(stdout: str) -> list[SubmoduleStatus]:
    rows: list[SubmoduleStatus] = []
    for raw in stdout.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        prefix = line[0]
        payload = line[1:].strip()
        parts = payload.split(maxsplit=2)
        if len(parts) < 2:
            continue
        rows.append(
            SubmoduleStatus(
                prefix=prefix,
                commit=parts[0],
                path=parts[1],
                detail=parts[2] if len(parts) > 2 else "",
            )
        )
    return rows


def list_gitlinks() -> set[str]:
    proc = run_git("ls-files", "--stage")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git ls-files --stage failed")
    paths: set[str] = set()
    for raw in proc.stdout.splitlines():
        if not raw.startswith("160000 "):
            continue
        parts = raw.split("\t", maxsplit=1)
        if len(parts) != 2:
            continue
        paths.add(normalize_path(parts[1]))
    return paths


def list_mapped_paths() -> set[str]:
    proc = run_git("config", "-f", str(GITMODULES), "--get-regexp", r"^submodule\..*\.path$")
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError(proc.stderr.strip() or ".gitmodules path lookup failed")
    paths: set[str] = set()
    for raw in proc.stdout.splitlines():
        parts = raw.split(maxsplit=1)
        if len(parts) != 2:
            continue
        paths.add(normalize_path(parts[1]))
    return paths


def fail_list(title: str, items: list[str]) -> str:
    if not items:
        return f"{title}: none"
    rendered = "\n".join(f"  - {item}" for item in items)
    return f"{title}:\n{rendered}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-uninitialized",
        action="store_true",
        default=False,
        help="Allow '-' submodule status entries (default: fail on uninitialized).",
    )
    parser.add_argument(
        "--check-recursive",
        action="store_true",
        help="Also validate `git submodule status --recursive` exit code.",
    )
    parser.add_argument(
        "--required-initialized",
        action="append",
        default=[],
        help="Require this submodule path to be initialized (can be repeated).",
    )
    args = parser.parse_args()

    errors: list[str] = []

    try:
        gitlinks = list_gitlinks()
        mapped = list_mapped_paths()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 2

    missing_mappings = sorted(gitlinks - mapped)
    if missing_mappings:
        errors.append(fail_list("Unmapped gitlinks", missing_mappings))

    status = run_git("submodule", "status")
    if status.returncode != 0:
        print("ERROR: `git submodule status` failed")
        print(status.stderr.strip() or status.stdout.strip())
        return 2
    rows = parse_status(status.stdout)

    drifted = sorted(row.path for row in rows if row.prefix == "+")
    conflicted = sorted(row.path for row in rows if row.prefix.upper() == "U")
    uninitialized = sorted(row.path for row in rows if row.prefix == "-")

    if drifted:
        errors.append(fail_list("Drifted submodules (+)", drifted))
    if conflicted:
        errors.append(fail_list("Conflicted submodules (U)", conflicted))
    if uninitialized and not args.allow_uninitialized:
        errors.append(fail_list("Uninitialized submodules (-)", uninitialized))

    if args.required_initialized:
        required_set = {normalize_path(path) for path in args.required_initialized}
        uninitialized_set = {normalize_path(path) for path in uninitialized}
        row_paths_set = {normalize_path(row.path) for row in rows}
        missing_required = sorted(
            path for path in required_set if path in uninitialized_set or path not in row_paths_set
        )
        if missing_required:
            errors.append(fail_list("Required initialized submodules missing", missing_required))

    if args.check_recursive:
        recursive = run_git("submodule", "status", "--recursive")
        if recursive.returncode != 0:
            msg = recursive.stderr.strip() or recursive.stdout.strip() or "recursive submodule status failed"
            errors.append(f"Recursive check failed:\n  - {msg}")

    if errors:
        print("FAIL: submodule integrity check failed")
        for issue in errors:
            print(issue)
        return 1

    print("PASS: submodule integrity check passed")
    print(f"  - gitlinks mapped (normalized): {len(gitlinks)}")
    print(f"  - uninitialized: {len(uninitialized)}")
    print(f"  - drifted: {len(drifted)}")
    print(f"  - conflicts: {len(conflicted)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
