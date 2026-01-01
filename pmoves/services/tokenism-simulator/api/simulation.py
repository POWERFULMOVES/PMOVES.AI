"""
Simulation API Endpoints for PMOVES Tokenism Simulator.

This module provides Flask Blueprint endpoints for the Tokenism Simulator service,
which models token economy dynamics including supply, price, staking behavior,
and economic metrics under various market scenarios.

Endpoints:
    - POST /api/v1/simulate: Run synchronous simulation
    - POST /api/v1/simulate/async: Queue asynchronous simulation
    - GET  /api/v1/simulate/<id>: Get async simulation status
    - GET  /api/v1/scenarios: List available economic scenarios
    - GET  /health: Detailed health check with timestamp
    - GET  /healthz: Kubernetes-style health check
    - GET  /metrics: Prometheus metrics exposition

Features:
    - Synchronous and asynchronous simulation execution
    - Background thread pool for concurrent simulations (max 4 workers)
    - In-memory result cache with LRU eviction (max 1000 entries)
    - Prometheus metrics for request counting and duration tracking
    - Support for multiple economic scenarios (baseline, optimistic, pessimistic, stress_test)

Thread Safety:
    All shared state is protected by threading locks:
    - _results_lock: Protects simulation results cache
    - _status_lock: Protects simulation status tracking
    - _executor_lock: Protects thread pool executor initialization

Example Usage:
    .. code-block:: python

        # Synchronous simulation
        response = client.post('/api/v1/simulate', json={
            'scenario': 'baseline',
            'parameters': {
                'initial_supply': 1000000,
                'initial_price': 1.0,
                'weeks': 52
            }
        })
        result = response.json

        # Asynchronous simulation
        response = client.post('/api/v1/simulate/async', json={
            'scenario': 'optimistic',
            'parameters': {'initial_supply': 1000000, 'weeks': 104}
        })
        sim_id = response.json['simulation_id']

        # Poll for completion
        status = client.get(f'/api/v1/simulate/{sim_id}').json
        while status['status'] == 'running':
            time.sleep(2)
            status = client.get(f'/api/v1/simulate/{sim_id}').json

        result = status['result']
"""

import asyncio
import logging
import threading
import uuid
import atexit
from collections import OrderedDict
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

# Background task storage with LRU eviction to prevent memory leaks
_MAX_RESULTS = 1000  # Maximum number of simulation results to keep in memory
_simulation_results: OrderedDict[str, dict[str, Any]] = OrderedDict()
_simulation_statuses: dict[str, str] = {}
_executor: ThreadPoolExecutor | None = None

# Thread safety for concurrent access
_results_lock = threading.Lock()
_status_lock = threading.Lock()
_executor_lock = threading.Lock()


def _evict_old_results() -> None:
    """Evict oldest results if we exceed the maximum cache size.

    This function implements LRU (Least Recently Used) eviction policy to
    prevent unbounded memory growth from storing simulation results. When the
    cache size exceeds `_MAX_RESULTS`, the oldest entries are removed from both
    the results and status tracking dictionaries.

    Thread safety is maintained by acquiring both locks during eviction to
    prevent inconsistent state between results and statuses.

    Note:
        This function must be called while holding the `_results_lock` to
        ensure atomicity of the check-and-evict operation.
    """
    # Collect IDs to evict first to minimize lock holding time
    ids_to_evict = []
    with _results_lock:
        while len(_simulation_results) > _MAX_RESULTS:
            oldest_id, _ = _simulation_results.popitem(last=False)
            ids_to_evict.append(oldest_id)

    # Evict corresponding status entries
    if ids_to_evict:
        with _status_lock:
            for old_id in ids_to_evict:
                _simulation_statuses.pop(old_id, None)


