"""AgentGym-RL integration for EvoSwarm controller.

This module extends the EvoSwarm controller with methods to:
1. Detect when RL training should be triggered
2. Launch AgentGym-RL training jobs
3. Track population-based training metrics
4. Implement ScalingInter-RL progressive horizon scaling
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("evo-controller.agentgym")


class AgentGymIntegration:
    """Mixin class for EvoSwarm controller to coordinate AgentGym-RL training."""

    def __init__(self) -> None:
        self.coordinator_url = os.getenv(
            "AGENTGYM_COORDINATOR_URL",
            "http://agentgym-rl-coordinator:8114"
        )
        self.enable_training = os.getenv("AGENTGYM_ENABLE", "true").lower() == "true"

        # Training triggers
        self.trigger_on_plateau = os.getenv("AGENTGYM_TRIGGER_ON_PLATEAU", "true").lower() == "true"
        self.plateau_window = int(os.getenv("AGENTGYM_PLATEAU_WINDOW", "5"))
        self.trigger_on_new_constellation = os.getenv("AGENTGYM_TRIGGER_ON_NEW_CONSTELLATION", "true").lower() == "true"
        self.periodic_interval = int(os.getenv("AGENTGYM_PERIODIC_TRAINING_INTERVAL", "100"))

        # Training defaults
        self.default_algorithm = os.getenv("AGENTGYM_DEFAULT_ALGORITHM", "ppo")
        self.default_horizon = int(os.getenv("AGENTGYM_DEFAULT_HORIZON", "10"))
        self.default_epochs = int(os.getenv("AGENTGYM_DEFAULT_EPOCHS", "25"))
        self.default_batch_size = int(os.getenv("AGENTGYM_DEFAULT_BATCH_SIZE", "32"))
        self.default_lr = float(os.getenv("AGENTGYM_DEFAULT_LR", "1e-6"))
        self.default_kl_coef = float(os.getenv("AGENTGYM_DEFAULT_KL_COEF", "0.001"))

        # Reward weights
        self.task_success_weight = float(os.getenv("AGENTGYM_TASK_SUCCESS_WEIGHT", "0.4"))
        self.retrieval_quality_weight = float(os.getenv("AGENTGYM_RETRIEVAL_QUALITY_WEIGHT", "0.3"))
        self.cgp_fitness_weight = float(os.getenv("AGENTGYM_CGP_FITNESS_WEIGHT", "0.2"))
        self.efficiency_weight = float(os.getenv("AGENTGYM_EFFICIENCY_WEIGHT", "0.1"))

        # ScalingInter-RL progressive horizon
        horizon_schedule_str = os.getenv("AGENTGYM_HORIZON_SCHEDULE", "5,10,15")
        self.horizon_schedule = [int(h.strip()) for h in horizon_schedule_str.split(",")]

        threshold_str = os.getenv("AGENTGYM_HORIZON_EPOCH_THRESHOLDS", "0,10,20")
        self.horizon_epoch_thresholds = [int(t.strip()) for t in threshold_str.split(",")]

        # Training state tracking
        self._current_epoch = 0
        self._current_generation = 0
        self._fitness_history: List[float] = []
        self._last_training_epoch = 0
        self._known_constellations: set[str] = set()

        logger.info(
            "AgentGym integration initialized: enable=%s, coordinator=%s",
            self.enable_training,
            self.coordinator_url
        )

    async def evaluate_training_trigger(
        self,
        cgps: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Decide if RL training should start based on:

        1. Fitness plateau: No improvement in N generations
        2. New constellation: Novel geometry structure detected
        3. Scheduled interval: Periodic retraining every K epochs
        4. Fitness degradation: Performance dropped below threshold

        Returns:
            dict with:
                - should_train: bool
                - reason: str (if should_train)
                - config: dict (if should_train)
        """
        if not self.enable_training:
            return {"should_train": False}

        # Extract fitness scores from recent CGPs
        recent_fitness = []
        for cgp in cgps:
            meta = cgp.get("meta", {}) if isinstance(cgp, dict) else {}
            fitness = meta.get("fitness", 0.0)
            if isinstance(fitness, (int, float)):
                recent_fitness.append(float(fitness))

        avg_fitness = sum(recent_fitness) / len(recent_fitness) if recent_fitness else 0.0

        # Update fitness history
        self._fitness_history.append(avg_fitness)
        if len(self._fitness_history) > self.plateau_window * 2:
            self._fitness_history = self._fitness_history[-self.plateau_window * 2:]

        # Check 1: Fitness plateau
        if self.trigger_on_plateau and self._is_fitness_plateau(recent_fitness):
            logger.info("Detected fitness plateau, triggering AgentGym training")
            return {
                "should_train": True,
                "reason": "fitness_plateau",
                "config": {
                    "algorithm": "grpo",  # Exploration-focused for plateau
                    "horizon": self._get_current_horizon(),
                    "num_epochs": self.default_epochs,
                    "batch_size": self.default_batch_size,
                    "learning_rate": self.default_lr,
                    "kl_coef": self.default_kl_coef
                }
            }

        # Check 2: New constellations
        if self.trigger_on_new_constellation:
            new_constellations = self._detect_new_constellations(cgps)
            if new_constellations:
                logger.info(
                    "Detected new constellations: %s, triggering AgentGym training",
                    new_constellations
                )
                return {
                    "should_train": True,
                    "reason": "new_constellation",
                    "config": {
                        "algorithm": self.default_algorithm,
                        "horizon": min(self._get_current_horizon(), 10),  # Start with shorter horizon for new content
                        "num_epochs": 15,  # Fewer epochs for quick adaptation
                        "batch_size": self.default_batch_size,
                        "learning_rate": self.default_lr * 2,  # Higher LR for faster learning
                        "kl_coef": self.default_kl_coef,
                        "focus_namespace": new_constellations[0]["namespace"]
                    }
                }

        # Check 3: Scheduled periodic training
        if self._should_periodic_train():
            logger.info("Periodic training interval reached, triggering AgentGym training")
            return {
                "should_train": True,
                "reason": "scheduled",
                "config": {
                    "algorithm": self.default_algorithm,
                    "horizon": self._get_current_horizon(),
                    "num_epochs": self.default_epochs,
                    "batch_size": self.default_batch_size,
                    "learning_rate": self.default_lr,
                    "kl_coef": self.default_kl_coef
                }
            }

        # Check 4: Fitness degradation
        if len(self._fitness_history) >= self.plateau_window * 2:
            old_avg = sum(self._fitness_history[:self.plateau_window]) / self.plateau_window
            new_avg = sum(self._fitness_history[-self.plateau_window:]) / self.plateau_window

            if new_avg < old_avg * 0.9:  # 10% degradation
                logger.warning(
                    "Fitness degraded from %.3f to %.3f, triggering AgentGym training",
                    old_avg,
                    new_avg
                )
                return {
                    "should_train": True,
                    "reason": "fitness_degradation",
                    "config": {
                        "algorithm": self.default_algorithm,
                        "horizon": self._get_current_horizon(),
                        "num_epochs": self.default_epochs,
                        "batch_size": self.default_batch_size,
                        "learning_rate": self.default_lr,
                        "kl_coef": self.default_kl_coef
                    }
                }

        return {"should_train": False}

    def _is_fitness_plateau(self, recent_fitness: List[float]) -> bool:
        """
        Detect if fitness has plateaued (no improvement in last N evals).

        Plateau criteria:
        - Low variance (< 0.01)
        - No upward trend
        - At least window size samples
        """
        if len(recent_fitness) < self.plateau_window:
            return False

        window = recent_fitness[-self.plateau_window:]
        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)

        # Check variance
        if variance >= 0.01:
            return False

        # Check trend (is latest value significantly better than first?)
        improvement = (window[-1] - window[0]) / max(window[0], 1e-6)

        # Plateau if variance low AND no improvement
        return improvement < 0.02  # Less than 2% improvement

    def _detect_new_constellations(
        self,
        cgps: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        Detect if any CGPs contain new constellation IDs not seen before.

        Returns:
            List of dicts with {constellation_id, namespace}
        """
        new_constellations = []

        for cgp in cgps:
            if not isinstance(cgp, dict):
                continue

            geometry = cgp.get("geometry", {})
            if not isinstance(geometry, dict):
                continue

            constellation = geometry.get("constellation", {})
            if not isinstance(constellation, dict):
                continue

            constellation_id = constellation.get("id")
            namespace = cgp.get("namespace", "default")

            if constellation_id and constellation_id not in self._known_constellations:
                self._known_constellations.add(constellation_id)
                new_constellations.append({
                    "constellation_id": constellation_id,
                    "namespace": namespace
                })
                logger.info("New constellation detected: %s (namespace: %s)", constellation_id, namespace)

        return new_constellations

    def _should_periodic_train(self) -> bool:
        """
        Check if periodic training interval has been reached.
        """
        epochs_since_training = self._current_epoch - self._last_training_epoch
        return epochs_since_training >= self.periodic_interval

    def _get_current_horizon(self) -> int:
        """
        Get current horizon for ScalingInter-RL progressive scaling.

        Horizon schedule example:
        - Epochs 0-10: horizon=5
        - Epochs 11-20: horizon=10
        - Epochs 21+: horizon=15

        Configured via:
        - AGENTGYM_HORIZON_SCHEDULE=5,10,15
        - AGENTGYM_HORIZON_EPOCH_THRESHOLDS=0,10,20
        """
        epoch = self._current_epoch

        for i, threshold in enumerate(self.horizon_epoch_thresholds):
            if epoch < threshold:
                # Use previous horizon
                return self.horizon_schedule[max(0, i - 1)]

        # Use last horizon in schedule
        return self.horizon_schedule[-1]

    async def launch_agentgym_training(
        self,
        decision: Dict[str, Any],
        parameter_pack: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Launch AgentGym-RL training via coordinator API.

        Args:
            decision: Training decision from evaluate_training_trigger()
            parameter_pack: Latest geometry parameter pack (optional)

        Returns:
            Training run result dict, or None if launch failed
        """
        if not decision.get("should_train"):
            return None

        base_model = os.getenv("AGENTGYM_BASE_MODEL", "Qwen2.5-7B-Instruct")
        env_namespace = os.getenv("AGENTGYM_ENV_NAMESPACE", "pmoves.consciousness")

        # Build training request
        training_request = {
            "environment": "pmoves-hirag",
            "base_model": base_model,
            "population_id": f"pop-{self._current_generation}",
            "training_config": decision["config"],
            "geometry_config": {
                "cgp_fitness_weight": self.cgp_fitness_weight,
                "retrieval_quality_weight": self.retrieval_quality_weight,
                "task_success_weight": self.task_success_weight,
                "efficiency_weight": self.efficiency_weight,
                "parameter_pack_id": parameter_pack.get("pack_id") if parameter_pack else None,
                "namespace": decision["config"].get("focus_namespace", env_namespace)
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.coordinator_url}/agentgym/train/start",
                    json=training_request
                )
                resp.raise_for_status()
                result = resp.json()

                logger.info(
                    "Launched AgentGym training run: %s (reason: %s, horizon: %d, epochs: %d)",
                    result["training_run_id"],
                    decision["reason"],
                    decision["config"]["horizon"],
                    decision["config"]["num_epochs"]
                )

                # Update state
                self._last_training_epoch = self._current_epoch
                self._current_generation += 1

                return result

        except httpx.HTTPStatusError as exc:
            logger.error(
                "Failed to launch AgentGym training: HTTP %d - %s",
                exc.response.status_code,
                exc.response.text
            )
            return None
        except Exception as e:
            logger.error("Failed to launch AgentGym training: %s", e, exc_info=True)
            return None

    async def publish_training_event(
        self,
        training_result: Dict[str, Any],
        decision: Dict[str, Any]
    ) -> None:
        """
        Publish training event to NATS: agentgym.train.started.v1

        Args:
            training_result: Response from coordinator /train/start endpoint
            decision: Training decision that triggered launch
        """
        base = os.getenv("AGENT_ZERO_BASE_URL") or os.getenv("AGENTZERO_BASE_URL") or "http://agent-zero:8080"
        url = f"{base.rstrip('/')}/events/publish"

        body = {
            "topic": "agentgym.train.started.v1",
            "source": "evo-controller",
            "payload": {
                "training_run_id": training_result.get("training_run_id"),
                "environment": training_result.get("environment", "pmoves-hirag"),
                "trigger_reason": decision.get("reason"),
                "population_id": training_result.get("population_id"),
                "algorithm": decision["config"].get("algorithm"),
                "horizon": decision["config"].get("horizon"),
                "num_epochs": decision["config"].get("num_epochs"),
                "learning_rate": decision["config"].get("learning_rate"),
                "geometry_config": {
                    "cgp_fitness_weight": self.cgp_fitness_weight,
                    "retrieval_quality_weight": self.retrieval_quality_weight,
                    "task_success_weight": self.task_success_weight
                },
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(url, json=body)
                r.raise_for_status()
                logger.debug("Published agentgym.train.started.v1 event")
        except Exception as e:
            logger.warning(
                "Failed to publish agentgym.train.started.v1: %s (agent-zero not reachable?)",
                e
            )

    def increment_epoch(self) -> None:
        """
        Increment current epoch counter (for ScalingInter-RL scheduling).

        Call this at the end of each EvoSwarm evolution cycle.
        """
        self._current_epoch += 1
        logger.debug(
            "EvoSwarm epoch incremented: %d (horizon: %d, generation: %d)",
            self._current_epoch,
            self._get_current_horizon(),
            self._current_generation
        )

    def get_training_status(self) -> Dict[str, Any]:
        """
        Return current AgentGym training status for observability.

        Exposed via /config or /swarm/status endpoint.
        """
        return {
            "enabled": self.enable_training,
            "current_epoch": self._current_epoch,
            "current_generation": self._current_generation,
            "current_horizon": self._get_current_horizon(),
            "last_training_epoch": self._last_training_epoch,
            "epochs_since_training": self._current_epoch - self._last_training_epoch,
            "known_constellations": len(self._known_constellations),
            "fitness_history_size": len(self._fitness_history),
            "avg_recent_fitness": (
                sum(self._fitness_history[-self.plateau_window:]) / self.plateau_window
                if len(self._fitness_history) >= self.plateau_window
                else 0.0
            ),
            "triggers": {
                "plateau": self.trigger_on_plateau,
                "new_constellation": self.trigger_on_new_constellation,
                "periodic_interval": self.periodic_interval
            },
            "reward_weights": {
                "task_success": self.task_success_weight,
                "retrieval_quality": self.retrieval_quality_weight,
                "cgp_fitness": self.cgp_fitness_weight,
                "efficiency": self.efficiency_weight
            }
        }
