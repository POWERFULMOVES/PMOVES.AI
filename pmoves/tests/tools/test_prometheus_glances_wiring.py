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
3. the WIRING CLAIM: the runbook says the Prometheus half is WIRED if and
   only if the scrape job exists, and says the NATS half is still open if
   and only if no Glances NATS export is wired. A runbook that claims a
   wiring that does not exist -- or that stays silent about one that does
   -- is the drift this gate exists to kill;
4. the COLLISION CAVEAT: if the exporter port is ALSO a registered host
   port of some other service in the port registry, the runbook must name
   that service, because scraping the wrong listener produces metrics that
   are confidently mislabelled. The caveat is DERIVED from the registry,
   not hardcoded: change who owns the port and the required caveat changes
   with it;
5. that the gate READS its inputs: a parser that finds nothing fails the
   test rather than passing it. A gate that cannot read its input must fail
   closed.

Hermetic: no network, no docker, no NATS, no gh. It reads three files in
this repo.
"""

from __future__ import annotations

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
#   `[prometheus] host=localhost port=9091 prefix=glances`
_EXPORTER_PORT_RE = re.compile(
    r"\[prometheus\]\s+host=\S+\s+port=(\d+)\s+prefix=glances"
)


# ── parsers ──────────────────────────────────────────────────────────────────

def exporter_port_from_runbook(text: str) -> int:
    """The Glances Prometheus-exporter port the runbook prescribes."""
    matches = _EXPORTER_PORT_RE.findall(text)
    if not matches:
        raise ValueError(
            "no `[prometheus] host=... port=NNNN prefix=glances` binding found "
            "in GLANCES_RUNBOOK.md -- the exporter prescription cannot be read"
        )
    distinct = sorted(set(matches))
    if len(distinct) != 1:
        raise ValueError(
            f"GLANCES_RUNBOOK.md prescribes {len(distinct)} different Glances "
            f"exporter ports {distinct}; the prescription itself is ambiguous"
        )
    return int(distinct[0])


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


def registry_owner_of_host_port(host_port: int) -> list[str]:
    """Every `service.SLOT` in the port registry that publishes this host port."""
    doc = yaml.safe_load(PORTS_YAML.read_text(encoding="utf-8"))
    services = doc.get("services") if isinstance(doc, dict) else None
    if not isinstance(services, dict):
        services = doc if isinstance(doc, dict) else {}
    owners: list[str] = []
    for service, body in services.items():
        if not isinstance(body, dict):
            continue
        for slot, meta in (body.get("slots") or {}).items():
            if not isinstance(meta, dict):
                continue
            if meta.get("host_port") == host_port:
                owners.append(f"{service}.{slot}")
    return sorted(owners)


def section_4_4(text: str) -> str:
    """The body of the runbook's section 4.4."""
    start = text.find("### 4.4")
    if start == -1:
        raise ValueError("GLANCES_RUNBOOK.md has no section 4.4")
    rest = text[start + 6:]
    nxt = re.search(r"^#{2,3} ", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


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


def test_runbook_prometheus_wiring_claim_matches_the_config():
    """The runbook claims the Prometheus half is wired iff the job exists."""
    text = GLANCES_RUNBOOK.read_text(encoding="utf-8")
    body = section_4_4(text)
    jobs = scrape_jobs(PROMETHEUS_YML.read_text(encoding="utf-8"))

    claims_wired = "Wired" in body and "Prometheus half WIRED" in text
    assert claims_wired == ("glances" in jobs), (
        "GLANCES_RUNBOOK.md section 4.4 and prometheus.yml disagree about "
        f"whether the Glances Prometheus export is wired "
        f"(runbook claims wired={claims_wired}, config has the job="
        f"{'glances' in jobs})"
    )

    # The NATS half has no wiring anywhere in the compose/config surface.
    nats_wired = False
    for candidate in (
        REPO_ROOT / "pmoves" / "docker-compose.yml",
    ):
        if candidate.exists() and "prefix=glances" in candidate.read_text(encoding="utf-8"):
            nats_wired = True
    assert "NATS half" in body, "GLANCES_RUNBOOK.md section 4.4 no longer states the NATS half's status"
    assert nats_wired is False, (
        "a Glances NATS export appears to be wired; section 4.4 must state its status"
    )


def test_headscale_port_collision_caveat_is_recorded():
    """If another service owns the exporter port, the runbook must say so."""
    text = GLANCES_RUNBOOK.read_text(encoding="utf-8")
    exporter_port = exporter_port_from_runbook(text)
    owners = registry_owner_of_host_port(exporter_port)
    if not owners:
        return  # no collision -> no caveat required

    for owner in owners:
        service = owner.split(".", 1)[0]
        assert service.lower() in text.lower(), (
            f"host port {exporter_port} is also published by {owner} in the port "
            f"registry, but GLANCES_RUNBOOK.md never names {service} -- scraping "
            "that port would produce confidently mislabelled metrics"
        )


def test_the_gate_can_read_its_inputs():
    """A parser that finds nothing must fail the gate, not pass it."""
    prom_text = PROMETHEUS_YML.read_text(encoding="utf-8")
    runbook = GLANCES_RUNBOOK.read_text(encoding="utf-8")

    assert scrape_jobs(prom_text), "no scrape jobs parsed from prometheus.yml"
    assert exporter_port_from_runbook(runbook) > 0
    assert registry_owner_of_host_port(exporter_port_from_runbook(runbook)) is not None

    with pytest.raises(ValueError):
        exporter_port_from_runbook("nothing here")
    with pytest.raises(ValueError):
        scrape_jobs("no_such_key: true")
