"""
Flute-Gateway TTS Client

Client for Flute-Gateway prosodic TTS synthesis API.
"""

from typing import Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

DEFAULT_FLUTE_URL = "http://localhost:8055"


class FluteTTSProvider:
    """Flute-Gateway TTS synthesis provider."""

    def __init__(self, base_url: str = DEFAULT_FLUTE_URL):
        """
        Initialize Flute TTS provider.

        Args:
            base_url: Flute-Gateway base URL
        """
        if not HAS_HTTPX:
            raise ImportError("httpx required for Flute-Gateway client")

        self.base_url = base_url.rstrip("/")
        self.api_base = f"{self.base_url}/v1/voice"

    async def synthesize_prosodic(
        self,
        text: str,
        voice: str = "default",
        timeout: float = 120.0,
    ) -> Optional[bytes]:
        """
        Synthesize speech using Flute-Gateway prosodic API.

        Args:
            text: Text to synthesize
            voice: Voice/model to use
            timeout: Request timeout in seconds

        Returns:
            Audio data as bytes, or None if failed
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.api_base}/synthesize/prosodic",
                    json={"text": text, "voice": voice},
                )
                response.raise_for_status()
                return response.content

        except Exception as e:
            print(f"Flute-Gateway TTS failed: {e}")
            return None

    async def health_check(self, timeout: float = 5.0) -> bool:
        """
        Check Flute-Gateway health status.

        Args:
            timeout: Request timeout in seconds

        Returns:
            True if healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{self.base_url}/healthz")
                return response.status_code == 200

        except Exception:
            return False
