"""The port registry ratchet: every published host port comes from the registry.

WHAT THIS FILE ASSERTS
----------------------
1. the DETECTOR: a bare-literal host port is flagged, a parameterised one is
   not, and a container-port-only entry (Docker assigns the host port) is not
   judged at all;
2. the SLOT GRAMMAR: builtin `open`-style three-slot and two-slot port
   entries both resolve, and a `${VAR:-default}` colon does not split the
   slot;
3. the REGISTRY RULES: a compose default that disagrees with the registry, a
   slot the registry does not know, and a registry slot nobody publishes are
   each reported;
4. the COLLISION BASELINE: a new collision fails and a stale baseline entry
   fails;
5. the PYTHON REGISTRIES: `service_catalog.py` and `port_allocator.py` are
   cross-checked against the canonical registry -- and the comparison is
   against the CONTAINER port, because the two Python registries record the
   port a service LISTENS on while compose publishes a HOST port
   (`pmoves-ui` listens on 3000 and is published on 4482). Comparing against
   the host port reports four false drifts; that was MEASURED, not assumed;
6. the LIVE tree: the gate is green against the committed registry and
   baseline, every compose file in scope parses with the ratchet's
   merge-tag-aware loader, and the 8115 pair the operator named is resolved.

Hermetic: no network, no docker, no NATS, no gh. It reads files in this repo
and runs the tool against pytest's tmp_path.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from pmoves.tools import port_registry_ratchet as ratchet

REPO_ROOT = Path(__file__).resolve().parents[3]
PMOVES = REPO_ROOT / "pmoves"
TOOL = PMOVES / "tools" / "port_registry_ratchet.py"
REGISTRY = PMOVES / "configs" / "ports.yaml"
COLLISIONS = PMOVES / "configs" / "port_registry" / "_known_collisions.yaml"

# The two claims that collided on 8115, as MEASURED before the fix.
NODE_REGISTRY_PORT = 8115
YT_COOKIE_REFRESHER_PORT = 8126


# ---------------------------------------------------------------------------
# 1. the detector
# ---------------------------------------------------------------------------


def test_a_bare_literal_host_port_is_flagged():
    value, var, is_bare = ratchet.resolve_host_slot("8115")
    assert value == 8115
    assert var is None
    assert is_bare is True


def test_a_parameterised_host_port_is_not_bare():
    value, var, is_bare = ratchet.resolve_host_slot("${NODE_REGISTRY_PORT:-8115}")
    assert value == 8115
    assert var == "NODE_REGISTRY_PORT"
    assert is_bare is False


def test_a_variable_with_no_default_is_not_bare_but_has_no_value():
    value, var, is_bare = ratchet.resolve_host_slot("${SOME_PORT}")
    assert value is None
    assert var == "SOME_PORT"
    assert is_bare is False


def test_a_container_port_only_entry_is_never_judged(tmp_path):
    """One slot = container port only; Docker assigns the host port."""
    path = _write_compose(
        tmp_path,
        "services:\n  demo:\n    ports:\n      - \"9001\"\n",
    )
    registry = {"demo": {"slots": {"DEMO_PORT": {"host_port": 9001, "container_port": 9001}}}}
    result = ratchet.scan(registry, [path])
    assert result["bare"] == [], result["bare"]
    assert result["unknown"] == [], result["unknown"]


def test_a_bind_address_is_not_a_host_port():
    """The 3-slot form is BIND:HOST:CONTAINER -- the bind is slot 0."""
    slots = ratchet.split_top_level("${BIND:-127.0.0.1}:${PORT:-8080}:8080")
    assert slots == ["${BIND:-127.0.0.1}", "${PORT:-8080}", "8080"]


def test_a_variable_default_colon_does_not_split_the_slot():
    slots = ratchet.split_top_level("${SUPABASE_DB_PORT:-54322}:5432")
    assert slots == ["${SUPABASE_DB_PORT:-54322}", "5432"]


def test_the_two_and_three_slot_forms_both_resolve():
    assert ratchet.split_top_level("8115:8115") == ["8115", "8115"]
    assert len(ratchet.split_top_level("127.0.0.1:8115:8115")) == 3


# ---------------------------------------------------------------------------
# 2. the registry rules
# ---------------------------------------------------------------------------


def _registry_with(slots: dict) -> dict:
    return {"svc": {"slots": slots}}


def test_a_missing_registry_file_is_an_instrument_error(tmp_path):
    with pytest.raises(ratchet.InstrumentError):
        ratchet.load_registry(tmp_path / "nope.yaml")


def test_a_registry_without_services_is_an_instrument_error(tmp_path):
    bad = tmp_path / "ports.yaml"
    bad.write_text("version: 1\n", encoding="utf-8")
    with pytest.raises(ratchet.InstrumentError):
        ratchet.load_registry(bad)


def _write_compose(tmp_path: Path, body: str) -> Path:
    root = tmp_path / "pmoves"
    root.mkdir(exist_ok=True)
    path = root / "docker-compose.synthetic.yml"
    path.write_text(body, encoding="utf-8")
    return path


def test_a_registry_drift_is_flagged(tmp_path):
    path = _write_compose(
        tmp_path,
        "services:\n  demo:\n    ports:\n      - \"${DEMO_PORT:-9001}:9001\"\n",
    )
    registry = {
        "demo": {"slots": {"DEMO_PORT": {"host_port": 9999, "container_port": 9001}}}
    }
    result = ratchet.scan(registry, [path])
    assert len(result["drift"]) == 1, result["drift"]
    assert result["drift"][0]["compose"] == 9001
    assert result["drift"][0]["registry"] == 9999


def test_a_container_port_drift_is_flagged(tmp_path):
    path = _write_compose(
        tmp_path,
        "services:\n  demo:\n    ports:\n      - \"${DEMO_PORT:-9001}:9001\"\n",
    )
    registry = {
        "demo": {"slots": {"DEMO_PORT": {"host_port": 9001, "container_port": 7777}}}
    }
    result = ratchet.scan(registry, [path])
    assert any(d.get("compose_container") == 9001 for d in result["drift"]), result["drift"]


def test_an_unknown_slot_is_flagged(tmp_path):
    path = _write_compose(
        tmp_path,
        "services:\n  demo:\n    ports:\n      - \"${DEMO_PORT:-9001}:9001\"\n",
    )
    registry = {"demo": {"slots": {"OTHER_PORT": {"host_port": 9001, "container_port": 9001}}}}
    result = ratchet.scan(registry, [path])
    assert len(result["unknown"]) == 1, result["unknown"]
    assert "DEMO_PORT" in result["unknown"][0]["reason"]


def test_an_unknown_service_is_flagged(tmp_path):
    path = _write_compose(
        tmp_path,
        "services:\n  demo:\n    ports:\n      - \"${DEMO_PORT:-9001}:9001\"\n",
    )
    result = ratchet.scan({}, [path])
    assert len(result["unknown"]) == 1, result["unknown"]


def test_an_orphan_slot_is_flagged(tmp_path):
    """A registry slot that no compose file publishes."""
    path = _write_compose(
        tmp_path,
        "services:\n  demo:\n    ports:\n      - \"${DEMO_PORT:-9001}:9001\"\n",
    )
    registry = {
        "demo": {
            "slots": {
                "DEMO_PORT": {"host_port": 9001, "container_port": 9001},
                "GHOST_PORT": {
                    "host_port": 9998,
                    "container_port": 9998,
                    "compose_files": ["docker-compose.synthetic.yml"],
                },
            }
        }
    }
    result = ratchet.scan(registry, [path])
    assert len(result["orphans"]) == 1, result["orphans"]
    assert result["orphans"][0]["port_var"] == "GHOST_PORT"


def test_a_container_port_only_entry_is_never_judged(tmp_path):
    """One slot = container port only; Docker assigns the host port."""
    path = _write_compose(
        tmp_path,
        "services:\n  demo:\n    ports:\n      - \"9001\"\n",
    )
    registry = {"demo": {"slots": {"DEMO_PORT": {"host_port": 9001, "container_port": 9001}}}}
    result = ratchet.scan(registry, [path])
    assert result["bare"] == [], result["bare"]
    assert result["unknown"] == [], result["unknown"]


def test_an_unparseable_compose_file_is_an_instrument_error(tmp_path):
    path = tmp_path / "pmoves" / "docker-compose.broken.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("services:\n  demo:\n   ports:\n  - broken: [\n", encoding="utf-8")
    result = ratchet.scan({}, [path])
    assert result["errors"], "an unparseable file must be reported, not skipped"
    assert "cannot parse" in result["errors"][0]["error"]


# ---------------------------------------------------------------------------
# 3. the collision baseline contract
# ---------------------------------------------------------------------------


def test_a_new_collision_is_flagged():
    published = [
        {"file": "a.yml", "service": "one", "port_var": "P1", "host_port": 9000, "container_port": 9000},
        {"file": "b.yml", "service": "two", "port_var": "P2", "host_port": 9000, "container_port": 9000},
    ]
    collisions = ratchet.find_collisions(published)
    assert collisions[9000]["count"] == 2
    assert collisions[9000]["services"] == ["one", "two"]


def test_a_dynamic_slot_is_not_a_collision():
    published = [
        {"file": "a.yml", "service": "one", "port_var": "P1", "host_port": None, "container_port": 9000},
    ]
    assert ratchet.find_collisions(published) == {}


# ---------------------------------------------------------------------------
# 4. the python registries
# ---------------------------------------------------------------------------


def test_the_python_registries_are_read():
    py = ratchet.load_python_registries()
    assert "service_catalog" in py and "port_allocator" in py
    assert py["service_catalog"]
    assert py["port_allocator"]


def test_the_python_registry_rule_accepts_a_container_port():
    """`pmoves-ui` listens on 3000 and is published on 4482 -- the catalog
    records 3000, which is the CONTAINER port."""
    registry = {
        "pmoves-ui": {
            "slots": {
                "PMOVES_UI_PORT": {"host_port": 4482, "container_port": 3000},
            }
        }
    }
    findings = ratchet.check_python_registries(registry, {"service_catalog": {"pmoves-ui": 3000}})
    assert findings == []


def test_the_python_registry_rule_accepts_a_host_port():
    registry = {
        "botz-gateway": {"slots": {"BOTZ_PORT": {"host_port": 8054, "container_port": 8054}}},
    }
    findings = ratchet.check_python_registries(registry, {"port_allocator": {"botz-gateway": 8054}})
    assert findings == []


def test_the_python_registry_rule_rejects_a_stale_port():
    registry = {
        "hi-rag-gateway-gpu": {
            "slots": {"HIRAG_V1_GPU_HOST_PORT": {"host_port": 8187, "container_port": 8086}},
        }
    }
    findings = ratchet.check_python_registries(
        registry, {"service_catalog": {"hi-rag-gateway-gpu": 8110}}
    )
    assert len(findings) == 1
    assert findings[0]["port"] == 8110


def test_the_python_registry_rule_rejects_an_unknown_service():
    findings = ratchet.check_python_registries({}, {"port_allocator": {"nope": 1234}})
    assert len(findings) == 1
    assert "not in the canonical registry" in findings[0]["reason"]


# ---------------------------------------------------------------------------
# 5. the live tree
# ---------------------------------------------------------------------------


def test_the_canonical_registry_exists_and_is_well_formed():
    assert REGISTRY.exists(), f"missing registry: {REGISTRY}"
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    assert data["version"] == 1
    services = data["services"]
    assert isinstance(services, dict) and services
    for name, entry in services.items():
        slots = entry.get("slots")
        assert isinstance(slots, dict) and slots, name
        for key, slot in slots.items():
            assert "host_port" in slot, f"{name}/{key}"
            assert "container_port" in slot, f"{name}/{key}"


def test_every_compose_file_in_scope_parses_with_the_ratchets_loader():
    """Three files carry `!reset`/`!override`; a loader that cannot read them
    is a gate with a hole exactly where the hardened overlay lives."""
    files = ratchet.compose_files()
    assert len(files) > 50
    for path in files:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=ratchet.ComposeLoader)
        assert isinstance(data, dict), path.name


def test_the_8115_pair_the_operator_named_is_resolved():
    """node-registry keeps 8115; yt-cookie-refresher moved off it."""
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["services"]
    node = data["node-registry"]["slots"]["NODE_REGISTRY_PORT"]
    yt = data["yt-cookie-refresher"]["slots"]["YT_COOKIE_REFRESHER_PORT"]
    assert node["host_port"] == NODE_REGISTRY_PORT
    assert yt["host_port"] == YT_COOKIE_REFRESHER_PORT
    assert yt["host_port"] != node["host_port"]


def test_every_cross_service_duplicate_host_port_is_documented():
    """A host port two DIFFERENT services claim must be a documented collision.

    The registry deliberately records a host port more than once when the
    fleet's own shape calls for it: a service may publish the same port
    from two compose files under two variable names (measured: firefly,
    gateway-agent, n8n, ultimate-tts-studio, wger), and a service that no
    compose file in scope publishes is recorded as a `__registry_only_`
    slot (21 of them, measured).

    What must NOT happen is two services sharing a host port with no
    recorded reason -- that is the 8115 defect this gate exists to catch.
    """
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["services"]
    known = yaml.safe_load(COLLISIONS.read_text(encoding="utf-8"))["known_collisions"]

    owners: dict = {}
    for name, entry in data.items():
        for key, slot in (entry.get("slots") or {}).items():
            port = slot.get("host_port")
            if not port:
                continue
            if key.startswith("__registry_only_"):
                # Published by no compose file in scope: it cannot collide.
                continue
            owners.setdefault(port, set()).add(name)

    undocumented = {
        port: sorted(svcs)
        for port, svcs in owners.items()
        if len(svcs) > 1 and str(port) not in known
    }
    assert undocumented == {}, (
        "the registry records a host port shared by two services with no "
        f"entry in {COLLISIONS.name}: {undocumented}"
    )


def test_every_documented_collision_names_the_services_that_claim_it():
    """The baseline's `services` list is COPIED FROM THE MEASUREMENT."""
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["services"]
    known = yaml.safe_load(COLLISIONS.read_text(encoding="utf-8"))["known_collisions"]
    for port, entry in known.items():
        assert entry["services"], f"host {port} names no services"
        assert entry["reason"], f"host {port} has no reason"
        assert not entry["reason"].upper().startswith("REVIEW THIS"), (
            f"host {port} still carries the placeholder reason"
        )
        for svc in entry["services"]:
            assert svc in data, f"host {port} names {svc}, which is not in the registry"


