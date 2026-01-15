from __future__ import annotations

import os
from pathlib import Path

RUNTIME_DIR = Path("pmoves/data/agent-zero/runtime/mcp").resolve()
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

def main() -> None:
    config = os.environ.get("A0_MCP_SERVERS", "").strip()
    outfile = RUNTIME_DIR / "servers.env"
    with outfile.open("w", encoding="utf-8") as f:
        f.write(config + "\n")
    print(f"✔ Wrote Agent Zero MCP server map to {outfile}")
    if not config:
        print("⚠ A0_MCP_SERVERS is empty; edit pmoves/env.shared and rerun.")

if __name__ == "__main__":
    main()

