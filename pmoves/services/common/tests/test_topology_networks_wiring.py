"""Regression test for the PMOVES_NETWORKS wiring (closed the #2183 gap).

``topology.py``'s ``TopologyContext.from_env()`` reads ``PMOVES_NETWORKS``
from the process environment, but no Compose file or bootstrap script
currently sets it (confirmed via repo-wide grep — see the PR #2183 review
thread and the fix/pmoves-networks-wiring design-plan PR). This test
inspects the actual SOURCE ``docker-compose.yml`` — the file the default
``make -C pmoves up`` bring-up path reads directly, and that
``scripts/split_compose.py`` reads FROM to generate the split overlays used
by the ``overlay-up-*`` targets — and asserts that a couple of representative
services mirror their own ``networks:`` list into a ``PMOVES_NETWORKS=``
entry in their ``environment:`` list, so that ``TopologyContext.from_env()``
would see a non-empty ``docker_networks`` set for that service once actually
deployed.

The wiring is produced by ``pmoves/scripts/inject_pmoves_networks.py`` (run in
CI via ``make -C pmoves compose-networks-check``); this test guards two
representative services so a future edit that drops the mirroring is caught.

Not part of the default ``pyproject.toml`` ``testpaths`` (like its sibling
``test_topology.py`` in this same directory) — run explicitly:
    uv run --no-project --with ruamel.yaml==0.19.1 --with pytest \\
        python -m pytest pmoves/services/common/tests/test_topology_networks_wiring.py -q
"""
from __future__ import annotations

import pathlib

import pytest
from ruamel.yaml import YAML

_COMMON_TESTS_DIR = pathlib.Path(__file__).resolve().parent
_PMOVES_DIR = _COMMON_TESTS_DIR.parents[2]  # pmoves/services/common/tests -> pmoves/
_SOURCE_COMPOSE = _PMOVES_DIR / "docker-compose.yml"

# Two real services picked to cover different network-tier combinations
# (cipher-api is dual-homed on pmoves_external; mesh-agent is internal-only),
# so a real fix has to handle per-service variance, not just one shape.
_SAMPLE_SERVICES = ["cipher-api", "mesh-agent"]


def _load_service(name: str) -> dict:
    yaml = YAML()
    with open(_SOURCE_COMPOSE, encoding="utf-8") as f:
        data = yaml.load(f)
    return data["services"][name]


@pytest.mark.skipif(
    not _SOURCE_COMPOSE.exists(),
    reason="docker-compose.yml not present in this checkout",
)
@pytest.mark.parametrize("service_name", _SAMPLE_SERVICES)
def test_service_environment_mirrors_networks_into_pmoves_networks(service_name):
    svc = _load_service(service_name)
    declared_networks = set(svc.get("networks", []))
    assert declared_networks, f"{service_name} has no networks: declared — pick a different sample service"

    env_list = svc.get("environment", [])
    pmoves_networks_value = None
    for entry in env_list:
        if isinstance(entry, str) and entry.startswith("PMOVES_NETWORKS="):
            pmoves_networks_value = entry.split("=", 1)[1]
            break

    assert pmoves_networks_value is not None, (
        f"{service_name}'s environment: list has no PMOVES_NETWORKS entry — "
        "the wiring gap from PR #2183 is still open"
    )
    wired_networks = {n.strip() for n in pmoves_networks_value.split(",") if n.strip()}
    assert wired_networks == declared_networks