def test_the_real_tree_has_both_python_registries():
    """The cross-check is only meaningful because the real tree HAS them.

    `load_python_registries` treats an ABSENT registry as "nothing to
    cross-check", so a tree that lost one of them would silently stop
    being checked. This test is what keeps that from happening.
    """
    assert (PMOVES / "tests" / "utils" / "service_catalog.py").is_file()
    assert (PMOVES / "scripts" / "port_allocator.py").is_file()
    py = ratchet.load_python_registries()
    assert py["service_catalog"], "the service catalog cross-check read nothing"
    assert py["port_allocator"], "the port allocator cross-check read nothing"


def test_the_live_gate_is_green_against_the_committed_registry():
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    payload = json.loads(proc.stdout)
    assert payload["bare_literals"] == [], payload["bare_literals"][:5]
    assert payload["registry_drift"] == [], payload["registry_drift"][:5]
    assert payload["unknown_slots"] == [], payload["unknown_slots"][:5]
    assert payload["orphan_slots"] == [], payload["orphan_slots"][:5]
    assert payload["python_registry_drift"] == [], payload["python_registry_drift"][:5]
    assert payload["problems"] == [], payload["problems"][:5]
    assert payload["new_collisions"] == {}, payload["new_collisions"]
    assert payload["stale_collisions"] == [], payload["stale_collisions"]
    assert proc.returncode == 0, proc.stdout[-4000:]


