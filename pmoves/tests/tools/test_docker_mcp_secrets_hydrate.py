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


# --- profile-aware discovery -------------------------------------------------
# The gateway runs `docker mcp gateway run --profile <p>`. The hydrator used to
# discover only from registry.yaml (the Toolkit's enabled-server list). Those are
# different sets, and on the 4090 the difference was silent: `github-official`
# lives in the pmoves_5090_web profile the gateway actually runs, is absent from
# registry.yaml, and so was never even considered -- not pushed, and not reported
# as a gap either. The server started with an empty
# GITHUB_PERSONAL_ACCESS_TOKEN and every call returned 401 Bad credentials.


def test_profiles_are_read_from_the_gateway_invocation(tmp_path: Path):
    """Ground truth for what runs is .mcp.json, not a hardcoded default.

    Both mcp-toolkit-connect.sh and mcp-toolkit-bootstrap.sh default to
    `pmoves_5090_web`, so trusting the default would report the same profile on
    every node regardless of what that node's gateway was actually started with.
    """
    mcp_json = tmp_path / ".mcp.json"
    mcp_json.write_text(
        '{"mcpServers":{"MCP_DOCKER":{"command":"docker","args":'
        '["mcp","gateway","run","--profile","pmoves_4090_web"],"type":"stdio"}}}',
        encoding="utf-8",
    )
    assert mod.profiles_from_mcp_json(mcp_json) == ["pmoves_4090_web"]


def test_no_mcp_json_yields_no_profiles_rather_than_a_guess(tmp_path: Path):
    """Absent config must not fall back to a node-named default."""
    assert mod.profiles_from_mcp_json(tmp_path / "nope.json") == []


def test_profile_secrets_are_discovered(monkeypatch):
    """A server's secrets are read from `docker mcp profile show` output."""
    profile_yaml = textwrap.dedent(
        """
        version: 1
        id: pmoves_5090_web
        servers:
            - type: image
              snapshot:
                server:
                    name: github-official
                    secrets:
                        - name: github.personal_access_token
                          env: GITHUB_PERSONAL_ACCESS_TOKEN
            - type: image
              snapshot:
                server:
                    name: context7
        """
    )
    monkeypatch.setattr(mod, "_profile_show", lambda name: profile_yaml)
    found = mod.load_required_from_profile("pmoves_5090_web")
    assert [(r.server, r.docker_name, r.env_var) for r in found] == [
        ("github-official", "github.personal_access_token", "GITHUB_PERSONAL_ACCESS_TOKEN")
    ]


def test_profile_and_registry_requirements_are_merged_without_duplicates(monkeypatch, tmp_path: Path):
    """A server in BOTH sources is required once, not twice.

    The union is the point: registry-only servers keep working, and profile-only
    servers stop being invisible.
    """
    (tmp_path / "catalogs").mkdir()
    (tmp_path / "registry.yaml").write_text(
        yaml.safe_dump({"registry": {"e2b": {}}}), encoding="utf-8"
    )
    (tmp_path / "catalogs" / "docker-mcp.yaml").write_text(
        yaml.safe_dump(
            {"registry": {"e2b": {"secrets": [{"name": "e2b.api_key", "env": "E2B_API_KEY"}]}}}
        ),
        encoding="utf-8",
    )
    profile_yaml = textwrap.dedent(
        """
        servers:
            - snapshot:
                server:
                    name: e2b
                    secrets:
                        - name: e2b.api_key
                          env: E2B_API_KEY
            - snapshot:
                server:
                    name: github-official
                    secrets:
                        - name: github.personal_access_token
                          env: GITHUB_PERSONAL_ACCESS_TOKEN
        """
    )
    monkeypatch.setattr(mod, "_profile_show", lambda name: profile_yaml)

    merged = mod.load_required(tmp_path, profiles=["p"])
    pairs = sorted((r.server, r.docker_name) for r in merged)
    assert pairs == [
        ("e2b", "e2b.api_key"),
        ("github-official", "github.personal_access_token"),
    ], pairs


