#!/usr/bin/env python3
"""Full Voicebox OpenAPI surface dump, grouped by tag."""
import json
import sys
from collections import defaultdict
from pathlib import Path


def main() -> int:
    """Dump Voicebox API surface organized by tag."""
    spec_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("voicebox_openapi_spec.json")
    if not spec_path.exists():
        print(f"Not found: {spec_path}")
        return 1

    with open(spec_path) as f:
        spec = json.load(f)

    info = spec.get("info", {})
    print(f"API: {info.get('title','?')} v{info.get('version','?')}")
    print(f"Description: {info.get('description','(none)')[:200]}")
    print()

    paths = spec.get("paths", {})
    by_tag = defaultdict(list)
    untagged = []
    for path, path_def in paths.items():
        for method, op_def in path_def.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue
            tags = op_def.get("tags", [])
            entry = {
                "method": method.upper(),
                "path": path,
                "summary": op_def.get("summary", ""),
            }
            if tags:
                for tag in tags:
                    by_tag[tag].append(entry)
            else:
                untagged.append(entry)

    for tag in sorted(by_tag):
        print(f"=== {tag} ({len(by_tag[tag])} ops) ===")
        for op in sorted(by_tag[tag], key=lambda e: (e["path"], e["method"])):
            print(f"  {op['method']:7s} {op['path']:50s} {op['summary']}")
        print()

    if untagged:
        print(f"=== untagged ({len(untagged)} ops) ===")
        for op in sorted(untagged, key=lambda e: (e["path"], e["method"])):
            print(f"  {op['method']:7s} {op['path']:50s} {op['summary']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
