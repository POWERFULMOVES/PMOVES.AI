"""The Glances <-> Prometheus wiring ratchet.

WHAT THIS FILE ASSERTS
----------------------
1. the PORT AGREEMENT: the host port Prometheus scrapes for the Glances
   exporter is the SAME port the Glances runbook tells an operator to bind
   the exporter to. These are two files edited by different hands at
   different times, and nothing else in the repo connects them -- the
   exporter port lives in prose, the scrape target lives in YAML;
2. the TARGET KIND: the scrape target is the Docker host gateway
   (`host.docker.internal`), because Glances is a HOST-LOCAL exporter with
   no compose service to scrape by name (GLANCES_RUNBOOK.md F3);
3. the PORT IS NOBODY'S: the exporter port is owned by NO service in the
   port registry. Host port 9091 is Headscale's registered slot, published by
   `pmoves/docker-compose.remote.yml`, so a scrape of the host gateway on
   9091 on the remote/VPS node reaches HEADSCALE -- and Prometheus ingests
   Headscale's series under `job="glances"`. Glances therefore uses 9092, and
   this gate is what stops it drifting back onto another service's slot;
4. the BIND ADDRESS IS REACHABLE: the exporter must not bind loopback.
   `host.docker.internal` resolves in the monitoring stack to the Docker host
   gateway, and a container cannot reach a host loopback listener through it
   -- the connection is refused and the job stays DOWN. The wildcard is
   equally wrong: it would put the exporter on the tailnet, which runbook
   4.0 forbids;
5. the WIRING CLAIMS: the runbook states, with a stable marker, whether each
   half of the export is wired, and those claims must match the config and
   the compose surface;
6. that the gate READS its inputs: a parser that finds nothing fails the
   test rather than passing it. A gate that cannot read its input must fail
   closed.

Hermetic: no network, no docker, no NATS, no gh. It reads four files in
this repo.
"""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]

PROMETHEUS_YML = REPO_ROOT / "pmoves" / "monitoring" / "prometheus" / "prometheus.yml"
GLANCES_RUNBOOK = REPO_ROOT / "pmoves" / "docs" / "operations" / "GLANCES_RUNBOOK.md"
PORTS_YAML = REPO_ROOT / "pmoves" / "configs" / "ports.yaml"

DOCKER_HOST_GATEWAY = "host.docker.internal"

# The runbook states the exporter binding as:
#   `[prometheus] host=172.17.0.1 port=9092 prefix=glances`
_EXPORTER_RE = re.compile(
    r"\[prometheus\]\s+host=(\S+)\s+port=(\d+)\s+prefix=glances"
)

# The runbook names the port the exporter deliberately avoids, and the port
# whose owner it must name in order to explain the choice.
_AVOIDED_PORT_RE = re.compile(r"AVOIDED PORT:\s*(\d+)")

# The stable, case-insensitive wiring markers. ONE scope (the section 4.4
# body), ONE shape, so a reword that preserves the meaning cannot flip the
# gate and a meaning change cannot dodge it.
_HALF_MARKER_RE = re.compile(
    r"(?P<half>prometheus|nats)\s+half\s*:\s*\**\s*(?P<state>not\s+wired|wired)",
    re.IGNORECASE,
)

# Bind addresses that make the target wrong in one direction or the other:
# loopback is unreachable from the monitoring container, and the wildcard puts
# the exporter on every interface, the tailnet included.
UNREACHABLE_OR_EXPOSED_BINDS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "[::1]",
    "0.0.0.0",
    "::",
}


# ── parsers ──────────────────────────────────────────────────────────────────

def exporter_binding_from_runbook(text: str) -> tuple[str, int]:
    """The Glances Prometheus-exporter bind address and port the runbook
    prescribes, as ``(host, port)``."""
    matches = _EXPORTER_RE.findall(text)
    if not matches:
        raise ValueError(
            "no `[prometheus] host=... port=NNNN prefix=glances` binding found "
            "in GLANCES_RUNBOOK.md -- the exporter prescription cannot be read"
        )
    distinct = sorted(set(matches))
    if len(distinct) != 1:
        raise ValueError(
            f"GLANCES_RUNBOOK.md prescribes {len(distinct)} different Glances "
            f"exporter bindings {distinct}; the prescription itself is ambiguous"
        )
    host, port = distinct[0]
    return host, int(port)


def exporter_port_from_runbook(text: str) -> int:
    """The Glances Prometheus-exporter port the runbook prescribes."""
    return exporter_binding_from_runbook(text)[1]


