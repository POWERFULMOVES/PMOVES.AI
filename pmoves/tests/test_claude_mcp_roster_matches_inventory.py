"""The generated Claude MCP roster must carry a cipher entry this node can reach.

`.claude/mcp.json` is generated from `pmoves/config/mcp_inventory.json`, and the
inventory has declared BOTH endpoints since it was written:

    cipher_local_url  http://localhost:8105/mcp/sse
    cipher_fleet_url  http://${TS_Z890}:8105/mcp/sse

Only the fleet one reached the roster, and cipher is published on 127.0.0.1 on
every node -- so the fleet URL resolves, the host pings, and the connection is
still refused. Claude Code reports no error for an MCP server it cannot reach;
it simply offers no tools. The whole failure mode is memory that silently is
not there, which is why it survived across every session on this node.

These tests do not re-assert a literal URL. They assert the roster and the
inventory AGREE, so the inventory stays the single source of truth and a future
endpoint change cannot leave the roster pointing somewhere unreachable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from pmoves.tools import mcp_config_generator as gen

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY = REPO_ROOT / "pmoves" / "config" / "mcp_inventory.json"
CLAUDE_ROSTER = REPO_ROOT / ".claude" / "mcp.json"

# `.claude/mcp.json` is a tracked config: it is generated with the repo default
# endpoint and with placeholder expansion OFF so no secret is ever committed.
TRACKED_KWARGS: Dict[str, Any] = {"endpoint": "fleet", "allow_os_environ": False}


@pytest.fixture(scope="module")
def inventory() -> Dict[str, Any]:
    return gen.load_inventory(INVENTORY)


@pytest.fixture(scope="module")
def generated(inventory: Dict[str, Any]) -> Dict[str, Any]:
    return gen.generate_for_client("claude", inventory=inventory, **TRACKED_KWARGS)


@pytest.fixture(scope="module")
def roster() -> Dict[str, Any]:
    return json.loads(CLAUDE_ROSTER.read_text(encoding="utf-8"))


def _cipher_entries(servers: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in servers.items() if "cipher" in k and not k.startswith("_")}


def test_generator_emits_the_inventorys_local_cipher_url(
    inventory: Dict[str, Any], generated: Dict[str, Any]
) -> None:
    """A Claude session must be handed the endpoint its own node publishes."""
    local_url = inventory["defaults"]["cipher_local_url"]
    entries = _cipher_entries(generated["mcpServers"])
    urls = {k: v.get("url") for k, v in entries.items()}
    assert local_url in urls.values(), (
        f"generated Claude roster has no cipher entry at the inventory's "
        f"cipher_local_url {local_url!r}; it offers {urls}. Cipher is published "
        "on loopback, so a fleet-only roster gives every session on this node "
        "zero memory tools and says nothing about it."
    )


def test_tracked_roster_agrees_with_the_generator(
    generated: Dict[str, Any], roster: Dict[str, Any]
) -> None:
    """The committed roster must be what the generator produces, not a hand-edit.

    Compared field-by-field rather than whole-entry: the generator MERGES into
    the existing file, so a tracked entry may legitimately carry hand-added keys
    the inventory does not describe (`_note` on `pmoves-cipher` records the
    measured bearer/path probes). Every field the inventory DOES describe must
    match, which is what catches a stale or hand-edited roster.
    """
    for key, entry in _cipher_entries(generated["mcpServers"]).items():
        assert key in roster["mcpServers"], (
            f"{key} is generated from the inventory but missing from "
            f"{CLAUDE_ROSTER}. Regenerate with "
            "`python -m pmoves.tools.mcp_config_generator --client claude`."
        )
        tracked = roster["mcpServers"][key]
        for field, value in entry.items():
            assert tracked.get(field) == value, (
                f"{key}.{field} in {CLAUDE_ROSTER} has drifted from the inventory.\n"
                f"  tracked:   {tracked.get(field)!r}\n"
                f"  generated: {value!r}\n"
                "Regenerate; do not hand-edit the generated roster."
            )


def test_cipher_bearer_keeps_the_load_bearing_default(generated: Dict[str, Any]) -> None:
    """`${VAR}` is forwarded LITERALLY by Claude Code and the shim 401s it.

    `${CIPHER_API_TOKEN:-}` sends an empty bearer when unset -- which the shim
    accepts -- and a real token on nodes that set one. Dropping the `:-` turns
    a working local cipher into a 401 on every node without a token.
    """
    for key, entry in _cipher_entries(generated["mcpServers"]).items():
        auth = entry.get("headers", {}).get("Authorization")
        assert auth == "Bearer ${CIPHER_API_TOKEN:-}", (
            f"{key} Authorization header is {auth!r}; the `:-` default is "
            "load-bearing and must survive tracked-config generation."
        )
