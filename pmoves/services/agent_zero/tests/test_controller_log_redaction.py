"""The controller must never log NATS userinfo.

NATS_URL carries user:password on this fleet, so the old
``logger.info("Connecting to NATS at %s", nats_url)`` put the credential into
``docker logs`` on every start (measured on Knuckles 2026-10-01).
"""

import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import pytest

import importlib

ctl = importlib.import_module("services.agent_zero.controller")

SECRET = "s3cr3t-pa55"
URL = f"nats://agentuser:{SECRET}@nats:4222"


class _StopAfterLog(Exception):
    pass


class _FakeNATS:
    async def connect(self, servers):  # noqa: ARG002 - signature mirrors nats-py
        raise _StopAfterLog


def test_start_logs_nats_url_without_credentials(monkeypatch, caplog):
    monkeypatch.setattr(ctl, "NATS", _FakeNATS)
    settings = ctl.ControllerSettings(nats_url=URL, use_jetstream=True)
    controller = ctl.AgentZeroController(settings)

    with caplog.at_level(logging.INFO, logger=ctl.logger.name):
        with pytest.raises(_StopAfterLog):
            asyncio.run(controller.start())

    connect_lines = [r.getMessage() for r in caplog.records if "Connecting to NATS" in r.getMessage()]
    assert connect_lines, "start() no longer logs the connect line; update this test"
    for line in connect_lines:
        assert SECRET not in line
        assert "agentuser" not in line
        assert "nats://nats:4222" in line