def _shutdown_executor() -> None:
    """Shutdown the background executor on application shutdown.

    This function is registered with `atexit` to ensure clean shutdown of
    the ThreadPoolExecutor when the application exits. It waits for all
    running tasks to complete before shutdown.

    The function is thread-safe and uses `_executor_lock` to prevent race
    conditions with concurrent calls to `_get_executor`.

    Note:
        This function should not be called directly by application code.
        It is invoked automatically by the `atexit` module during process
        termination.
    """
    global _executor
    with _executor_lock:
        if _executor is not None:
            logger.info("Shutting down simulation executor...")
            _executor.shutdown(wait=True)
            _executor = None


# Register shutdown handler to run on process exit
atexit.register(_shutdown_executor)


def _get_executor() -> ThreadPoolExecutor:
    """Get or create the background task executor (thread-safe).

    This function implements lazy initialization of a ThreadPoolExecutor for
    running asynchronous simulations. The executor is created on first access
    and reused for subsequent calls.

    The executor is configured with a maximum of 4 worker threads, each named
    with the prefix "sim_worker" for easy identification in debug logs.

    Returns:
        ThreadPoolExecutor: The thread pool executor instance for running
            background simulation tasks. The same instance is returned on
            subsequent calls.

    Note:
        This function is thread-safe and uses `_executor_lock` to prevent
        race conditions during initialization. The executor is automatically
        shut down when the application exits via `_shutdown_executor`.
    """
    global _executor
    with _executor_lock:
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

    This function executes a token economy simulation asynchronously in a
    background thread. It creates a new asyncio event loop for the thread,
    runs the simulation using the simulation engine, stores the result in
    the in-memory cache, and updates Prometheus metrics.

    The function handles both successful and failed simulations, updating
    the simulation status accordingly. If the cache exceeds `_MAX_RESULTS`,
    old results are automatically evicted using the LRU policy.

    Args:
        simulation_id: Unique simulation identifier for tracking and
            retrieving results. Should be formatted as "sim_{timestamp}_{uuid}".
        parameters: Simulation parameters including economic variables,
            token supply, and configuration settings.
        scenario: Economic scenario defining market conditions and
            external factors (e.g., BASELINE, OPTIMISTIC, PESSIMISTIC).
        webhook_url: Optional URL to POST the simulation result when complete.
            Currently not implemented (logged but not executed).

    Raises:
        Exception: Any exception from the simulation engine is caught, logged,
            and stored as an error result. The function does not propagate
            exceptions to avoid crashing the background thread.

    Note:
        This function creates its own asyncio event loop since it runs in a
        separate thread. The loop is closed in the finally block to ensure
        proper cleanup.

    Note:
        Thread safety is ensured by acquiring both `_results_lock` and
        `_status_lock` together when updating shared state, preventing
        inconsistent reads during concurrent access.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        start_time = datetime.now(timezone.utc)
        with _status_lock:
            _simulation_statuses[simulation_id] = "running"

        engine = loop.run_until_complete(get_simulation_engine())
        result = loop.run_until_complete(engine.run_simulation(parameters, scenario))

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Store result and trigger eviction if needed (acquire locks together for consistency)
        with _results_lock, _status_lock:
            _simulation_results[simulation_id] = result.model_dump(mode='json')
            _evict_old_results()
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
        # Acquire locks together for consistency with success path
        with _status_lock, _results_lock:
            _simulation_statuses[simulation_id] = "failed"
            _simulation_results[simulation_id] = {"error": str(e)}
            _evict_old_results()
        simulation_requests.labels(
            scenario=scenario.value,
            status='error'
        ).inc()
        logger.exception(f"Background simulation {simulation_id} failed: {e}")

    finally:
        loop.close()


