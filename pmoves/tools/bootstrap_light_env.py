#!/usr/bin/env python3
"""Bootstrap a lightweight PMOVES runtime environment (uv-first)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PMOVES_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create/update a lightweight local venv for PMOVES tooling and "
            "validate baseline host commands."
        )
    )
    parser.add_argument(
        "--venv",
        default=".venv-pmoves",
        help="Virtual environment path relative to pmoves/ (default: .venv-pmoves).",
    )
    parser.add_argument(
        "--requirements",
        action="append",
        default=None,
        help=(
            "Requirements file(s) relative to pmoves/ (repeatable). "
            "Defaults to tools/requirements-lite.txt when omitted."
        ),
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Create/check the venv but skip package installation.",
    )
    parser.add_argument(
        "--strict-tools",
        action="store_true",
        help="Fail when make/docker/uv are missing on host.",
    )
    return parser.parse_args()


def resolve_under_pmoves(path_like: str) -> Path:
    candidate = Path(path_like).expanduser()
    if candidate.is_absolute():
        return candidate
    return (PMOVES_ROOT / candidate).resolve()


def run(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"command failed (exit={exc.returncode}): {' '.join(cmd)}"
        ) from exc


def venv_python_path(venv_path: Path) -> Path:
    if os.name == "nt":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def ensure_venv(venv_path: Path) -> tuple[str | None, Path]:
    uv_bin = shutil.which("uv")
    if not venv_path.exists():
        if uv_bin:
            run([uv_bin, "venv", str(venv_path)])
        else:
            run([sys.executable, "-m", "venv", str(venv_path)])

    py = venv_python_path(venv_path)
    if not py.exists():
        raise FileNotFoundError(f"Unable to resolve venv python: {py}")
    return uv_bin, py


def install_requirements(
    *,
    uv_bin: str | None,
    venv_python: Path,
    requirement_files: list[Path],
) -> None:
    for req in requirement_files:
        if not req.exists():
            print(f"WARN: requirements file not found: {req}")
            continue
        print(f"Installing dependencies from {req}")
        if uv_bin:
            run([uv_bin, "pip", "install", "--python", str(venv_python), "-r", str(req)])
        else:
            run([str(venv_python), "-m", "pip", "install", "-r", str(req)])


def host_tool_report(strict: bool) -> int:
    tool_names = ("make", "docker", "uv")
    missing: list[str] = []
    print("Host tool check:")
    for name in tool_names:
        binary = shutil.which(name)
        if binary:
            print(f"  OK     {name}: {binary}")
        else:
            print(f"  MISSING {name}")
            missing.append(name)
    if strict and missing:
        print(f"ERROR: missing required host tools: {', '.join(missing)}")
        return 1
    return 0


def activation_hint(venv_path: Path) -> None:
    if os.name == "nt":
        print(f"Activate (PowerShell): {venv_path}\\Scripts\\Activate.ps1")
    else:
        print(f"Activate (bash/zsh): source {venv_path}/bin/activate")


def main() -> int:
    args = parse_args()
    venv_path = resolve_under_pmoves(args.venv)
    requirement_inputs = args.requirements or ["tools/requirements-lite.txt"]
    req_files = [resolve_under_pmoves(item) for item in requirement_inputs]

    print(f"PMOVES root: {PMOVES_ROOT}")
    print(f"Repository root: {REPO_ROOT}")
    print(f"Venv path: {venv_path}")

    uv_bin, venv_python = ensure_venv(venv_path)
    print(f"Using venv python: {venv_python}")
    print(f"uv available: {'yes' if uv_bin else 'no'}")

    if not args.skip_install:
        install_requirements(uv_bin=uv_bin, venv_python=venv_python, requirement_files=req_files)

    activation_hint(venv_path)
    return host_tool_report(strict=args.strict_tools)


if __name__ == "__main__":
    raise SystemExit(main())
