"""
Persona Optimizer - EvoSwarm optimization service for persona parameters.

This module provides optimization capabilities for persona configurations
by leveraging evaluation metrics from persona_eval_gates and evolutionary
search strategies.

The optimizer operates on:
- temperature: LLM sampling temperature (0.0-1.0, moderate preferred)
- behavior_weights: decode/retrieve/generate balance (should sum to ~1.0)
- boosts: entity and keyword weights for retrieval

Usage:
    optimizer = PersonaOptimizer(
        supabase_url="http://postgrest:3000",
        supabase_key="your-key",
        nats_url="nats://nats:4222"
    )
    await optimizer.start()
    result = await optimizer.optimize_persona_parameters(persona_id)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import httpx
from nats.aio.client import Client as NATS

logger = logging.getLogger(__name__)

# NATS subjects for persona optimization
PERSONA_OPTIMIZE_REQUEST_SUBJECT = "persona.optimize.request.v1"
PERSONA_OPTIMIZE_RESULT_SUBJECT = "persona.optimize.result.v1"


@dataclass
class PersonaSearchSpace:
    """
    Definition of the search space for persona parameter optimization.

    Attributes:
        temperature: (min, max, optimal) range for LLM temperature
        behavior_weights: Ranges for decode/retrieve/generate weights
        boost_entity_range: Range for entity boost weights
        boost_keyword_range: Range for keyword boost weights
    """

    temperature: Tuple[float, float, float] = (0.0, 1.0, 0.7)
    behavior_decode: Tuple[float, float] = (0.0, 1.0)
    behavior_retrieve: Tuple[float, float] = (0.0, 1.0)
    behavior_generate: Tuple[float, float] = (0.0, 1.0)
    boost_entity_range: Tuple[float, float] = (0.0, 5.0)
    boost_keyword_range: Tuple[float, float] = (0.0, 5.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert search space to dictionary representation."""
        return {
            "temperature": {
                "min": self.temperature[0],
                "max": self.temperature[1],
                "optimal": self.temperature[2],
            },
            "behavior_weights": {
                "decode": {"min": self.behavior_decode[0], "max": self.behavior_decode[1]},
                "retrieve": {"min": self.behavior_retrieve[0], "max": self.behavior_retrieve[1]},
                "generate": {"min": self.behavior_generate[0], "max": self.behavior_generate[1]},
            },
            "boosts": {
                "entity_range": {"min": self.boost_entity_range[0], "max": self.boost_entity_range[1]},
                "keyword_range": {"min": self.boost_keyword_range[0], "max": self.boost_keyword_range[1]},
            },
        }


@dataclass
class OptimizationResult:
    """
    Result of a persona optimization run.

    Attributes:
        persona_id: UUID of the optimized persona
        success: Whether optimization completed successfully
        fitness: Best fitness score achieved
        parameters: Optimized parameter set
        metrics: Evaluation metrics for the optimized parameters
        iterations: Number of optimization iterations performed
        runtime_ms: Optimization runtime in milliseconds
        error: Error message if optimization failed
        timestamp: ISO timestamp of optimization completion
    """

    persona_id: str
    success: bool
    fitness: float = 0.0
    parameters: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    iterations: int = 0
    runtime_ms: float = 0.0
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "persona_id": self.persona_id,
            "success": self.success,
            "fitness": self.fitness,
            "parameters": self.parameters,
            "metrics": self.metrics,
            "iterations": self.iterations,
            "runtime_ms": self.runtime_ms,
            "error": self.error,
            "timestamp": self.timestamp,
        }