def scrape_jobs(prom_text: str) -> dict[str, list[str]]:
    """job_name -> the static_configs targets, for every job in the file."""
    doc = yaml.safe_load(prom_text)
    if not isinstance(doc, dict) or "scrape_configs" not in doc:
        raise ValueError("prometheus.yml has no scrape_configs block")
    jobs: dict[str, list[str]] = {}
    for job in doc["scrape_configs"] or []:
        if not isinstance(job, dict):
            continue
        name = job.get("job_name")
        if not name:
            continue
        targets: list[str] = []
        for static in job.get("static_configs") or []:
            if not isinstance(static, dict):
                continue
            targets.extend(static.get("targets") or [])
        jobs[str(name)] = targets
    return jobs


def _registry_services(ports_text: str | None = None) -> dict:
    """The registry's `services` map, from the live file or from *ports_text*."""
    text = (
        ports_text
        if ports_text is not None
        else PORTS_YAML.read_text(encoding="utf-8")
    )
    doc = yaml.safe_load(text)
    services = doc.get("services") if isinstance(doc, dict) else None
    if not isinstance(services, dict):
        services = doc if isinstance(doc, dict) else {}
    return services


def registry_slot_count(ports_text: str | None = None) -> int:
    """How many slots the port registry yielded.

    A registry that yields ZERO slots was not READ. "No service owns this
    port" is then indistinguishable from "the parser is broken", which is
    exactly the hole a fail-closed gate must not have.
    """
    count = 0
    for body in _registry_services(ports_text).values():
        if not isinstance(body, dict):
            continue
        for meta in (body.get("slots") or {}).values():
            if isinstance(meta, dict):
                count += 1
    return count


def registry_owner_of_host_port(
    host_port: int, ports_text: str | None = None
) -> list[str]:
    """Every `service.SLOT` in the port registry that publishes this host port.

    FAILS CLOSED. If the registry yielded no slots at all it was not read, and
    an empty owner list would then be a LIE rather than an answer, so this
    raises instead of returning it.
    """
    owners: list[str] = []
    for service, body in _registry_services(ports_text).items():
        if not isinstance(body, dict):
            continue
        for slot, meta in (body.get("slots") or {}).items():
            if isinstance(meta, dict) and meta.get("host_port") == host_port:
                owners.append(f"{service}.{slot}")
    if not owners and registry_slot_count(ports_text) == 0:
        raise ValueError(
            "the port registry yielded no slots -- it was not read, so 'no "
            "service owns this port' cannot be trusted"
        )
    return sorted(owners)


def compose_files_carrying_a_glances_nats_export(root: Path) -> list[str]:
    """Every compose file that wires a Glances NATS export.

    The scan covers the WHOLE compose surface (`pmoves/**/docker-compose*.yml`),
    not one file: a single-file scan misses the wiring in every other compose
    file, which is how "not wired" becomes a claim nothing can check.

    SCOPE, stated honestly: this covers the COMPOSE surface. A NATS export
    wired the HOST-LOCAL way the Prometheus half is wired -- a native process
    outside compose -- appears in no compose file. So what this gate can say
    is "the runbook's NATS status matches the compose surface", and the
    runbook is where a host-local wiring must be recorded.
    """
    hits: list[str] = []
    for path in sorted(root.glob("pmoves/**/docker-compose*.yml")):
        text = path.read_text(encoding="utf-8")
        if "--export nats" in text and "prefix=glances" in text:
            hits.append(path.relative_to(root).as_posix())
    return hits


