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
key is on the project default network, which is not internal. Network keys are
resolved to their real `name:`.

A network declared `external: true` (pmoves_external, pmoves_db_egress) is not
created by compose, so compose never says whether it is internal: that is fixed
where the Makefile/mk CREATE it (`docker network create ...`). Its internal flag
is therefore read from those create sites, and EXTERNAL_NON_INTERNAL pins the two
that must stay non-internal -- the ones every published service relies on.

Scope, stated rather than implied: only the default STACK_FILES are scanned;
other overlays (per-node, vps, elder-melchor, …) are not, and compose's
`!reset`/`!override` merge tags are not modelled (yaml.safe_load would refuse
them; none of the scanned files uses them today).

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

# Measured 2026-09-27 on origin/main f9d8a8228.
# neo4j is here BY DESIGN (#3201, operator option A): it stays internal-only
# (app/bus/data; no egress, no host port) and is reached over the tailnet through
# the neo4j-tailnet forwarder (docker-compose.neo4j-tailnet.yml), per
# DOCKER_NETWORK_HARDENING Rule 5 ("gateway-front it"). Its `ports:` stay only to
# carry ${NEO4J_BIND}; on internal-only networks they are inert.
KNOWN_VIOLATORS = frozenset({
    "neo4j",
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


# Must stay non-internal: created outside compose (external: true), and the only
# route by which a service on internal networks can publish a port.
EXTERNAL_NON_INTERNAL = frozenset({"pmoves_external", "pmoves_db_egress"})

_CREATE = re.compile(r"docker network create\b([^\n|;&]*)")


def _join_continuations(text: str) -> str:
    """Join backslash-continued lines, as make and the shell both do, so a
    `docker network create` whose --internal sits on a continuation line is
    read as one command."""
    return re.sub(r"\\\n[ \t]*", " ", text)


def _create_sites(texts: list[str] | None = None) -> dict[str, list[str]]:
    """{real network name: [the flag text of each `docker network create` for it]}."""
    if texts is None:
        texts = [f.read_text() for f in [PMOVES / "Makefile", *sorted((PMOVES / "mk").glob("*.mk"))]]
    sites: dict[str, list[str]] = {}
    for text in texts:
        for m in _CREATE.finditer(_join_continuations(text)):
            words = m.group(1).split()
            names = [w for w in words if not w.startswith("-") and not w.startswith(">")
                     and not w[0].isdigit() and w not in ("bridge",)]
            if names:
                sites.setdefault(names[-1].strip('"'), []).append(m.group(1))
    return sites


CREATE_SITES = _create_sites()


def _stack() -> tuple[dict, dict]:
    services: dict[str, dict] = {}
    networks: dict[str, bool] = {}   # keyed by the compose KEY services reference
    for f in _stack_files():
        doc = yaml.safe_load((PMOVES / f).read_text()) or {}
        for key, spec in (doc.get("networks") or {}).items():
            spec = spec or {}
            real = spec.get("name") or key
            if spec.get("external"):
                sites = CREATE_SITES.get(real)
                assert sites, f"external network {real!r} has no `docker network create` site to check"
                networks[key] = any("--internal" in s for s in sites)
            else:
                networks[key] = bool(spec.get("internal"))
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


@pytest.mark.parametrize("name", sorted(EXTERNAL_NON_INTERNAL))
def test_external_networks_are_created_without_internal(name):
    """P2-A (#3201 review): every Makefile/mk site that CREATES this network must
    omit --internal, or every service relying on it silently loses its ports."""
    sites = CREATE_SITES.get(name)
    assert sites, f"no `docker network create ... {name}` site found -- parser or Makefile changed"
    bad = [s.strip() for s in sites if "--internal" in s]
    assert not bad, f"{name} is created with --internal at: {bad}"


def test_positive_control_an_internal_create_site_is_caught():
    fake = "docker network create --driver bridge --internal pmoves_external"
    m = _CREATE.search(fake)
    assert m and "--internal" in m.group(1)



# --- #3201 option A: neo4j stays internal-only; the forwarder fronts it ------

NEO4J_NETWORKS = {"pmoves_app", "pmoves_bus", "pmoves_data", "pmoves_graph_front"}


def test_neo4j_joins_only_internal_networks_and_no_new_ones():
    """DOCKER_NETWORK_HARDENING Rule 1: a data service never joins an egress-capable
    network (pmoves_external). Option A keeps neo4j on exactly app/bus/data plus the
    graph front to its tailnet forwarder -- every one of them internal."""
    nets = SERVICES["neo4j"]["networks"]
    assert nets == NEO4J_NETWORKS, f"neo4j networks changed: {sorted(nets)}"
    assert all(NETWORKS[n] for n in nets), "every neo4j network must be internal"


def test_neo4j_does_not_share_another_containers_netns():
    assert SERVICES["neo4j"]["network_mode"] is None


def test_the_graph_front_is_internal_and_neo4j_is_its_only_stack_member():
    """Least privilege: in the default stack only neo4j joins pmoves_graph_front;
    the forwarder joins it from its own overlay (docker-compose.neo4j-tailnet.yml)."""
    assert NETWORKS.get("pmoves_graph_front") is True
    members = sorted(n for n, s in SERVICES.items() if "pmoves_graph_front" in s["networks"])
    assert members == ["neo4j"], members



def test_a_continuation_line_internal_flag_is_caught():
    """P3 (#3201 review): --internal on a backslash-continued line must count."""
    text = ("net:\n\t@docker network create --driver bridge \\\n"
            "\t\t--internal --subnet 10.0.0.0/24 \\\n\t\tpmoves_external\n")
    sites = _create_sites([text])
    assert sites.get("pmoves_external"), sites
    assert any("--internal" in x for x in sites["pmoves_external"]), sites
