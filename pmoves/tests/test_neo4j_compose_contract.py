"""The neo4j compose contract (docs/TAC/TAC_NEO4J.md section 4), as one test per row.

Every row cites the Neo4j 5 Operations Manual (OM) or the vendor entrypoint.
`docker-compose.core.yml` is generated from docker-compose.yml, so both are checked;
`docker-compose.base.yml` declares the volumes the split files use.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

PMOVES = Path(__file__).resolve().parents[1]
VENDOR = "neo4j:5.26.30-community@sha256:037cf5756f0135cbfd66b739b6df7c7c4bb100f9ce11602f6f9538e17e02c74d"

PENDING = "pending road compose:pr:<N>: the compose half is a prepared patch (ops/knuckles-neo4j-compose-reconcile)"

# Rows this change introduces carry PEND; rows that already hold on main (the explicit
# APOC list, the LOAD CSV blocklist) are plain guards and run unmarked.
PEND = pytest.mark.xfail(strict=True, reason=PENDING) if PENDING else (lambda f: f)


def _svc(name: str = "docker-compose.yml", service: str = "neo4j") -> dict:
    return yaml.safe_load((PMOVES / name).read_text())["services"][service]


def _env(svc: dict) -> dict[str, str]:
    env = svc.get("environment") or []
    if isinstance(env, dict):
        return {k: str(v) for k, v in env.items()}
    return dict(e.split("=", 1) for e in env)


SPLIT = ("docker-compose.yml", "docker-compose.core.yml")


@PEND
@pytest.mark.parametrize("f", SPLIT)
def test_no_env_file(f):
    # the entrypoint turns every NEO4J_* var into a setting and does not skip NEO4J_PASSWORD
    assert "env_file" not in _svc(f)


@PEND
@pytest.mark.parametrize("f", SPLIT)
def test_no_host_ports(f):
    # internal-only; reached through the neo4j-tailnet forwarder (#3201)
    assert "ports" not in _svc(f)


@PEND
@pytest.mark.parametrize("f", SPLIT)
def test_plugins_variable_is_the_5x_name(f):
    env = _env(_svc(f))
    assert env.get("NEO4J_PLUGINS") == '["apoc"]'          # OM docker/plugins
    assert "NEO4JLABS_PLUGINS" not in env


@PEND
@pytest.mark.parametrize("f", SPLIT)
def test_apoc_file_config_key_is_spelled_right(f):
    env = _env(_svc(f))
    assert env.get("NEO4J_apoc_import_file_use__neo4j__config") == "true"
    assert not any(k.endswith("__config__true") for k in env)


@pytest.mark.parametrize("f", SPLIT)
def test_unrestricted_is_explicit_and_never_all_of_apoc(f):
    # explicit, so the plugin step's apoc.* default is skipped (neo4j-plugins.json)
    un = _env(_svc(f)).get("NEO4J_dbms_security_procedures_unrestricted", "")
    assert un and "apoc.*" not in un.split(",")          # OM security/securing-extensions


@PEND
@pytest.mark.parametrize("f", SPLIT)
def test_heap_is_set_and_initial_equals_max(f):
    env = _env(_svc(f))
    assert env.get("NEO4J_server_memory_heap_initial__size")                       # OM docker/configuration
    assert env["NEO4J_server_memory_heap_initial__size"] == env.get("NEO4J_server_memory_heap_max__size")  # OM performance/memory-configuration
    assert env.get("NEO4J_server_memory_pagecache_size")


@PEND
@pytest.mark.parametrize("f", SPLIT)
def test_logs_have_a_named_volume(f):
    assert "neo4j-logs:/logs" in _svc(f)["volumes"]       # OM docker/mounting-volumes


@PEND
@pytest.mark.parametrize("f", ("docker-compose.yml", "docker-compose.base.yml"))
def test_logs_volume_is_declared(f):
    assert "neo4j-logs" in (yaml.safe_load((PMOVES / f).read_text()).get("volumes") or {})


@PEND
@pytest.mark.parametrize("f", SPLIT)
def test_auth_guard_names_the_file_that_has_the_key(f):
    auth = _env(_svc(f))["NEO4J_AUTH"]
    assert auth.startswith("neo4j/${NEO4J_PASSWORD:?") and "env.shared" in auth


@PEND
@pytest.mark.parametrize("f", SPLIT)
def test_image_is_overridable_and_defaults_to_the_digest_pin(f):
    assert _svc(f)["image"] == "${NEO4J_IMAGE:-" + VENDOR + "}"


@pytest.mark.parametrize("f", SPLIT)
def test_load_csv_blocklist_kept(f):
    assert _env(_svc(f)).get("NEO4J_internal_dbms_cypher__ip__blocklist") == "0.0.0.0/0,::/0"


@PEND
def test_no_neo4j_bind_anywhere():
    for f in (*SPLIT, "Makefile"):
        assert "NEO4J_BIND" not in (PMOVES / f).read_text(), f
    assert not (PMOVES / "scripts" / "neo4j_bind_from_env_file.py").exists()


FALLBACK = re.compile(r"\$\{[A-Z0-9_]*PASSWORD:-[^}]")


@pytest.mark.parametrize("f,service", [
    ("docker-compose.elder-melchor.yml", "neo4j"),
    ("docker-compose.jellyfin-ai.yml", "jellyfin-neo4j"),
])
@PEND
def test_no_hardcoded_fallback_password(f, service):
    text = (PMOVES / f).read_text()
    assert not FALLBACK.search(text), FALLBACK.findall(text)


@PEND
def test_jellyfin_neo4j_is_digest_pinned_with_5x_memory_keys():
    svc = _svc("docker-compose.jellyfin-ai.yml", "jellyfin-neo4j")
    assert "@sha256:" in svc["image"]
    env = _env(svc)
    assert not any(k.startswith("NEO4J_dbms_memory_") for k in env)
    assert not any("gds." in v for v in env.values())     # no GDS plugin is installed
