"""Tests for CHIT canonical signing in Agent Zero MCP server.

Verifies that geometry_publish_cgp signs CGPs before sending.
"""
import importlib.util
import pathlib
import sys

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

_AGENT_ZERO = pathlib.Path(__file__).resolve().parents[1] / "services" / "agent-zero"


def _load_agent_zero_mcp_server():
    """Load *the agent-zero* `mcp_server`, unambiguously.

    Two modules in this repo are named `mcp_server`:
    `pmoves/tools/mcp_server.py`, which imports the third-party `mcp` package at
    module scope, and `pmoves/services/agent-zero/mcp_server.py`, which is the
    one under test. A bare `import mcp_server` returns whichever already sits in
    `sys.modules`, so these tests used to pass or fail depending on which other
    test file shared their pytest process — surfacing as
    `ModuleNotFoundError: No module named 'mcp'` whenever the tools module won.

    The old `sys.path.insert(0, "pmoves/services/agent-zero")` was also relative
    to the working directory, so it only worked when pytest happened to be run
    from the repo root.

    Loading by absolute path removes both dependencies. The module is registered
    under the name `mcp_server` because `patch("mcp_server.httpx.AsyncClient")`
    resolves its target through `sys.modules`.
    """
    if str(_AGENT_ZERO) not in sys.path:
        sys.path.insert(0, str(_AGENT_ZERO))

    try:
        from services.common.bootstrap import bootstrap_import_paths
    except ImportError:
        pass
    else:
        bootstrap_import_paths()

    sys.modules.pop("mcp_server", None)
    spec = importlib.util.spec_from_file_location(
        "mcp_server", _AGENT_ZERO / "mcp_server.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["mcp_server"] = module
    spec.loader.exec_module(module)
    return module


class TestMCPServerCHITSigning:
    """Test MCP server signs CGPs before gateway post."""

    def test_sign_cgp_if_available_with_passphrase(self, monkeypatch):
        """_sign_cgp_if_available signs CGP when passphrase is set."""
        monkeypatch.setenv("CHIT_PASSPHRASE", "test-mcp-signing-key")
        # Import the function directly
        # Need to handle the bootstrap import
        mcp_server = _load_agent_zero_mcp_server()

        cgp = {
            "spec": "geometry.cgp.v1",
            "meta": {"source": "test"},
            "super_nodes": [],
        }
        result = mcp_server._sign_cgp_if_available(cgp)
        assert "sig" in result
        assert "hmac" in result["sig"]

    def test_sign_cgp_if_available_dev_mode(self, monkeypatch):
        """_sign_cgp_if_available returns unsigned in dev mode."""
        monkeypatch.delenv("CHIT_PASSPHRASE", raising=False)
        monkeypatch.delenv("CHIT_SIGNING_KEY", raising=False)
        mcp_server = _load_agent_zero_mcp_server()

        cgp = {
            "spec": "geometry.cgp.v1",
            "meta": {"source": "test"},
            "super_nodes": [],
        }
        result = mcp_server._sign_cgp_if_available(cgp)
        assert "sig" not in result

    @pytest.mark.asyncio
    async def test_geometry_publish_cgp_calls_sign(self, monkeypatch):
        """geometry_publish_cgp signs CGP before posting to gateway."""
        monkeypatch.setenv("CHIT_PASSPHRASE", "test-mcp-signing-key")
        mcp_server = _load_agent_zero_mcp_server()

        signed_cgps = []
        original_sign = mcp_server._sign_cgp_if_available

        def capture_sign(cgp):
            result = original_sign(cgp)
            signed_cgps.append(result)
            return result

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "shape_id": "test123"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(mcp_server, "_sign_cgp_if_available", side_effect=capture_sign):
            with patch("mcp_server.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                cgp = {
                    "spec": "geometry.cgp.v1",
                    "meta": {"source": "test"},
                    "super_nodes": [],
                }
                await mcp_server.geometry_publish_cgp(cgp)

        # Verify sign was called
        assert len(signed_cgps) == 1
        assert "sig" in signed_cgps[0]
