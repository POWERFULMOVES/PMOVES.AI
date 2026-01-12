"""Base class for voice providers."""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, Optional


class VoiceProvider(ABC):
    """Abstract base class for voice providers (TTS/STT)."""

    def __init__(self, base_url: str):
        """Initialize provider with base URL."""
        self.base_url = base_url

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """
        Synthesize speech from text (batch mode).

        Args:
            text: Text to synthesize
            voice: Voice preset/ID
            **kwargs: Provider-specific parameters

        Returns:
            Audio data as bytes
        """
        pass

    @abstractmethod
    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[bytes]:
        """
        Stream synthesized speech chunks.

        Args:
            text: Text to synthesize
            voice: Voice preset/ID
            **kwargs: Provider-specific parameters

        Yields:
            Audio chunks as bytes
        """
        pass

    @abstractmethod
    async def recognize(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Recognize speech from audio data (batch mode).

        Args:
            audio_data: Audio bytes to transcribe
            language: Language code (e.g., 'en', 'es')
            **kwargs: Provider-specific parameters

        Returns:
            Dictionary with 'text', 'confidence', 'language'
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if provider is available.

        Returns:
            True if healthy, False otherwise
        """
        pass
