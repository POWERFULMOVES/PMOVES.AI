"""A service that publishes ports must be on at least one NON-internal network.

Docker publishes NOTHING for a container attached only to `internal: true`
networks: HostConfig.PortBindings is honoured nowhere and NetworkSettings.Ports
stays empty, with no error. Phase 1b of the Neo4j migration (#3193/#3196) hit
exactly that: the compose neo4j came up healthy on pmoves_app/bus/data, all
internal, and its tailnet bind silently did not exist. The render and dry-run
gates could not see it; they read the REQUESTED bindings.

Measured on Knuckles 2026-09-27 against running containers: 15 of 15 running
services this test lists had requested bindings and ZERO effective ones;
cipher-api, minio and presign (each also on a non-internal network) published.

The stack is the Makefile's default STACK_FILES, parsed from the YAML directly
(no docker, no env files), merged by service name as compose does for these keys:
ports append; networks union; network_mode wins. A service with no `networks:`
key is on the project default network, which is not internal.

KNOWN_VIOLATORS are the services that already break the rule on main. They are
recorded, not silently passed: each is xfail(strict=True), so FIXING one turns
its case into an XPASS failure until it is removed from the set.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

PMOVES = Path(__file__).resolve().parents[1]

# Measured 2026-09-27 on origin/main f9d8a8228. neo4j is deliberately NOT here:
# it is the service this change fixes (it joins pmoves_external, like cipher-api).
KNOWN_VIOLATORS = frozenset({
    "a2ui-nats-bridge", "a2ui-renderer", "consciousness-service", "gateway-agent",
    "gpu-orchestrator", "grayjay-plugin-host", "grayjay-server", "hf-research-agent",
    "invidious-companion-proxy", "langextract", "llama-throughput-lab", "meilisearch",
    "nats_event_bus", "notebook-mcp", "notebook-sync", "nvidia-nim",
    "p7-room-orchestrator", "pdf-ingest", "pinokio_bridge", "qdrant", "retrieval-eval",
    "session-context-worker", "supabase-pooler", "supabase-realtime", "supabase-storage",
    "supabase-studio", "supaserch", "tensorzero-clickhouse", "tokenism-simulator",
    "tokenism-ui", "voice-relay", "voice-sampler", "watch-folder-router", "wealth-mcp",
})


def _stack_files() -> list[str]:
    mk = (PMOVES / "Makefile").read_text()
    m = re.search(r"^STACK_FILES \?= \\\n((?:\t-f \S+(?: \\)?\n)+)", mk, re.M)
    assert m, "could not find the STACK_FILES block in the Makefile -- parser is broken"
    return re.findall(r"-f (\S+)", m.group(1))


def _stack() -> tuple[dict, dict]:
    services: dict[str, dict] = {}
    networks: dict[str, bool] = {}
    for f in _stack_files():
        doc = yaml.safe_load((PMOVES / f).read_text()) or {}
        for name, spec in (doc.get("networks") or {}).items():
            networks[name] = bool((spec or {}).get("internal"))
        for name, sv in (doc.get("services") or {}).items():
            sv = sv or {}
            cur = services.setdefault(name, {"ports": [], "networks": set(), "network_mode": None})
            cur["ports"] += sv.get("ports") or []
            nw = sv.get("networks")
            if isinstance(nw, (dict, list)):
                cur["networks"] |= set(nw)
            if sv.get("network_mode"):
                cur["network_mode"] = sv["network_mode"]
    return services, networks


SERVICES, NETWORKS = _stack()
PUBLISHED = sorted(n for n, s in SERVICES.items() if s["ports"] and not s["network_mode"])


def _all_internal(name: str) -> tuple[bool, list[str]]:
    nets = sorted(SERVICES[name]["networks"]) or ["default"]
    return all(NETWORKS.get(n, False) for n in nets if n != "default") and "default" not in nets, nets


def test_the_parser_sees_the_fleet():
    assert len(_stack_files()) >= 6
    assert {"pmoves_app", "pmoves_bus", "pmoves_data"} <= {n for n, i in NETWORKS.items() if i}
    assert NETWORKS.get("pmoves_external") is False, "pmoves_external must exist and be non-internal"
    assert "neo4j" in PUBLISHED and "cipher-api" in PUBLISHED


@pytest.mark.parametrize(
    "service",
    [pytest.param(s, marks=pytest.mark.xfail(strict=True, reason="known violator on main (see KNOWN_VIOLATORS)"))
     if s in KNOWN_VIOLATORS else s for s in PUBLISHED],
)
def test_a_published_service_is_on_a_non_internal_network(service):
    internal_only, nets = _all_internal(service)
    assert not internal_only, (
        f"{service} publishes {SERVICES[service]['ports']} but every network it joins "
        f"({', '.join(nets)}) is internal: Docker will publish NOTHING. Add a non-internal "
        f"network (e.g. pmoves_external, as cipher-api does)."
    )


def test_known_violators_is_not_stale():
    """Every listed name must still exist and still publish; a rename or removal
    must shrink the list, not leave a dead entry that no case exercises."""
    stale = sorted(KNOWN_VIOLATORS - set(PUBLISHED))
    assert not stale, f"KNOWN_VIOLATORS names services that no longer publish in the stack: {stale}"