@simulation_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint.

    Provides a detailed health status for the Tokenism Simulator service,
    including the current timestamp for monitoring uptime and responsiveness.

    Returns:
        tuple: A tuple containing:
            - dict: Health status response with keys:
                - status (str): Always "healthy" if service is running.
                - service (str): Service identifier "tokenism-simulator".
                - timestamp (str): Current UTC timestamp in ISO 8601 format.
            - int: HTTP status code 200.

    Examples:
        >>> response = client.get('/health')
        >>> response.json
        {'status': 'healthy', 'service': 'tokenism-simulator',
         'timestamp': '2025-12-31T12:00:00+00:00'}
    """
    return jsonify({
        'status': 'healthy',
        'service': 'tokenism-simulator',
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }), 200


@simulation_bp.route('/healthz', methods=['GET'])
def healthz():
    """Kubernetes-style health check.

    Provides a minimal health check endpoint compatible with Kubernetes
    liveness and readiness probes. This endpoint follows the convention
    of returning a simple "ok" status for container orchestration systems.

    Returns:
        tuple: A tuple containing:
            - dict: Health status response with key:
                - status (str): Always "ok" if service is running.
            - int: HTTP status code 200.

    Examples:
        >>> response = client.get('/healthz')
        >>> response.json
        {'status': 'ok'}

    Note:
        Kubernetes uses this endpoint for both liveness and readiness
        probes by default. The service must return 200 for the pod to
        be considered healthy.
    """
    return jsonify({'status': 'ok'}), 200


@simulation_bp.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint.

    Exposes Prometheus metrics in the standard text-based exposition format
    for scraping by a Prometheus server. Metrics include simulation request
    counts, duration histograms, and any other instrumented values.

    Returns:
        tuple: A tuple containing:
            - bytes: Prometheus metrics in text/plain format with metric
                definitions and values.
            - int: HTTP status code 200.
            - dict: Headers with Content-Type: text/plain.

    Examples:
        >>> response = client.get('/metrics')
        >>> b'# HELP tokenism_simulation_requests_total Total simulation requests'
        >>> b'# TYPE tokenism_simulation_requests_total counter'
        >>> b'tokenism_simulation_requests_total{scenario="baseline",status="success"} 42'

    Note:
        This endpoint is typically polled by Prometheus every 15-60 seconds
        as configured in the Prometheus scrape configuration. The metrics
        include labels for scenario type and status (success/error/queued).
    """
    return generate_latest(), 200


