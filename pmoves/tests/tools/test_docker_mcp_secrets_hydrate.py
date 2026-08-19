"""Tests for pmoves.tools.docker_mcp_secrets_hydrate — the Docker MCP recovery road.

Guards the 2026-08-17 incident fix: a Docker Desktop VMM/backend migration wedged
the MCP secret resolver, and Docker re-prompted for keys the operator had entered by
hand. This tool re-pushes funnel-managed values from env.shared (no re-typing, no
rotation) and names non-funnel secrets as manual gaps instead of guessing.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import yaml

from pmoves.tools import docker_mcp_secrets_hydrate as mod


def _make_docker_mcp_dir(tmp_path: Path, enabled, catalog_secrets) -> Path:
    """Build a fake ~/.docker/mcp with registry.yaml + catalogs/docker-mcp.yaml."""
    d = tmp_path / "dockermcp"
    (d / "catalogs").mkdir(parents=True)
    (d / "registry.yaml").write_text(
        yaml.safe_dump({"registry": {s: {"ref": ""} for s in enabled}}), encoding="utf-8"
    )
    registry = {}
    for server, secs in catalog_secrets.items():
        registry[server] = {"secrets": secs} if secs else {}
    (d / "catalogs" / "docker-mcp.yaml").write_text(
        yaml.safe_dump({"version": 3, "registry": registry}), encoding="utf-8"
    )
    return d


def test_load_required_only_enabled_with_secrets(tmp_path):
    d = _make_docker_mcp_dir(
        tmp_path,
        enabled=["hostinger-mcp-server", "duckduckgo", "postman"],  # duckduckgo disabled-from-catalog view
        catalog_secrets={
            "hostinger-mcp-server": [{"name": "hostinger-mcp-server.api_token", "env": "APITOKEN"}],
            "duckduckgo": [],  # public, no secrets
            "postman": [{"name": "postman.postman-api-key", "env": "POSTMAN_API_KEY"}],
            "mcp-discord": [{"name": "discord.token", "env": "DISCORD_TOKEN"}],  # NOT enabled
        },
    )
    required = mod.load_required(d)
    names = {r.docker_name for r in required}
    assert names == {"hostinger-mcp-server.api_token", "postman.postman-api-key"}
    # disabled server's secret is excluded even though it's in the catalog
    assert "discord.token" not in names


def test_build_plan_classifies_pushable_missing_operator_only():
    required = [
        mod.Required("hostinger-mcp-server", "hostinger-mcp-server.api_token", "APITOKEN"),
        mod.Required("dockerhub", "dockerhub.pat_token", "HUB_PAT_TOKEN"),
        mod.Required("postman", "postman.postman-api-key", "POSTMAN_API_KEY"),
    ]
    secret_map = {
        "hostinger-mcp-server.api_token": "HOSTINGER_API_KEY",  # funnel-managed
        "dockerhub.pat_token": None,                            # declared operator-only
        # postman not in map -> falls back to env_var POSTMAN_API_KEY
    }
    env_shared = {"HOSTINGER_API_KEY": "realhostingervalue", "POSTMAN_API_KEY": "changeme"}

    plan = mod.build_plan(required, secret_map, env_shared)

    assert [r.docker_name for r, _ in plan.pushable] == ["hostinger-mcp-server.api_token"]
    assert plan.pushable[0][1] == "realhostingervalue"
    assert [r.docker_name for r in plan.operator_only] == ["dockerhub.pat_token"]
    # postman resolved via fallback to POSTMAN_API_KEY but that's a placeholder -> gap
    assert [r.docker_name for r, _ in plan.missing_in_funnel] == ["postman.postman-api-key"]


def test_hydrate_pushes_via_setter():
    plan = mod.Plan(pushable=[
        (mod.Required("hostinger-mcp-server", "hostinger-mcp-server.api_token", "APITOKEN"), "v1"),
        (mod.Required("postman", "postman.postman-api-key", "POSTMAN_API_KEY"), "v2"),
    ])
    calls = []

    def fake_setter(name, value):
        calls.append((name, value))
        return True, None

    pushed, errors = mod.hydrate(plan, setter=fake_setter)

    assert pushed == ["hostinger-mcp-server.api_token", "postman.postman-api-key"]
    assert errors == []
    assert calls == [("hostinger-mcp-server.api_token", "v1"), ("postman.postman-api-key", "v2")]


def test_hydrate_dry_run_pushes_nothing():
    plan = mod.Plan(pushable=[
        (mod.Required("hostinger-mcp-server", "hostinger-mcp-server.api_token", "APITOKEN"), "v1"),
    ])
    called = []
    pushed, errors = mod.hydrate(plan, dry_run=True, setter=lambda n, v: called.append(n) or (True, None))
    assert pushed == ["hostinger-mcp-server.api_token"]
    assert errors == []
    assert called == []  # setter never invoked in dry-run


def test_hydrate_collects_setter_errors():
    plan = mod.Plan(pushable=[
        (mod.Required("hostinger-mcp-server", "hostinger-mcp-server.api_token", "APITOKEN"), "v1"),
    ])
    pushed, errors = mod.hydrate(plan, setter=lambda n, v: (False, "resolver timeout"))
    assert pushed == []
    assert errors == [("hostinger-mcp-server.api_token", "resolver timeout")]


def test_load_key_mapping_treats_blank_as_operator_only(tmp_path):
    p = tmp_path / "map.yaml"
    p.write_text(textwrap.dedent("""
        version: 1
        map:
          hostinger-mcp-server.api_token: HOSTINGER_API_KEY
          dockerhub.pat_token:
    """), encoding="utf-8")
    m = mod.load_key_mapping(p)
    assert m["hostinger-mcp-server.api_token"] == "HOSTINGER_API_KEY"
    assert m["dockerhub.pat_token"] is None
