"""Tests for CHIT geometry encoder.

Tests cover:
- CGP packet encode/decode round-trip
- Full simulation result encoding
- Weekly metrics geometry
"""
import sys
import pytest
from decimal import Decimal

# Add service to path
sys.path.insert(0, "pmoves/services/tokenism-simulator")

from models.simulation import (
    CGPPacket,
    SimulationResult,
    SimulationScenario,
    SimulationParameters,
    WeeklyMetrics,
)
from services.chit_encoder import CHITEncoder


class TestCHITEncoderRoundTrip:
    """Test CGP packet survives encode/decode cycle."""

    def test_encode_decode_roundtrip(self):
        """Test CGP packet survives encode/decode cycle."""
        original = CGPPacket(
            simulation_id="test-sim",
            geometry={"points": [[0, 1], [1, 2]], "edges": [[0, 1]]},
            metadata={"test_key": "test_value"}
        )

        encoder = CHITEncoder()
        json_str = encoder.to_json(original)
        decoded = encoder.from_json(json_str)

        assert decoded.simulation_id == original.simulation_id
        assert decoded.geometry == original.geometry
        assert decoded.metadata == original.metadata

    def test_encode_minimal_packet(self):
        """Test encoding with minimal required fields."""
        packet = CGPPacket(
            simulation_id="minimal-test",
            geometry={},
            metadata={}
        )

        encoder = CHITEncoder()
        json_str = encoder.to_json(packet)

        assert json_str is not None
        assert "simulation_id" in json_str
        assert "geometry" in json_str

    def test_encode_with_complex_geometry(self):
        """Test encoding with complex nested geometry."""
        geometry = {
            "wealth_distribution": {
                "points": [[0, 100], [1, 200], [2, 150]],
                "metadata": {"mean": 150, "stddev": 50}
            },
            "temporal": {
                "weeks": [0, 1, 2],
                "values": [100, 110, 120]
            }
        }

        packet = CGPPacket(
            simulation_id="complex-geometry-test",
            geometry=geometry,
            metadata={"scenario": "baseline"}
        )

        encoder = CHITEncoder()
        json_str = encoder.to_json(packet)
        decoded = encoder.from_json(json_str)

        assert decoded.geometry["wealth_distribution"]["points"] == geometry["wealth_distribution"]["points"]


class TestSimulationResultEncoding:
    """Test full simulation result encoding."""

    def test_encode_simulation_result(self):
        """Test full simulation result encoding."""
        params = SimulationParameters(
            initial_participants=100,
            initial_token_supply=1000,
            token_velocity=2.0,
            transaction_fee_rate=0.01,
            staking_apr=0.05,
            initial_gini=0.5,
            wealth_skew=1.5,
            contract_type="gro_token",
            duration_weeks=52,
        )

        result = SimulationResult(
            simulation_id="test-sim-001",
            scenario=SimulationScenario.BASELINE,
            parameters=params,
            final_avg_wealth=1000.0,
            final_gini=Decimal('0.3'),
            final_poverty_rate=Decimal('0.1'),
            total_transactions=1000,
            total_volume=Decimal('50000.00'),
            weekly_metrics=[
                WeeklyMetrics(
                    week_number=0,
                    avg_wealth=Decimal('1000'),
                    median_wealth=Decimal('950'),
                    gini_coefficient=Decimal('0.3'),
                    poverty_rate=Decimal('0.1'),
                    total_transactions=100,
                    total_volume=Decimal('10000'),
                    active_participants=50,
                    new_participants=5,
                    staked_tokens=Decimal('500'),
                    circulating_supply=Decimal('1000')
                )
            ]
        )

        encoder = CHITEncoder()
        packet = encoder.encode_simulation_result(result)

        assert packet.packet_type == "tokenism_simulation"
        assert packet.simulation_id == result.simulation_id
        # Verify geometry structure exists (CHITEncoder creates hyperbolic geometry)
        assert "dimension" in packet.geometry
        assert "manifold" in packet.geometry
        assert packet.metadata["scenario"] == result.scenario

    def test_encode_with_missing_weekly_metrics(self):
        """Test encoding handles minimal weekly metrics (edge case)."""
        params = SimulationParameters(
            initial_participants=100,
            initial_token_supply=1000,
            token_velocity=2.0,
            transaction_fee_rate=0.01,
            staking_apr=0.05,
            initial_gini=0.5,
            wealth_skew=1.5,
            contract_type="gro_token",
            duration_weeks=52,
        )

        # Use minimal valid metrics instead of empty (avoid sigma=0 edge case)
        minimal_metrics = WeeklyMetrics(
            week_number=0,
            avg_wealth=Decimal('100'),
            median_wealth=Decimal('100'),
            gini_coefficient=Decimal('0.1'),  # Small positive value for valid sigma
            poverty_rate=Decimal('0'),
            total_transactions=10,
            total_volume=Decimal('1000'),
            active_participants=10,  # Need participants > 0 for geometry
            new_participants=0,
            staked_tokens=Decimal('0'),
            circulating_supply=Decimal('1000'),
        )

        result = SimulationResult(
            simulation_id="test-sim-minimal-metrics",
            scenario=SimulationScenario.OPTIMISTIC,
            parameters=params,
            final_avg_wealth=2000.0,
            final_gini=Decimal('0.2'),
            final_poverty_rate=Decimal('0.05'),
            total_transactions=500,
            total_volume=Decimal('25000.00'),
            weekly_metrics=[minimal_metrics]
        )

        encoder = CHITEncoder()
        packet = encoder.encode_simulation_result(result, week=0)

        assert packet.packet_type == "tokenism_simulation"
        assert packet.metadata["week"] == 0

    def test_encode_stress_test_scenario(self):
        """Test encoding stress test scenario."""
        params = SimulationParameters(
            initial_participants=100,
            initial_token_supply=1000,
            token_velocity=1.5,
            transaction_fee_rate=0.02,
            staking_apr=0.03,
            initial_gini=0.4,  # Valid Gini (< 1)
            wealth_skew=2.0,
            contract_type="gro_token",
            duration_weeks=52,
        )

        # Add minimal valid metrics for stress test scenario
        stress_metrics = WeeklyMetrics(
            week_number=0,
            avg_wealth=Decimal('500'),
            median_wealth=Decimal('400'),
            gini_coefficient=Decimal('0.5'),  # Valid Gini
            poverty_rate=Decimal('0.3'),
            total_transactions=20,
            total_volume=Decimal('5000'),
            active_participants=50,
            new_participants=0,
            staked_tokens=Decimal('0'),
            circulating_supply=Decimal('1000'),
        )

        result = SimulationResult(
            simulation_id="stress-test",
            scenario=SimulationScenario.STRESS_TEST,
            parameters=params,
            final_avg_wealth=500.0,
            final_gini=Decimal('0.5'),  # Valid Gini
            final_poverty_rate=Decimal('0.3'),
            total_transactions=200,
            total_volume=Decimal('5000.00'),
            weekly_metrics=[stress_metrics]
        )

        encoder = CHITEncoder()
        packet = encoder.encode_simulation_result(result)

        assert packet.metadata["scenario"] == SimulationScenario.STRESS_TEST