@simulation_bp.route('/api/v1/simulate', methods=['POST'])
def run_simulation():
    """Run a token economy simulation synchronously.

    Executes a token economy simulation immediately and returns the complete
    results. This endpoint blocks until the simulation completes, making it
    suitable for shorter-running simulations or when immediate results are
    required.

    The simulation models token supply dynamics, price movements, staking
    behavior, and economic metrics over a specified time period under the
    chosen scenario conditions.

    Request Body:
        {
            "scenario": "baseline" | "optimistic" | "pessimistic" | "stress_test",
            "parameters": {
                "initial_supply": int,
                "initial_price": float,
                "staking_rate": float,
                "weekly_burn_rate": float,
                "weekly_mint_rate": float,
                "volatility": float,
                "weeks": int
            }
        }

    Returns:
        tuple: A tuple containing:
            - dict: SimulationResult serialized to JSON with keys:
                - simulation_id (str): Unique identifier for this simulation.
                - parameters (dict): Input parameters used.
                - scenario (str): Scenario type that was run.
                - weekly_metrics (list): Array of weekly data points.
                - summary (dict): Aggregate statistics and analysis.
            - int: HTTP status code 200 on success.

    Raises:
        ValueError: If the scenario string is not a valid SimulationScenario.
        ValidationError: If parameters fail pydantic validation.

    Examples:
        >>> request_data = {
        ...     'scenario': 'baseline',
        ...     'parameters': {
        ...         'initial_supply': 1000000,
        ...         'initial_price': 1.0,
        ...         'weeks': 52
        ...     }
        ... }
        >>> response = client.post('/api/v1/simulate', json=request_data)
        >>> result = response.json
        >>> result['scenario']
        'baseline'
        >>> len(result['weekly_metrics'])
        52

    Note:
        This endpoint creates a new asyncio event loop for each request to
        run the async simulation engine. The loop is properly closed after
        the simulation completes.

    Note:
        For long-running simulations, consider using the asynchronous
        endpoint `/api/v1/simulate/async` instead, which returns immediately
        with a simulation ID for polling.
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
    """Run a simulation asynchronously.

    Queues a token economy simulation for background processing and returns
    immediately with a simulation ID. This endpoint is ideal for long-running
    simulations or when you don't want to block the HTTP request.

    The simulation runs in a background thread pool with up to 4 concurrent
    workers. Results are stored in an in-memory cache with LRU eviction
    (max 1000 results). Use the returned simulation_id to poll for status
    and retrieve results.

    Request Body:
        {
            "scenario": "baseline" | "optimistic" | "pessimistic" | "stress_test",
            "parameters": {
                "initial_supply": int,
                "initial_price": float,
                "staking_rate": float,
                "weekly_burn_rate": float,
                "weekly_mint_rate": float,
                "volatility": float,
                "weeks": int
            },
            "webhook_url": "https://..."  # Optional: POST result when complete
        }

    Returns:
        tuple: A tuple containing:
            - dict: Response with keys:
                - simulation_id (str): Unique identifier for this simulation.
                - status (str): Always "queued" on successful submission.
                - message (str): Human-readable status message.
                - check_url (str): URL to poll for simulation status.
            - int: HTTP status code 202 (Accepted).

    Raises:
        ValueError: If the scenario string is not a valid SimulationScenario.
        ValidationError: If parameters fail pydantic validation.

    Examples:
        >>> request_data = {
        ...     'scenario': 'optimistic',
        ...     'parameters': {
        ...         'initial_supply': 1000000,
        ...         'initial_price': 1.0,
        ...         'weeks': 104
        ...     }
        ... }
        >>> response = client.post('/api/v1/simulate/async', json=request_data)
        >>> response.status_code
        202
        >>> data = response.json
        >>> data['status']
        'queued'
        >>> sim_id = data['simulation_id']

        # Poll for results
        >>> status = client.get(f'/api/v1/simulate/{sim_id}').json
        >>> status['status']
        'running'  # or 'complete', 'failed'

    Note:
        The webhook_url parameter is currently not implemented. The parameter
        is accepted and logged, but no webhook is actually sent when the
        simulation completes.

    Note:
        Simulation results are stored in memory and may be evicted if the
        cache exceeds 1000 entries. For long-term persistence, clients should
        retrieve and store results promptly after completion.
    """
    try:
        data = request.get_json()
        webhook_url = data.get('webhook_url')

        # Parse and validate input
        scenario_str = data.get('scenario', 'baseline')
        scenario = SimulationScenario(scenario_str)
        params_data = data.get('parameters', {})
        parameters = SimulationParameters(**params_data)

        # Generate unique simulation ID with UUID fragment to prevent collisions
        simulation_id = f"sim_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

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
    """Get the status and result of an async simulation.

    Retrieves the current status and, if available, the results of a
    previously submitted asynchronous simulation. Use this endpoint to
    poll for completion after submitting a simulation via the async endpoint.

    The status can be one of:
    - "queued": Simulation is waiting to start
    - "running": Simulation is currently executing
    - "complete": Simulation finished successfully (results included)
    - "failed": Simulation encountered an error (error message included)
    - "unknown": Simulation ID not found or expired

    Args:
        simulation_id: Unique simulation identifier returned from the
            `/api/v1/simulate/async` endpoint. Format: "sim_{timestamp}_{uuid}".

    Returns:
        tuple: A tuple containing:
            - dict: Response varies by status:
                - Complete: {'simulation_id': str, 'status': 'complete',
                             'result': dict}
                - Failed: {'simulation_id': str, 'status': 'failed',
                           'error': str}
                - Running: {'simulation_id': str, 'status': 'running',
                            'message': str}
                - Unknown: {'error': str}
            - int: HTTP status code (200, 202, 500, or 404).

    Raises:
        None: All error cases are returned as HTTP error responses.

    Examples:
        >>> # After submitting async simulation
        >>> sim_id = 'sim_20251231_120000_abc12345'
        >>> response = client.get(f'/api/v1/simulate/{sim_id}')
        >>> data = response.json

        >>> # Still running
        >>> if data['status'] == 'running':
        ...     response.status_code
        202

        >>> # Completed successfully
        >>> if data['status'] == 'complete':
        ...     result = data['result']
        ...     result['weekly_metrics'][0]['price']
        1.05

        >>> # Failed
        >>> if data['status'] == 'failed':
        ...     error = data['error']

    Note:
        Results are stored in an in-memory cache with LRU eviction (max 1000
        entries). Old simulation IDs may return 404 if they have been evicted.

    Note:
        For polling, implement exponential backoff (e.g., 1s, 2s, 4s, 8s...)
        to avoid overwhelming the service with frequent requests.
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
    """List available simulation scenarios.

    Returns a comprehensive list of all economic scenarios available for
    simulation, including their IDs, human-readable names, and detailed
    descriptions. Use this endpoint to discover valid scenario values before
    submitting simulation requests.

    Each scenario represents a distinct set of economic conditions and market
    dynamics that affect token price, supply, staking behavior, and other
    metrics throughout the simulation.

    Returns:
        tuple: A tuple containing:
            - dict: Response with key:
                - scenarios (list): Array of scenario objects, each containing:
                    - id (str): Scenario identifier for API requests.
                    - name (str): Human-readable scenario name.
                    - description (str): Detailed scenario description.
            - int: HTTP status code 200.

    Examples:
        >>> response = client.get('/api/v1/scenarios')
        >>> scenarios = response.json['scenarios']
        >>> scenarios[0]['id']
        'baseline'
        >>> scenarios[0]['name']
        'Baseline'
        >>> scenarios[0]['description']
        'Standard economic conditions with historical parameters'

        >>> # Use scenario ID in simulation request
        >>> client.post('/api/v1/simulate', json={
        ...     'scenario': scenarios[0]['id'],
        ...     'parameters': {...}
        ... })

    Note:
        Scenario IDs are case-sensitive and must match exactly as returned
        by this endpoint.
    """
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


