#!/usr/bin/env python3
"""Sync the Pmoves-hyperdimensions submodule into website/hyperdim/.

The pmoves.ai gallery viewer (website/hyperdim/) is GENERATED from the
Pmoves-hyperdimensions submodule (single source of truth — also consumed by the
nginx :8100 container) rather than hand-maintained. This mirrors the submodule's
working tree into the deploy directory, excluding repo/container scaffolding.

Cross-platform (pure stdlib shutil) — replaces an rsync recipe that doesn't
exist on Windows. Invoked by `make pmoves-ai-sync-hyperdim` before dev/deploy.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# Files in the fork that are scaffolding for its standalone/container use and
# must NOT ship to the static CF Pages site.
EXCLUDE = {".git", "docker-compose.yml", "LICENSE", "README.md"}


def sync(src: Path, dst: Path) -> int:
    if not (src / "index.html").is_file():
        print(
            f"[sync] ERROR: {src}/index.html missing - run: "
            "git submodule update --init Pmoves-hyperdimensions",
            file=sys.stderr,
        )
        return 1

    print(f"[sync] {src.name} -> {dst}")
    dst.mkdir(parents=True, exist_ok=True)

    src_names = {p.name for p in src.iterdir() if p.name not in EXCLUDE}

    # Mirror: remove anything in dst that is no longer in src (the --delete part).
    for existing in dst.iterdir():
        if existing.name not in src_names:
            if existing.is_dir():
                shutil.rmtree(existing)
            else:
                existing.unlink()

    # Copy each top-level entry from src.
    for entry in src.iterdir():
        if entry.name in EXCLUDE:
            continue
        target = dst / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target)

    print("[sync] website/hyperdim/ synced from fork")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True, help="Pmoves-hyperdimensions submodule path")
    ap.add_argument("--dst", required=True, help="website/hyperdim/ target path")
    args = ap.parse_args()
    return sync(Path(args.src), Path(args.dst))


if __name__ == "__main__":
    raise SystemExit(main())
