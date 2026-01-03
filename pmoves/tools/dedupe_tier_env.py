#!/usr/bin/env python3
"""Remove duplicate entries from tier env files, keeping last occurrence."""

from pathlib import Path

pmoves_root = Path("/home/pmoves/PMOVES.AI/pmoves")

for env_file in pmoves_root.glob("env.tier-*"):
    if env_file.suffix == ".example":
        continue

    lines = env_file.read_text().splitlines()
    seen = {}
    unique = []
    comments = []

    for line in lines:
        if line.startswith("#") or not line.strip():
            comments.append(line)
        elif "=" in line:
            key = line.split("=", 1)[0]
            seen[key] = line

    # Combine header comments with deduplicated keys
    result = comments + [seen[key] for key in sorted(seen.keys())]
    env_file.write_text("\n".join(result) + "\n")
    print(f"Deduped {env_file.name}: {len(seen)} unique entries")
