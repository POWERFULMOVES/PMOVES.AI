"""Tests for pmoves.tools.mcp_config_generator."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from pmoves.tools import mcp_config_generator as gen


@pytest.fixture
def sample_inventory(tmp_path: Path) -> Path:
    path = tmp_path / "mcp_inventory.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "defaults": {
                    "cipher_local_url": "http://localhost:8105/mcp/sse",
                    "cipher_fleet_url": "http://${TS_Z890}:8105/mcp/sse",
                    "agent_zero_fleet_url": "http://${TS_Z890}:8080/mcp",
                },
                "groups": {
                    "core_pmoves": {
                        "servers": [
                            {
                                "key": "pmoves-cipher",
                                "description": "Cipher memory",
                                "transport": "sse",
                                "endpoint": "fleet",
                                "url": "http://${TS_Z890}:8105/mcp/sse",
                                "headers": {"Authorization": "Bearer ${CIPHER_API_TOKEN}"},
                            },
                            {
                                "key": "agent-zero",
                                "description": "Agent Zero",
                                "transport": "http",
                                "endpoint": "fleet",
                                "url": "http://${TS_Z890}:8080/mcp",
                            },
                            {
                                "key": "pmoves-nats-fleet",
                                "description": "NATS",
                                "transport": "stdio",
                                "command": "uv",
                                "args": ["run", "nats_mcp.server"],
                                "env": {"NATS_URL": "${NATS_URL}"},
                            },
                            {
                                "key": "hermes-only",
                                "description": "Hermes-only server",
                                "transport": "sse",
                                "url": "http://localhost:7000/sse",
                                "clients": ["hermes"],
                            },
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def context() -> dict[str, str]:
    return {
        "TS_Z890": "z890.example.com",
        "CIPHER_API_TOKEN": "test-token",
        "NATS_URL": "nats://localhost:4222",
    }


def test_load_inventory_version_guard(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"version": 99}), encoding="utf-8")
    with pytest.raises(gen.MCPConfigError):
        gen.load_inventory(path)


def test_expand_simple_and_default() -> None:
    env = {"EXISTING": "value"}
    assert gen._expand("${EXISTING}", env) == "value"
    assert gen._expand("${MISSING:-fallback}", env) == "fallback"
    assert gen._expand("${MISSING}", env) == "${MISSING}"


def test_expand_nested_default() -> None:
    env = {"OUTER": "outer-value"}
    # inner ${OUTER} should resolve, then outer default uses it
    assert gen._expand("${MISSING:-${OUTER}}", env) == "outer-value"
    assert gen._expand("${A:-${B:-fallback}}", {}) == "fallback"


def test_render_claude_kimi(sample_inventory: Path, context: dict[str, str]) -> None:
    inventory = gen.load_inventory(sample_inventory)
    rendered = gen.generate_for_client("claude", inventory=inventory, context=context)
    servers = rendered["mcpServers"]
    assert "pmoves-cipher" in servers
    assert servers["pmoves-cipher"]["type"] == "sse"
    assert servers["pmoves-cipher"]["url"] == "http://z890.example.com:8105/mcp/sse"
    assert servers["pmoves-cipher"]["headers"]["Authorization"] == "Bearer test-token"
    assert "hermes-only" not in servers


def test_render_kilocode_permission_object(sample_inventory: Path, context: dict[str, str]) -> None:
    inventory = gen.load_inventory(sample_inventory)
    rendered = gen.generate_for_client("kilocode", inventory=inventory, context=context)
    assert "pmoves-cipher_*" in rendered["permission"]
    assert rendered["permission"]["pmoves-cipher_*"] == "allow"
    assert rendered["mcp"]["pmoves-nats-fleet"]["type"] == "local"


def test_render_crush_uses_sse_type(sample_inventory: Path, context: dict[str, str]) -> None:
    inventory = gen.load_inventory(sample_inventory)
    rendered = gen.generate_for_client("crush", inventory=inventory, context=context)
    assert rendered["mcp"]["pmoves-cipher"]["type"] == "sse"
    assert rendered["mcp"]["agent-zero"]["type"] == "http"


def test_render_hermes_local_cipher(sample_inventory: Path, context: dict[str, str]) -> None:
    inventory = gen.load_inventory(sample_inventory)
    rendered = gen.generate_for_client("hermes", inventory=inventory, context=context)
    servers = rendered["mcp_servers"]
    assert "pmoves-cipher" in servers
    assert "hermes-only" in servers
    assert servers["pmoves-cipher"]["enabled"] is True


def test_write_client_config_merges_json(tmp_path: Path, sample_inventory: Path, context: dict[str, str]) -> None:
    inventory = gen.load_inventory(sample_inventory)
    existing = tmp_path / "mcp.json"
    existing.write_text(json.dumps({"mcpServers": {"old": {"type": "sse", "url": "http://old"}}}), encoding="utf-8")
    gen.write_client_config("kimi", existing, merge=True, inventory=inventory, context=context)
    data = json.loads(existing.read_text(encoding="utf-8"))
    assert "old" in data["mcpServers"]
    assert "pmoves-cipher" in data["mcpServers"]
    assert (tmp_path / "mcp.json.pre-mcp-bootstrap.bak").exists()


def test_write_client_config_kilocode_permissions_merge(tmp_path: Path, sample_inventory: Path, context: dict[str, str]) -> None:
    inventory = gen.load_inventory(sample_inventory)
    existing = tmp_path / "kilo.json"
    existing.write_text(
        json.dumps(
            {
                "mcp": {"existing": {"type": "remote", "url": "http://existing"}},
                "permission": {"bash": "allow", "existing_*": "allow"},
            }
        ),
        encoding="utf-8",
    )
    gen.write_client_config("kilocode", existing, merge=True, inventory=inventory, context=context)
    data = json.loads(existing.read_text(encoding="utf-8"))
    assert "existing" in data["mcp"]
    assert "pmoves-cipher" in data["mcp"]
    assert data["permission"]["bash"] == "allow"
    assert data["permission"]["pmoves-cipher_*"] == "allow"


def test_deep_merge_lists_unique() -> None:
    merged = gen._deep_merge(["a"], ["a", "b"])
    assert merged == ["a", "b"]


def test_deep_merge_args_replaces_list() -> None:
    base = {"command": "npx", "args": ["-y", "old-package"]}
    overlay = {"args": ["-y", "new-package"]}
    merged = gen._deep_merge(base, overlay)
    assert merged["args"] == ["-y", "new-package"]
