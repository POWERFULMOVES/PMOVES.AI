from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description="Generate CHIT codebook JSONL from a source JSONL")
    p.add_argument("input", help="Input JSONL with fields like text/title/summary")
    p.add_argument("output", help="Output JSONL (structured_dataset.jsonl)")
    p.add_argument("--max", type=int, default=1000, help="Max records")
    args = p.parse_args()

    src = Path(args.input)
    dst = Path(args.output)

    n = 0
    with src.open("r", encoding="utf-8") as f, dst.open("w", encoding="utf-8") as out:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            text = obj.get("text") or obj.get("summary") or obj.get("title")
            if not text:
                continue
            out_obj = {"text": text}
            out.write(json.dumps(out_obj, ensure_ascii=False) + "\n")
            n += 1
            if n >= args.max:
                break

    print(f"wrote {n} items to {dst}")


if __name__ == "__main__":
    sys.exit(main())

