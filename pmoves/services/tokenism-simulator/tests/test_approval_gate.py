"""Approval-gate tests for Tokenism Simulator API requests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.pop("services", None)

from app import create_app


def test_approval_gated_sync_simulation_skips_without_operator_approval(monkeypatch):
    """Approval-gated sync requests should skip before engine/NATS work."""
    monkeypatch.setenv("TOKENISM_DISABLE_NATS_CONSUMER", "true")
    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/simulate",
        json={
            "scenario": "baseline",
            "approval_gated": True,
            "parameters": {"duration_weeks": 1},
        },
    )

    assert response.status_code == 202
    assert response.json["status"] == "skipped"
    assert response.json["reason"] == "approval_required"


def test_approval_gated_async_simulation_skips_without_operator_approval(monkeypatch):
    """Approval-gated async requests should not enqueue a worker without approval."""
    monkeypatch.setenv("TOKENISM_DISABLE_NATS_CONSUMER", "true")
    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/simulate/async",
        json={
            "scenario": "baseline",
            "requires_approval": True,
            "parameters": {"duration_weeks": 1},
        },
    )

    assert response.status_code == 202
    assert response.json["status"] == "skipped"
    assert response.json["reason"] == "approval_required"
