"""
Simulation API Endpoints for PMOVES Tokenism Simulator

Flask API endpoints for:
- Running simulations
- Querying results
- Health checks
- Metrics exposure
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from flask import Blueprint, request, jsonify
from prometheus_client import Counter, Histogram, generate_latest

from models.simulation import (
    SimulationParameters,
    SimulationResult,
    SimulationScenario,
)
from services.simulation_engine import get_simulation_engine

logger = logging.getLogger(__name__)

# Create API blueprint
simulation_bp = Blueprint('simulation', __name__)

# Prometheus metrics
simulation_requests = Counter(
    'tokenism_simulation_requests_total',
    'Total simulation requests',
    ['scenario', 'status']
)
simulation_duration = Histogram(
    'tokenism_simulation_duration_seconds',
    'Simulation duration in seconds',
    ['scenario']
)


@simulation_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'tokenism-simulator',
        'timestamp': datetime.utcnow().isoformat(),
    }), 200


@simulation_bp.route('/healthz', methods=['GET'])
def healthz():
    """Kubernetes-style health check."""
    return jsonify({'status': 'ok'}), 200


@simulation_bp.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest(), 200


@simulation_bp.route('/api/v1/simulate', methods=['POST'])
def run_simulation():
    """
    Run a token economy simulation.

    Request body:
    {
        "scenario": "baseline" | "optimistic" | "pessimistic" | "stress_test",
        "parameters": { ... SimulationParameters }
    }

    Returns:
        SimulationResult with weekly metrics and analysis
    """
    try:
        data = request.get_json()

        # Parse scenario
        scenario_str = data.get('scenario', 'baseline')
        try:
            scenario = SimulationScenario(scenario_str)
        except ValueError:
            return jsonify({
                'error': f'Invalid scenario: {scenario_str}',
                'valid_scenarios': [s.value for s in SimulationScenario],
            }), 400

        # Parse parameters
        params_data = data.get('parameters', {})
        try:
            parameters = SimulationParameters(**params_data)
        except Exception as e:
            return jsonify({
                'error': f'Invalid parameters: {str(e)}',
            }), 400

        # Run simulation asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            start_time = datetime.utcnow()

            engine = loop.run_until_complete(get_simulation_engine())
            result = loop.run_until_complete(engine.run_simulation(parameters, scenario))

            duration = (datetime.utcnow() - start_time).total_seconds()

            # Update metrics
            simulation_requests.labels(
                scenario=scenario.value,
                status='success'
            ).inc()
            simulation_duration.labels(scenario=scenario.value).observe(duration)

            return jsonify(result.model_dump(mode='json')), 200

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Error running simulation: {e}")
        simulation_requests.labels(
            scenario=scenario.value if 'scenario' in locals() else 'unknown',
            status='error'
        ).inc()
        return jsonify({
            'error': str(e),
        }), 500


@simulation_bp.route('/api/v1/simulate/async', methods=['POST'])
def run_simulation_async():
    """
    Run a simulation asynchronously (returns immediately with simulation_id).

    Request body:
    {
        "scenario": "baseline",
        "parameters": { ... },
        "webhook_url": "https://..."  # Optional: POST result when complete
    }

    Returns:
        { "simulation_id": "...", "status": "running" }
    """
    try:
        data = request.get_json()
        webhook_url = data.get('webhook_url')

        # Parse and validate input
        scenario_str = data.get('scenario', 'baseline')
        scenario = SimulationScenario(scenario_str)
        params_data = data.get('parameters', {})
        parameters = SimulationParameters(**params_data)

        # In production, this would queue the job
        # For now, return a placeholder response
        simulation_id = f"sim_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        simulation_requests.labels(
            scenario=scenario.value,
            status='queued'
        ).inc()

        return jsonify({
            'simulation_id': simulation_id,
            'status': 'queued',
            'message': 'Simulation queued for processing',
        }), 202

    except Exception as e:
        logger.error(f"Error queuing simulation: {e}")
        return jsonify({'error': str(e)}), 500


@simulation_bp.route('/api/v1/scenarios', methods=['GET'])
def list_scenarios():
    """List available simulation scenarios."""
    return jsonify({
        'scenarios': [
            {
                'id': s.value,
                'name': s.value.replace('_', ' ').title(),
                'description': _get_scenario_description(s),
            }
            for s in SimulationScenario
        ]
    }), 200


@simulation_bp.route('/api/v1/contracts', methods=['GET'])
def list_contracts():
    """List available token economy contract types."""
    from models.simulation import ContractType

    return jsonify({
        'contracts': [
            {
                'id': c.value,
                'name': c.value.replace('_', ' ').title(),
                'description': _get_contract_description(c),
            }
            for c in ContractType
        ]
    }), 200


def _get_scenario_description(scenario: SimulationScenario) -> str:
    """Get description for a simulation scenario."""
    descriptions = {
        SimulationScenario.OPTIMISTIC: "High growth, low inequality scenario",
        SimulationScenario.BASELINE: "Standard economic conditions",
        SimulationScenario.PESSIMISTIC: "Low growth, high inequality scenario",
        SimulationScenario.STRESS_TEST: "Extreme conditions for resilience testing",
        SimulationScenario.CUSTOM: "User-defined parameters",
    }
    return descriptions.get(scenario, "Custom scenario")


def _get_contract_description(contract) -> str:
    """Get description for a contract type."""
    from models.simulation import ContractType

    descriptions = {
        ContractType.GRO_TOKEN: "Daily token distribution to participants",
        ContractType.FOOD_USD: "Stablecoin pegged to food prices",
        ContractType.GROUP_PURCHASE: "Bulk buying with cooperative discounts",
        ContractType.GRO_VAULT: "Staking with yield rewards",
        ContractType.COOP_GOVERNOR: "Governance token with voting rewards",
    }
    return descriptions.get(contract, "Custom contract")
