"""Cast audio output processor for Pipecat pipelines.

Extends VibeVoice TTS with Google Cast device output for dual audio
(local speakers + Cast devices).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, AsyncGenerator, Optional

import httpx

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Pipecat imports - gracefully handle if not installed
try:
    from pipecat.frames.frames import (
        AudioRawFrame,
        EndFrame,
        ErrorFrame,
        Frame,
        TextFrame,
        TTSAudioRawFrame,
        TTSStartedFrame,
        TTSStoppedFrame,
    )
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

    PIPECAT_AVAILABLE = True
except ImportError:
    PIPECAT_AVAILABLE = False

    # Stub classes for when pipecat not installed (type hints only)
    class FrameProcessor:  # type: ignore[no-redef]
        """Stub FrameProcessor for when pipecat not installed."""

        async def cancel(self) -> None:
            """Stub cancel method."""
            pass

        async def cleanup(self) -> None:
            """Stub cleanup method."""
            pass

    Frame = object
    FrameDirection = None


class CastAudioOutputProcessor(FrameProcessor):
    """Pipecat processor for casting TTS audio to Google Cast devices.

    This processor extends VibeVoice TTS output with simultaneous casting
    to Google Cast devices (Nest Audio, Nest Mini, Smart TVs, etc.).

    The processor operates in dual-output mode:
    - Local TTS audio (via VibeVoice)
    - Cast TTS audio (via Cast TTS Gateway API)

    Attributes:
        cast_gateway_url: Cast TTS Gateway service URL.
        default_device: Default Cast device name (None = auto-select).
        enable_local_audio: Whether to yield local TTS frames.
        voice: Voice name for synthesis.
        timeout: HTTP request timeout in seconds.

    Example:
        >>> cast = CastAudioOutputProcessor(
        ...     cast_gateway_url="http://localhost:8060",
        ...     default_device="Brysons Speakers speaker"
        ... )
        >>> pipeline = Pipeline([vibevoice_tts, cast, ...])
    """

    def __init__(
        self,
        cast_gateway_url: str = "http://localhost:8060",
        default_device: Optional[str] = None,
        enable_local_audio: bool = True,
        voice: str = "default",
        timeout: float = 30.0,
    ):
        """Initialize Cast audio output processor.

        Args:
            cast_gateway_url: Cast TTS Gateway service URL.
            default_device: Default Cast device name (None for auto-selection).
            enable_local_audio: Whether to yield local TTS audio frames.
            voice: Voice name for TTS synthesis.
            timeout: HTTP request timeout in seconds.

        Raises:
            ImportError: If pipecat-ai is not installed.
        """
        if not PIPECAT_AVAILABLE:
            raise ImportError(
                "pipecat-ai is required for CastAudioOutputProcessor. "
                "Install with: pip install pipecat-ai[silero]"
            )

        super().__init__()
        self._cast_gateway_url = cast_gateway_url.rstrip("/")
        self._default_device = default_device
        self._enable_local_audio = enable_local_audio
        self._voice = voice
        self._timeout = timeout
        self._casting = False

    @property
    def voice(self) -> str:
        """Get current voice name."""
        return self._voice

    @voice.setter
    def voice(self, value: str) -> None:
        """Set voice name for synthesis."""
        self._voice = value

    @property
    def default_device(self) -> Optional[str]:
        """Get default Cast device."""
        return self._default_device

    @default_device.setter
    def default_device(self, value: Optional[str]) -> None:
        """Set default Cast device."""
        self._default_device = value

    async def process_frame(
        self, frame: Frame, direction: FrameDirection
    ) -> AsyncGenerator[Frame, None]:
        """Process incoming frames and cast to Google Cast devices.

        Args:
            frame: Input frame (TextFrame triggers casting).
            direction: Frame direction (downstream/upstream).

        Yields:
            TextFrame: Passthrough for local TTS if enabled.
            ErrorFrame: On casting errors (non-fatal, continues pipeline).
        """
        await super().process_frame(frame, direction)

        if isinstance(frame, TextFrame):
            text = frame.text.strip()
            if not text:
                yield frame
                return

            # Cast to device (non-blocking)
            self._casting = True
            try:
                await self._cast_speech(text)
                logger.debug(f"Cast successful: '{text[:50]}...'")
            except Exception as e:
                error_msg = f"Cast TTS Gateway error: {e}"
                logger.warning(error_msg)
                # Non-fatal: yield error frame but continue pipeline
                yield ErrorFrame(error=error_msg)
            finally:
                self._casting = False

            # Passthrough for local TTS (dual-output mode)
            if self._enable_local_audio:
                yield frame  # Let VibeVoiceTTSProcessor handle local audio

        elif isinstance(frame, EndFrame):
            # Stop any ongoing casting
            self._casting = False
            yield frame

        else:
            # Pass through other frames unchanged
            yield frame

    async def _cast_speech(self, text: str) -> dict:
        """Call Cast TTS Gateway API to synthesize and cast.

        Args:
            text: Text to synthesize and cast.

        Returns:
            Response JSON from Cast TTS Gateway.

        Raises:
            httpx.HTTPError: On HTTP errors.
            asyncio.TimeoutError: On timeout.
        """
        url = f"{self._cast_gateway_url}/cast/speech"
        payload = {
            "text": text,
            "device": self._default_device,
            "voice": self._voice,
            "use_flute": True,  # Use Flute-Gateway for prosodic TTS
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

            if not result.get("success"):
                error = result.get("error", "Unknown casting error")
                raise RuntimeError(f"Cast failed: {error}")

            return result

    async def cancel(self) -> None:
        """Cancel ongoing casting."""
        self._casting = False
        await super().cancel()


class CastAudioOnlyProcessor(FrameProcessor):
    """Cast-only processor (no local TTS output).

    This processor casts TTS to Google Cast devices without yielding
    local audio frames. Use this when you want Cast-only output.

    Attributes:
        cast_gateway_url: Cast TTS Gateway service URL.
        default_device: Default Cast device name (None = auto-select).
        voice: Voice name for synthesis.
        timeout: HTTP request timeout in seconds.

    Example:
        >>> cast_only = CastAudioOnlyProcessor(
        ...     cast_gateway_url="http://localhost:8060",
        ...     default_device="Brysons Speakers speaker"
        ... )
        >>> pipeline = Pipeline([cast_only, ...])
    """

    def __init__(
        self,
        cast_gateway_url: str = "http://localhost:8060",
        default_device: Optional[str] = None,
        voice: str = "default",
        timeout: float = 30.0,
    ):
        """Initialize Cast-only audio output processor.

        Args:
            cast_gateway_url: Cast TTS Gateway service URL.
            default_device: Default Cast device name (None for auto-selection).
            voice: Voice name for TTS synthesis.
            timeout: HTTP request timeout in seconds.

        Raises:
            ImportError: If pipecat-ai is not installed.
        """
        if not PIPECAT_AVAILABLE:
            raise ImportError(
                "pipecat-ai is required for CastAudioOnlyProcessor. "
                "Install with: pip install pipecat-ai[silero]"
            )

        super().__init__()
        self._cast_gateway_url = cast_gateway_url.rstrip("/")
        self._default_device = default_device
        self._voice = voice
        self._timeout = timeout
        self._casting = False

    async def process_frame(
        self, frame: Frame, direction: FrameDirection
    ) -> AsyncGenerator[Frame, None]:
        """Process incoming frames and cast to Google Cast devices.

        Args:
            frame: Input frame (TextFrame triggers casting).
            direction: Frame direction (downstream/upstream).

        Yields:
            TTSStartedFrame: Before casting begins.
            TTSStoppedFrame: After casting completes.
            ErrorFrame: On casting errors.
        """
        await super().process_frame(frame, direction)

        if isinstance(frame, TextFrame):
            text = frame.text.strip()
            if not text:
                return

            # Signal TTS start
            yield TTSStartedFrame()
            self._casting = True

            try:
                await self._cast_speech(text)
                logger.debug(f"Cast-only successful: '{text[:50]}...'")

            except Exception as e:
                error_msg = f"Cast-only error: {e}"
                logger.error(error_msg)
                yield ErrorFrame(error=error_msg)

            finally:
                self._casting = False
                yield TTSStoppedFrame()

        elif isinstance(frame, EndFrame):
            self._casting = False
            yield frame

    async def _cast_speech(self, text: str) -> dict:
        """Call Cast TTS Gateway API to synthesize and cast.

        Args:
            text: Text to synthesize and cast.

        Returns:
            Response JSON from Cast TTS Gateway.

        Raises:
            httpx.HTTPError: On HTTP errors.
            asyncio.TimeoutError: On timeout.
        """
        url = f"{self._cast_gateway_url}/cast/speech"
        payload = {
            "text": text,
            "device": self._default_device,
            "voice": self._voice,
            "use_flute": True,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

            if not result.get("success"):
                error = result.get("error", "Unknown casting error")
                raise RuntimeError(f"Cast failed: {error}")

            return result

    async def cancel(self) -> None:
        """Cancel ongoing casting."""
        self._casting = False
        await super().cancel()
