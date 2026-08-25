"""The semantic-cache attribution publisher must not write to the ledger blind.

`tokenism.attribution.recorded.v1` feeds the settlement ledger and `address` is
inside the Merkle leaf, so a malformed record cannot be amended -- only appended
to. The publisher had no validation at all and sent a payload sharing ZERO
fields with its own contract. There are no callers yet and `tokenism_enabled`
defaults to True, so the first call site anyone wires would have fired it.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / "pmoves" / "services" / "semantic-cache" / "tokenism.py"


def _tokenism():
    """Load the publisher with its sibling `config` import stubbed.

    The service uses flat sibling imports (`from config import ...`), so it is
    not importable as a package from here. Stubbing only `config` keeps the
    module under test genuine.
    """
    stub = types.ModuleType("config")

    class _Settings:
        tokenism_enabled = True
        nats_url = ""

    stub.CacheSettings = _Settings
    stub.get_settings = lambda: _Settings()
    sys.modules["config"] = stub

    spec = importlib.util.spec_from_file_location("sc_tokenism", MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["sc_tokenism"] = module
    spec.loader.exec_module(module)
    return module


tk = _tokenism()

# The exact payload the module built before this guard existed.
LEGACY_PAYLOAD = {
    "agent_id": "cache-1",
    "tokens_saved": 1200,
    "cost_saved_usd": 0.031,
    "cache_key": "sha256:abc",
}

# Contract-shaped. `week` is an INTEGER and `timestamp` is date-time -- both
# caught a hand-written "valid" payload during development, which is the point.
VALID_PAYLOAD = {
    "chit_id": "chit-1",
    "address": "pmoves1qexample",
    "action": "cache_hit",
    "amount": 0.031,
    "week": 35,
    "timestamp": "2026-08-25T18:00:00+00:00",
}


def test_the_legacy_payload_is_refused():
    """Six required fields missing, four sent fields forbidden, zero overlap."""
    ok, reason = tk.validate_attribution(LEGACY_PAYLOAD)
    assert not ok
    for field in ("chit_id", "address", "action", "amount", "week", "timestamp"):
        assert field in reason, f"{field} not named in the refusal"


def test_a_contract_shaped_payload_is_accepted():
    """The guard must not simply refuse everything -- that would pass the test
    above while making the publisher permanently dead."""
    ok, reason = tk.validate_attribution(VALID_PAYLOAD)
    assert ok, reason


@pytest.mark.parametrize("field", ["chit_id", "address", "action", "amount",
                                   "week", "timestamp"])
def test_each_required_field_is_individually_enforced(field):
    payload = dict(VALID_PAYLOAD)
    payload.pop(field)
    ok, reason = tk.validate_attribution(payload)
    assert not ok and field in reason


def test_extra_fields_are_rejected():
    """additionalProperties: false -- the ledger's shape is closed."""
    payload = dict(VALID_PAYLOAD, agent_id="cache-1")
    ok, _ = tk.validate_attribution(payload)
    assert not ok


def test_week_must_be_an_integer():
    """Caught a hand-written payload that looked right: `2026-W35` is a string."""
    ok, reason = tk.validate_attribution(dict(VALID_PAYLOAD, week="2026-W35"))
    assert not ok and "integer" in reason


def test_an_unreachable_contract_refuses_rather_than_permits(monkeypatch):
    """The failure mode this guard exists to prevent, applied to itself.

    If the schema cannot be loaded, the honest answer is "I could not check",
    and for a Merkle-leafed ledger that must mean DO NOT WRITE. A guard that
    treats an unreachable contract as permission is the same silent pass it
    was built to remove.
    """
    monkeypatch.setattr(tk, "_contracts_dir", lambda: None)
    ok, reason = tk.validate_attribution(VALID_PAYLOAD)
    assert not ok
    assert "not reachable" in reason and "refusing" in reason


def test_the_publisher_actually_calls_the_guard():
    """A validator nothing calls is the defect, not the fix.

    Structural rather than behavioural: exercising the publish path needs a
    live NATS connection, and a test that mocked it would assert against its
    own mock rather than against the module.
    """
    source = MODULE.read_text(encoding="utf-8")
    body = source.split("async def publish_attribution", 1)[1]
    call = body.find("validate_attribution(payload)")
    publish = body.find("self._nc.publish")
    assert call != -1, "publish_attribution does not validate"
    assert publish != -1, "publish_attribution no longer publishes"
    assert call < publish, "validation must happen BEFORE the publish, not after"
