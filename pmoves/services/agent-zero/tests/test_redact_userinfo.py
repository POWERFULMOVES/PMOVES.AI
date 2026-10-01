"""URL userinfo must never leave Agent Zero through logs or its unauthenticated routes."""

from __future__ import annotations

import asyncio
import importlib
import logging
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


from .test_main import _prepare_agent_zero

# Synthetic credential pair; it is not, and must never become, a real one.
SECRET = "example-pass"
WITH_CREDS = f"nats://example-user:{SECRET}@nats:4222"
REDACTED = "nats://***@nats:4222"
PLAIN = "nats://nats:4222"


def _load(monkeypatch, load_service_module, nats_url):
    monkeypatch.setenv("NATS_URL", nats_url)
    module = load_service_module("agent_zero_main", "services/agent-zero/main.py")
    module.service_config = module.load_service_config()
    return _prepare_agent_zero(module, monkeypatch)


@pytest.mark.parametrize("nats_url, expected", [(WITH_CREDS, REDACTED), (PLAIN, PLAIN)])
def test_config_environment_redacts_userinfo(monkeypatch, load_service_module, nats_url, expected):
    module = _load(monkeypatch, load_service_module, nats_url)
    with TestClient(module.app) as client:
        response = client.get("/config/environment")
    assert response.status_code == 200
    assert response.json()["nats_url"] == expected
    assert SECRET not in response.text
    # The live config keeps the real URL; only the response is redacted.
    assert module.service_config.nats_url == nats_url


@pytest.mark.parametrize("nats_url, expected", [(WITH_CREDS, REDACTED), (PLAIN, PLAIN)])
def test_healthz_redacts_userinfo(monkeypatch, load_service_module, nats_url, expected):
    module = _load(monkeypatch, load_service_module, nats_url)
    module.process_manager._process = SimpleNamespace(returncode=None, pid=4242)

    async def fake_health():
        return {"status": "ok"}

    monkeypatch.setattr(module.client, "health", fake_health)
    with TestClient(module.app) as client:
        response = client.get("/healthz")
    assert response.json()["nats"]["url"] == expected
    assert SECRET not in response.text


@pytest.mark.parametrize("nats_url, expected", [(WITH_CREDS, REDACTED), (PLAIN, PLAIN)])
def test_controller_logs_redacted_url(monkeypatch, caplog, nats_url, expected):
    # The package re-exports an instance named `controller`; import the module itself.
    ctl = importlib.import_module("services.agent_zero.controller")

    class _Stop(Exception):
        pass

    class _FakeNATS:
        async def connect(self, servers):
            assert servers == [nats_url]  # the real URL is still what connects
            raise _Stop

    monkeypatch.setattr(ctl, "NATS", _FakeNATS)
    controller = ctl.AgentZeroController(ctl.ControllerSettings(nats_url=nats_url, use_jetstream=True))
    with caplog.at_level(logging.INFO, logger=ctl.logger.name):
        with pytest.raises(_Stop):
            asyncio.run(controller.start())
    assert f"Connecting to NATS at {expected}" in caplog.text
    assert SECRET not in caplog.text
