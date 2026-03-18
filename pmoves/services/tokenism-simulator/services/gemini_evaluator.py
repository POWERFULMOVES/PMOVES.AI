import os
import json
import asyncio
import logging
from typing import Dict, Any

import requests

logger = logging.getLogger(__name__)

class GeminiEvoSwarmEvaluator:
    """
    Integrates Gemini 1.5 Pro as the "EvoSwarm" fitness evaluator for economic simulations.
    Routes through TensorZero gateway for centralized observability.
    Analyzes the geometric distribution on the Poincare disk (Dirichlet weights, Gini coefficient)
    and suggests optimization parameters.
    """
    def __init__(self, nc, config: Dict[str, Any]):
        self.nc = nc
        self.config = config
        self.tensorzero_url = os.environ.get("TENSORZERO_URL", "http://localhost:3030")
        self.model = os.environ.get("GEMINI_MODEL", "chat_gemini_pro")
        self.enabled = True

    async def start(self):
        if not self.enabled:
            return
        
        # Subscribe to the weekly CGP geometry payload
        await self.nc.subscribe("tokenism.cgp.ready.v1", cb=self.handle_weekly_cgp)
        logger.info(f"GeminiEvoSwarmEvaluator subscribed to tokenism.cgp.ready.v1 using {self.model}")

    async def handle_weekly_cgp(self, msg):
        try:
            payload = json.loads(msg.data.decode())
            logger.info("Received weekly CGP for Gemini evaluation.")
            
            # Analyze using Gemini in a background thread to avoid blocking the NATS loop
            recommendations = await asyncio.to_thread(self._evaluate_cgp, payload)
            
            # Publish recommendations back to the swarm population
            await self.nc.publish(
                "tokenism.swarm.population.v1",
                json.dumps(recommendations).encode()
            )
            logger.info("Published Gemini swarm optimization recommendations.")
            
        except Exception as e:
            logger.error(f"Error in Gemini evaluator: {e}")

    def _evaluate_cgp(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            "You are the PMOVES.AI EvoSwarm Evaluator. Analyze the following weekly Compressed "
            "Geometry Payload (CGP) from the PMOVES-ToKenism simulation.\n\n"
            "Evaluate the geometric distribution on the Poincare disk, considering the Dirichlet weights, "
            "the Gini coefficient, and the Poverty Rate.\n\n"
            "Suggest optimization parameters for 'alpha_i' (smoothing) and 'halfLife' (temporal decay) "
            "to better target the cooperative Gini target (< 0.4).\n\n"
            f"Payload:\n{json.dumps(payload, indent=2)}\n\n"
            "Return a JSON object containing the suggested 'alpha_i' float, 'halfLife' float, and a 'reasoning' string."
        )

        body = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "user", "content": prompt}
            ],
        }
        try:
            r = requests.post(
                f"{self.tensorzero_url.rstrip('/')}/openai/v1/chat/completions",
                json=body,
                timeout=120,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError) as e:
            logger.error("Failed to evaluate CGP via TensorZero: %s", e)
            return {"error": str(e), "alpha_i": 1.0, "halfLife": 1.0, "reasoning": "Fallback"}
