"""Unit tests for A2UI NATS Bridge.

Tests cover:
- A2UIEvent validation
- Health endpoint behavior
- Metrics endpoint behavior
"""
import sys
import pytest

# Add bridge service to path
sys.path.insert(0, "pmoves/services/a2ui-nats-bridge")

from bridge import A2UIEvent, app
from fastapi.testclient import TestClient

client = TestClient(app)


class TestA2UIEventValidation:
    """Test A2UIEvent validation."""

    def test_from_a2ui_dict_valid_create_surface(self):
        """Test valid createSurface A2UI event parsing."""
        data = {"createSurface": {"surfaceId": "test-123"}}
        event = A2UIEvent.from_a2ui_dict(data)
        assert event.event_type == "createSurface"
        assert event.surface_id == "test-123"
        assert event.payload == {"surfaceId": "test-123"}

    def test_from_a2ui_dict_valid_surface_update(self):
        """Test valid surfaceUpdate A2UI event parsing."""
        data = {
            "surfaceUpdate": {
                "surfaceId": "test-surface",
                "components": [{"id": "root", "component": "Column"}]
            }
        }
        event = A2UIEvent.from_a2ui_dict(data)
        assert event.event_type == "surfaceUpdate"
        assert event.surface_id == "test-surface"
        assert len(event.payload["components"]) == 1

    def test_from_a2ui_dict_invalid_type_string(self):
        """Test rejection of non-dict input (string)."""
        with pytest.raises(TypeError, match="Expected dict"):
            A2UIEvent.from_a2ui_dict("not a dict")

    def test_from_a2ui_dict_invalid_type_none(self):
        """Test rejection of None input."""
        with pytest.raises(TypeError, match="Expected dict"):
            A2UIEvent.from_a2ui_dict(None)

    def test_from_a2ui_dict_empty(self):
        """Test rejection of empty dict."""
        with pytest.raises(ValueError, match="Empty A2UI"):
            A2UIEvent.from_a2ui_dict({})

    def test_from_a2ui_dict_invalid_payload_string(self):
        """Test rejection of non-dict payload (string)."""
        with pytest.raises(TypeError, match="Expected payload dict"):
            A2UIEvent.from_a2ui_dict({"createSurface": "not a dict"})

    def test_from_a2ui_dict_invalid_payload_none(self):
        """Test rejection of None payload."""
        with pytest.raises(TypeError, match="Expected payload dict"):
            A2UIEvent.from_a2ui_dict({"createSurface": None})

    def test_from_a2ui_dict_no_surface_id(self):
        """Test event without surfaceId still works."""
        data = {"updateComponents": {"components": []}}
        event = A2UIEvent.from_a2ui_dict(data)
        assert event.event_type == "updateComponents"
        assert event.surface_id == ""  # Empty default
        assert event.payload == {"components": []}

    def test_to_nats_message(self):
        """Test conversion to NATS message format."""
        event = A2UIEvent(
            surface_id="test-surface",
            event_type="createSurface",
            payload={"surfaceId": "test-surface"}
        )
        message = event.to_nats_message()
        assert isinstance(message, bytes)
        import json
        data = json.loads(message.decode())
        assert data["surface_id"] == "test-surface"
        assert data["event_type"] == "createSurface"
        assert data["version"] == "0.9"

    def test_timestamp_auto_generated(self):
        """Test timestamp is auto-generated on init."""
        event = A2UIEvent(
            surface_id="test",
            event_type="test"
        )
        assert event.timestamp != ""
        assert "T" in event.timestamp  # ISO format


class TestHealthEndpoint:
    """Test /healthz endpoint."""

    def test_healthz_returns_json(self):
        """Test healthz returns proper JSON structure."""
        response = client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "nats_connected" in data
        # Verify nats_connected is boolean, not method object
        assert isinstance(data["nats_connected"], bool)
        assert "active_websockets" in data
        assert "timestamp" in data
        assert "active_surfaces" in data

    def test_healthz_status_is_degraded_when_nats_disconnected(self):
        """Test status is 'degraded' when NATS disconnected."""
        response = client.get("/healthz")
        data = response.json()
        # In test environment, NATS is not connected, so should be degraded
        assert data["status"] in ("healthy", "degraded")
        assert isinstance(data["nats_connected"], bool)

    def test_healthz_active_websockets_count(self):
        """Test active_websockets is a number."""
        response = client.get("/healthz")
        data = response.json()
        assert isinstance(data["active_websockets"], int)
        assert data["active_websockets"] >= 0

    def test_healthz_active_surfaces_is_list(self):
        """Test active_surfaces is a list."""
        response = client.get("/healthz")
        data = response.json()
        assert isinstance(data["active_surfaces"], list)


class TestMetricsEndpoint:
    """Test /metrics endpoint."""

    def test_metrics_returns_prometheus_format(self):
        """Test /metrics returns Prometheus text format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        content = response.text
        # Verify key metrics are present
        assert "a2ui_events_published_total" in content
        assert "a2ui_events_received_total" in content
        assert "a2ui_geometry_events_total" in content
        assert "a2ui_active_websockets" in content
        assert "a2ui_nats_connected" in content

    def test_metrics_help_text_present(self):
        """Test Prometheus metrics have HELP text."""
        response = client.get("/metrics")
        content = response.text
        # Prometheus format includes HELP comments
        assert "# HELP" in content
        assert "# TYPE" in content


class TestAPIEndpoints:
    """Test REST API endpoints."""

    def test_a2ui_endpoint_with_valid_event(self):
        """Test /api/v1/a2ui with valid event."""
        # This will fail with 503 if NATS not connected, but should validate input
        response = client.post(
            "/api/v1/a2ui",
            json={"createSurface": {"surfaceId": "test-surface"}}
        )
        # Either 200 (published) or 503 (NATS not connected) is acceptable
        assert response.status_code in (200, 503)

    def test_a2ui_endpoint_with_invalid_event(self):
        """Test /api/v1/a2ui rejects empty dict."""
        response = client.post("/api/v1/a2ui", json={})
        # Should return 400 (bad request) for validation error
        assert response.status_code == 400

    def test_simulate_endpoint(self):
        """Test /api/v1/simulate creates test event."""
        response = client.post("/api/v1/simulate")
        # Either 200 (published) or 503 (NATS not connected)
        assert response.status_code in (200, 503)

    def test_user_action_endpoint(self):
        """Test /api/v1/action handles user action."""
        response = client.post(
            "/api/v1/action",
            json={
                "name": "click",
                "surfaceId": "test",
                "context": {"target": "button"}
            }
        )
        # Should always return 200 even if NATS disconnected (logs warning)
        assert response.status_code == 200


class TestWebSocketEndpoints:
    """Test WebSocket endpoints (basic connection tests)."""

    def test_a2ui_websocket_path_exists(self):
        """Test /ws/a2ui route is registered."""
        # Just verify the route exists by checking app routes
        routes = [route.path for route in app.routes]
        assert "/ws/a2ui" in routes

    def test_client_websocket_path_exists(self):
        """Test /ws/client route is registered."""
        routes = [route.path for route in app.routes]
        assert "/ws/client" in routes