# --- the two sync tools must agree on Docker's secret NAMES ------------------
# There are two writers into the same Docker MCP secret store:
#   scripts/mcp-toolkit-secrets-sync.sh   env-var -> docker-secret-name
#   config/docker_mcp_secret_map.yaml     docker-secret-name -> env.shared key
# They are keyed on the same strings from opposite directions, with nothing
# holding them together. `postman.api_key` in the shell script vs
# `postman.postman-api-key` everywhere else is what that costs: the sync writes
# a secret under a name no server reads, reports success, and the server still
# starts unauthenticated.


def _shell_secret_names() -> set[str]:
    """Docker secret names the shell sync script writes."""
    import re

    script = (
        Path(__file__).resolve().parents[3]
        / "pmoves" / "scripts" / "mcp-toolkit-secrets-sync.sh"
    )
    text = script.read_text(encoding="utf-8")
    block = text.split("declare -A SECRET_MAP=(", 1)[1].split(")", 1)[0]
    return set(re.findall(r'\]="([^"]+)"', block))


def _map_secret_names() -> set[str]:
    """Docker secret names the hydrate key-map knows."""
    path = (
        Path(__file__).resolve().parents[3]
        / "pmoves" / "config" / "docker_mcp_secret_map.yaml"
    )
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return set((doc.get("map") or {}).keys())


def test_the_shell_sync_and_the_hydrate_map_agree_on_secret_names():
    """A name in one and not the other is a secret nobody provisions correctly.

    Measured against the live profile on 2026-08-28, Docker's own names are
    hostinger-mcp-server.api_token, dockerhub.pat_token,
    github.personal_access_token and postman.postman-api-key. Any name here that
    Docker does not use writes into a slot no server reads.
    """
    shell = _shell_secret_names()
    mapped = _map_secret_names()

    only_shell = shell - mapped
    assert not only_shell, (
        "secret names the shell sync writes but the hydrate map does not know "
        f"(hydrate will never resolve them): {sorted(only_shell)}"
    )


def test_every_mapped_name_is_dotted_and_lowercase():
    """Docker MCP secret ids are `<server>.<field>`. A typo here is silent."""
    for name in _map_secret_names():
        assert "." in name, f"not a namespaced Docker secret id: {name!r}"
        assert name == name.lower(), f"Docker secret ids are lowercase: {name!r}"


# --- the SSE listener path has no .mcp.json ---------------------------------
# Two supported ways to run the gateway, and they name the profile differently:
#   stdio  -> root .mcp.json carries `--profile <p>`
#   SSE    -> scripts/mcp-toolkit-gateway-listen.sh reads PMOVES_MCP_PROFILE_ID
# Discovering only the first left the SSE path silently registry-only -- the
# same hole this branch set out to close, on the path the Makefile documents.


def test_the_sse_listener_profile_env_is_honoured(monkeypatch, tmp_path: Path):
    """With no .mcp.json, PMOVES_MCP_PROFILE_ID is what the gateway was run with."""
    monkeypatch.setenv("PMOVES_MCP_PROFILE_ID", "pmoves_4090_web")
    assert mod.discover_profiles(mcp_json=tmp_path / "absent.json") == ["pmoves_4090_web"]


def test_mcp_json_wins_over_the_env(monkeypatch, tmp_path: Path):
    """A running stdio gateway is stronger evidence than an exported default."""
    monkeypatch.setenv("PMOVES_MCP_PROFILE_ID", "pmoves_4090_web")
    mcp_json = tmp_path / ".mcp.json"
    mcp_json.write_text(
        '{"mcpServers":{"MCP_DOCKER":{"args":["mcp","gateway","run","--profile","pmoves_5090_web"]}}}',
        encoding="utf-8",
    )
    assert mod.discover_profiles(mcp_json=mcp_json) == ["pmoves_5090_web"]


def test_an_unset_env_is_not_a_guess(monkeypatch, tmp_path: Path):
    """The listener DEFAULTS to pmoves_5090_web when the var is unset.

    Mirroring that default here would reintroduce exactly the node-named guess
    this branch removed: every node would report the 5090's profile whether or
    not it runs it. Only an explicitly exported value counts.
    """
    monkeypatch.delenv("PMOVES_MCP_PROFILE_ID", raising=False)
    assert mod.discover_profiles(mcp_json=tmp_path / "absent.json") == []
