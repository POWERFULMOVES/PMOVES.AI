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
import threading
from datetime import datetime, timezone
from typing import Any
from concurrent.futures import ThreadPoolExecutor

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

# Background task storage
_simulation_results: dict[str, dict[str, Any]] = {}
_simulation_statuses: dict[str, str] = {}
_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    """Get or create the background task executor."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sim_worker")
    return _executor


def _run_simulation_background(
    simulation_id: str,
    parameters: SimulationParameters,
    scenario: SimulationScenario,
    webhook_url: str | None = None,
) -> None:
    """Run simulation in background thread and store result.

    Args:
        simulation_id: Unique simulation identifier.
        parameters: Simulation parameters.
        scenario: Economic scenario.
        webhook_url: Optional URL to POST result when complete.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        start_time = datetime.now(timezone.utc)
        _simulation_statuses[simulation_id] = "running"

        engine = loop.run_until_complete(get_simulation_engine())
        result = loop.run_until_complete(engine.run_simulation(parameters, scenario))

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Store result
        _simulation_results[simulation_id] = result.model_dump(mode='json')
        _simulation_statuses[simulation_id] = "complete"

        simulation_requests.labels(
            scenario=scenario.value,
            status='success'
        ).inc()
        simulation_duration.labels(scenario=scenario.value).observe(duration)

        logger.info(f"Background simulation {simulation_id} completed in {duration:.2f}s")

        # TODO: Send webhook if provided
        if webhook_url:
            logger.info(f"Would send webhook to {webhook_url} (not implemented)")

    except Exception as e:
        _simulation_statuses[simulation_id] = "failed"
        _simulation_results[simulation_id] = {"error": str(e)}
        simulation_requests.labels(
            scenario=scenario.value,
            status='error'
        ).inc()
        logger.error(f"Background simulation {simulation_id} failed: {e}")

    finally:
        loop.close()


@simulation_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'tokenism-simulator',
        'timestamp': datetime.now(timezone.utc).isoformat(),
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
            start_time = datetime.now(timezone.utc)

            engine = loop.run_until_complete(get_simulation_engine())
            result = loop.run_until_complete(engine.run_simulation(parameters, scenario))

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

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

        # Generate unique simulation ID
        simulation_id = f"sim_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        # Submit background task
        executor = _get_executor()
        executor.submit(
            _run_simulation_background,
            simulation_id,
            parameters,
            scenario,
            webhook_url
        )

        simulation_requests.labels(
            scenario=scenario.value,
            status='queued'
        ).inc()

        return jsonify({
            'simulation_id': simulation_id,
            'status': 'queued',
            'message': 'Simulation queued for processing',
            'check_url': f'/api/v1/simulate/{simulation_id}',
        }), 202

    except Exception as e:
        logger.error(f"Error queuing simulation: {e}")
        return jsonify({'error': str(e)}), 500


@simulation_bp.route('/api/v1/simulate/<simulation_id>', methods=['GET'])
def get_simulation_status(simulation_id: str):
    """
    Get the status and result of an async simulation.

    Args:
        simulation_id: The simulation ID returned from the async endpoint.

    Returns:
        Status information and result if complete.
    """
    status = _simulation_statuses.get(simulation_id, 'unknown')

    if status == 'complete':
        result = _simulation_results.get(simulation_id, {})
        return jsonify({
            'simulation_id': simulation_id,
            'status': status,
            'result': result,
        }), 200
    elif status == 'failed':
        result = _simulation_results.get(simulation_id, {})
        return jsonify({
            'simulation_id': simulation_id,
            'status': status,
            'error': result.get('error', 'Unknown error'),
        }), 500
    elif status == 'running':
        return jsonify({
            'simulation_id': simulation_id,
            'status': status,
            'message': 'Simulation still in progress',
        }), 202
    else:
        return jsonify({
            'error': f'Simulation {simulation_id} not found',
        }), 404


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
