#!/usr/bin/env python3
"""
Deduplicate keys in a .env file:
- Keeps the last occurrence (to match dotenv resolution)
- Comments and blank lines preserved where possible
- Writes a backup .env.bak

Run:
  python tools/env_dedupe.py                 # operates on .env in repo root
  python tools/env_dedupe.py --input path --output path
"""
from __future__ import annotations
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IN = ROOT / ".env"
DEFAULT_OUT = DEFAULT_IN


def dedupe_env(path: Path, output: Path) -> int:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    seen = set()
    ordered = []
    # Iterate forward collecting lines; mark duplicates to be overridden
    for idx, ln in enumerate(lines):
        t = ln.strip()
        if not t or t.startswith('#') or '=' not in t:
            ordered.append((idx, ln, None))
            continue
        key = t.split('=', 1)[0].strip()
        ordered.append((idx, ln, key))
    # Keep last occurrence -> walk backward
    kept_keys = set()
    output_lines = []
    for idx, ln, key in reversed(ordered):
        if key is None:
            output_lines.append(ln)
            continue
        if key in kept_keys:
            # skip duplicate
            continue
        kept_keys.add(key)
        output_lines.append(ln)
    output_lines.reverse()
    # Backup
    if output.exists():
        bak = output.with_suffix(output.suffix + ".bak")
        output.replace(bak)
    output.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    return len(ordered) - len(output_lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=DEFAULT_IN)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    removed = dedupe_env(args.input, args.output)
    print(f"Removed {removed} duplicate entries. Backup written next to output file.")


if __name__ == "__main__":
    main()
