"""
Unit tests for Persona Gate Service.

Tests the threshold-based persona evaluation including:
- Threshold gate evaluation
- NATS message handling
- Pass/fail determination
"""

import json
import pytest
from unittest import mock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from persona_gate import PersonaGateService


class TestPersonaGateService:
    """Tests for PersonaGateService class."""

    @pytest.fixture
    def service(self):
        """Create PersonaGateService instance for testing."""
        return PersonaGateService()

    def test_service_initialization(self, service):
        """Service initializes with default thresholds."""
        assert service.thresholds is not None
        assert "min_empirical_support" in service.thresholds
        assert "min_philosophical_coherence" in service.thresholds
        assert "min_integration_potential" in service.thresholds
        assert "min_description_length" in service.thresholds
        assert "min_proponents" in service.thresholds

    def test_default_thresholds(self, service):
        """Default thresholds are set correctly."""
        assert service.thresholds["min_empirical_support"] == 0.3
        assert service.thresholds["min_philosophical_coherence"] == 0.4
        assert service.thresholds["min_integration_potential"] == 0.3
        assert service.thresholds["min_description_length"] == 50
        assert service.thresholds["min_proponents"] == 1


class TestEvaluate:
    """Tests for persona evaluation."""

    @pytest.fixture
    def service(self):
        return PersonaGateService()

    @pytest.mark.asyncio
    async def test_evaluate_all_pass(self, service):
        """Evaluation passes when all metrics meet thresholds."""
        metrics = {
            "empirical_support": 0.5,
            "philosophical_coherence": 0.6,
            "integration_potential": 0.5,
            "description_length": 100,
            "proponent_count": 3
        }

        result = await service.evaluate("persona-123", metrics)

        assert result["passed"] is True
        assert result["persona_id"] == "persona-123"
        assert result["summary"]["passed_gates"] == 5
        assert result["summary"]["failed_gates"] == 0

    @pytest.mark.asyncio
    async def test_evaluate_one_fails(self, service):
        """Evaluation fails when any metric below threshold."""
        metrics = {
            "empirical_support": 0.1,  # Below 0.3 threshold
            "philosophical_coherence": 0.6,
            "integration_potential": 0.5,
            "description_length": 100,
            "proponent_count": 3
        }

        result = await service.evaluate("persona-456", metrics)

        assert result["passed"] is False
        assert result["summary"]["failed_gates"] == 1

        # Check specific gate failure
        emp_eval = next(e for e in result["evaluations"] if e["gate"] == "empirical_support")
        assert emp_eval["passed"] is False

    @pytest.mark.asyncio
    async def test_evaluate_multiple_fail(self, service):
        """Evaluation tracks all failures."""
        metrics = {
            "empirical_support": 0.1,
            "philosophical_coherence": 0.2,
            "integration_potential": 0.1,
            "description_length": 10,
            "proponent_count": 0
        }

        result = await service.evaluate("persona-789", metrics)

        assert result["passed"] is False
        assert result["summary"]["failed_gates"] == 5
        assert result["summary"]["passed_gates"] == 0

    @pytest.mark.asyncio
    async def test_evaluate_missing_metrics(self, service):
        """Missing metrics default to zero (fail)."""
        metrics = {}  # All metrics missing

        result = await service.evaluate("persona-empty", metrics)

        assert result["passed"] is False
        # All gates should fail with zero values
        assert result["summary"]["failed_gates"] == 5

    @pytest.mark.asyncio
    async def test_evaluate_boundary_values(self, service):
        """Metrics exactly at threshold pass."""
        metrics = {
            "empirical_support": 0.3,  # Exactly at threshold
            "philosophical_coherence": 0.4,
            "integration_potential": 0.3,
            "description_length": 50,
            "proponent_count": 1
        }

        result = await service.evaluate("persona-boundary", metrics)

        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_evaluate_returns_evaluations(self, service):
        """Evaluation result includes detailed evaluations."""
        metrics = {
            "empirical_support": 0.5,
            "philosophical_coherence": 0.6,
            "integration_potential": 0.5,
            "description_length": 100,
            "proponent_count": 3
        }

        result = await service.evaluate("persona-detail", metrics)

        assert "evaluations" in result
        assert len(result["evaluations"]) == 5

        for eval_item in result["evaluations"]:
            assert "gate" in eval_item
            assert "value" in eval_item
            assert "threshold" in eval_item
            assert "passed" in eval_item

    @pytest.mark.asyncio
    async def test_evaluate_includes_timestamp(self, service):
        """Evaluation result includes timestamp."""
        result = await service.evaluate("persona-ts", {"empirical_support": 0.5})

        assert "timestamp" in result
        assert result["timestamp"].endswith("Z")


