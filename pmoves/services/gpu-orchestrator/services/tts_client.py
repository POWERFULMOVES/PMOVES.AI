"""Ultimate TTS Studio client for TTS engine management."""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class TtsClient:
    """Client for interacting with Ultimate TTS Studio (Gradio-based).

    Ultimate TTS Studio loads multiple TTS engines. This client
    provides visibility into which engines are loaded but cannot
    dynamically unload individual engines.
    """

    def __init__(self, base_url: str = "http://ultimate-tts-studio:7861"):
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(30.0, connect=5.0)

        # Known TTS engines and their estimated VRAM usage
        self.engine_vram_estimates = {
            "kokoro": 2048,
            "f5-tts": 3072,
            "voxcpm": 2560,
            "kitten-tts": 1536,
            "melo-tts": 1024,
            "gtts": 0,  # Uses Google API, no local GPU
            "piper": 512,
        }

    async def health_check(self) -> bool:
        """Check if Ultimate TTS Studio is healthy."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/gradio_api/info")
                return response.status_code == 200
        except httpx.RequestError:
            return False

    async def get_info(self) -> Optional[Dict[str, Any]]:
        """Get Gradio API info including available endpoints."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/gradio_api/info")
                if response.status_code == 200:
                    return response.json()
        except httpx.RequestError as e:
            logger.error(f"Error getting TTS info: {e}")
        return None

    async def list_engines(self) -> List[str]:
        """
        List available TTS engines.

        Note: Ultimate TTS Studio loads all engines at startup,
        so this returns configured engines, not just loaded ones.
        """
        info = await self.get_info()
        if info:
            # Try to extract engine names from the API info
            # This depends on how Ultimate TTS Studio exposes engine info
            engines = []

            # Look for named_endpoints or components
            if "named_endpoints" in info:
                for endpoint in info["named_endpoints"]:
                    if "engine" in endpoint.lower() or "tts" in endpoint.lower():
                        engines.append(endpoint)

            if not engines:
                # Return default known engines
                return list(self.engine_vram_estimates.keys())

            return engines

        return list(self.engine_vram_estimates.keys())

    async def get_loaded_engines(self) -> Dict[str, int]:
        """
        Get currently loaded engines with their VRAM usage.

        Returns a dict of engine_name -> vram_mb
        """
        is_healthy = await self.health_check()
        if not is_healthy:
            logger.warning("Ultimate TTS Studio unhealthy, returning estimated VRAM")
            return dict(self.engine_vram_estimates)

        # Ultimate TTS Studio loads all engines at startup
        # Return estimates for all known engines
        return dict(self.engine_vram_estimates)

    async def get_total_vram_usage(self) -> int:
        """Get total estimated VRAM usage for all TTS engines."""
        is_healthy = await self.health_check()
        if not is_healthy:
            return 0

        return sum(self.engine_vram_estimates.values())

    async def is_engine_available(self, engine_name: str) -> bool:
        """Check if a specific TTS engine is available."""
        engines = await self.list_engines()
        return engine_name.lower() in [e.lower() for e in engines]

    # Note: Ultimate TTS Studio doesn't support dynamic engine loading/unloading
    async def load_engine(self, engine_name: str) -> bool:
        """
        Load a TTS engine (not supported dynamically).

        Ultimate TTS Studio loads all engines at startup.
        Returns False as dynamic loading is not supported.
        """
        logger.warning(
            f"Ultimate TTS Studio does not support dynamic engine loading. "
            f"Engine {engine_name} is loaded if configured at startup."
        )
        return False

    async def unload_engine(self, engine_name: str) -> bool:
        """
        Unload a TTS engine (not supported dynamically).

        Returns False as dynamic unloading is not supported.
        Stop the container to free GPU memory.
        """
        logger.warning(
            "Ultimate TTS Studio does not support dynamic engine unloading. "
            "Stop the container to free GPU memory."
        )
        return False

    def get_engine_vram_estimate(self, engine_name: str) -> int:
        """Get estimated VRAM usage for a specific engine."""
        return self.engine_vram_estimates.get(engine_name.lower(), 1024)
