#!/usr/bin/env python3
"""Render Makefile target help text without awk dependency."""

from __future__ import annotations

import re
import sys
from pathlib import Path


PATTERN = re.compile(r"^([A-Za-z0-9_./-]+):.*##\s*(.+)$")


def main(argv: list[str]) -> int:
    targets: dict[str, str] = {}

    for raw in argv:
        path = Path(raw)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = PATTERN.match(line)
            if not match:
                continue
            target, description = match.groups()
            targets[target] = description.strip()

    for target in sorted(targets):
        print(f"  {target:<32} {targets[target]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
