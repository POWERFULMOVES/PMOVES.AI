import importlib
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

sys.modules.setdefault("services", importlib.import_module("pmoves.services"))

from services.common.nats_client import (
    DEFAULT_NATS_URL,
    NatsConnectionConfig,
    create_nats_connection,
    publish_cgp,
)


def test_default_nats_url_from_env(monkeypatch):
    """DEFAULT_NATS_URL reads from NATS_URL env var."""
    monkeypatch.setenv("NATS_URL", "nats://custom:4222")
    # Re-import to pick up env change
    import importlib
    from services.common import nats_client as nc_mod
    importlib.reload(nc_mod)
    assert nc_mod.DEFAULT_NATS_URL == "nats://custom:4222"
    # Restore
    monkeypatch.delenv("NATS_URL")
    importlib.reload(nc_mod)


def test_nats_connection_config_defaults():
    """NatsConnectionConfig has sensible defaults."""
    config = NatsConnectionConfig()
    assert config.max_reconnect_attempts == 60
    assert config.reconnect_time_wait == 2.0
    assert config.connect_timeout == 10.0
    assert config.ping_interval == 120.0
    assert config.max_outstanding_pings == 2
    assert config.name is None
    assert config.error_cb is None


def test_nats_connection_config_custom():
    """NatsConnectionConfig accepts custom values."""
    cb = MagicMock()
    config = NatsConnectionConfig(
        url="nats://host:1234",
        name="test-svc",
        max_reconnect_attempts=5,
        connect_timeout=3.0,
        error_cb=cb,
    )
    assert config.url == "nats://host:1234"
    assert config.name == "test-svc"
    assert config.max_reconnect_attempts == 5
    assert config.connect_timeout == 3.0
    assert config.error_cb is cb
    kwargs = config.to_connect_kwargs()
    assert kwargs["name"] == "test-svc"
    assert kwargs["error_cb"] is cb


def test_redact_url_strips_userinfo():
    """NATS credentials are not emitted in connection logs."""
    from services.common import nats_client as nc_mod

    assert (
        nc_mod._redact_url("nats://pmoves:secret@nats.example:4222")
        == "nats://nats.example:4222"
    )
    assert nc_mod._redact_url("nats://nats.example:4222") == "nats://nats.example:4222"


@pytest.mark.asyncio
async def test_create_nats_connection_success():
    """create_nats_connection returns a connected client."""
    mock_nc = MagicMock()
    mock_nats_module = MagicMock()
    mock_nats_module.connect = AsyncMock(return_value=mock_nc)
    with patch.dict("sys.modules", {"nats": mock_nats_module}):
        result = await create_nats_connection()
        assert result is mock_nc
        mock_nats_module.connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_nats_connection_retry_on_failure():
    """create_nats_connection raises ConnectionError on failure."""
    mock_nats_module = MagicMock()
    mock_nats_module.connect = AsyncMock(side_effect=Exception("connection refused"))
    with patch.dict("sys.modules", {"nats": mock_nats_module}):
        with pytest.raises(ConnectionError, match="NATS connection failed"):
            await create_nats_connection()


@pytest.mark.asyncio
async def test_publish_cgp_uses_explicit_nats_url():
    """publish_cgp honors its nats_url override instead of falling back to env."""
    mock_nc = AsyncMock()
    packet = {"spec": "chit.cgp.v0.2", "summary": "test"}

    with patch("services.common.nats_client.nats_connection") as mock_conn_ctx, patch(
        "services.common.nats_client.traced_publish", new_callable=AsyncMock
    ) as mock_publish:
        mock_conn_ctx.return_value.__aenter__.return_value = mock_nc
        result = await publish_cgp(
            packet,
            subject="tokenism.prosodic.bpm.v1",
            nats_url="nats://override:4222",
        )

    assert result is True
    config = mock_conn_ctx.call_args.args[0]
    assert config.url == "nats://override:4222"
    assert config.name == "cgp-publisher"
    mock_publish.assert_awaited_once()
