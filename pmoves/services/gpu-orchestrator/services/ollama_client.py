"""Ollama API client for model management."""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for interacting with Ollama API for model lifecycle management."""

    def __init__(self, base_url: str = "http://pmoves-ollama:11434"):
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(30.0, connect=5.0)

    async def health_check(self) -> bool:
        """Check if Ollama is healthy."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/version")
                return response.status_code == 200
        except httpx.RequestError:
            return False

    async def list_models(self) -> List[Dict[str, Any]]:
        """List all available models."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return data.get("models", [])
        except httpx.RequestError as e:
            logger.error(f"Error listing Ollama models: {e}")
            return []  # Empty list indicates Ollama unavailable
        except (httpx.DecodeError, KeyError) as e:
            logger.warning(f"Error parsing Ollama models response: {e}")
            return []

    async def list_running_models(self) -> List[Dict[str, Any]]:
        """List currently running/loaded models (Ollama 0.5+)."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/ps")
                if response.status_code == 200:
                    data = response.json()
                    return data.get("models", [])
        except httpx.RequestError as e:
            logger.error(f"Error listing running models: {e}")
        return []

    async def load_model(self, model_name: str, keep_alive: int = -1) -> bool:
        """
        Load a model into memory.

        Args:
            model_name: Name of the model to load
            keep_alive: How long to keep model loaded (-1 = indefinitely)

        Returns:
            True if model was loaded successfully
        """
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
                # Use generate endpoint with empty prompt to load model
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": "",  # Empty prompt just loads the model
                        "keep_alive": keep_alive,
                    },
                )
                if response.status_code == 200:
                    logger.info(f"Loaded model {model_name}")
                    return True
                else:
                    logger.error(f"Failed to load model {model_name}: {response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Error loading model {model_name}: {e}")
        return False

    async def unload_model(self, model_name: str) -> bool:
        """
        Unload a model from memory.

        Uses keep_alive=0 to immediately unload the model.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": "",
                        "keep_alive": 0,  # 0 = unload immediately
                    },
                )
                if response.status_code == 200:
                    logger.info(f"Unloaded model {model_name}")
                    return True
                else:
                    logger.error(f"Failed to unload model {model_name}: {response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Error unloading model {model_name}: {e}")
        return False

    async def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a model."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/show",
                    json={"name": model_name},
                )
                if response.status_code == 200:
                    return response.json()
        except httpx.RequestError as e:
            logger.error(f"Error getting model info for {model_name}: {e}")
        return None

    async def get_running_model_vram(self) -> Dict[str, int]:
        """Get VRAM usage per running model."""
        result = {}
        running_models = await self.list_running_models()
        for model in running_models:
            name = model.get("name", "")
            # Ollama reports size_vram in bytes
            vram_bytes = model.get("size_vram", 0)
            result[name] = vram_bytes // (1024 * 1024)  # Convert to MB
        return result

    async def touch_model(self, model_name: str) -> bool:
        """
        Touch a model to reset its keep_alive timer.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": "",
                        "keep_alive": -1,  # Keep indefinitely
                    },
                )
                return response.status_code == 200
        except httpx.RequestError:
            return False