class TestUpdateThresholds:
    """Tests for threshold updates."""

    @pytest.fixture
    def service(self):
        return PersonaGateService()

    def test_update_single_threshold(self, service):
        """Update a single threshold."""
        service.update_thresholds({"min_empirical_support": 0.5})

        assert service.thresholds["min_empirical_support"] == 0.5
        # Others unchanged
        assert service.thresholds["min_philosophical_coherence"] == 0.4

    def test_update_multiple_thresholds(self, service):
        """Update multiple thresholds."""
        service.update_thresholds({
            "min_empirical_support": 0.6,
            "min_philosophical_coherence": 0.7
        })

        assert service.thresholds["min_empirical_support"] == 0.6
        assert service.thresholds["min_philosophical_coherence"] == 0.7

    def test_update_unknown_threshold(self, service):
        """Unknown thresholds are added."""
        service.update_thresholds({"custom_threshold": 0.9})

        assert service.thresholds["custom_threshold"] == 0.9


class TestNATSConnection:
    """Tests for NATS connection handling."""

    @pytest.fixture
    def service(self):
        return PersonaGateService()

    @pytest.mark.asyncio
    async def test_connect(self, service):
        """Connect establishes NATS connection."""
        with mock.patch('persona_gate.nats.connect') as mock_connect:
            mock_nc = mock.AsyncMock()
            mock_connect.return_value = mock_nc

            await service.connect()

            assert service.nc is not None
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self, service):
        """Close drains NATS connection."""
        mock_nc = mock.AsyncMock()
        service.nc = mock_nc

        await service.close()

        mock_nc.drain.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_connection(self, service):
        """Close handles missing connection gracefully."""
        service.nc = None

        # Should not raise
        await service.close()

    @pytest.mark.asyncio
    async def test_subscribe(self, service):
        """Subscribe registers message handler."""
        mock_nc = mock.AsyncMock()
        service.nc = mock_nc

        await service.subscribe()

        mock_nc.subscribe.assert_called_once()


class TestHandleRequest:
    """Tests for NATS message handling."""

    @pytest.fixture
    def service(self):
        return PersonaGateService()

    @pytest.mark.asyncio
    async def test_handle_request_valid(self, service):
        """Handle valid persona publish request."""
        mock_nc = mock.AsyncMock()
        service.nc = mock_nc

        request_data = {
            "persona_id": "test-persona",
            "metrics": {
                "empirical_support": 0.5,
                "philosophical_coherence": 0.6,
                "integration_potential": 0.5,
                "description_length": 100,
                "proponent_count": 3
            }
        }

        mock_msg = mock.Mock()
        mock_msg.data = json.dumps(request_data).encode()

        await service._handle_request(mock_msg)

        # Should publish result
        mock_nc.publish.assert_called_once()
        call_args = mock_nc.publish.call_args
        assert call_args[0][0] == "persona.publish.result.v1"

    @pytest.mark.asyncio
    async def test_handle_request_invalid_json(self, service):
        """Handle invalid JSON gracefully."""
        mock_nc = mock.AsyncMock()
        service.nc = mock_nc

        mock_msg = mock.Mock()
        mock_msg.data = b"invalid json"

        # Should not raise, just log error
        await service._handle_request(mock_msg)

        # Should not publish on error
        mock_nc.publish.assert_not_called()
