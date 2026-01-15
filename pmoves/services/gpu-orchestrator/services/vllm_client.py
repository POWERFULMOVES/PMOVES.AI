"""vLLM API client for model management."""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class VllmClient:
    """Client for interacting with vLLM server.

    Note: vLLM typically requires server restart for model changes,
    so dynamic loading/unloading is limited compared to Ollama.
    """

    def __init__(self, base_url: str = "http://pmoves-vllm:8000"):
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(30.0, connect=5.0)

    async def health_check(self) -> bool:
        """Check if vLLM is healthy."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except httpx.RequestError:
            return False

    async def list_models(self) -> List[Dict[str, Any]]:
        """List loaded models (vLLM only loads one model at a time)."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/v1/models")
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
        except httpx.RequestError as e:
            logger.error(f"Error listing vLLM models: {e}")
            return []  # Empty list indicates vLLM unavailable
        except (httpx.DecodeError, KeyError) as e:
            logger.warning(f"Error parsing vLLM models response: {e}")
            return []

    async def get_current_model(self) -> Optional[str]:
        """Get the currently loaded model name."""
        models = await self.list_models()
        if models:
            return models[0].get("id")
        return None

    async def get_model_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the loaded model."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Try metrics endpoint for detailed info
                response = await client.get(f"{self.base_url}/metrics")
                if response.status_code == 200:
                    return {"metrics": response.text}
        except httpx.RequestError as e:
            logger.debug(f"Could not get vLLM metrics: {e}")

        models = await self.list_models()
        if models:
            return models[0]
        return None

    async def is_model_loaded(self, model_name: str) -> bool:
        """Check if a specific model is loaded."""
        current = await self.get_current_model()
        return current == model_name if current else False

    # Note: vLLM doesn't support dynamic model loading/unloading
    # The following methods are placeholders that return appropriate values

    async def load_model(self, model_name: str) -> bool:
        """
        Load a model (not supported - requires server restart).

        Returns False as vLLM requires server configuration changes.
        """
        logger.warning(
            f"vLLM does not support dynamic model loading. "
            f"To load {model_name}, restart vLLM with the new model configured."
        )
        return False

    async def unload_model(self, model_name: str) -> bool:
        """
        Unload a model (not supported - requires server restart).

        Returns False as vLLM requires server stop.
        """
        logger.warning(
            "vLLM does not support dynamic model unloading. "
            "Stop the vLLM container to free GPU memory."
        )
        return False

    async def get_model_vram_usage(self) -> int:
        """
        Estimate VRAM usage for the loaded model.

        Returns estimated usage in MB or 0 if no model loaded.
        """
        model = await self.get_current_model()
        if not model:
            return 0

        # Parse Prometheus metrics if available
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/metrics")
                if response.status_code == 200:
                    # Look for gpu_cache_usage_perc or similar metrics
                    for line in response.text.split("\n"):
                        if "gpu_cache" in line.lower() and not line.startswith("#"):
                            # Try to parse cache usage
                            pass
        except httpx.RequestError:
            pass

        # Default estimate for vLLM models (16GB is common for 70B models)
        return 16384
