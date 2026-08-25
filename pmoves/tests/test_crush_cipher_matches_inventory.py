"""crush_configurator must not drift from the canonical MCP inventory.

`pmoves/config/mcp_inventory.json` is the source of truth for MCP wiring, and
`.claude/mcp.json` / `kilo.json` are generated from it. `crush_configurator.py`
is NOT -- it carries its own literals -- which is how it kept two defects that
#2729 had already fixed everywhere else:

  * path   `/api/mcp/sse` answers 404; `/mcp/sse` answers 200. Verified against
           two independently-built containers, so it is a property of the server.
  * bearer an unset `${CIPHER_API_TOKEN}` is sent LITERALLY per Claude Code's MCP
           docs, and the shim 401s any non-empty token. `:-` sends empty, which
           the shim accepts, and a real token on nodes that set one.

Neither failure blocks a launch. Crush comes up and cipher is simply dark, which
is why this survived: the only symptom is memory that silently isn't there.

This test does not re-assert the correct values -- it asserts the two files
AGREE, so fixing the inventory is enough and this cannot drift again.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY = REPO_ROOT / "pmoves" / "config" / "mcp_inventory.json"
CONFIGURATOR = REPO_ROOT / "pmoves" / "tools" / "crush_configurator.py"

CIPHER_KEYS = ("pmoves-cipher", "pmoves-cipher-local")


def _inventory_text() -> str:
    return INVENTORY.read_text(encoding="utf-8")


def _configurator_text() -> str:
    return CONFIGURATOR.read_text(encoding="utf-8")


def test_both_files_exist():
    assert INVENTORY.is_file(), f"canonical inventory missing: {INVENTORY}"
    assert CONFIGURATOR.is_file(), f"generator missing: {CONFIGURATOR}"


def test_cipher_path_agrees_with_inventory():
    """The generator must use whatever path the inventory declares."""
    inv_paths = set(re.findall(r"8105(/[\w/-]*)", _inventory_text()))
    gen_paths = set(re.findall(r"8105(/[\w/-]*)", _configurator_text()))
    assert inv_paths, "inventory declares no :8105 path -- test anchor is stale"
    assert gen_paths <= inv_paths, (
        f"crush_configurator uses cipher path(s) {sorted(gen_paths - inv_paths)} "
        f"that the canonical inventory does not declare {sorted(inv_paths)}. "
        "Mirror the inventory; it is the source of truth."
    )


def test_no_bare_cipher_token_expansion():
    """`${VAR}` with no default is sent literally and is a guaranteed 401."""
    text = _configurator_text()
    assert "${CIPHER_API_TOKEN}" not in text, (
        "bare ${CIPHER_API_TOKEN} found. An unset variable is forwarded as the "
        "literal string and the cipher shim rejects any non-empty bearer, so "
        "cipher never connects. Use ${CIPHER_API_TOKEN:-}."
    )


def test_bearer_form_agrees_with_inventory():
    inv = set(re.findall(r"Bearer \$\{CIPHER_API_TOKEN[^\"]*", _inventory_text()))
    gen = set(re.findall(r"Bearer \$\{CIPHER_API_TOKEN[^\"]*", _configurator_text()))
    if gen:
        assert gen <= inv, (
            f"crush bearer form {sorted(gen)} diverges from inventory {sorted(inv)}"
        )


@pytest.mark.parametrize("key", CIPHER_KEYS)
def test_generated_config_carries_the_live_path(key):
    """End-to-end through the generator's own data, not a regex over source."""
    spec = importlib.util.spec_from_file_location("crush_configurator", CONFIGURATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules["crush_configurator"] = module
    spec.loader.exec_module(module)

    specs = [s for s in getattr(module, "MCP_SPECS", []) if getattr(s, "key", None) == key]
    if not specs:
        pytest.skip(f"{key} not present in MCP_SPECS (renamed or removed)")
    url = (specs[0].config or {}).get("url", "")
    assert "/api/mcp/sse" not in url, f"{key} still points at the 404 path: {url}"
    assert url.endswith("/mcp/sse"), f"{key} unexpected cipher URL: {url}"
