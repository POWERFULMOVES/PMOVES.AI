"""
Fallback Strategies

Multi-level TTS and device fallback with graceful degradation.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from datetime import datetime


@dataclass
class FallbackResult:
    """Result from fallback chain execution."""

    success: bool
    provider_used: Optional[str] = None
    device_used: Optional[str] = None
    attempts: int = 0
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "provider_used": self.provider_used,
            "device_used": self.device_used,
            "attempts": self.attempts,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class FallbackProvider(ABC):
    """Abstract base class for fallback providers."""

    @abstractmethod
    async def synthesize(self, text: str, voice: str = "default") -> Optional[bytes]:
        """
        Synthesize speech from text.

        Args:
            text: Text to synthesize
            voice: Voice identifier

        Returns:
            Audio data as bytes, or None if failed
        """

    @abstractmethod
    def provider_name(self) -> str:
        """Get provider name."""


class FluteTTSProvider(FallbackProvider):
    """Flute-Gateway TTS provider."""

    def __init__(self, gateway_url: str):
        """
        Initialize Flute provider.

        Args:
            gateway_url: Flute-Gateway URL
        """
        self.gateway_url = gateway_url

    async def synthesize(self, text: str, voice: str = "default") -> Optional[bytes]:
        """Synthesize using Flute-Gateway."""
        try:
            # Import here to avoid circular dependency
            from flute_client import FluteTTSProvider as FluteClient

            client = FluteClient(self.gateway_url)
            return await client.synthesize_prosodic(text=text, voice=voice)

        except Exception:
            return None

    def provider_name(self) -> str:
        """Get provider name."""
        return "flute"


class UltimateTTSProvider(FallbackProvider):
    """Ultimate-TTS-Studio provider."""

    def __init__(self, gateway_url: str):
        """
        Initialize Ultimate-TTS provider.

        Args:
            gateway_url: Ultimate-TTS URL
        """
        self.gateway_url = gateway_url

    async def synthesize(
        self,
        text: str,
        voice: str = "default",
        speed: float = 1.0,
        pitch: float = 1.0,
    ) -> Optional[bytes]:
        """
        Synthesize using Ultimate-TTS with configurable parameters.

        Args:
            text: Text to synthesize
            voice: Voice model name (default: "Kokoro")
            speed: Speech speed multiplier (0.5-2.0, default: 1.0)
            pitch: Pitch multiplier (0.5-2.0, default: 1.0)

        Returns:
            Audio data as bytes, or None if synthesis failed
        """
        try:
            import httpx

            # Map voice name to Ultimate-TTS model
            voice_model = "Kokoro" if voice == "default" else voice

            # Clamp speed and pitch to valid range
            speed = max(0.5, min(2.0, speed))
            pitch = max(0.5, min(2.0, pitch))

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.gateway_url}/api/predict",
                    json={"data": [text, voice_model, speed, pitch, speed]},
                )
                response.raise_for_status()
                result_data = response.json()

                if "data" in result_data and len(result_data["data"]) > 0:
                    audio_path = result_data["data"][0]

                    # Read audio file
                    with open(audio_path, "rb") as f:
                        return f.read()

        except Exception:
            return None

    def provider_name(self) -> str:
        """Get provider name."""
        return "ultimate_tts"


class GoogleTTSProvider(FallbackProvider):
    """Google TTS provider (fallback)."""

    async def synthesize(self, text: str, voice: str = "default") -> Optional[bytes]:
        """Synthesize using Google TTS (gtts library)."""
        try:
            from gtts import gTTS
            import io

            tts = gTTS(text=text, lang="en")
            audio_fp = io.BytesIO()
            tts.write_to_fp(audio_fp)
            audio_fp.seek(0)
            return audio_fp.read()

        except Exception:
            return None

    def provider_name(self) -> str:
        """Get provider name."""
        return "google_tts"


class TTSGatewayFallback:
    """Multi-level TTS provider fallback with circuit breaker integration."""

    # Canonical circuit breaker keys per provider
    PROVIDER_CB_KEYS = {
        "flute": "tts.flute",
        "ultimate_tts": "tts.ultimate_tts",
        "google_tts": "tts.google_tts",
    }

    def __init__(self, providers: list[FallbackProvider], recovery_manager=None, on_transition=None):
        """
        Initialize TTS fallback chain.

        Args:
            providers: Ordered list of TTS providers (primary first)
            recovery_manager: Optional RecoveryManager for circuit breaker integration
            on_transition: Optional callback(from_state, to_state, service_key) for metrics
        """
        self.providers = providers
        self.recovery_manager = recovery_manager
        self._on_transition = on_transition

    def _cb_key(self, provider: FallbackProvider) -> str:
        """Get circuit breaker key for a provider."""
        return self.PROVIDER_CB_KEYS.get(
            provider.provider_name(), f"tts.{provider.provider_name()}"
        )

    async def synthesize_with_fallback(
        self,
        text: str,
        voice: str = "default",
    ) -> FallbackResult:
        """
        Synthesize with fallback chain.

        Args:
            text: Text to synthesize
            voice: Voice identifier

        Returns:
            FallbackResult with audio data or error
        """
        import time

        start_time = time.time()

        for provider in self.providers:
            cb_key = self._cb_key(provider)

            # Check circuit breaker before attempting provider
            if self.recovery_manager:
                breaker = self.recovery_manager.get_circuit_breaker(cb_key)
                if not breaker.allow_request():
                    continue

            try:
                audio_data = await provider.synthesize(text, voice)

                if audio_data:
                    duration_ms = (time.time() - start_time) * 1000

                    # Record success with circuit breaker (isolated from result)
                    try:
                        if self.recovery_manager:
                            breaker = self.recovery_manager.get_circuit_breaker(cb_key)
                            prev = breaker.get_state().state
                            breaker.record_success()
                            curr = breaker.get_state().state
                            if prev != curr and self._on_transition:
                                self._on_transition(prev.value, curr.value, cb_key)
                    except Exception:
                        pass  # CB bookkeeping must not mask a successful synthesis

                    return FallbackResult(
                        success=True,
                        provider_used=provider.provider_name(),
                        attempts=self.providers.index(provider) + 1,
                        duration_ms=duration_ms,
                    )

            except Exception as e:
                # Record failure with circuit breaker (isolated)
                try:
                    if self.recovery_manager:
                        breaker = self.recovery_manager.get_circuit_breaker(cb_key)
                        prev = breaker.get_state().state
                        breaker.record_failure()
                        curr = breaker.get_state().state
                        if prev != curr and self._on_transition:
                            self._on_transition(prev.value, curr.value, cb_key)
                except Exception:
                    pass  # CB bookkeeping must not prevent fallback to next provider
                # Try next provider
                continue

        # All providers failed
        duration_ms = (time.time() - start_time) * 1000

        return FallbackResult(
            success=False,
            attempts=len(self.providers),
            error="All TTS providers failed",
            duration_ms=duration_ms,
        )

    def add_provider(self, provider: FallbackProvider, position: Optional[int] = None):
        """
        Add provider to fallback chain.

        Args:
            provider: Provider to add
            position: Position to insert (None for end)
        """
        if position is None:
            self.providers.append(provider)
        else:
            self.providers.insert(position, provider)

    def remove_provider(self, provider_name: str) -> bool:
        """
        Remove provider from fallback chain.

        Args:
            provider_name: Name of provider to remove

        Returns:
            True if removed, False if not found
        """
        for i, provider in enumerate(self.providers):
            if provider.provider_name() == provider_name:
                self.providers.pop(i)
                return True

        return False

    def list_providers(self) -> list[str]:
        """
        List providers in fallback chain.

        Returns:
            List of provider names in order
        """
        return [p.provider_name() for p in self.providers]


class DeviceFallback:
    """Device fallback strategy."""

    def __init__(self, devices: list[str]):
        """
        Initialize device fallback.

        Args:
            devices: Ordered list of device names (primary first)
        """
        self.devices = devices

    async def cast_with_fallback(
        self,
        cast_fn: Callable[[str], Any],
        text: str = "",
    ) -> FallbackResult:
        """
        Cast with device fallback.

        Args:
            cast_fn: Async function that takes device name and returns result
            text: Text being cast (for logging)

        Returns:
            FallbackResult with result or error
        """
        import time

        start_time = time.time()

        for device in self.devices:
            try:
                result = await cast_fn(device)

                if result.get("success"):
                    duration_ms = (time.time() - start_time) * 1000

                    return FallbackResult(
                        success=True,
                        device_used=device,
                        attempts=self.devices.index(device) + 1,
                        duration_ms=duration_ms,
                    )

            except Exception as e:
                # Try next device
                continue

        # All devices failed
        duration_ms = (time.time() - start_time) * 1000

        return FallbackResult(
            success=False,
            attempts=len(self.devices),
            error="All devices failed",
            duration_ms=duration_ms,
        )

    def add_device(self, device: str, position: Optional[int] = None):
        """
        Add device to fallback chain.

        Args:
            device: Device name to add
            position: Position to insert (None for end)
        """
        if position is None:
            self.devices.append(device)
        else:
            self.devices.insert(position, device)

    def remove_device(self, device: str) -> bool:
        """
        Remove device from fallback chain.

        Args:
            device: Device name to remove

        Returns:
            True if removed, False if not found
        """
        if device in self.devices:
            self.devices.remove(device)
            return True

        return False

    def list_devices(self) -> list[str]:
        """
        List devices in fallback chain.

        Returns:
            List of device names in order
        """
        return self.devices.copy()


class FallbackManager:
    """Manage all fallback strategies."""

    def __init__(self, recovery_manager=None, on_transition=None):
        """Initialize fallback manager."""
        self.tts_fallback: Optional[TTSGatewayFallback] = None
        self.device_fallbacks: dict[str, DeviceFallback] = {}
        self.recovery_manager = recovery_manager
        self._on_transition = on_transition

    def configure_tts_fallback(
        self,
        providers: list[FallbackProvider],
    ) -> dict:
        """
        Configure TTS fallback chain.

        Args:
            providers: Ordered list of TTS providers

        Returns:
            Result dict
        """
        self.tts_fallback = TTSGatewayFallback(
            providers, self.recovery_manager, self._on_transition,
        )

        return {
            "success": True,
            "providers": [p.provider_name() for p in providers],
            "message": "Configured TTS fallback chain",
        }

    def configure_device_fallback(
        self,
        name: str,
        devices: list[str],
    ) -> dict:
        """
        Configure device fallback chain.

        Args:
            name: Fallback chain name
            devices: Ordered list of device names

        Returns:
            Result dict
        """
        self.device_fallbacks[name] = DeviceFallback(devices)

        return {
            "success": True,
            "name": name,
            "devices": devices,
            "message": f"Configured device fallback chain '{name}'",
        }

    async def synthesize_tts(
        self,
        text: str,
        voice: str = "default",
    ) -> tuple[Optional[bytes], FallbackResult]:
        """
        Synthesize TTS with fallback.

        Args:
            text: Text to synthesize
            voice: Voice identifier

        Returns:
            Tuple of (audio_data, fallback_result)
        """
        if not self.tts_fallback:
            return None, FallbackResult(
                success=False,
                error="TTS fallback not configured",
            )

        # For now, return result without actual audio
        # In production, you'd need to modify FallbackResult to include audio
        result = await self.tts_fallback.synthesize_with_fallback(text, voice)

        return (None, result)

    async def cast_with_device_fallback(
        self,
        name: str,
        cast_fn: Callable[[str], Any],
        text: str = "",
    ) -> FallbackResult:
        """
        Cast with device fallback.

        Args:
            name: Fallback chain name
            cast_fn: Async function that takes device name and returns result
            text: Text being cast

        Returns:
            FallbackResult
        """
        fallback = self.device_fallbacks.get(name)

        if not fallback:
            return FallbackResult(
                success=False,
                error=f"Device fallback '{name}' not found",
            )

        return await fallback.cast_with_fallback(cast_fn, text)

    def list_tts_providers(self) -> list[str]:
        """List TTS providers in fallback chain."""
        if self.tts_fallback:
            return self.tts_fallback.list_providers()
        return []

    def list_device_fallbacks(self) -> dict[str, list[str]]:
        """List all device fallback chains."""
        return {
            name: fallback.list_devices()
            for name, fallback in self.device_fallbacks.items()
        }
