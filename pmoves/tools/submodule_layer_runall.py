#!/usr/bin/env python3
"""Run deterministic submodule-layer validation one module at a time."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from submodule_utils import parse_gitmodules_rows  # type: ignore


REPO_ROOT = Path(__file__).resolve().parents[2]
GITMODULES = REPO_ROOT / ".gitmodules"
VALIDATOR = REPO_ROOT / "pmoves" / "tools" / "submodule_layer_validate.py"
DEFAULT_MANIFEST = REPO_ROOT / "pmoves" / "configs" / "submodule_layer_validation_manifest.json"
DEFAULT_OUT_DIR = REPO_ROOT / "pmoves" / "docs" / "evidence" / "submodule_layer"
DEFAULT_SUMMARY_JSON = REPO_ROOT / "pmoves" / "docs" / "evidence" / "submodule_layer_runall.json"
DEFAULT_SUMMARY_MD = REPO_ROOT / "pmoves" / "docs" / "SUBMODULE_LAYER_RUNALL.md"


@dataclass
class ModuleRun:
    name: str
    path: str
    returncode: int
    errors: int
    warnings: int
    json_path: Path
    md_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--strict", action="store_true", help="Fail run when warnings exist.")
    parser.add_argument("--allow-uninitialized", action="store_true")
    parser.add_argument("--skip-python-compile", action="store_true")
    parser.add_argument("--skip-remote-check", action="store_true")
    parser.add_argument("--check-uninitialized-remote", action="store_true")
    parser.add_argument("--remote-timeout", type=float, default=20.0)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_SUMMARY_MD)
    parser.add_argument("--match", default="", help="Only include modules matching this substring in name/path.")
    return parser.parse_args()


def parse_gitmodules(path: Path) -> list[tuple[str, str]]:
    return [(row["name"], row["path"]) for row in parse_gitmodules_rows(path)]


def sanitize(path_value: str) -> str:
    return path_value.replace("\\", "__").replace("/", "__").replace(":", "_")


def read_summary(json_path: Path) -> tuple[int, int]:
    if not json_path.exists():
        print(f"WARN: summary json missing: {json_path}")
        return (1, 0)
    try:
        data = json.loads(json_path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError as exc:
        print(f"WARN: summary json malformed: {json_path} ({exc})")
        return (1, 0)
    except Exception as exc:
        print(f"WARN: unable to parse summary json: {json_path} ({exc})")
        return (1, 0)
    summary = data.get("summary", {}) if isinstance(data, dict) else {}
    return int(summary.get("errors", 0)), int(summary.get("warnings", 0))


def render_summary_md(runs: list[ModuleRun], manifest: Path) -> str:
    total = len(runs)
    err_total = sum(run.errors for run in runs)
    warn_total = sum(run.warnings for run in runs)
    lines = [
        "# Submodule Layer Run-All",
        "",
        "## Summary",
        f"- Manifest: `{manifest}`",
        f"- Modules checked: **{total}**",
        f"- Total errors: **{err_total}**",
        f"- Total warnings: **{warn_total}**",
        "",
        "## Per-module results",
        "| Module | Path | Exit | Errors | Warnings | JSON | Report |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for run in runs:
        lines.append(
            f"| `{run.name}` | `{run.path}` | `{run.returncode}` | `{run.errors}` | `{run.warnings}` | "
            f"`{run.json_path.relative_to(REPO_ROOT).as_posix()}` | "
            f"`{run.md_path.relative_to(REPO_ROOT).as_posix()}` |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    modules = parse_gitmodules(GITMODULES)
    match_filter = args.match.strip().lower()
    if match_filter:
        modules = [
            (name, path)
            for name, path in modules
            if match_filter in name.lower() or match_filter in path.lower()
        ]
    if not modules:
        print("No submodules matched selection.")
        return 2

    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_json = args.summary_json.resolve()
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_md = args.summary_md.resolve()
    summary_md.parent.mkdir(parents=True, exist_ok=True)

    runs: list[ModuleRun] = []
    for name, module_path in modules:
        slug = sanitize(module_path)
        out_json = out_dir / f"{slug}.json"
        out_md = out_dir / f"{slug}.md"
        cmd = [
            sys.executable,
            str(VALIDATOR),
            "--manifest",
            str(args.manifest.resolve()),
            "--only",
            module_path,
            "--output-json",
            str(out_json),
            "--output-md",
            str(out_md),
            "--remote-timeout",
            str(args.remote_timeout),
        ]
        if args.strict:
            cmd.append("--strict")
        if args.allow_uninitialized:
            cmd.append("--allow-uninitialized")
        if args.skip_python_compile:
            cmd.append("--skip-python-compile")
        if args.skip_remote_check:
            cmd.append("--skip-remote-check")
        if args.check_uninitialized_remote:
            cmd.append("--check-uninitialized-remote")

        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), text=True, capture_output=True, check=False)
        errors, warnings = read_summary(out_json)
        runs.append(
            ModuleRun(
                name=name,
                path=module_path,
                returncode=proc.returncode,
                errors=errors,
                warnings=warnings,
                json_path=out_json,
                md_path=out_md,
            )
        )
        status = "ok" if proc.returncode == 0 else "fail"
        print(f"[{status}] {module_path} errors={errors} warnings={warnings}")

    data = {
        "manifest": str(args.manifest.resolve()),
        "modules_checked": len(runs),
        "total_errors": sum(run.errors for run in runs),
        "total_warnings": sum(run.warnings for run in runs),
        "runs": [
            {
                "name": run.name,
                "path": run.path,
                "returncode": run.returncode,
                "errors": run.errors,
                "warnings": run.warnings,
                "json_path": str(run.json_path.relative_to(REPO_ROOT).as_posix()),
                "md_path": str(run.md_path.relative_to(REPO_ROOT).as_posix()),
            }
            for run in runs
        ],
    }
    summary_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
    summary_md.write_text(render_summary_md(runs, args.manifest.resolve()), encoding="utf-8")
    print(f"Wrote {summary_json.relative_to(REPO_ROOT).as_posix()}")
    print(f"Wrote {summary_md.relative_to(REPO_ROOT).as_posix()}")

    if any(run.returncode != 0 for run in runs):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
