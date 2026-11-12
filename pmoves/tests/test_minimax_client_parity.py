"""Tests for the MiniMax Code client PMOVES parity lane (2026-10-26).

The operator's other agent stacks (claude, kimi, kilocode, opencode, hermes,
crush) each receive the PMOVES MCP roster from
``pmoves/config/mcp_inventory.json`` via ``pmoves/tools/mcp_config_generator.py``.
The MiniMax Code client (the Mavis desktop runtime) was not a generator
target, so ``~/.minimax/mcp.json`` carried only the ``composio`` entry and the
client had none of the PMOVES integration its siblings have.

This lane closes that gap in three coupled pieces:

1. ``render_minimax()`` -- a MiniMax-NATIVE renderer. The client needs
   ``type`` / ``enabled`` / ``configured`` / ``builtin`` per server, which the
   Claude/Kimi renderer omits.
2. A ``pmoves.bootstrap/v1`` client profile
   (``pmoves/configs/mavis_collection/clients/minimax-code.yaml``) that pins
   the roster AND carries the service tags / routing / constraints halves of
   the bootstrap contract.
3. A profile-driven roster filter, so the profile is load-bearing rather
   than documentation -- the rendered config and the profile can be diffed
   against each other.

The tests below pin each of those contracts. The static ones run anywhere;
the profile-validation test shells out to the same resolver the operator
would use.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pmoves.tools import mcp_config_generator as gen


REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = (
    REPO_ROOT
    / "pmoves"
    / "configs"
    / "mavis_collection"
    / "clients"
    / "minimax-code.yaml"
)
SCHEMA_PATH = (
    REPO_ROOT
    / "pmoves"
    / "configs"
    / "mavis_collection"
    / "manifest.schema.yaml"
)
RESOLVER_PATH = REPO_ROOT / "pmoves" / "tools" / "mavis_collection_resolve.py"

REMOTE_TRANSPORTS = ("sse", "http", "streamable-http")


@pytest.fixture
def sample_inventory(tmp_path: Path) -> Path:
    """A minimal inventory shaped like the real one (v1, groups, defaults)."""
    path = tmp_path / "mcp_inventory.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "defaults": {
                    "cipher_local_url": "http://localhost:8105/api/mcp/sse",
                    "agent_zero_local_url": "http://localhost:8081/mcp",
                },
                "groups": {
                    "core_pmoves": {
                        "servers": [
                            {
                                "key": "pmoves-cipher-local",
                                "description": "Local cipher memory",
                                "transport": "sse",
                                "endpoint": "local",
                                "endpoint_prefix": "cipher",
                                "url": "http://localhost:8105/api/mcp/sse",
                                "headers": {"Authorization": "Bearer ${CIPHER_API_TOKEN}"},
                                "clients": ["hermes", "claude", "minimax"],
                            },
                            {
                                "key": "agent-zero",
                                "description": "Agent Zero",
                                "transport": "sse",
                                "endpoint": "local",
                                "endpoint_prefix": "agent_zero",
                                "url": "http://localhost:8081/mcp",
                            },
                            {
                                "key": "pmoves-nats-fleet",
                                "description": "NATS bridge",
                                "transport": "stdio",
                                "command": "uv",
                                "args": ["run", "nats_mcp.server"],
                                "env": {"NATS_URL": "${NATS_URL}"},
                            },
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# 1. The client is a first-class generator target.
# ---------------------------------------------------------------------------


def test_minimax_is_a_registered_client_target() -> None:
    """`minimax` must be renderable and have a default output path.

    Regression guard: a renderer that exists but has no DEFAULT_OUTPUTS entry
    would make `--client minimax` write to nowhere, and the client would
    silently keep its composio-only roster.
    """
    assert "minimax" in gen.RENDERERS
    assert "minimax" in gen.DEFAULT_OUTPUTS
    assert gen.DEFAULT_OUTPUTS["minimax"].name == "mcp.json"
    assert gen.DEFAULT_OUTPUTS["minimax"].parent.name == ".minimax"


def test_minimax_has_a_registered_client_profile() -> None:
    """A client with a profile must have the profile ON DISK.

    The profile is what pins the roster; a registered-but-missing profile
    would make every `--client minimax` run fail closed.
    """
    assert "minimax" in gen.CLIENT_PROFILES
    profile = gen.CLIENT_PROFILES["minimax"]
    assert profile.exists(), f"registered client profile is missing: {profile}"
    assert profile == PROFILE_PATH


# ---------------------------------------------------------------------------
# 2. The MiniMax-NATIVE schema.
# ---------------------------------------------------------------------------


def test_render_minimax_emits_the_minimax_native_keys(sample_inventory: Path) -> None:
    """Every rendered server carries the four MiniMax runtime keys.

    MiniMax Code requires an explicit `type` transport discriminator (the
    Claude renderer omits it and lets Claude infer), uses `enabled` rather
    than `disabled`, and the runtime owns `configured` / `builtin`.
    """
    inventory = gen.load_inventory(sample_inventory)
    rendered = gen.generate_for_client(
        "minimax",
        inventory=inventory,
        endpoint="local",
        use_profile=False,
    )
    servers = rendered["mcpServers"]
    assert servers, "rendered an empty roster"
    for key, entry in servers.items():
        assert entry["type"] in REMOTE_TRANSPORTS + ("stdio",), f"{key}: bad type"
        assert isinstance(entry["enabled"], bool), f"{key}: enabled must be a bool"
        assert entry["configured"] is True, f"{key}: configured must be True"
        assert entry["builtin"] is False, f"{key}: builtin must be False"


def test_render_minimax_never_mixes_stdio_and_remote_fields(sample_inventory: Path) -> None:
    """A server is EITHER stdio (command/args/env) OR remote (url/headers).

    The MiniMax MCP contract does not allow both on one entry -- the runtime
    picks the launcher path by `type` and a mixed entry dead-ends silently.
    """
    inventory = gen.load_inventory(sample_inventory)
    rendered = gen.generate_for_client(
        "minimax", inventory=inventory, endpoint="local", use_profile=False
    )
    for key, entry in rendered["mcpServers"].items():
        if entry["type"] == "stdio":
            assert "command" in entry, f"{key}: stdio entry needs a command"
            assert "url" not in entry, f"{key}: stdio entry must not carry a url"
            assert "headers" not in entry, f"{key}: stdio entry must not carry headers"
        else:
            assert "url" in entry, f"{key}: remote entry needs a url"
            assert "command" not in entry, f"{key}: remote entry must not carry a command"
            assert "args" not in entry, f"{key}: remote entry must not carry args"


def test_render_minimax_maps_disabled_to_enabled_false(sample_inventory: Path) -> None:
    """The inventory's `disabled: true` renders as MiniMax's `enabled: false`.

    MiniMax has no `disabled` key -- a renderer that emitted `disabled`
    would produce an entry the runtime ignores, i.e. a server that stays ON.
    """
    inventory = gen.load_inventory(sample_inventory)
    inventory["groups"]["core_pmoves"]["servers"][0]["disabled"] = True
    rendered = gen.generate_for_client(
        "minimax", inventory=inventory, endpoint="local", use_profile=False
    )
    entry = rendered["mcpServers"]["pmoves-cipher-local"]
    assert entry["enabled"] is False
    assert "disabled" not in entry


# ---------------------------------------------------------------------------
# 3. The profile is load-bearing.
# ---------------------------------------------------------------------------


def test_profile_filter_renders_exactly_the_declared_roster() -> None:
    """Only the profile's `tools[].key` entries are rendered.

    This is the property that makes the profile and the generated config
    diffable against each other. It also keeps the client off servers the
    operator has not sanctioned for it (the docker gateway, pipecat, e2b).
    """
    import yaml

    profile = yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8"))
    declared = [
        t["key"] for t in profile["super_nodes"]["tools"] if isinstance(t, dict) and t.get("key")
    ]
    assert declared, "the client profile declares no tools"

    inventory = gen.load_inventory()
    rendered = gen.generate_for_client("minimax", inventory=inventory, endpoint="local")
    assert sorted(rendered["mcpServers"]) == sorted(declared)


def test_profile_filter_fails_closed_on_an_unknown_key() -> None:
    """A profile naming a server the inventory does not resolve is an error.

    Fail-closed on purpose: a well-formed but dead roster entry is exactly
    the class of bug this lane exists to prevent.
    """
    import yaml
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        broken = Path(tmp) / "broken.yaml"
        profile = yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8"))
        profile["super_nodes"]["tools"].append(
            {"key": "no-such-mcp-server", "transport": "sse"}
        )
        broken.write_text(yaml.safe_dump(profile), encoding="utf-8")

        with pytest.raises(gen.MCPConfigError) as exc:
            gen.generate_for_client(
                "minimax", inventory=gen.load_inventory(), endpoint="local", profile_path=broken
            )
        assert "no-such-mcp-server" in str(exc.value)


def test_profile_filter_can_be_bypassed_explicitly() -> None:
    """`use_profile=False` renders the whole inventory (the escape hatch)."""
    inventory = gen.load_inventory()
    filtered = gen.generate_for_client("minimax", inventory=inventory, endpoint="local")
    unfiltered = gen.generate_for_client(
        "minimax", inventory=inventory, endpoint="local", use_profile=False
    )
    assert len(unfiltered["mcpServers"]) > len(filtered["mcpServers"])


# ---------------------------------------------------------------------------
# 4. The bootstrap profile itself.
# ---------------------------------------------------------------------------


def test_client_profile_validates_against_the_bootstrap_schema() -> None:
    """The shipped profile must validate against pmoves.bootstrap/v1.

    Runs the same resolver the operator would run, so a schema change that
    breaks the profile fails here rather than at client boot.
    """
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, str(RESOLVER_PATH), "validate", "--manifest", str(PROFILE_PATH)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, f"profile failed validation:\n{proc.stdout}\n{proc.stderr}"


def test_client_profile_carries_all_four_bootstrap_halves() -> None:
    """identity + tools + services + routing + constraints must all be present.

    The bootstrap contract is: identity (who is loading), available tools +
    MCPs, service tags, routing, and constraints (what NOT to do). A profile
    missing any one of them is not the full contract.
    """
    import yaml

    profile = yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8"))
    assert profile["spec"] == "pmoves.bootstrap/v1"
    assert profile["identity"]["agent"] == "Mavis"
    assert profile["meta"]["home"] == "~/.minimax/"

    super_nodes = profile["super_nodes"]
    for group in ("tools", "services", "routing", "constraints"):
        assert super_nodes.get(group), f"client profile is missing the '{group}' group"

    # Every declared tool key must exist in the real inventory.
    inventory = gen.load_inventory()
    known = {
        s["key"]
        for g in inventory["groups"].values()
        for s in g["servers"]
    }
    for entry in super_nodes["tools"]:
        assert entry["key"] in known, f"profile declares unknown tool key: {entry['key']}"


def test_client_profile_constraints_all_cite_a_source() -> None:
    """Every constraint states where the rule came from.

    A prohibition a later agent cannot cite is a prohibition it will not
    follow. `source` is the pointer the resolver requires.
    """
    import yaml

    profile = yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8"))
    for entry in profile["super_nodes"]["constraints"]:
        assert entry.get("source"), f"constraint has no source: {entry.get('rule')}"
        assert entry.get("reason"), f"constraint has no reason: {entry.get('rule')}"


def test_bootstrap_schema_declares_the_four_client_groups() -> None:
    """The schema must declare tools/services/routing/constraints.

    The schema is permissive at the edges (additionalProperties) so a missing
    group would NOT fail validation -- it would just never be checked. This
    ratchet is what keeps the permissive edge honest.
    """
    import yaml

    schema = yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))
    properties = schema["properties"]["super_nodes"]["properties"]
    for group in ("tools", "services", "routing", "constraints"):
        assert group in properties, f"bootstrap schema does not declare '{group}'"


def test_minimax_agent_form_exists_and_is_named_mavis() -> None:
    """The profile's `form_ref` must point at a real form named Mavis.

    The schema's `identity.agent` enum allows "Mavis"; the forms directory
    had no such form until this lane added one. A dangling form_ref would
    make the profile point at nothing.
    """
    import yaml

    profile = yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8"))
    form_path = REPO_ROOT / profile["identity"]["form_ref"]
    assert form_path.exists(), f"form_ref points at a missing file: {form_path}"
    form = yaml.safe_load(form_path.read_text(encoding="utf-8"))
    assert form["name"] == profile["identity"]["agent"]
