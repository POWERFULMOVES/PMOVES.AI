#!/usr/bin/env python3
"""Unified PMOVES env setup entrypoint with production-oriented diagnostics."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PMOVES_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run PMOVES environment setup through scripts/bootstrap_env.py and "
            "optionally execute strict drift + showtime diagnostics."
        )
    )
    parser.add_argument(
        "-y",
        "--yes",
        "--accept-defaults",
        action="store_true",
        dest="accept_defaults",
        help="Use default/generated values for required fields without prompting.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate required values only; do not write files.",
    )
    parser.add_argument(
        "--skip-env-doctor",
        action="store_true",
        help="Skip strict Supabase env drift checks after setup.",
    )
    parser.add_argument(
        "--skip-showtime",
        action="store_true",
        help="Skip quick retro/showtime terminal diagnostics.",
    )
    parser.add_argument(
        "--theme",
        default=None,
        help="Theme forwarded to retro flight check (default: RETRO_THEME_QUICK or cb).",
    )
    parser.add_argument(
        "--service",
        action="append",
        default=[],
        help="Limit setup/check to one or more service ids from bootstrap/registry.json.",
    )
    parser.add_argument(
        "--registry",
        default=None,
        help="Path to bootstrap registry JSON (defaults to scripts/bootstrap_env.py default).",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Compatibility no-op (retained for old env_setup callers).",
    )
    parser.add_argument(
        "--from",
        dest="provider",
        default=None,
        help="Compatibility no-op (external provider pull is now handled outside this tool).",
    )
    return parser.parse_args()


def _python() -> str:
    return sys.executable or "python"


def _run(cmd: list[str], *, label: str) -> int:
    print(f"\n== {label} ==")
    print(" ".join(cmd))
    completed = subprocess.run(cmd, cwd=PMOVES_ROOT)
    return int(completed.returncode)


def _bootstrap_cmd(args: argparse.Namespace, *, check_only: bool) -> list[str]:
    cmd = [_python(), str(PMOVES_ROOT / "scripts" / "bootstrap_env.py")]
    if args.registry:
        cmd.extend(["--registry", args.registry])
    for service in args.service:
        cmd.extend(["--service", service])
    if check_only:
        cmd.append("--check")
    elif args.accept_defaults or not sys.stdin.isatty():
        cmd.append("--accept-defaults")
    return cmd


def main() -> int:
    args = parse_args()

    if args.force:
        print("Note: --force is deprecated in unified setup and is treated as a no-op.")
    if args.provider:
        print("Note: --from is deprecated in unified setup and is treated as a no-op.")

    print("PMOVES env setup (unified)")
    print(f"Root: {PMOVES_ROOT}")
    print(f"Mode: {'check-only' if args.check_only else 'setup'}")
    if args.service:
        print(f"Services: {', '.join(args.service)}")

    rc = _run(_bootstrap_cmd(args, check_only=args.check_only), label="Bootstrap Registry")
    if rc != 0:
        return rc

    if args.check_only:
        return 0

    rc = _run(_bootstrap_cmd(args, check_only=True), label="Post-Setup Required Key Check")
    if rc != 0:
        return rc

    if not args.skip_env_doctor:
        rc = _run(
            [_python(), str(PMOVES_ROOT / "scripts" / "supabase" / "env_doctor.py"), "--strict"],
            label="Supabase Env Doctor (strict)",
        )
        if rc != 0:
            return rc

    if not args.skip_showtime:
        theme = args.theme or "cb"
        _run(
            [
                _python(),
                str(PMOVES_ROOT / "tools" / "flightcheck" / "retro_flightcheck.py"),
                "--quick",
                "--theme",
                theme,
            ],
            label="Showtime Quick Diagnostics",
        )

    print("\nEnvironment setup completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
