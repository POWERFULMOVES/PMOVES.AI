#!/usr/bin/env python3
"""Decode a CHIT Geometry Packet (CGP) back into environment secrets."""

from __future__ import annotations

import sys
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PMOVES_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CGP = PMOVES_DIR / "data/chit/env.cgp.json"

from pmoves.chit import decode_secret_map, load_cgp


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cgp",
        default=DEFAULT_CGP,
        type=Path,
        help=f"Input CGP JSON path (default: {DEFAULT_CGP})",
    )
    parser.add_argument(
        "--out",
        default=None,
        type=Path,
        help="Optional .env-style output path. When omitted, values print to stdout.",
    )
    parser.add_argument(
        "--keys",
        nargs="*",
        default=None,
        help="Optional subset of keys to extract",
    )
    args = parser.parse_args()

    payload = load_cgp(args.cgp)
    secrets = decode_secret_map(payload)

    if args.keys:
        subset = {}
        for key in args.keys:
            if key not in secrets:
                raise KeyError(f"{key!r} not found in CGP payload")
            subset[key] = secrets[key]
        secrets = subset

    lines = [f"{key}={value}" for key, value in sorted(secrets.items())]

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Wrote {len(lines)} secrets to {args.out}")
    else:
        for line in lines:
            print(line)


if __name__ == "__main__":
    main()
