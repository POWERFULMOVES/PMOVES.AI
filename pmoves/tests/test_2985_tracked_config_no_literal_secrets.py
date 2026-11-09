"""Regression tests for issue #2985: tracked bootstrap configs must never
render literal secrets from the OS environment — ${VAR} placeholders only.

`bootstrap_opencode` and `bootstrap_openclaw_scopes` drive tracked config
generation; if they ever call the generator with ``allow_os_environ=True``
(the old default), a node whose env holds real credentials writes live
tokens into committed files (caught on the 5090 by push protection,
2026-09-06 — origin stayed clean).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from pmoves.tools import bootstrap_opencode as bo
from pmoves.tools import bootstrap_openclaw_scopes as bos

# Shapes that must NEVER appear literally in tracked configs. Keep in sync
# with the credential families the inventory references (${HF_TOKEN},
# ${TAILSCALE_API_KEY}, ${E2B_API_KEY}, MCP path tokens).
SECRET_SHAPES = re.compile(
    r"(hf_[A-Za-z0-9]{20,}|tskey-[A-Za-z0-9\-]{10,}|e2b_[A-Za-z0-9]{30,}"
    r"|sk_e2b_[A-Za-z0-9]{20,}|/mcp/t-[A-Za-z0-9]{8,}/)"
)

POISON_ENV = {
    "HF_TOKEN": "hf_POISONpoisonPOISONpoisonPOISON",
    "TAILSCALE_API_KEY": "tskey-api-POISONpoisonPOISON",
    "E2B_API_KEY": "e2b_" + "0" * 40,
    "CIPHER_API_TOKEN": "poison-cipher-token",
    "TS_Z890": "10.0.0.1",
}


@pytest.fixture
def poisoned_inventory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Minimal inventory with one secret-bearing server; cache neutralized."""
    inv = tmp_path / "mcp_inventory.json"
    inv.write_text(
        json.dumps(
            {
                "version": 1,
                "defaults": {
                    "cipher_local_url": "http://localhost:8105/api/mcp/sse",
                },
                "groups": {
                    "core_pmoves": {
                        "servers": [
                            {
                                "key": "pmoves-cipher",
                                "description": "Cipher memory",
                                "transport": "sse",
                                "endpoint": "local",
                                "headers": {
                                    "Authorization": "Bearer ${CIPHER_API_TOKEN}"
                                },
                            }
                        ]
                    }
                },
            }
        )
    )
    monkeypatch.setattr(bo, "INVENTORY_PATH", inv)
    monkeypatch.setattr(bos, "INVENTORY_PATH", inv)
    return inv


@pytest.mark.parametrize("module", ["opencode", "scopes"])
def test_tracked_bootstrap_never_renders_os_env(
    poisoned_inventory: Path,
    monkeypatch: pytest.MonkeyPatch,
    module: str,
) -> None:
    """With poisoned OS env, rendered configs keep ${VAR}, never literals."""
    for var, value in POISON_ENV.items():
        monkeypatch.setenv(var, value)

    if module == "opencode":
        rendered = bo.canonical_opencode_mcp_servers()
    else:
        rendered = bos.canonical_scope_mcp_servers("edge", "local")

    blob = json.dumps(rendered)
    assert "${CIPHER_API_TOKEN}" in blob, "placeholder was lost from tracked render"
    assert not SECRET_SHAPES.search(blob), (
        "tracked bootstrap rendered a literal secret from the OS environment"
    )


def test_tracked_mode_is_explicit_in_source() -> None:
    """Static guard: both bootstrap tools must pass allow_os_environ=False."""
    for path in (bo.__file__, bos.__file__):
        assert "allow_os_environ=False" in Path(path).read_text(encoding="utf-8"), (
            f"{path} must generate tracked configs with allow_os_environ=False"
        )
