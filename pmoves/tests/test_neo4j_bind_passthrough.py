"""The NEO4J_BIND pass-through (#3196, option B) is retired.

#3196 validated a NEO4J_BIND from the command line, the caller's environment or the
node-local env file and exported it to every compose call, so Neo4j could publish
7474/7687 on a chosen interface. #3201 then made Neo4j internal-only behind the
neo4j-tailnet forwarder, which left those `ports:` inert on internal networks, and
the compose reconciliation removed them. With nothing left to bind, the Makefile
block, its validator (scripts/neo4j_bind_from_env_file.py) and its tests went too.
The full compose contract lives in tests/test_neo4j_compose_contract.py; this file
keeps the retirement from being silently undone.
"""
from __future__ import annotations

from pathlib import Path

PMOVES = Path(__file__).resolve().parents[1]


def test_no_neo4j_bind_in_the_makefile_or_compose():
    for f in ("Makefile", "docker-compose.yml", "docker-compose.core.yml", "env.mesh-bind.example"):
        assert "NEO4J_BIND" not in (PMOVES / f).read_text(), f


def test_the_validator_script_is_gone():
    assert not (PMOVES / "scripts" / "neo4j_bind_from_env_file.py").exists()
