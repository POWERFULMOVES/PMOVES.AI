"""VibeVoice TTS processor for pipecat pipelines.

Wraps the existing VibeVoiceProvider as a pipecat FrameProcessor that:
- Accepts TextFrame input
- Yields AudioRawFrame output (PCM16, 24kHz)
- Handles busy errors with backpressure
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, AsyncGenerator, Optional

import numpy as np

if TYPE_CHECKING:
    from providers.vibevoice import VibeVoiceProvider

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


class VibeVoiceTTSProcessor(FrameProcessor):
    """Pipecat TTS processor using VibeVoice streaming synthesis.

    This processor wraps flute-gateway's VibeVoiceProvider to provide
    streaming TTS in pipecat pipelines.

    Attributes:
        provider: The underlying VibeVoice provider instance.
        voice: Voice name to use for synthesis.
        sample_rate: Output audio sample rate (24000 Hz).

    Example:
        >>> provider = VibeVoiceProvider(url="ws://localhost:3000")
        >>> tts = VibeVoiceTTSProcessor(provider, voice="default")
        >>> pipeline = Pipeline([..., tts, ...])
    """

    def __init__(
        self,
        provider: "VibeVoiceProvider",
        voice: str = "default",
        sample_rate: int = 24000,
        channels: int = 1,
    ):
        """Initialize VibeVoice TTS processor.

        Args:
            provider: Configured VibeVoiceProvider instance.
            voice: Voice name for synthesis.
            sample_rate: Audio sample rate in Hz.
            channels: Number of audio channels.
        """
        if not PIPECAT_AVAILABLE:
            raise ImportError(
                "pipecat-ai is required for VibeVoiceTTSProcessor. "
                "Install with: pip install pipecat-ai[silero]"
            )

        super().__init__()
        self._provider = provider
        self._voice = voice
        self._sample_rate = sample_rate
        self._channels = channels
        self._synthesizing = False

    @property
    def voice(self) -> str:
        """Get current voice name."""
        return self._voice

    @voice.setter
    def voice(self, value: str) -> None:
        """Set voice name for synthesis."""
        self._voice = value

    async def process_frame(
        self, frame: Frame, direction: FrameDirection
    ) -> AsyncGenerator[Frame, None]:
        """Process incoming frames and generate TTS audio.

        Args:
            frame: Input frame (TextFrame triggers synthesis).
            direction: Frame direction (downstream/upstream).

        Yields:
            TTSStartedFrame: Before synthesis begins.
            TTSAudioRawFrame: Audio chunks during synthesis.
            TTSStoppedFrame: After synthesis completes.
            ErrorFrame: On synthesis errors.
        """
        await super().process_frame(frame, direction)

        if isinstance(frame, TextFrame):
            text = frame.text.strip()
            if not text:
                yield frame
                return

            # Signal TTS start
            yield TTSStartedFrame()
            self._synthesizing = True

            try:
                chunk_count = 0
                async for audio_chunk in self._provider.synthesize_stream(
                    text, self._voice
                ):
                    if not self._synthesizing:
                        # Synthesis was interrupted
                        break

                    # Convert bytes to numpy array for AudioRawFrame
                    audio_array = np.frombuffer(audio_chunk, dtype=np.int16)

                    yield TTSAudioRawFrame(
                        audio=audio_array.tobytes(),
                        sample_rate=self._sample_rate,
                        num_channels=self._channels,
                    )
                    chunk_count += 1

                logger.debug(
                    f"VibeVoice TTS completed: {chunk_count} chunks for '{text[:50]}...'"
                )

            except Exception as e:
                error_msg = f"VibeVoice TTS error: {e}"
                logger.error(error_msg)
                yield ErrorFrame(error=error_msg)

            finally:
                self._synthesizing = False
                yield TTSStoppedFrame()

        elif isinstance(frame, EndFrame):
            # Stop any ongoing synthesis
            self._synthesizing = False
            yield frame

        else:
            # Pass through other frames unchanged
            yield frame

    async def cancel(self) -> None:
        """Cancel ongoing synthesis."""
        self._synthesizing = False
        await super().cancel()
