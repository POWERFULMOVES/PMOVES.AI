"""CHIT signing/verification tests for the evo-controller.

Covers the two attach points: outbound geometry.swarm.meta.v1 payload signing
in _publish_swarm_meta (via Agent Zero's events API) and inbound CGP
verification in _filter_verified_cgps.
"""

import importlib.util
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "app.py"
SPEC = importlib.util.spec_from_file_location("pmoves.services.evo_controller.app_chit", MODULE_PATH)
assert SPEC and SPEC.loader
app = importlib.util.module_from_spec(SPEC)
sys.modules["pmoves.services.evo_controller.app_chit"] = app
SPEC.loader.exec_module(app)

from pmoves.tools.chit_security import sign_cgp, verify_cgp  # noqa: E402

PASSPHRASE = "evo-test-key"


@pytest.fixture(autouse=True)
def clean_chit_env(monkeypatch):
    for var in ("CHIT_SIGNING_KEY", "CHIT_PASSPHRASE", "CHIT_REQUIRE_SIGNATURE"):
        monkeypatch.delenv(var, raising=False)


def make_controller() -> Any:
    return app.EvoSwarmController(app.EvoConfig(rest_url=None, service_key=None))


class FakeAsyncClient:
    """Captures the events-API POST from _publish_swarm_meta."""

    posted: list[dict] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None):
        FakeAsyncClient.posted.append({"url": url, "body": json})

        class _Resp:
            def raise_for_status(self):
                return None

        return _Resp()


@pytest.fixture
def capture_publish(monkeypatch):
    FakeAsyncClient.posted = []
    monkeypatch.setattr(app.httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient.posted


class TestPublishSwarmMeta:
    @pytest.mark.asyncio
    async def test_payload_signed_when_key_present(self, capture_publish, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
        await make_controller()._publish_swarm_meta({"namespace": "pmoves", "status": "draft"})
        assert len(capture_publish) == 1
        payload = capture_publish[0]["body"]["payload"]
        assert "sig" in payload
        assert verify_cgp(payload, passphrase=PASSPHRASE) is True

    @pytest.mark.asyncio
    async def test_unsigned_dev_mode_when_no_key(self, capture_publish, caplog):
        await make_controller()._publish_swarm_meta({"namespace": "pmoves"})
        assert len(capture_publish) == 1
        assert "sig" not in capture_publish[0]["body"]["payload"]
        assert any("unsigned" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_fail_closed_refuses_unsigned_publish(self, capture_publish, monkeypatch):
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "true")
        await make_controller()._publish_swarm_meta({"namespace": "pmoves"})
        assert capture_publish == []


class TestFilterVerifiedCgps:
    def test_valid_signatures_kept(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
        signed = sign_cgp({"namespace": "pmoves", "n": 1}, passphrase=PASSPHRASE)
        assert make_controller()._filter_verified_cgps([signed]) == [signed]

    def test_tampered_always_dropped(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
        tampered = sign_cgp({"namespace": "pmoves", "n": 1}, passphrase=PASSPHRASE)
        tampered["n"] = 2
        assert make_controller()._filter_verified_cgps([tampered]) == []

    def test_unsigned_kept_in_dev_mode(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
        unsigned = {"namespace": "pmoves"}
        assert make_controller()._filter_verified_cgps([unsigned]) == [unsigned]

    def test_unsigned_dropped_when_required(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "1")
        assert make_controller()._filter_verified_cgps([{"namespace": "pmoves"}]) == []

    def test_no_key_dev_mode_passthrough(self):
        cgps = [{"namespace": "pmoves"}]
        assert make_controller()._filter_verified_cgps(cgps) == cgps

    def test_no_key_fail_closed_drops_all(self, monkeypatch):
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "true")
        assert make_controller()._filter_verified_cgps([{"namespace": "pmoves"}]) == []

    def test_non_dict_entries_pass_through_in_dev_mode(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
        assert make_controller()._filter_verified_cgps([None]) == [None]

    def test_non_dict_entries_dropped_fail_closed(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "true")
        assert make_controller()._filter_verified_cgps([None]) == []
