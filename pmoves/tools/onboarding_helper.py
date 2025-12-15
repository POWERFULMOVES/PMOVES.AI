"""Onboarding helper for PMOVES secret management."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path
from typing import Sequence

from pmoves.chit.codec import decode_secret_map, load_cgp
from pmoves.tools import secrets_sync

REPO_ROOT = secrets_sync.REPO_ROOT


def format_missing(missing: Sequence[str]) -> str:
    if not missing:
        return "None"
    return "\n  - " + "\n  - ".join(sorted(missing))


def cmd_status(manifest: Path) -> int:
    cgp_path, entries = secrets_sync.load_manifest(manifest)
    secrets = decode_secret_map(load_cgp(cgp_path))
    outputs, missing = secrets_sync.build_outputs(secrets, entries, strict=False)
    total_entries = len(entries)
    decoded = len(secrets)
    targets = {file: len(values) for file, values in outputs.items()}

    print(f"Manifest: {manifest.relative_to(REPO_ROOT)}")
    print(f"CGP file: {cgp_path.relative_to(REPO_ROOT)}")
    print(f"Entries defined: {total_entries}")
    print(f"Secrets decoded: {decoded}")
    print("Planned outputs:")
    for file, count in sorted(targets.items()):
        print(f"  - {file}: {count} variables")
    print("Missing required labels:" + format_missing(missing))
    if missing:
        print(
            "\nAdd the missing labels to the CHIT bundle defined in pmoves/chit/secrets_manifest.yaml "
            "or relax `required: true` for optional keys."
        )
    return 0


def cmd_generate(manifest: Path) -> int:
    cgp_path, entries = secrets_sync.load_manifest(manifest)
    secrets = decode_secret_map(load_cgp(cgp_path))
    outputs, missing = secrets_sync.build_outputs(secrets, entries, strict=False)
    if missing:
        print("Cannot generate env files; required secrets missing:")
        for label in sorted(missing):
            print(f"  - {label}")
        print("Update the CHIT payload before rerunning.")
        return 1
    secrets_sync.write_env_files(outputs)
    print(secrets_sync.report(outputs))
    return 0


def parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        if not line or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        env[key.strip()] = val
    return env


def cmd_prompt(manifest: Path, out_file: Path) -> int:
    _cgp_path, entries = secrets_sync.load_manifest(manifest)
    # Collect required target keys (unique)
    required_keys: list[str] = []
    for entry in entries:
        if not entry.required:
            continue
        for target in entry.targets:
            key = target.key
            if key not in required_keys:
                required_keys.append(key)

    existing = parse_env_file(out_file)
    updated = dict(existing)

    print(f"Prompting for {len(required_keys)} required keys. Press Enter to keep existing values.")
    for key in required_keys:
        current = existing.get(key, "")
        prompt = f"{key} [{'<set>' if current else ''}]: "
        val = getpass.getpass(prompt)
        if not val and current:
            val = current
        updated[key] = val

    # Preserve any non-required keys that were in the file
    for k, v in existing.items():
        if k not in updated:
            updated[k] = v

    lines = [f"{k}={v}" for k, v in sorted(updated.items())]
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines) + "\n")
    print(f"Wrote {len(updated)} keys to {out_file.relative_to(REPO_ROOT)}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Automated onboarding helper for PMOVES secrets.")
    parser.add_argument(
        "command",
        choices=("status", "generate", "prompt"),
        help="status → report manifest coverage; generate → write env files from CGP; prompt → interactively fill required keys into an env file",
    )
    parser.add_argument(
        "--manifest",
        default="pmoves/chit/secrets_manifest.yaml",
        help="path to secrets manifest (default: pmoves/chit/secrets_manifest.yaml)",
    )
    parser.add_argument(
        "--out",
        default="pmoves/env.shared",
        help="env file to write when using 'prompt' (default: pmoves/env.shared)",
    )
    args = parser.parse_args(argv)
    manifest_path = (REPO_ROOT / args.manifest).resolve()
    if args.command == "status":
        return cmd_status(manifest_path)
    if args.command == "generate":
        return cmd_generate(manifest_path)
    return cmd_prompt(manifest_path, (REPO_ROOT / args.out).resolve())


if __name__ == "__main__":
    sys.exit(main())
