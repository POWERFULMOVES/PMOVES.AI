"""
Neo4j ports: HTTP 7474 and Bolt 7687 stay separate, and neither is published on the host.

PR #483 split one NEO4J_PORT into NEO4J_HTTP_PORT / NEO4J_BOLT_PORT. Since the
compose reconciliation (ops/knuckles-neo4j-compose-reconcile) Neo4j publishes NO
host port at all: it is internal-only, and the fleet reaches Bolt through the
neo4j-tailnet forwarder (docker-compose.neo4j-tailnet.yml, #3201), which forwards
7687 only. See docs/TAC/TAC_NEO4J.md section 3.
"""

import pytest
import yaml

from _smoke_helpers import PMOVES_DIR


COMPOSE = PMOVES_DIR / "docker-compose.yml"
FORWARDER = PMOVES_DIR / "docker-compose.neo4j-tailnet.yml"


@pytest.mark.smoke
def test_neo4j_publishes_no_host_port() -> None:
    svc = yaml.safe_load(COMPOSE.read_text())["services"]["neo4j"]
    assert "ports" not in svc, "Neo4j is internal-only; use the neo4j-tailnet forwarder"


@pytest.mark.smoke
def test_neo4j_never_uses_a_single_port_variable() -> None:
    assert "NEO4J_PORT:" not in COMPOSE.read_text()


@pytest.mark.smoke
def test_the_forwarder_carries_bolt() -> None:
    assert "neo4j:7687" in FORWARDER.read_text()
