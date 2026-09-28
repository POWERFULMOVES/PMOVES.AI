#!/usr/bin/env python3
"""Print the Neo4j container name. The single source is docker-compose.yml.

`services.neo4j.container_name` in pmoves/docker-compose.yml is the only place
the name is written. backup-neo4j.sh and the Makefile neo4j-backup /
neo4j-restore targets ask this helper instead of carrying their own copy.
Those copies had drifted: the script looked for `pmoves-neo4j-1` and the
targets for `$(DC) ps -q neo4j`, while the live container on Knuckles was an
out-of-compose `pmoves-neo4j` that neither could see. Both then fell through
to STARTING a second Neo4j on the same data volume.

Exit codes follow the fleet doctrine: 0 printed a name, 3 could not measure
(the file is unreadable, or the service declares no container_name). There
is deliberately no fallback name: a guessed name is how the drift started.
"""
from __future__ import annotations

import sys
from pathlib import Path

COMPOSE = Path(__file__).resolve().parent.parent / "docker-compose.yml"


def container_name(compose: Path = COMPOSE) -> str:
    import yaml

    doc = yaml.safe_load(compose.read_text(encoding="utf-8")) or {}
    name = (((doc.get("services") or {}).get("neo4j") or {}).get("container_name") or "").strip()
    if not name:
        raise LookupError(f"{compose}: services.neo4j declares no container_name")
    return name


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else COMPOSE
    try:
        print(container_name(path))
    except Exception as exc:  # noqa: BLE001 -- reported, and exit 3 is not a pass
        print(f"neo4j_container: could not determine the Neo4j container name: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
