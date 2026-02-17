#!/usr/bin/env python3
"""
Update env.tier-llm from decoded CGP secrets.
"""

import json
from pathlib import Path

# CGP file
cgp_file = Path("/home/pmoves/PMOVES.AI/pmoves/data/chit/env.cgp.json")
env_file = Path("/home/pmoves/PMOVES.AI/pmoves/env.tier-llm")

# Load CGP and decode
with open(cgp_file) as f:
    cgp = json.load(f)

# Extract secrets into a dict
secrets = {point["label"]: point["value"] for point in cgp["points"]}

# Read current env file
env_content = env_file.read_text()
lines = env_content.split("\n")

# Update or add each secret
updated_count = 0
for label, value in sorted(secrets.items()):
    matched = False
    for i, line in enumerate(lines):
        if line.startswith(f"{label}="):
            lines[i] = f"{label}={value}"
            matched = True
            updated_count += 1
            break
    if not matched:
        for i, line in enumerate(lines):
            if line == f"{label}=":
                lines[i] = f"{label}={value}"
                updated_count += 1
                break

# Write back
env_file.write_text("\n".join(lines))

print(f"\nUpdated env.tier-llm with {updated_count}/{len(secrets)} credentials")
