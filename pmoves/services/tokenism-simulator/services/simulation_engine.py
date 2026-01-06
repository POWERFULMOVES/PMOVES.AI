"""
Token Economy Simulation Engine

Core simulation logic for PMOVES Tokenism Simulator.
Implements economic modeling for token economy contracts.

Following PMOVES.AI patterns:
- Async execution with event publishing
- Integration with NATS message bus
- LLM-powered analysis via TensorZero
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from config import ServiceConfig
from config.nats import NATSClient
from config.tensorzero import TensorZeroClient
from models.simulation import (
    SimulationParameters,
    SimulationResult,
    WeeklyMetrics,
    SimulationScenario,
    ContractType,
)
from services.chit_encoder import CHITEncoder

logger = logging.getLogger(__name__)


class SimulationEngine:
    """
    Token economy simulation engine.

    Supports 5 contract types:
    - GroToken: Daily token distribution to participants
    - FoodUSD: Stablecoin pegged to food prices
    - GroupPurchase: Bulk buying discounts
    - GroVault: Staking with yield
    - CoopGovernor: Governance token with voting
    """

    def __init__(self, config: ServiceConfig):
        self.config = config
        self.nats: NATSClient | None = None
        self.tensorzero: TensorZeroClient | None = None
        self.chit: CHITEncoder | None = None

    async def initialize(self):
        """Initialize external service connections."""
        # Connect to NATS
        self.nats = NATSClient(self.config.nats)
        await self.nats.connect()

        # Initialize TensorZero client
        self.tensorzero = TensorZeroClient(self.config.tensorzero)

        # Initialize CHIT encoder
        self.chit = CHITEncoder(self.config.chit.cgp_version)

        logger.info("Simulation engine initialized")

    async def run_simulation(
        self,
        parameters: SimulationParameters,
        scenario: SimulationScenario = SimulationScenario.BASELINE,
    ) -> SimulationResult:
        """
        Run a complete token economy simulation.

        Args:
            parameters: Simulation parameters
            scenario: Economic scenario (optimistic, baseline, pessimistic, stress_test)

        Returns:
            SimulationResult with weekly metrics and analysis
        """
        simulation_id = f"sim_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        logger.info(f"Starting simulation {simulation_id} with scenario {scenario}")

        # Apply scenario modifiers
        params = self._apply_scenario_modifiers(parameters, scenario)

        # Run week-by-week simulation
        weekly_metrics = []
        current_state = self._initialize_state(params)

        for week in range(params.duration_weeks):
            metrics = await self._simulate_week(params, current_state, week)
            weekly_metrics.append(metrics)

            # Update state for next week
            self._update_state(params, current_state, metrics)

        # Calculate summary statistics
        result = SimulationResult(
            simulation_id=simulation_id,
            scenario=scenario,
            parameters=params,
            weekly_metrics=weekly_metrics,
            final_avg_wealth=weekly_metrics[-1].avg_wealth,
            final_gini=weekly_metrics[-1].gini_coefficient,
            final_poverty_rate=weekly_metrics[-1].poverty_rate,
            total_transactions=sum(m.total_transactions for m in weekly_metrics),
            total_volume=sum(m.total_volume for m in weekly_metrics),
        )

        # Calculate risk indicators
        result.wealth_volatility = self._calculate_volatility(weekly_metrics)
        result.systemic_risk_score = self._calculate_systemic_risk(result)

        # Generate AI analysis
        if self.tensorzero:
            result.analysis = await self.tensorzero.analyze_simulation(
                result.model_dump(mode='json')
            )
            result.risk_report = await self.tensorzero.generate_risk_report(
                {
                    "final_gini": result.final_gini,
                    "final_poverty_rate": result.final_poverty_rate,
                    "wealth_volatility": result.wealth_volatility,
                    "systemic_risk": result.systemic_risk_score,
                }
            )

        # Publish results to NATS
        if self.nats:
            await self.nats.publish_simulation_result(result.model_dump(mode='json'))

            # Publish CGP packet to geometry bus
            if self.chit:
                cgp = self.chit.encode_simulation_result(result)
                await self.nats.publish_cgp_packet(cgp.model_dump(mode='json'))

        logger.info(f"Simulation {simulation_id} completed")
        return result

    def _apply_scenario_modifiers(
        self,
        params: SimulationParameters,
        scenario: SimulationScenario,
    ) -> SimulationParameters:
        """Apply scenario-based modifiers to parameters."""
        params_dict = params.model_dump()

        match scenario:
            case SimulationScenario.OPTIMISTIC:
                params_dict["token_velocity"] *= 1.2
                params_dict["staking_apr"] *= 1.3
                params_dict["initial_gini"] *= 0.8
            case SimulationScenario.PESSIMISTIC:
                params_dict["token_velocity"] *= 0.8
                params_dict["staking_apr"] *= 0.7
                params_dict["initial_gini"] *= 1.2
            case SimulationScenario.STRESS_TEST:
                params_dict["token_velocity"] *= 0.5
                params_dict["transaction_fee_rate"] *= 2.0
                params_dict["initial_gini"] = 0.8

        return SimulationParameters(**params_dict)

    def _initialize_state(self, params: SimulationParameters) -> dict[str, Any]:
        """Initialize simulation state."""
        # Generate initial wealth distribution
        np.random.seed(42)
        sigma = -np.log(1 - params.initial_gini) * 0.5
        mu = np.log(1000) - sigma**2 / 2

        initial_wealth = np.random.lognormal(mu, sigma, params.initial_participants)

        return {
            "wealth": list(initial_wealth),
            "participants": params.initial_participants,
            "supply": params.initial_token_supply,
            "staked": 0.0,
            "week": 0,
        }

    async def _simulate_week(
        self,
        params: SimulationParameters,
        state: dict[str, Any],
        week_num: int,
    ) -> WeeklyMetrics:
        """Simulate one week of token economy activity."""
        wealth = np.array(state["wealth"])
        n_participants = len(wealth)

        # Calculate transaction count based on velocity
        transactions_per_week = int(n_participants * params.token_velocity * 7 / 365)

        # Calculate transaction volume (proportional to total wealth)
        total_wealth = np.sum(wealth)
        avg_transaction = total_wealth / n_participants * 0.1
        total_volume = avg_transaction * transactions_per_week

        # Apply contract-specific logic
        new_wealth, staked = self._apply_contract_logic(params, wealth, state)

        # Calculate metrics
        avg_wealth = float(np.mean(new_wealth))
        median_wealth = float(np.median(new_wealth))

        # Gini coefficient
        sorted_wealth = np.sort(new_wealth)
        n = len(sorted_wealth)
        cum_wealth = np.cumsum(sorted_wealth)
        gini = (n + 1 - 2 * np.sum(cum_wealth) / cum_wealth[-1]) / n if n > 0 else 0

        # Poverty rate (below 20% of median)
        poverty_line = median_wealth * 0.2
        poverty_rate = np.sum(new_wealth < poverty_line) / n if n > 0 else 0

        # New participants (growth model)
        growth_rate = 0.01 if week_num < 52 else 0.005
        new_participants = max(0, int(n_participants * growth_rate * np.random.uniform(0.8, 1.2)))

        # Update circulating supply (inflation + staking)
        inflation = state["supply"] * params.gro_token_daily_rate * 7
        circulating_supply = state["supply"] + inflation - staked

        return WeeklyMetrics(
            week_number=week_num,
            avg_wealth=avg_wealth,
            median_wealth=median_wealth,
            gini_coefficient=float(np.clip(gini, 0, 1)),
            poverty_rate=float(np.clip(poverty_rate, 0, 1)),
            total_transactions=transactions_per_week,
            total_volume=total_volume,
            active_participants=n_participants,
            new_participants=new_participants,
            staked_tokens=staked,
            circulating_supply=circulating_supply,
        )

    def _apply_contract_logic(
        self,
        params: SimulationParameters,
        wealth: np.ndarray,
        state: dict[str, Any],
    ) -> tuple[np.ndarray, float]:
        """Apply contract-specific token economics."""
        staked = 0.0

        match params.contract_type:
            case ContractType.GRO_TOKEN:
                # Daily distribution proportional to existing wealth
                distribution = state["supply"] * params.gro_token_daily_rate * 7
                per_capita = distribution / len(wealth)
                wealth += per_capita

            case ContractType.FOOD_USD:
                # Peg stabilizes wealth, low volatility
                stability_factor = 0.95
                target = np.mean(wealth) * params.food_usd_peg_ratio
                wealth = wealth * stability_factor + target * (1 - stability_factor)

            case ContractType.GROUP_PURCHASE:
                # Cooperative discounts boost lower wealth participants
                threshold = np.percentile(wealth, 60)
                discount = 0.05
                wealth = np.where(wealth < threshold, wealth * (1 + discount), wealth)

            case ContractType.GRO_VAULT:
                # Staking rewards
                stake_rate = 0.3
                staking_participants = int(len(wealth) * stake_rate)
                staker_indices = np.random.choice(len(wealth), staking_participants, replace=False)

                for idx in staker_indices:
                    stake_amount = wealth[idx] * 0.5
                    wealth[idx] -= stake_amount
                    wealth[idx] += stake_amount * (1 + params.staking_apr / 52)
                    staked += stake_amount

            case ContractType.COOP_GOVERNOR:
                # Governance rewards participation
                participation_bonus = 0.02
                wealth *= (1 + participation_bonus * np.random.uniform(0.8, 1.2, len(wealth)))

        return wealth, staked

    def _update_state(
        self,
        params: SimulationParameters,
        state: dict[str, Any],
        metrics: WeeklyMetrics,
    ):
        """Update state after weekly simulation."""
        state["week"] += 1
        state["participants"] += metrics.new_participants
        state["supply"] = metrics.circulating_supply
        state["staked"] = metrics.staked_tokens

    def _calculate_volatility(self, weekly_metrics: list[WeeklyMetrics]) -> float:
        """Calculate wealth volatility across simulation."""
        if len(weekly_metrics) < 2:
            return 0.0

        wealth_changes = [
            weekly_metrics[i].avg_wealth - weekly_metrics[i-1].avg_wealth
            for i in range(1, len(weekly_metrics))
        ]

        return float(np.std(wealth_changes)) if wealth_changes else 0.0

    def _calculate_systemic_risk(self, result: SimulationResult) -> float:
        """
        Calculate systemic risk score (0-1).

        Combines:
        - Gini coefficient (wealth inequality)
        - Poverty rate
        - Wealth volatility
        """
        # Normalize components
        gini_risk = result.final_gini  # 0-1
        poverty_risk = result.final_poverty_rate  # 0-1
        volatility_risk = min(result.wealth_volatility / 500, 1.0)  # Cap at 500

        # Weighted average
        systemic_risk = (
            gini_risk * 0.4 +
            poverty_risk * 0.3 +
            volatility_risk * 0.3
        )

        return float(np.clip(systemic_risk, 0, 1))

    async def close(self):
        """Close external connections."""
        if self.nats:
            await self.nats.close()
        logger.info("Simulation engine closed")


# Global engine instance
_engine: SimulationEngine | None = None


async def get_simulation_engine(config: ServiceConfig | None = None) -> SimulationEngine:
    """Get or create the global simulation engine."""
    global _engine

    if _engine is None:
        from config import config as default_config
        cfg = config or default_config
        _engine = SimulationEngine(cfg)
        await _engine.initialize()

    return _engine
