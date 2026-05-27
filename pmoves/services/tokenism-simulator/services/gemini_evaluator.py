import os
import json
import asyncio
import logging
from typing import Dict, Any

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class GeminiEvoSwarmEvaluator:
    """
    Integrates Gemini 1.5 Pro as the "EvoSwarm" fitness evaluator for economic simulations.
    Analyzes the geometric distribution on the Poincare disk (Dirichlet weights, Gini coefficient)
    and suggests optimization parameters.
    """
    def __init__(self, nc, config: Dict[str, Any]):
        self.nc = nc
        self.config = config
        self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.model = os.environ.get("GEMINI_MODEL", "gemini-1.5-pro")
        
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set. GeminiEvoSwarmEvaluator will not function.")
            self.client = None
        else:
            self.client = genai.Client(api_key=self.api_key)

    async def start(self):
        if not self.client:
            return
        
        # Subscribe to the weekly CGP geometry payload
        await self.nc.subscribe("tokenism.cgp.weekly.v1", cb=self.handle_weekly_cgp)
        logger.info(f"GeminiEvoSwarmEvaluator subscribed to tokenism.cgp.weekly.v1 using {self.model}")

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
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
        )
        
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("Failed to parse Gemini JSON response.")
            return {"error": "Invalid response from Gemini", "alpha_i": 1.0, "halfLife": 1.0, "reasoning": "Fallback"}