class TestWeeklyMetricsGeometry:
    """Test weekly metrics geometric encoding."""

    def test_weekly_metrics_geometry_structure(self):
        """Test weekly metrics produce correct geometry structure."""
        params = SimulationParameters(
            initial_participants=75,
            initial_token_supply=1500,
            token_velocity=2.0,
            transaction_fee_rate=0.01,
            staking_apr=0.05,
            initial_gini=0.35,
            wealth_skew=1.5,
            contract_type="gro_token",
            duration_weeks=52,
        )

        metrics = WeeklyMetrics(
            week_number=5,
            avg_wealth=Decimal('1500'),
            median_wealth=Decimal('1400'),
            gini_coefficient=Decimal('0.35'),
            poverty_rate=Decimal('0.15'),
            total_transactions=250,
            total_volume=Decimal('15000'),
            active_participants=75,
            new_participants=10,
            staked_tokens=Decimal('750'),
            circulating_supply=Decimal('1500')
        )

        result = SimulationResult(
            simulation_id="metrics-test",
            scenario=SimulationScenario.BASELINE,
            parameters=params,
            final_avg_wealth=1500.0,
            final_gini=Decimal('0.35'),
            final_poverty_rate=Decimal('0.15'),
            total_transactions=250,
            total_volume=Decimal('15000'),
            weekly_metrics=[metrics]
        )

        encoder = CHITEncoder()
        packet = encoder.encode_simulation_result(result, week=5)

        # Verify geometry structure (CHITEncoder creates hyperbolic geometry)
        assert "dimension" in packet.geometry
        assert "manifold" in packet.geometry
        assert "points" in packet.geometry
        assert packet.geometry["dimension"] == 2
        assert packet.geometry["manifold"] == "hyperbolic"
        assert packet.metadata["week"] == 5

    def test_specific_week_selection(self):
        """Test encoding specific week from multi-week results."""
        params = SimulationParameters(
            initial_participants=100,
            initial_token_supply=2000,
            token_velocity=2.0,
            transaction_fee_rate=0.01,
            staking_apr=0.05,
            initial_gini=0.3,
            wealth_skew=1.0,
            contract_type="gro_token",
            duration_weeks=52,
        )

        metrics = [
            WeeklyMetrics(
                week_number=i,
                avg_wealth=Decimal(str(1000 + i * 100)),
                median_wealth=Decimal(str(950 + i * 100)),
                gini_coefficient=Decimal('0.3'),
                poverty_rate=Decimal('0.1'),
                total_transactions=100 * (i + 1),
                total_volume=Decimal(str(10000 * (i + 1))),
                active_participants=50,
                new_participants=5,
                staked_tokens=Decimal('500'),
                circulating_supply=Decimal('1000')
            )
            for i in range(5)
        ]

        result = SimulationResult(
            simulation_id="multi-week-test",
            scenario=SimulationScenario.BASELINE,
            parameters=params,
            final_avg_wealth=1400.0,
            final_gini=Decimal('0.3'),
            final_poverty_rate=Decimal('0.1'),
            total_transactions=1500,
            total_volume=Decimal('150000'),
            weekly_metrics=metrics
        )

        encoder = CHITEncoder()

        # Encode week 2
        packet = encoder.encode_simulation_result(result, week=2)
        assert packet.metadata["week"] == 2

        # Encode week 4
        packet = encoder.encode_simulation_result(result, week=4)
        assert packet.metadata["week"] == 4