def test_the_gate_exits_one_on_a_violation(tmp_path):
    """Drive the shipped CLI against a synthetic tree."""
    root = tmp_path / "repo"
    pmoves = root / "pmoves"
    pmoves.mkdir(parents=True)
    (pmoves / "docker-compose.test.yml").write_text(
        "services:\n  demo:\n    ports:\n      - \"9001:9001\"\n", encoding="utf-8"
    )
    registry = tmp_path / "ports.yaml"
    registry.write_text(
        "version: 1\nservices:\n  demo:\n    slots:\n      DEMO_PORT:\n"
        "        host_port: 9001\n        container_port: 9001\n",
        encoding="utf-8",
    )
    collisions = tmp_path / "collisions.yaml"
    collisions.write_text("known_collisions: {}\n", encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--registry",
            str(registry),
            "--collisions",
            str(collisions),
            "--repo-root",
            str(root),
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(tmp_path),
    )
    payload = json.loads(proc.stdout)
    assert payload["bare_literals"], "a bare-literal host port must be reported"
    assert proc.returncode == 1, proc.stdout[-2000:]


def test_a_compose_file_with_no_services_is_not_an_instrument_error(tmp_path):
    """`docker-compose.base.yml` declares anchors, volumes and networks and
    NO services -- so it publishes zero host ports. That is a measured fact
    about the file, not a failure to measure it."""
    path = _write_compose(tmp_path, "x-env-tier-api:\n  cap_drop:\n  - ALL\n")
    result = ratchet.scan({}, [path])
    assert result["errors"] == [], result["errors"]
    assert result["anchors_only"], "the anchors-only file must be reported as such"


