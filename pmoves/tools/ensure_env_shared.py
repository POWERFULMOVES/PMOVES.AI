#!/usr/bin/env python3
"""Create env.shared from template when missing (shell-agnostic)."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pmoves.tools._secrets_common import env_write_lock  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ensure env.shared exists for local workflows.")
    parser.add_argument("--env-file", default="env.shared", help="Target env file path.")
    parser.add_argument("--template", default="env.shared.example", help="Template file path.")
    parser.add_argument(
        "--invidious-keys",
        choices=("gate", "mint", "fix"),
        default="gate",
        help="Invidious key preflight mode. gate (default) never writes and never "
        "blocks: ensure-env-shared is a prerequisite of read-only goals too. mint "
        "writes absent keys; fix also rotates published/invalid ones (funnel only).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env_file = Path(args.env_file)
    # Seed, brand_defaults and the Invidious preflight are each a read-modify-write
    # of the same file. Hold the directory's env write lock across all three so a
    # parallel (make -j) invidious-keys-preflight cannot interleave with them. The
    # preflight child inherits PMOVES_ENV_WRITE_LOCK_HELD and does not re-acquire.
    env_file.parent.mkdir(parents=True, exist_ok=True)
    with env_write_lock(env_file):
        return _ensure(env_file, Path(args.template), args.invidious_keys)


def _create_private(env_file: Path, content: bytes) -> None:
    """Create *env_file* as 0600 in one step (O_CREAT|O_EXCL), whatever the umask.

    copyfile/touch created it 0644 -- world-readable -- and every secret the
    funnel later writes into it inherited that mode (atomic writes preserve the
    original's mode). O_EXCL also means a file that appeared meanwhile is never
    truncated.
    """
    env_file.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.fchmod(fd, 0o600)  # the mode argument is filtered by umask; pin it
        os.write(fd, content)
    finally:
        os.close(fd)


def _report_loose_mode(env_file: Path) -> None:
    """Name an EXISTING env file readable by group/others; never chmod it.

    Changing the mode of a live file is the operator's decision (a container or
    another user may read it on purpose). Closed message: path and octal mode
    only, never content.
    """
    try:
        mode = env_file.stat().st_mode & 0o777
    except OSError:
        return
    if mode & 0o077:
        print(
            f"WARNING: {env_file} is mode {mode:04o} (readable beyond its owner); "
            f"left unchanged. To restrict: chmod 600 {env_file}"
        )


def _ensure(env_file: Path, template: Path, invidious_keys: str = "gate") -> int:
    if not env_file.exists() and template.exists():
        print(f"-> Seeding {env_file} from {template}")
        _create_private(env_file, template.read_bytes())
    elif not env_file.exists():
        print(f"-> Creating empty {env_file} (no template found)")
        _create_private(env_file, b"")
    else:
        _report_loose_mode(env_file)

    brand_defaults = Path(__file__).resolve().with_name("brand_defaults.py")
    if brand_defaults.exists():
        generated_path = env_file.parent / ".env.generated"
        subprocess.run(
            [
                sys.executable,
                str(brand_defaults),
                "--env-file",
                str(env_file),
                "--generated-env-file",
                str(generated_path),
            ],
            check=True,
        )

    # The Invidious keys have exactly one owner: the preflight. Its MODE is the
    # caller's choice. Default GATE: read-only and never blocking, because
    # ensure-env-shared is a prerequisite of read-only goals (auth-check,
    # a0-model-sync-check, cf-pages-status, ...) that must not rotate a key under
    # running containers, nor fail over a key they never use. The funnel's
    # secrets-ensure-generated opts into FIX (Makefile target-specific
    # ENSURE_ENV_INVIDIOUS_KEYS). In mint/fix, exit 1 means compose's ${VAR:?}
    # would fail anyway, so it is passed through; 3 never blocks.
    preflight = Path(__file__).resolve().with_name("invidious_keys_preflight.py")
    if preflight.exists():
        flag = {"gate": ["--gate"], "mint": ["--mint"], "fix": []}[invidious_keys]
        rc = subprocess.run(
            [sys.executable, str(preflight), *flag, "--env-file", str(env_file)], check=False
        ).returncode
        if rc == 1 and invidious_keys != "gate":
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
