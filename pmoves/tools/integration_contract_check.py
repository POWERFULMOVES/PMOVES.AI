#!/usr/bin/env python3
"""Validate PMOVES integration overlays against the contract layout."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REQUIRED_ENTRIES: list[tuple[str, str]] = [
    ("README.md", "file"),
    ("compose/docker-compose.pmoves-net.yml", "file"),
    ("tools/validate-submodule.sh", "file"),
    ("tools/submodule-sitrep.sh", "file"),
    ("models/profiles", "dir"),
    ("models/mappings", "dir"),
    ("n8n/flows", "dir"),
    ("events/subjects.yaml", "file"),
    ("secrets/labels.yaml", "file"),
    ("auth/bootstrap.sh", "file"),
    ("docs/OPERATIONS.md", "file"),
]

REQUIRED_SUBJECTS = {
    "pmoves.announcer.event.v1",
    "mesh.gpu.model.loaded.v1",
    "mesh.gpu.model.unloaded.v1",
}

HOOK_TERMS = {
    "pmoves-announcer",
    "tensorzero-gateway",
    "model-registry",
    "gpu-orchestrator",
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _collect_subjects(subjects_file: Path) -> set[str]:
    pattern = re.compile(r"^\s*-\s*name:\s*([A-Za-z0-9._-]+)\s*$")
    subjects: set[str] = set()
    for line in _read_text(subjects_file).splitlines():
        match = pattern.match(line)
        if match:
            subjects.add(match.group(1))
    return subjects


def _resolve_overlay_root(path: Path) -> Path:
    nested = path / "pmoves-integrations"
    if nested.is_dir():
        return nested
    return path


def _validate_path(path: Path, strict_hooks: bool) -> tuple[list[str], list[str], Path]:
    errors: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return [f"path does not exist: {path}"], [], path
    if not path.is_dir():
        return [f"path is not a directory: {path}"], [], path

    overlay_root = _resolve_overlay_root(path)

    for rel_path, entry_type in REQUIRED_ENTRIES:
        candidate = overlay_root / rel_path
        if entry_type == "file" and not candidate.is_file():
            errors.append(f"missing file: {candidate}")
        if entry_type == "dir" and not candidate.is_dir():
            errors.append(f"missing directory: {candidate}")

    subjects_file = overlay_root / "events" / "subjects.yaml"
    if subjects_file.is_file():
        declared = _collect_subjects(subjects_file)
        missing_subjects = sorted(REQUIRED_SUBJECTS - declared)
        if missing_subjects:
            errors.append(
                "missing required subjects: " + ", ".join(missing_subjects)
            )

    readme_file = overlay_root / "README.md"
    if readme_file.is_file():
        readme_text = _read_text(readme_file).lower()
        missing_terms = sorted(t for t in HOOK_TERMS if t not in readme_text)
        if missing_terms:
            message = "README.md missing hook terms: " + ", ".join(missing_terms)
            if strict_hooks:
                errors.append(message)
            else:
                warnings.append(message)

    auth_bootstrap = overlay_root / "auth" / "bootstrap.sh"
    if auth_bootstrap.is_file() and os.name != "nt":
        if not os.access(auth_bootstrap, os.X_OK):
            warnings.append(f"auth bootstrap is not executable: {auth_bootstrap}")

    return errors, warnings, overlay_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a pmoves-integrations overlay against required layout, "
            "subjects, and hook references."
        )
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Integration overlay path(s), e.g. pmoves/integrations/_template/pmoves-integrations",
    )
    parser.add_argument(
        "--strict-hooks",
        action="store_true",
        help="Treat missing README hook terms as failures.",
    )
    args = parser.parse_args()

    overall_errors = 0
    for raw_path in args.paths:
        target = Path(raw_path).resolve()
        errors, warnings, overlay_root = _validate_path(
            target, strict_hooks=args.strict_hooks
        )

        print(f"[integration-contract] {target}")
        if overlay_root != target:
            print(f"  INFO: using nested overlay root {overlay_root}")
        if warnings:
            for warning in warnings:
                print(f"  WARN: {warning}")
        if errors:
            for error in errors:
                print(f"  FAIL: {error}")
            overall_errors += len(errors)
        else:
            print("  PASS: contract checks succeeded")

    return 1 if overall_errors else 0


if __name__ == "__main__":
    sys.exit(main())
