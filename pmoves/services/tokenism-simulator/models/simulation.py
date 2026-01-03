"""
Token Economy Simulation Models

Defines data structures for:
- Simulation parameters and results
- Calibration data
- Wealth distribution metrics
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from enum import Enum

from pydantic import BaseModel, Field


class ContractType(str, Enum):
    """Token economy contract types."""
    GRO_TOKEN = "gro_token"
    FOOD_USD = "food_usd"
    GROUP_PURCHASE = "group_purchase"
    GRO_VAULT = "gro_vault"
    COOP_GOVERNOR = "coop_governor"


class SimulationScenario(str, Enum):
    """Predefined simulation scenarios."""
    OPTIMISTIC = "optimistic"
    BASELINE = "baseline"
    PESSIMISTIC = "pessimistic"
    STRESS_TEST = "stress_test"
    CUSTOM = "custom"


class SimulationParameters(BaseModel):
    """Parameters for token economy simulation."""

    # Initial conditions
    initial_participants: int = Field(default=1000, description="Number of initial participants")
    initial_token_supply: float = Field(default=1_000_000, description="Initial token supply")

    # Economic parameters
    token_velocity: float = Field(default=2.0, ge=0, le=10, description="Token velocity per year")
    transaction_fee_rate: float = Field(default=0.01, ge=0, le=0.1, description="Transaction fee rate")
    staking_apr: float = Field(default=0.05, ge=0, le=0.5, description="Annual staking reward rate")

    # Distribution parameters
    initial_gini: float = Field(default=0.5, ge=0, le=1, description="Initial Gini coefficient")
    wealth_skew: float = Field(default=1.5, ge=1, description="Wealth distribution skew factor")

    # Contract-specific settings
    contract_type: ContractType = Field(default=ContractType.GRO_TOKEN)
    gro_token_daily_rate: float = Field(default=0.001, ge=0, description="Daily GroToken distribution rate")
    food_usd_peg_ratio: float = Field(default=1.0, ge=0.5, le=2.0, description="FoodUSD peg ratio")
    group_purchase_min_size: int = Field(default=10, ge=1, description="Minimum group purchase size")

    # Simulation settings
    duration_weeks: int = Field(default=260, ge=1, le=520, description="Simulation duration in weeks (5 years)")
    time_step_days: int = Field(default=1, ge=1, le=7, description="Simulation time step in days")

    class Config:
        json_schema_extra = {
            "example": {
                "initial_participants": 1000,
                "initial_token_supply": 1000000,
                "token_velocity": 2.0,
                "transaction_fee_rate": 0.01,
                "staking_apr": 0.05,
                "initial_gini": 0.5,
                "wealth_skew": 1.5,
                "contract_type": "gro_token",
                "duration_weeks": 260,
            }
        }


class WeeklyMetrics(BaseModel):
    """Metrics for a single week of simulation."""

    week_number: int = Field(..., ge=0)
    avg_wealth: float = Field(..., ge=0, description="Average wealth per participant")
    median_wealth: float = Field(..., ge=0, description="Median wealth")
    gini_coefficient: float = Field(..., ge=0, le=1, description="Wealth inequality (0=equality, 1=inequality)")
    poverty_rate: float = Field(..., ge=0, le=1, description="Rate of participants below poverty line")
    total_transactions: int = Field(..., ge=0, description="Total transactions this week")
    total_volume: float = Field(..., ge=0, description="Total transaction volume")
    active_participants: int = Field(..., ge=0, description="Active participants this week")
    new_participants: int = Field(default=0, ge=0, description="New participants this week")
    staked_tokens: float = Field(default=0, ge=0, description="Total staked tokens")
    circulating_supply: float = Field(..., ge=0, description="Circulating token supply")

    class Config:
        json_schema_extra = {
            "example": {
                "week_number": 52,
                "avg_wealth": 1250.50,
                "median_wealth": 850.00,
                "gini_coefficient": 0.48,
                "poverty_rate": 0.12,
                "total_transactions": 5420,
                "total_volume": 125000.00,
                "active_participants": 980,
                "new_participants": 15,
                "staked_tokens": 350000.00,
                "circulating_supply": 980000.00,
            }
        }


class SimulationResult(BaseModel):
    """Complete simulation result."""

    simulation_id: str = Field(..., description="Unique simulation identifier")
    scenario: SimulationScenario = Field(default=SimulationScenario.BASELINE)
    parameters: SimulationParameters
    weekly_metrics: list[WeeklyMetrics] = Field(..., description="Metrics for each week")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Summary statistics
    final_avg_wealth: float = Field(..., description="Final average wealth")
    final_gini: float = Field(..., description="Final Gini coefficient")
    final_poverty_rate: float = Field(..., description="Final poverty rate")
    total_transactions: int = Field(..., description="Total transactions across simulation")
    total_volume: float = Field(..., description="Total transaction volume")

    # Risk indicators
    wealth_volatility: float = Field(default=0.0, ge=0, description="Standard deviation of wealth changes")
    systemic_risk_score: float = Field(default=0.0, ge=0, le=1, description="Systemic risk (0-1)")

    # LLM analysis (optional)
    analysis: Optional[str] = Field(default=None, description="AI-generated analysis")
    risk_report: Optional[str] = Field(default=None, description="AI-generated risk report")

    class Config:
        json_schema_extra = {
            "example": {
                "simulation_id": "sim_20250130_001",
                "scenario": "baseline",
                "final_avg_wealth": 1450.25,
                "final_gini": 0.52,
                "final_poverty_rate": 0.10,
                "total_transactions": 1250000,
                "total_volume": 28000000.00,
                "wealth_volatility": 125.50,
                "systemic_risk_score": 0.35,
            }
        }


class CalibrationData(BaseModel):
    """Data for calibrating simulation to real-world observations."""

    calibration_id: str = Field(..., description="Unique calibration identifier")
    simulation_id: str = Field(..., description="Reference to simulation being calibrated")
    parameter_name: str = Field(..., description="Parameter being calibrated")
    old_value: float = Field(..., description="Original parameter value")
    new_value: float = Field(..., description="Calibrated parameter value")
    confidence_score: float = Field(default=0.5, ge=0, le=1, description="Confidence in calibration")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Calibration metadata
    observed_value: Optional[float] = Field(default=None, description="Observed real-world value")
    target_error: float = Field(default=0.0, ge=0, description="Target error tolerance")
    actual_error: float = Field(default=0.0, ge=0, description="Actual error after calibration")
    iterations: int = Field(default=1, ge=1, description="Number of calibration iterations")

    class Config:
        json_schema_extra = {
            "example": {
                "calibration_id": "cal_20250130_001",
                "simulation_id": "sim_20250130_001",
                "parameter_name": "token_velocity",
                "old_value": 2.0,
                "new_value": 1.85,
                "confidence_score": 0.78,
                "observed_value": 1.82,
                "target_error": 0.05,
                "actual_error": 0.016,
                "iterations": 3,
            }
        }


class CGPPacket(BaseModel):
    """CHIT Geometry Packet for token economy data.

    Encodes simulation results into geometric representation
    for visualization and analysis via the Geometry Bus.
    """

    cgp_version: str = Field(default="0.2", description="CGP schema version")
    packet_type: str = Field(default="tokenism_simulation", description="Packet type identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Source identification
    source: str = Field(default="tokenism-simulator", description="Source service")
    simulation_id: str = Field(..., description="Reference simulation")

    # Geometric data (hyperbolic representation)
    geometry: dict[str, Any] = Field(..., description="Geometric encoding of data")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "cgp_version": "0.2",
                "packet_type": "tokenism_simulation",
                "simulation_id": "sim_20250130_001",
                "geometry": {
                    "dimension": 2,
                    "manifold": "hyperbolic",
                    "points": [[0.1, 0.2], [0.3, 0.4]],
                    "edges": [[0, 1]],
                },
                "metadata": {
                    "scenario": "baseline",
                    "week": 52,
                },
            }
        }
