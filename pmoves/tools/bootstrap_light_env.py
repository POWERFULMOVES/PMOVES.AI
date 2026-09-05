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
        "--python",
        default="3.11",
        help=(
            "Python version for fresh venv creation (default: 3.11 — the fleet "
            "standard; pyproject requires-python is >=3.11). Ignored when the "
            "venv already exists."
        ),
    )
    parser.add_argument(
        "--requirements",
        action="append",
        default=["tools/requirements-lite.txt"],
        help="Requirements file(s) relative to pmoves/ (repeatable).",
    )
    parser.add_argument(
        "--with-embeddings",
        action="store_true",
        help=(
            "Also install tools/requirements-lite-embeddings.txt (torch stack, "
            "hundreds of MB — only for embedding-decode tools; the core lite "
            "venv is deliberately CUDA-free)."
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
    subprocess.run(cmd, check=True)


def venv_python_path(venv_path: Path) -> Path:
    if os.name == "nt":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def resolve_pinned_interpreter(python_pin: str) -> str | None:
    """Find an interpreter matching `python_pin` (e.g. "3.11") without uv.

    Tries the version-suffixed name first, then the Windows launcher. Returns
    None when nothing matching is on the host -- the caller decides what that
    means.
    """
    exact = shutil.which(f"python{python_pin}")
    if exact:
        return exact
    if os.name == "nt":
        launcher = shutil.which("py")
        if launcher:
            probe = subprocess.run(
                [launcher, f"-{python_pin}", "-c", "import sys; print(sys.executable)"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if probe.returncode == 0 and probe.stdout.strip():
                return probe.stdout.strip()
    return None


def ensure_venv(
    venv_path: Path, python_pin: str = "3.11", *, strict: bool = False
) -> tuple[str | None, Path]:
    uv_bin = shutil.which("uv")
    if not venv_path.exists():
        if uv_bin:
            # Pin the interpreter: bare `uv venv` grabs uv's newest managed
            # CPython (3.14.x), which produced broken venvs on fleet nodes.
            run([uv_bin, "venv", "--python", python_pin, str(venv_path)])
        else:
            # No uv is a supported state for non-strict `env-bootstrap-lite`,
            # but --python must not be silently dropped here: the whole point of
            # the pin is that an off-version interpreter produces exactly the
            # broken venv this script exists to prevent. Resolve the pinned
            # interpreter from the host; only fall back to sys.executable, and
            # only loudly, when it cannot be found.
            interpreter = resolve_pinned_interpreter(python_pin)
            if interpreter is None:
                running = f"{sys.version_info.major}.{sys.version_info.minor}"
                if running != python_pin:
                    msg = (
                        f"requested Python {python_pin} but neither uv nor a "
                        f"python{python_pin} interpreter is on PATH; the venv would be "
                        f"built with Python {running} ({sys.executable})"
                    )
                    if strict:
                        raise SystemExit(
                            f"ERROR: {msg}.\n"
                            f"       Install uv, or install Python {python_pin}, "
                            f"or pass --python {running} to accept it."
                        )
                    print(f"WARN: {msg} — proceeding unpinned (--strict-tools would fail here)")
                interpreter = sys.executable
            run([interpreter, "-m", "venv", str(venv_path)])

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
    dotnet_ok, dotnet_detail = has_dotnet_sdk(8)
    if dotnet_ok:
        print(f"  OK     dotnet-sdk: {dotnet_detail}")
    else:
        print("  MISSING dotnet-sdk: required .NET SDK 8+ not found")
        print("          Install: winget install --id Microsoft.DotNet.SDK.8 --exact")
        missing.append("dotnet-sdk")
    if strict and missing:
        print(f"ERROR: missing required host tools: {', '.join(missing)}")
        return 1
    return 0


def has_dotnet_sdk(min_major: int) -> tuple[bool, str]:
    dotnet_bin = shutil.which("dotnet")
    if not dotnet_bin:
        return False, "dotnet CLI not found"
    try:
        completed = subprocess.run(
            [dotnet_bin, "--list-sdks"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        return False, f"failed to query SDKs: {exc}"
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        return False, "no SDKs installed"
    majors: list[int] = []
    for line in lines:
        version_token = line.split(" ", 1)[0]
        major_token = version_token.split(".", 1)[0]
        if major_token.isdigit():
            majors.append(int(major_token))
    if not majors or max(majors) < min_major:
        return False, f"highest SDK major {max(majors) if majors else 'none'}"
    return True, lines[0]


def activation_hint(venv_path: Path) -> None:
    if os.name == "nt":
        print(f"Activate (PowerShell): {venv_path}\\Scripts\\Activate.ps1")
    else:
        print(f"Activate (bash/zsh): source {venv_path}/bin/activate")


def main() -> int:
    args = parse_args()
    venv_path = resolve_under_pmoves(args.venv)
    req_files = [resolve_under_pmoves(item) for item in args.requirements]
    if args.with_embeddings:
        req_files.append(resolve_under_pmoves("tools/requirements-lite-embeddings.txt"))

    print(f"PMOVES root: {PMOVES_ROOT}")
    print(f"Repository root: {REPO_ROOT}")
    print(f"Venv path: {venv_path}")

    uv_bin, venv_python = ensure_venv(
        venv_path, python_pin=args.python, strict=args.strict_tools
    )
    print(f"Using venv python: {venv_python}")
    print(f"uv available: {'yes' if uv_bin else 'no'}")

    if not args.skip_install:
        install_requirements(uv_bin=uv_bin, venv_python=venv_python, requirement_files=req_files)

    activation_hint(venv_path)
    return host_tool_report(strict=args.strict_tools)


if __name__ == "__main__":
    raise SystemExit(main())