def _get_scenario_description(scenario: SimulationScenario) -> str:
    """Get human-readable description for a scenario.

    Returns a detailed description of the economic conditions and market
    dynamics represented by a simulation scenario. Used by the scenarios
    list endpoint to provide context for each available scenario.

    Args:
        scenario: The scenario enum value to get a description for.
            Must be a member of the SimulationScenario enum.

    Returns:
        str: Human-readable description of the scenario's economic
            conditions and assumptions. Returns "Unknown scenario" if
            the scenario is not recognized.

    Examples:
        >>> _get_scenario_description(SimulationScenario.BASELINE)
        'Standard economic conditions with historical parameters'

        >>> _get_scenario_description(SimulationScenario.STRESS_TEST)
        'Extreme stress test with severe shocks'

        >>> # Used in scenario list endpoint
        >>> scenario = SimulationScenario.OPTIMISTIC
        >>> {
        ...     'id': scenario.value,
        ...     'description': _get_scenario_description(scenario)
        ... }
        {'id': 'optimistic', 'description': 'Growth-oriented scenario with favorable conditions'}

    Note:
        This is a private helper function used internally by the
        `/api/v1/scenarios` endpoint.
    """
    descriptions = {
        SimulationScenario.BASELINE: 'Standard economic conditions with historical parameters',
        SimulationScenario.OPTIMISTIC: 'Growth-oriented scenario with favorable conditions',
        SimulationScenario.PESSIMISTIC: 'Contraction scenario with stressed conditions',
        SimulationScenario.STRESS_TEST: 'Extreme stress test with severe shocks',
    }
    return descriptions.get(scenario, 'Unknown scenario')
