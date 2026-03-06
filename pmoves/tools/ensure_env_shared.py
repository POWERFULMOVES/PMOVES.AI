#!/usr/bin/env python3
"""Create env.shared from template when missing (shell-agnostic)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ensure env.shared exists for local workflows.")
    parser.add_argument("--env-file", default="env.shared", help="Target env file path.")
    parser.add_argument("--template", default="env.shared.example", help="Template file path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env_file = Path(args.env_file)
    template = Path(args.template)

    if not env_file.exists() and template.exists():
        print(f"-> Seeding {env_file} from {template}")
        env_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template, env_file)
    elif not env_file.exists():
        print(f"-> Creating empty {env_file} (no template found)")
        env_file.parent.mkdir(parents=True, exist_ok=True)
        env_file.touch()

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
