"""Tests for the /metrics endpoint on omnivoice_server.

These tests run WITHOUT a GPU or the omnivoice package.  The startup hook
that loads the model is patched out, so all we exercise is the Prometheus
instrumentation layer and the endpoint routing.

Skips cleanly when torch or soundfile are unavailable (e.g. a lightweight
test runner that only has the creator-operator base deps installed).
"""
import os
import sys
import types

import pytest

# ---------------------------------------------------------------------------
# Guard: skip the entire module if the heavy ML deps are absent.
# torch and soundfile are imported at module level in omnivoice_server.py, so
# they must be importable before we even load the server module.
# ---------------------------------------------------------------------------
torch = pytest.importorskip("torch", reason="torch not installed — skipping omnivoice_server tests")
pytest.importorskip("soundfile", reason="soundfile not installed — skipping omnivoice_server tests")


# ---------------------------------------------------------------------------
# Stub out the 'omnivoice' package so the startup hook doesn't blow up when
# we exercise it (it's imported lazily inside _load_model, not at module top).
# We inject a minimal fake before importing the server module.
# ---------------------------------------------------------------------------
def _install_omnivoice_stub():
    fake_pkg = types.ModuleType("omnivoice")

    class _FakeModel:
        """Minimal stand-in for OmniVoice that never touches a GPU."""
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

        def generate(self, text: str, **_kw):
            import numpy as np
            # Return a list of zero-length arrays (shape matches OmniVoice output)
            return [np.zeros(24000, dtype="float32")]

    fake_pkg.OmniVoice = _FakeModel
    sys.modules.setdefault("omnivoice", fake_pkg)


_install_omnivoice_stub()


# ---------------------------------------------------------------------------
# Set env vars BEFORE importing the server module so module-level constants
# (AUTH_TOKEN, MODEL_ID, etc.) are populated correctly for the test session.
# ---------------------------------------------------------------------------
os.environ.setdefault("OMNIVOICE_TOKEN", "test-token-for-pytest")
os.environ.setdefault("OMNIVOICE_MODEL", "k2-fsa/OmniVoice")
os.environ.setdefault("OMNIVOICE_DEVICE", "cpu")

# Force a fresh import so the env vars above are picked up.
if "omnivoice_server" in sys.modules:
    del sys.modules["omnivoice_server"]

import omnivoice_server  # noqa: E402 — must come after env + stubs
from fastapi.testclient import TestClient  # noqa: E402


# ---------------------------------------------------------------------------
# Shared TestClient — startup event fires once, which loads our fake model
# and sets MODEL_LOADED gauge to 1.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    with TestClient(omnivoice_server.app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_metrics_endpoint_status(client):
    """GET /metrics must return 200 without authentication."""
    resp = client.get("/metrics")
    assert resp.status_code == 200


def test_metrics_content_type(client):
    """Response must carry the Prometheus text content-type."""
    resp = client.get("/metrics")
    assert "text/plain" in resp.headers["content-type"]


def test_metrics_contains_synth_requests(client):
    """omnivoice_synth_requests_total must appear in the scrape body."""
    resp = client.get("/metrics")
    assert b"omnivoice_synth_requests_total" in resp.content


def test_metrics_contains_synth_latency(client):
    """omnivoice_synth_latency_seconds must appear in the scrape body."""
    resp = client.get("/metrics")
    assert b"omnivoice_synth_latency_seconds" in resp.content


def test_metrics_contains_synth_errors(client):
    """omnivoice_synth_errors_total must appear in the scrape body."""
    resp = client.get("/metrics")
    assert b"omnivoice_synth_errors_total" in resp.content


def test_metrics_contains_model_loaded(client):
    """omnivoice_model_loaded gauge must appear in the scrape body."""
    resp = client.get("/metrics")
    assert b"omnivoice_model_loaded" in resp.content


def test_metrics_model_loaded_is_one(client):
    """After startup the model-loaded gauge must read 1."""
    resp = client.get("/metrics")
    text = resp.text
    # Find the gauge line: omnivoice_model_loaded 1.0
    lines = [ln for ln in text.splitlines() if ln.startswith("omnivoice_model_loaded") and not ln.startswith("#")]
    assert lines, "omnivoice_model_loaded metric not found"
    assert lines[0].split()[-1] == "1.0", f"expected 1.0, got: {lines[0]}"


def test_metrics_no_auth_required(client):
    """/metrics must be accessible without the X-OmniVoice-Token header."""
    # Deliberately omit the token header
    resp = client.get("/metrics", headers={})
    assert resp.status_code == 200