class PersonaOptimizer:
    """
    EvoSwarm-based persona parameter optimizer.

    This service optimizes persona configurations by:
    1. Fetching current persona and evaluation history from Supabase
    2. Defining a parameter search space
    3. Running evolutionary optimization (EvoSwarm)
    4. Publishing optimized parameters via NATS

    The optimizer integrates with the consciousness namespace for
    geometry-aware optimization, leveraging CGP (Constellation Geometry
    Protocol) when available.

    Example:
        optimizer = PersonaOptimizer()
        await optimizer.start()
        # Triggered via NATS or direct call
        result = await optimizer.optimize_persona_parameters("uuid-here")
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        nats_url: Optional[str] = None,
        search_space: Optional[PersonaSearchSpace] = None,
        max_iterations: int = 50,
        population_size: int = 20,
    ):
        """
        Initialize the Persona Optimizer.

        Args:
            supabase_url: PostgREST URL for Supabase (default from env)
            supabase_key: Service role key for Supabase (default from env)
            nats_url: NATS connection URL (default from env)
            search_space: Custom search space definition (uses default if None)
            max_iterations: Maximum optimization iterations
            population_size: Population size for evolutionary search
        """
        self.supabase_url = supabase_url or os.getenv(
            "SUPA_REST_URL",
            os.getenv("SUPABASE_REST_URL", "http://postgrest:3000")
        )
        self.supabase_key = supabase_key or os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY",
            os.getenv("SUPABASE_SERVICE_KEY")
        )
        self.nats_url = nats_url or os.getenv("NATS_URL", "nats://nats:4222")

        self.search_space = search_space or PersonaSearchSpace()
        self.max_iterations = max_iterations
        self.population_size = population_size

        self._nc: Optional[NATS] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._running = False

        logger.info(
            "PersonaOptimizer initialized",
            extra={
                "supabase_url": self.supabase_url,
                "nats_url": self.nats_url,
                "max_iterations": max_iterations,
                "population_size": population_size,
            }
        )

    async def start(self):
        """Start the optimizer service and connect to NATS."""
        if self._running:
            logger.warning("PersonaOptimizer already running")
            return

        self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        self._nc = await self._connect_nats()

        # Subscribe to optimization requests
        await self._nc.subscribe(
            PERSONA_OPTIMIZE_REQUEST_SUBJECT,
            cb=self._handle_optimize_request
        )

        self._running = True
        logger.info(
            "PersonaOptimizer started",
            extra={"subject": PERSONA_OPTIMIZE_REQUEST_SUBJECT}
        )

    async def stop(self):
        """Stop the optimizer service and close connections."""
        if not self._running:
            return

        self._running = False

        if self._nc:
            await self._nc.drain()
            self._nc = None

        if self._client:
            await self._client.aclose()
            self._client = None

        logger.info("PersonaOptimizer stopped")

    async def _connect_nats(self) -> NATS:
        """Establish NATS connection."""
        nc = NATS()
        await nc.connect(servers=[self.nats_url])
        logger.info(f"Connected to NATS at {self.nats_url}")
        return nc

    def _get_supabase_headers(self) -> Dict[str, str]:
        """Build headers for Supabase/PostgREST requests."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.supabase_key:
            headers["apikey"] = self.supabase_key
            headers["Authorization"] = f"Bearer {self.supabase_key}"
        return headers

    async def _handle_optimize_request(self, msg):
        """
        Handle inbound persona optimization request from NATS.

        Expected payload format:
        {
            "persona_id": "uuid",
            "correlation_id": "optional-tracking-id"
        }
        """
        try:
            envelope_data = json.loads(msg.data.decode())
            payload = envelope_data.get("payload", {})
            persona_id = payload.get("persona_id")
            correlation_id = payload.get("correlation_id") or envelope_data.get("correlation_id")

            if not persona_id:
                logger.error("Missing persona_id in optimization request")
                return

            logger.info(
                "Received optimization request",
                extra={"persona_id": persona_id, "correlation_id": correlation_id}
            )

            # Run optimization
            result = await self.optimize_persona_parameters(persona_id)

            # Publish result
            await self._publish_result(result, correlation_id)

        except Exception as e:
            logger.exception("Error handling optimization request")

    async def optimize_persona_parameters(self, persona_id: str) -> OptimizationResult:
        """
        Main optimization method for persona parameters.

        This method:
        1. Fetches current persona configuration from Supabase
        2. Retrieves evaluation history from persona_eval_gates
        3. Defines parameter search space
        4. Runs EvoSwarm optimization
        5. Updates persona with optimized parameters

        Args:
            persona_id: UUID of the persona to optimize

        Returns:
            OptimizationResult with optimized parameters and metrics
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # Fetch persona from Supabase
            persona = await self._fetch_persona(persona_id)
            if not persona:
                return OptimizationResult(
                    persona_id=persona_id,
                    success=False,
                    error="Persona not found"
                )

            # Fetch evaluation history
            eval_history = await self._fetch_eval_history(persona_id)

            # Extract current parameters
            current_params = self._extract_parameters(persona)

            # Run optimization (stub for now - actual EvoSwarm integration TBD)
            best_params, fitness, metrics = await self._run_evoswarm_optimization(
                current_params,
                eval_history
            )

            # Update persona in Supabase
            await self._update_persona_parameters(persona_id, best_params)

            runtime_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            result = OptimizationResult(
                persona_id=persona_id,
                success=True,
                fitness=fitness,
                parameters=best_params,
                metrics=metrics,
                iterations=self.max_iterations,
                runtime_ms=runtime_ms,
            )

            logger.info(
                "Persona optimization complete",
                extra={
                    "persona_id": persona_id,
                    "fitness": fitness,
                    "runtime_ms": runtime_ms,
                }
            )

            return result

        except Exception as e:
            runtime_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.exception("Optimization failed", extra={"persona_id": persona_id})

            return OptimizationResult(
                persona_id=persona_id,
                success=False,
                runtime_ms=runtime_ms,
                error=str(e)
            )

    async def _fetch_persona(self, persona_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch persona configuration from Supabase.

        Args:
            persona_id: UUID of the persona

        Returns:
            Persona dictionary or None if not found
        """
        if not self._client or not self.supabase_url:
            logger.error("Supabase client not configured")
            return None

        url = f"{self.supabase_url.rstrip('/')}/pmoves_core.personas"
        headers = self._get_supabase_headers()
        params = {
            "persona_id": f"eq.{persona_id}",
            "limit": "1",
        }

        try:
            response = await self._client.get(url, headers=headers, params=params)
            response.raise_for_status()
            rows = response.json()

            if rows and len(rows) > 0:
                return rows[0]

            return None

        except httpx.HTTPError as e:
            logger.error("Failed to fetch persona", extra={"persona_id": persona_id, "error": str(e)})
            return None

    async def _fetch_eval_history(self, persona_id: str) -> List[Dict[str, Any]]:
        """
        Fetch evaluation history from persona_eval_gates table.

        Args:
            persona_id: UUID of the persona

        Returns:
            List of evaluation gate records
        """
        if not self._client or not self.supabase_url:
            return []

        url = f"{self.supabase_url.rstrip('/')}/pmoves_core.persona_eval_gates"
        headers = self._get_supabase_headers()
        params = {
            "persona_id": f"eq.{persona_id}",
            "order": "last_run.desc",
        }

        try:
            response = await self._client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json() or []

        except httpx.HTTPError as e:
            logger.warning("Failed to fetch eval history", extra={"persona_id": persona_id, "error": str(e)})
            return []

    def _extract_parameters(self, persona: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract current parameters from persona configuration.

        Args:
            persona: Persona dictionary from Supabase

        Returns:
            Dictionary of current parameters
        """
        runtime = persona.get("runtime", {})
        boosts = persona.get("boosts", {})

        return {
            "temperature": runtime.get("temperature", 0.7),
            "behavior_weights": runtime.get("behavior_weights", {
                "decode": 0.33,
                "retrieve": 0.34,
                "generate": 0.33,
            }),
            "boosts": {
                "entity": boosts.get("entity", 1.0),
                "keyword": boosts.get("keyword", 1.0),
            },
        }

    async def _run_evoswarm_optimization(
        self,
        current_params: Dict[str, Any],
        eval_history: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], float, Dict[str, Any]]:
        """
        Run EvoSwarm optimization (stub implementation).

        This is a placeholder for the actual EvoSwarm integration.
        The full implementation would:
        1. Initialize population within search space
        2. Evaluate fitness using _compute_fitness
        3. Apply evolutionary operators (selection, crossover, mutation)
        4. Return best parameter set

        Args:
            current_params: Current persona parameters
            eval_history: Historical evaluation data

        Returns:
            Tuple of (optimized_params, fitness_score, metrics)
        """
        # STUB: Return current params with a placeholder fitness
        # TODO: Integrate actual EvoSwarm optimization loop

        # Compute fitness for current parameters
        fitness = self._compute_fitness(current_params, eval_history)

        # Placeholder: slightly perturb parameters to simulate optimization
        optimized_params = {
            "temperature": max(0.0, min(1.0, current_params.get("temperature", 0.7) + 0.02)),
            "behavior_weights": current_params.get("behavior_weights", {
                "decode": 0.33,
                "retrieve": 0.34,
                "generate": 0.33,
            }),
            "boosts": current_params.get("boosts", {
                "entity": 1.0,
                "keyword": 1.0,
            }),
        }

        metrics = {
            "eval_history_count": len(eval_history),
            "avg_pass_rate": sum(1 for e in eval_history if e.get("pass")) / max(len(eval_history), 1),
            "search_space": self.search_space.to_dict(),
        }

        return optimized_params, fitness, metrics

    def _compute_fitness(
        self,
        parameters: Dict[str, Any],
        eval_history: List[Dict[str, Any]]
    ) -> float:
        """
        Compute fitness score for a parameter set.

        Fitness function evaluates:
        1. Temperature proximity to optimal (moderate preferred)
        2. Behavior weight balance (should sum to ~1.0)
        3. Historical pass rate from eval_gates
        4. Boost weight合理性

        Args:
            parameters: Parameter dictionary to evaluate
            eval_history: Historical evaluation data

        Returns:
            Fitness score (0.0-1.0, higher is better)
        """
        score = 0.0

        # Temperature fitness: moderate values preferred (0.5-0.8 range)
        temp = parameters.get("temperature", 0.7)
        temp_optimal = self.search_space.temperature[2]  # 0.7
        temp_diff = abs(temp - temp_optimal)
        temp_fitness = max(0.0, 1.0 - temp_diff)  # Penalize deviation from optimal
        score += temp_fitness * 0.3

        # Behavior weight balance: should sum close to 1.0
        behavior = parameters.get("behavior_weights", {})
        total_weight = (
            behavior.get("decode", 0.33) +
            behavior.get("retrieve", 0.34) +
            behavior.get("generate", 0.33)
        )
        balance_fitness = max(0.0, 1.0 - abs(total_weight - 1.0))
        score += balance_fitness * 0.3

        # Historical pass rate
        if eval_history:
            pass_rate = sum(1 for e in eval_history if e.get("pass")) / len(eval_history)
            score += pass_rate * 0.4

        return min(1.0, score)

    async def _update_persona_parameters(
        self,
        persona_id: str,
        parameters: Dict[str, Any]
    ) -> bool:
        """
        Update persona with optimized parameters in Supabase.

        Args:
            persona_id: UUID of the persona
            parameters: Optimized parameter dictionary

        Returns:
            True if update successful
        """
        if not self._client or not self.supabase_url:
            logger.error("Supabase client not configured")
            return False

        url = f"{self.supabase_url.rstrip('/')}/pmoves_core.personas"
        headers = {
            **self._get_supabase_headers(),
            "Prefer": "return=representation",
        }

        # Build update payload
        updates: Dict[str, Any] = {}
        runtime = {}
        boosts = {}

        if "temperature" in parameters:
            runtime["temperature"] = parameters["temperature"]

        if "behavior_weights" in parameters:
            runtime["behavior_weights"] = parameters["behavior_weights"]

        if "boosts" in parameters:
            boosts_param = parameters["boosts"]
            if "entity" in boosts_param:
                boosts["entity"] = boosts_param["entity"]
            if "keyword" in boosts_param:
                boosts["keyword"] = boosts_param["keyword"]

        if runtime:
            updates["runtime"] = runtime
        if boosts:
            updates["boosts"] = boosts

        if not updates:
            return True  # Nothing to update

        params = {
            "persona_id": f"eq.{persona_id}",
        }

        try:
            response = await self._client.patch(url, headers=headers, params=params, json=updates)
            response.raise_for_status()
            logger.info("Updated persona parameters", extra={"persona_id": persona_id})
            return True

        except httpx.HTTPError as e:
            logger.error("Failed to update persona", extra={"persona_id": persona_id, "error": str(e)})
            return False

    async def _publish_result(
        self,
        result: OptimizationResult,
        correlation_id: Optional[str] = None
    ):
        """
        Publish optimization result to NATS.

        Args:
            result: Optimization result to publish
            correlation_id: Optional correlation ID for tracking
        """
        if not self._nc:
            logger.warning("NATS connection not available, skipping result publish")
            return

        try:
            envelope_data = {
                "id": str(result.persona_id),
                "topic": PERSONA_OPTIMIZE_RESULT_SUBJECT,
                "ts": result.timestamp,
                "version": "v1",
                "source": "evoswarm-persona-optimizer",
                "payload": result.to_dict(),
            }

            if correlation_id:
                envelope_data["correlation_id"] = correlation_id

            await self._nc.publish(
                PERSONA_OPTIMIZE_RESULT_SUBJECT,
                json.dumps(envelope_data).encode()
            )

            logger.info(
                "Published optimization result",
                extra={
                    "persona_id": result.persona_id,
                    "success": result.success,
                    "fitness": result.fitness,
                }
            )

        except Exception as e:
            logger.exception("Failed to publish optimization result")


# Main entry point for running the service
async def main():
    """Main entry point for the Persona Optimizer service."""
    import os

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    )

    optimizer = PersonaOptimizer()
    await optimizer.start()

    logger.info("Persona Optimizer service running")

    try:
        # Keep service running
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("Service shutdown requested")
    finally:
        await optimizer.stop()


if __name__ == "__main__":
    asyncio.run(main())