def test_a_compose_file_whose_services_is_not_a_mapping_is_an_instrument_error(tmp_path):
    path = _write_compose(tmp_path, "services:\n  - not\n  - a\n  - mapping\n")
    result = ratchet.scan({}, [path])
    assert result["errors"], "a malformed `services:` must be reported, not skipped"
    assert "not a mapping" in result["errors"][0]["error"]


def test_a_variable_with_no_default_is_looked_up_by_its_name(tmp_path):
    """`${FOO_PORT}` has no default, so its value is unknown -- but the NAME
    is still the registry key, and the entry must be checked against the
    registry rather than reported as an unknown slot."""
    value, var, is_bare = ratchet.resolve_host_slot("${DEMO_PORT}")
    assert value is None
    assert var == "DEMO_PORT"
    assert is_bare is False

    path = _write_compose(
        tmp_path,
        "services:\n  demo:\n    ports:\n      - \"${DEMO_PORT}:9001\"\n",
    )
    registry = {"demo": {"slots": {"DEMO_PORT": {"host_port": 9001, "container_port": 9001}}}}
    result = ratchet.scan(registry, [path])
    assert result["unknown"] == [], result["unknown"]
    assert result["bare"] == [], result["bare"]


def test_an_unreviewed_collision_entry_fails_the_gate(tmp_path):
    """The baseline writer emits the placeholder "REVIEW THIS"; the gate
    must refuse it, because a reason that says nothing is a claim nobody
    checked."""
    root = tmp_path / "repo"
    pmoves = root / "pmoves"
    pmoves.mkdir(parents=True)
    (pmoves / "docker-compose.test.yml").write_text(
        "services:\n"
        "  one:\n    ports:\n      - \"${ONE_PORT:-9000}:9000\"\n"
        "  two:\n    ports:\n      - \"${TWO_PORT:-9000}:9000\"\n",
        encoding="utf-8",
    )
    registry = tmp_path / "ports.yaml"
    registry.write_text(
        "version: 1\nservices:\n"
        "  one:\n    slots:\n      ONE_PORT:\n        host_port: 9000\n        container_port: 9000\n"
        "  two:\n    slots:\n      TWO_PORT:\n        host_port: 9000\n        container_port: 9000\n",
        encoding="utf-8",
    )
    collisions = tmp_path / "collisions.yaml"
    collisions.write_text(
        "known_collisions:\n"
        "  '9000':\n"
        "    services: [one, two]\n"
        "    files: [docker-compose.test.yml]\n"
        "    reason: REVIEW THIS -- a pre-existing duplicate host port\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--registry",
            str(registry),
            "--collisions",
            str(collisions),
            "--repo-root",
            str(root),
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    payload = json.loads(proc.stdout)
    assert payload["unreviewed_collisions"] == ["9000"], payload["unreviewed_collisions"]
    assert payload["new_collisions"] == {}, payload["new_collisions"]
    assert proc.returncode == 1, proc.stdout[-2000:]


def test_a_stale_collision_entry_fails_the_gate(tmp_path):
    """A baseline entry whose SET OF CLAIMANTS changed is stale: the reason on
    file was written about different services."""
    root = tmp_path / "repo"
    pmoves = root / "pmoves"
    pmoves.mkdir(parents=True)
    (pmoves / "docker-compose.test.yml").write_text(
        "services:\n"
        "  one:\n    ports:\n      - \"${ONE_PORT:-9000}:9000\"\n"
        "  two:\n    ports:\n      - \"${TWO_PORT:-9000}:9000\"\n",
        encoding="utf-8",
    )
    registry = tmp_path / "ports.yaml"
    registry.write_text(
        "version: 1\nservices:\n"
        "  one:\n    slots:\n      ONE_PORT:\n        host_port: 9000\n        container_port: 9000\n"
        "  two:\n    slots:\n      TWO_PORT:\n        host_port: 9000\n        container_port: 9000\n",
        encoding="utf-8",
    )
    collisions = tmp_path / "collisions.yaml"
    collisions.write_text(
        "known_collisions:\n"
        "  '9000':\n"
        "    services: [one, some-service-that-was-renamed]\n"
        "    files: [docker-compose.test.yml]\n"
        "    reason: these two are alternatives\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--registry",
            str(registry),
            "--collisions",
            str(collisions),
            "--repo-root",
            str(root),
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    payload = json.loads(proc.stdout)
    assert payload["stale_collisions"] == ["9000"], payload["stale_collisions"]
    assert proc.returncode == 1, proc.stdout[-2000:]
