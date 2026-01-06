"""
Persona Gate Service: Evaluate persona selections against metric thresholds.

This module provides threshold-based persona evaluation for the consciousness
taxonomy, ensuring that personas meet quality gates before publishing.
"""

import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import nats
from nats.aio.client import Client as NATS

logger = logging.getLogger(__name__)

# Configuration
NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "http://postgrest:3000")

# NATS subjects
PERSONA_REQUEST_SUBJECT = "persona.publish.request.v1"
PERSONA_RESULT_SUBJECT = "persona.publish.result.v1"


class PersonaGateService:
    """
    Evaluate persona selections against metrics thresholds.

    Subscribes to persona publish requests, evaluates against threshold gates,
    and publishes results to NATS.
    """

    def __init__(self):
        """Initialize the persona gate service."""
        self.nc: Optional[NATS] = None
        self.thresholds = {
            "min_empirical_support": 0.3,
            "min_philosophical_coherence": 0.4,
            "min_integration_potential": 0.3,
            "min_description_length": 50,
            "min_proponents": 1,
        }
        logger.info("PersonaGateService initialized")

    async def connect(self):
        """Connect to NATS message bus."""
        self.nc = await nats.connect(NATS_URL)
        logger.info(f"Connected to NATS at {NATS_URL}")

    async def close(self):
        """Close NATS connection."""
        if self.nc:
            await self.nc.drain()
            logger.info("NATS connection closed")

    async def subscribe(self):
        """Subscribe to persona publish request subject."""
        if not self.nc:
            await self.connect()

        await self.nc.subscribe(PERSONA_REQUEST_SUBJECT, cb=self._handle_request)
        logger.info(f"Subscribed to {PERSONA_REQUEST_SUBJECT}")

    async def _handle_request(self, msg):
        """Handle incoming persona publish request."""
        try:
            data = json.loads(msg.data.decode())
            persona_id = data.get("persona_id")
            metrics = data.get("metrics", {})

            logger.info(f"Received evaluation request for persona {persona_id}")

            result = await self.evaluate(persona_id, metrics)

            await self.nc.publish(
                PERSONA_RESULT_SUBJECT, json.dumps(result).encode()
            )
            logger.info(f"Published evaluation result for persona {persona_id}")

        except Exception as e:
            logger.error(f"Error handling persona request: {e}")

    async def evaluate(self, persona_id: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate persona against threshold gates.

        Args:
            persona_id: Unique identifier for the persona
            metrics: Dictionary of metrics to evaluate:
                - empirical_support: 0-1 scale
                - philosophical_coherence: 0-1 scale
                - integration_potential: 0-1 scale
                - description_length: int
                - proponent_count: int

        Returns:
            Evaluation result with pass/fail status and details
        """
        evaluations = []
        all_passed = True

        # Check empirical support
        empirical = metrics.get("empirical_support", 0)
        emp_passed = empirical >= self.thresholds["min_empirical_support"]
        evaluations.append({
            "gate": "empirical_support",
            "value": empirical,
            "threshold": self.thresholds["min_empirical_support"],
            "passed": emp_passed,
        })
        all_passed = all_passed and emp_passed

        # Check philosophical coherence
        coherence = metrics.get("philosophical_coherence", 0)
        coh_passed = coherence >= self.thresholds["min_philosophical_coherence"]
        evaluations.append({
            "gate": "philosophical_coherence",
            "value": coherence,
            "threshold": self.thresholds["min_philosophical_coherence"],
            "passed": coh_passed,
        })
        all_passed = all_passed and coh_passed

        # Check integration potential
        integration = metrics.get("integration_potential", 0)
        int_passed = integration >= self.thresholds["min_integration_potential"]
        evaluations.append({
            "gate": "integration_potential",
            "value": integration,
            "threshold": self.thresholds["min_integration_potential"],
            "passed": int_passed,
        })
        all_passed = all_passed and int_passed

        # Check description length
        desc_len = metrics.get("description_length", 0)
        desc_passed = desc_len >= self.thresholds["min_description_length"]
        evaluations.append({
            "gate": "description_length",
            "value": desc_len,
            "threshold": self.thresholds["min_description_length"],
            "passed": desc_passed,
        })
        all_passed = all_passed and desc_passed

        # Check proponent count
        proponents = metrics.get("proponent_count", 0)
        prop_passed = proponents >= self.thresholds["min_proponents"]
        evaluations.append({
            "gate": "proponent_count",
            "value": proponents,
            "threshold": self.thresholds["min_proponents"],
            "passed": prop_passed,
        })
        all_passed = all_passed and prop_passed

        result = {
            "persona_id": persona_id,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "passed": all_passed,
            "evaluations": evaluations,
            "summary": {
                "total_gates": len(evaluations),
                "passed_gates": sum(1 for e in evaluations if e["passed"]),
                "failed_gates": sum(1 for e in evaluations if not e["passed"]),
            },
        }

        logger.info(
            f"Persona {persona_id} evaluation: {'PASSED' if all_passed else 'FAILED'}"
        )
        return result

    def update_thresholds(self, new_thresholds: Dict[str, float]):
        """Update evaluation thresholds."""
        self.thresholds.update(new_thresholds)
        logger.info(f"Updated thresholds: {self.thresholds}")
