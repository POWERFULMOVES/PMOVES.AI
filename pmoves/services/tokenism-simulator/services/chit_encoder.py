"""
CHIT Encoder for PMOVES Tokenism Simulator

Encodes simulation results into CHIT Geometry Packets (CGP)
for integration with the PMOVES.AI Geometry Bus.

Following CHIT/Geometry Bus patterns:
- Hyperbolic geometry for wealth distribution
- Geometric encoding of economic relationships
- Compatibility with geometry.* NATS subjects
"""

import logging
from typing import Any
from datetime import datetime, timezone
import json

import numpy as np

from models.simulation import (
    SimulationResult,
    WeeklyMetrics,
    CGPPacket,
)

logger = logging.getLogger(__name__)


class CHITEncoder:
    """
    Encodes token economy simulation data into CHIT Geometry Packets.

    Supports:
    - Hyperbolic representation of wealth distribution
    - Temporal evolution as geometric paths
    - Network relationships as edges
    """

    def __init__(self, cgp_version: str = "0.2"):
        self.cgp_version = cgp_version

    def encode_simulation_result(
        self,
        result: SimulationResult,
        week: int | None = None,
    ) -> CGPPacket:
        """
        Encode a simulation result as a CGP packet.

        Args:
            result: Simulation result to encode
            week: Optional specific week to encode (defaults to final week)

        Returns:
            CGPPacket ready for publishing to geometry bus
        """
        # Get metrics for the specified week
        if week is not None:
            metrics = next((m for m in result.weekly_metrics if m.week_number == week), None)
        else:
            metrics = result.weekly_metrics[-1] if result.weekly_metrics else None

        if metrics is None:
            logger.warning(f"No metrics found for week {week}, using zero defaults")
            metrics = WeeklyMetrics(
                week_number=0,
                avg_wealth=0,
                median_wealth=0,
                gini_coefficient=0,
                poverty_rate=0,
                total_transactions=0,
                total_volume=0,
                active_participants=0,
                new_participants=0,
                staked_tokens=0,
                circulating_supply=0,
            )

        # Create geometric representation
        geometry = self._create_wealth_geometry(result, metrics)

        return CGPPacket(
            cgp_version=self.cgp_version,
            packet_type="tokenism_simulation",
            simulation_id=result.simulation_id,
            geometry=geometry,
            metadata={
                "scenario": result.scenario,
                "week": metrics.week_number,
                "contract_type": result.parameters.contract_type,
                "final_avg_wealth": result.final_avg_wealth,
                "final_gini": result.final_gini,
                "systemic_risk": result.systemic_risk_score,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _create_wealth_geometry(
        self,
        result: SimulationResult,
        metrics: WeeklyMetrics,
    ) -> dict[str, Any]:
        """
        Create geometric representation of wealth distribution.

        Uses hyperbolic geometry to represent:
        - X-axis: log(wealth)
        - Y-axis: participant density
        - Color/radius: transaction volume

        Args:
            result: Full simulation result
            metrics: Specific week metrics

        Returns:
            Geometric data dictionary
        """
        # Generate synthetic wealth distribution based on metrics
        # In production, this would use actual participant data
        n_participants = metrics.active_participants
        avg_wealth = metrics.avg_wealth
        gini = metrics.gini_coefficient

        # Generate points using log-normal distribution (matches Gini)
        # Scale parameter derived from Gini coefficient
        sigma = -np.log(1 - gini) * 0.5
        mu = np.log(avg_wealth) - sigma**2 / 2

        # Generate participant wealth points
        wealth_points = np.random.lognormal(mu, sigma, n_participants)

        # Create 2D hyperbolic representation
        # X: log(wealth), Y: random (visualizes distribution spread)
        points = []
        for w in wealth_points[:100]:  # Limit to 100 points for visualization
            x = np.log1p(w)
            y = np.random.uniform(-1, 1)
            points.append([float(x), float(y)])

        # Create edges for high-wealth connections (network effects)
        edges = []
        sorted_indices = sorted(range(len(wealth_points)), key=lambda i: wealth_points[i], reverse=True)
        top_wealth_indices = sorted_indices[:min(10, len(wealth_points))]

        for i in range(len(top_wealth_indices) - 1):
            edges.append([top_wealth_indices[i], top_wealth_indices[i + 1]])

        return {
            "dimension": 2,
            "manifold": "hyperbolic",
            "coordinates": "poincare_disk",
            "points": points,
            "edges": edges,
            "bounds": {
                "x_min": float(np.log1p(avg_wealth * 0.1)),
                "x_max": float(np.log1p(avg_wealth * 3)),
                "y_min": -1.0,
                "y_max": 1.0,
            },
            "statistics": {
                "mean_log_wealth": float(np.mean([p[0] for p in points])),
                "std_log_wealth": float(np.std([p[0] for p in points])),
                "density_peaks": len(points) // 4,
            },
        }

    def encode_temporal_evolution(
        self,
        result: SimulationResult,
    ) -> CGPPacket:
        """
        Encode the temporal evolution of a simulation as a geometric path.

        Args:
            result: Simulation result with weekly metrics

        Returns:
            CGPPacket with temporal geometry
        """
        # Extract time series data
        weeks = [m.week_number for m in result.weekly_metrics]
        avg_wealth = [m.avg_wealth for m in result.weekly_metrics]
        gini = [m.gini_coefficient for m in result.weekly_metrics]

        # Normalize for visualization
        max_week = max(weeks) if weeks else 1
        max_wealth = max(avg_wealth) if avg_wealth else 1

        # Create path points (week, normalized wealth, gini)
        points = []
        for i, (w, wealth, g) in enumerate(zip(weeks, avg_wealth, gini)):
            x = w / max_week  # Time normalized to [0, 1]
            y = wealth / max_wealth  # Wealth normalized to [0, 1]
            z = g  # Gini stays in [0, 1]
            points.append([x, y, z])

        # Create edges connecting temporal sequence
        edges = [[i, i + 1] for i in range(len(points) - 1)]

        return CGPPacket(
            cgp_version=self.cgp_version,
            packet_type="tokenism_temporal",
            simulation_id=result.simulation_id,
            geometry={
                "dimension": 3,
                "manifold": "euclidean",
                "coordinates": "cartesian",
                "points": points,
                "edges": edges,
                "bounds": {
                    "x_min": 0.0,
                    "x_max": 1.0,
                    "y_min": 0.0,
                    "y_max": 1.0,
                    "z_min": 0.0,
                    "z_max": 1.0,
                },
            },
            metadata={
                "scenario": result.scenario,
                "contract_type": result.parameters.contract_type,
                "total_weeks": len(weeks),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    def encode_calibration(
        self,
        simulation_id: str,
        parameter_name: str,
        old_value: float,
        new_value: float,
        confidence: float,
    ) -> CGPPacket:
        """
        Encode a calibration event as a CGP packet.

        Args:
            simulation_id: Reference simulation
            parameter_name: Calibrated parameter
            old_value: Original value
            new_value: New calibrated value
            confidence: Confidence score

        Returns:
            CGPPacket for geometry bus
        """
        # Geometric representation: parameter space point
        point = [old_value, new_value, confidence]

        return CGPPacket(
            cgp_version=self.cgp_version,
            packet_type="tokenism_calibration",
            simulation_id=simulation_id,
            geometry={
                "dimension": 3,
                "manifold": "euclidean",
                "coordinates": "cartesian",
                "points": [point],
                "edges": [],
                "parameter_space": {
                    "parameter": parameter_name,
                    "old_value": old_value,
                    "new_value": new_value,
                    "delta": new_value - old_value,
                },
            },
            metadata={
                "parameter_name": parameter_name,
                "confidence": confidence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    def to_json(self, packet: CGPPacket) -> str:
        """Convert CGP packet to JSON string."""
        return packet.model_dump_json(exclude_none=True)

    def from_json(self, json_str: str) -> CGPPacket:
        """Parse CGP packet from JSON string."""
        data = json.loads(json_str)
        return CGPPacket(**data)


# Global encoder instance
_encoder: CHITEncoder | None = None


def get_chit_encoder(cgp_version: str = "0.2") -> CHITEncoder:
    """Get or create the global CHIT encoder."""
    global _encoder
    if _encoder is None:
        _encoder = CHITEncoder(cgp_version)
    return _encoder
