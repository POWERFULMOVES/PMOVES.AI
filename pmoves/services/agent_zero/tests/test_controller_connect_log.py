"""The controller's NATS connect log must not carry NATS_URL credentials.

Companion to test_healthz_never_returns_nats_credentials in
services/agent-zero/tests/test_main.py: the same PR fixed both leak sites, and
this pins the second one (AgentZeroController.start's "Connecting to NATS" log).
"""

import importlib
import logging
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import pytest

# services.agent_zero re-exports a module-level `controller` *instance* that shadows
# the submodule attribute, so fetch the module itself to patch its NATS binding.
controller_mod = importlib.import_module("services.agent_zero.controller")
AgentZeroController = controller_mod.AgentZeroController
ControllerSettings = controller_mod.ControllerSettings

CREDENTIALED_URL = "nats://svc-user:s3cret-pass@nats:4222"


class _StopAfterConnect(Exception):
    """Raised by the fake client once connect() has been observed."""


class _FakeNATS:
    servers_seen: List[List[str]] = []

    async def connect(self, servers: List[str], **_: object) -> None:
        type(self).servers_seen.append(list(servers))
        raise _StopAfterConnect()


@pytest.mark.asyncio
async def test_controller_connect_log_has_no_nats_userinfo(monkeypatch, caplog):
    _FakeNATS.servers_seen = []
    monkeypatch.setattr(controller_mod, "NATS", _FakeNATS)
    controller = AgentZeroController(
        ControllerSettings(nats_url=CREDENTIALED_URL, use_jetstream=True)
    )

    with caplog.at_level(logging.INFO, logger=controller_mod.logger.name):
        with pytest.raises(_StopAfterConnect):
            await controller.start()

    connect_lines = [r.getMessage() for r in caplog.records if "Connecting to NATS" in r.getMessage()]
    assert connect_lines == ["Connecting to NATS at nats://nats:4222"]
    assert "s3cret-pass" not in caplog.text
    assert "svc-user" not in caplog.text
    # Redaction is for the log only: the client still connects with the credentials.
    assert _FakeNATS.servers_seen == [[CREDENTIALED_URL]]