def section_4_4(text: str) -> str:
    """The body of the runbook's section 4.4.

    The body starts AFTER the heading LINE. Slicing a fixed number of
    characters off the heading's start leaves the heading's own tail in the
    body -- a body that begins with a stray "4" and the rest of the heading --
    and every assertion that substring-searches over it then matches the
    heading instead of the section it meant to read. The heading is also the
    one place a marker can be duplicated, so it must not be in the body at
    all.
    """
    start = text.find("### 4.4")
    if start == -1:
        raise ValueError("GLANCES_RUNBOOK.md has no section 4.4")
    line_end = text.find("\n", start)
    if line_end == -1:
        raise ValueError("GLANCES_RUNBOOK.md section 4.4 has no body")
    rest = text[line_end + 1:]
    nxt = re.search(r"^#{2,3} ", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def half_wiring_state(body: str, half: str) -> str:
    """The runbook's own wiring claim for one half: `wired` or `not wired`.

    Read from a STABLE MARKER in ONE scope (the section 4.4 body),
    case-insensitively, so a reword that preserves the meaning cannot flip
    the gate, and a meaning change cannot dodge it.
    """
    states: list[str] = []
    for match in _HALF_MARKER_RE.finditer(body):
        if match.group("half").lower() != half.lower():
            continue
        states.append(re.sub(r"\s+", " ", match.group("state").strip().lower()))
    if not states:
        raise ValueError(
            f"GLANCES_RUNBOOK.md section 4.4 does not state the {half} half's "
            f"status with a `**{half.capitalize()} half: WIRED**` / "
            f"`**{half.capitalize()} half: NOT WIRED**` marker"
        )
    if len(set(states)) != 1:
        raise ValueError(
            f"GLANCES_RUNBOOK.md section 4.4 states the {half} half's status "
            f"{len(set(states))} different ways: {sorted(set(states))}"
        )
    return states[0]


# ── the gate ─────────────────────────────────────────────────────────────────

def test_glances_scrape_target_port_matches_runbook_exporter_port():
    """The scraped port IS the port the exporter is told to bind."""
    prom_text = PROMETHEUS_YML.read_text(encoding="utf-8")
    jobs = scrape_jobs(prom_text)
    assert "glances" in jobs, (
        "prometheus.yml has no `glances` scrape job -- the Glances exporter is "
        "not wired (GLANCES_RUNBOOK.md F12)"
    )

    exporter_port = exporter_port_from_runbook(GLANCES_RUNBOOK.read_text(encoding="utf-8"))

    scraped_ports = set()
    for target in jobs["glances"]:
        host, _, port = target.rpartition(":")
        assert port.isdigit(), f"unparseable glances target {target!r}"
        scraped_ports.add(int(port))

    assert scraped_ports == {exporter_port}, (
        f"prometheus.yml scrapes Glances on port(s) {sorted(scraped_ports)} but "
        f"GLANCES_RUNBOOK.md binds the exporter to {exporter_port} -- the scrape "
        "would hit the wrong listener"
    )


def test_glances_scrape_target_uses_the_docker_host_gateway():
    """Glances has no compose service, so the target must be the host gateway."""
    jobs = scrape_jobs(PROMETHEUS_YML.read_text(encoding="utf-8"))
    assert "glances" in jobs
    for target in jobs["glances"]:
        host, _, _port = target.rpartition(":")
        assert host == DOCKER_HOST_GATEWAY, (
            f"glances target {target!r} does not use the Docker host gateway "
            f"{DOCKER_HOST_GATEWAY!r} -- Glances is a host-local exporter "
            "(GLANCES_RUNBOOK.md F3), not a compose service"
        )


def test_the_exporter_port_is_owned_by_no_registered_service():
    """The exporter port must not be another service's registered slot.

    Host port 9091 is Headscale's slot (`pmoves/configs/ports.yaml`,
    `HEADSCALE_9091_PORT`, published by `pmoves/docker-compose.remote.yml`). On
    the remote/VPS node carrying that compose, the host gateway on 9091 IS
    Headscale -- so Prometheus would ingest Headscale's series under
    `job="glances"` / `source="glances"`: telemetry that is confidently
    mislabelled. Glances uses 9092, which no service owns.
    """
    text = GLANCES_RUNBOOK.read_text(encoding="utf-8")
    _host, port = exporter_binding_from_runbook(text)
    owners = registry_owner_of_host_port(port)
    assert not owners, (
        f"the Glances exporter port {port} is ALSO a registered host port of "
        f"{owners} in pmoves/configs/ports.yaml. A scrape of the host gateway "
        "on that port reaches the OTHER service, and its series would be "
        "ingested under job=\"glances\" -- telemetry that is confidently "
        "mislabelled. Give the exporter a port no service owns."
    )


def test_the_exporter_binds_an_address_prometheus_can_reach():
    """The exporter must NOT bind loopback: the container reaches the GATEWAY.

    `host.docker.internal` resolves in the monitoring stack to the Docker host
    gateway (`extra_hosts: host.docker.internal:host-gateway`, in
    `pmoves/monitoring/docker-compose.monitoring.yml`), which on native Linux
    is the default bridge's gateway. A listener bound to loopback is NOT
    reachable through it: the connection is refused and the job stays DOWN for
    ever. The wildcard is equally wrong -- it would put the exporter on every
    interface, the tailnet included, which runbook 4.0 forbids.
    """
    text = GLANCES_RUNBOOK.read_text(encoding="utf-8")
    host, _port = exporter_binding_from_runbook(text)
    assert host.lower() not in UNREACHABLE_OR_EXPOSED_BINDS, (
        f"the runbook prescribes the exporter bind address {host!r}, which is "
        "either loopback -- unreachable from the monitoring container through "
        "the Docker host gateway -- or the wildcard, which would publish the "
        "exporter on the tailnet (runbook 4.0). Bind the Docker bridge gateway."
    )
    try:
        ipaddress.ip_address(host)
    except ValueError as exc:
        raise AssertionError(
            f"the runbook prescribes the exporter bind address {host!r}, which "
            "is not a concrete IP address -- a placeholder would make the "
            "scrape target unreachable on every node"
        ) from exc


def test_the_runbook_names_the_owner_of_the_port_it_avoids():
    """The avoided port must be explained by naming who owns it."""
    text = GLANCES_RUNBOOK.read_text(encoding="utf-8")
    body = section_4_4(text)
    match = _AVOIDED_PORT_RE.search(body)
    assert match, (
        "GLANCES_RUNBOOK.md section 4.4 does not state which host port the "
        "exporter avoids -- the port choice has to be explained, not asserted"
    )
    avoided = int(match.group(1))
    owners = registry_owner_of_host_port(avoided)
    assert owners, (
        f"section 4.4 declares AVOIDED PORT {avoided}, but no service in the "
        "port registry owns it -- there is no collision to avoid"
    )
    for owner in owners:
        service = owner.split(".", 1)[0]
        assert service.lower() in body.lower(), (
            f"section 4.4 avoids host port {avoided} but never names "
            f"{service}, the service that owns it in the port registry -- the "
            "port choice is unexplained"
        )


def test_runbook_prometheus_wiring_claim_matches_the_config():
    """The runbook claims the Prometheus half is wired iff the job exists."""
    text = GLANCES_RUNBOOK.read_text(encoding="utf-8")
    body = section_4_4(text)
    jobs = scrape_jobs(PROMETHEUS_YML.read_text(encoding="utf-8"))

    claimed = half_wiring_state(body, "prometheus")
    assert claimed == ("wired" if "glances" in jobs else "not wired"), (
        "GLANCES_RUNBOOK.md section 4.4 and prometheus.yml disagree about "
        f"whether the Glances Prometheus export is wired "
        f"(runbook claims {claimed!r}, config has the job="
        f"{'glances' in jobs})"
    )


def test_runbook_nats_claim_matches_the_compose_surface():
    """The NATS half's stated status must match the compose surface.

    SCOPE, stated honestly: the scan covers the whole compose surface
    (`pmoves/**/docker-compose*.yml`). A NATS export wired the HOST-LOCAL way
    the Prometheus half is wired would appear in NO compose file, so what this
    gate can enforce is that the runbook's claim agrees with the compose
    surface -- not that the wiring does not exist somewhere else. The runbook
    is where a host-local wiring has to be recorded, and this gate makes a
    drift between the two fail instead of passing unnoticed.
    """
    text = GLANCES_RUNBOOK.read_text(encoding="utf-8")
    body = section_4_4(text)
    wiring_files = compose_files_carrying_a_glances_nats_export(REPO_ROOT)
    claimed = half_wiring_state(body, "nats")
    assert claimed == ("wired" if wiring_files else "not wired"), (
        "GLANCES_RUNBOOK.md section 4.4 states the NATS half's status as "
        f"{claimed!r}, but the compose surface wires a Glances NATS export in "
        f"{wiring_files} -- the runbook must state the status it actually has"
    )


def test_the_gate_can_read_its_inputs():
    """A parser that finds nothing must fail the gate, not pass it."""
    prom_text = PROMETHEUS_YML.read_text(encoding="utf-8")
    runbook = GLANCES_RUNBOOK.read_text(encoding="utf-8")

    assert scrape_jobs(prom_text), "no scrape jobs parsed from prometheus.yml"
    assert exporter_port_from_runbook(runbook) > 0

    # The port registry must have been READ. An empty owner list is a
    # legitimate answer -- "no service owns this port" -- so the assertion is
    # on the registry's SLOT COUNT: a registry that yields no slots at all
    # means the parser failed, and "no owner" would then be indistinguishable
    # from "no collision". Asserting the owner list is not None proves
    # nothing: a list is never None, not even an empty one.
    assert registry_slot_count() > 0, (
        "the port registry parser found no slots at all -- the registry was not "
        "read, so 'no service owns this port' cannot be trusted"
    )

    with pytest.raises(ValueError):
        exporter_port_from_runbook("nothing here")
    with pytest.raises(ValueError):
        scrape_jobs("no_such_key: true")
    with pytest.raises(ValueError):
        registry_owner_of_host_port(9091, ports_text="services: {}")
    with pytest.raises(ValueError):
        half_wiring_state("no markers here", "prometheus")
    with pytest.raises(ValueError):
        section_4_4("no section here")
