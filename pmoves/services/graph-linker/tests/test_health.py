"""Tests for /health, /ready, and /metrics endpoints."""

import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def healthy_client():
    with patch("app.Neo4jClient") as MockNeo4j,          patch("app.NATSHandler") as MockNATS,          patch("app.get_settings") as mock_settings:
        from config import Settings
        mock_settings.return_value = Settings(
            neo4j_url="bolt://localhost:7687",
            neo4j_password="test",
            nats_url="nats://nats:pmoves@nats:4222",
        )
        neo4j_inst = MagicMock()
        neo4j_inst.connect = AsyncMock()
        neo4j_inst.close = AsyncMock()
        neo4j_inst.apply_migrations = MagicMock()
        neo4j_inst.is_healthy.return_value = True
        MockNeo4j.return_value = neo4j_inst
        nats_inst = MagicMock()
        nats_inst.connect = AsyncMock()
        nats_inst.subscribe = AsyncMock()
        nats_inst.close = AsyncMock()
        nats_inst.is_connected = True
        MockNATS.return_value = nats_inst
        from app import app
        with TestClient(app) as client:
            yield client


@pytest.fixture
def degraded_client():
    with patch("app.Neo4jClient") as MockNeo4j,          patch("app.NATSHandler") as MockNATS,          patch("app.get_settings") as mock_settings:
        from config import Settings
        mock_settings.return_value = Settings(
            neo4j_url="bolt://localhost:7687",
            neo4j_password="test",
            nats_url="nats://nats:pmoves@nats:4222",
        )
        neo4j_inst = MagicMock()
        neo4j_inst.connect = AsyncMock()
        neo4j_inst.close = AsyncMock()
        neo4j_inst.apply_migrations = MagicMock()
        neo4j_inst.is_healthy.return_value = False
        MockNeo4j.return_value = neo4j_inst
        nats_inst = MagicMock()
        nats_inst.connect = AsyncMock()
        nats_inst.subscribe = AsyncMock()
        nats_inst.close = AsyncMock()
        nats_inst.is_connected = False
        MockNATS.return_value = nats_inst
        from app import app
        with TestClient(app) as client:
            yield client


class TestHealthEndpoint:
    def test_health_returns_200(self, healthy_client):
        resp = healthy_client.get("/health")
        assert resp.status_code == 200

    def test_health_returns_ok(self, healthy_client):
        data = healthy_client.get("/health").json()
        assert data["status"] == "ok"
        assert data["service"] == "graph-linker"
        assert data["version"] == "0.2.0"


class TestReadyEndpoint:
    def test_ready_healthy(self, healthy_client):
        data = healthy_client.get("/ready").json()
        assert data["status"] == "ready"
        assert data["neo4j"] == "ok"
        assert data["nats"] == "ok"

    def test_ready_degraded(self, degraded_client):
        data = degraded_client.get("/ready").json()
        assert data["status"] == "degraded"
        assert data["neo4j"] == "unavailable"
        assert data["nats"] == "unavailable"


class TestMetricsEndpoint:
    def test_metrics_returns_200(self, healthy_client):
        resp = healthy_client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_content_type(self, healthy_client):
        resp = healthy_client.get("/metrics")
        assert "text/plain" in resp.headers.get("content-type", "")

    def test_metrics_has_data(self, healthy_client):
        resp = healthy_client.get("/metrics")
        assert "graph_linker_" in resp.text or "python_" in resp.text
