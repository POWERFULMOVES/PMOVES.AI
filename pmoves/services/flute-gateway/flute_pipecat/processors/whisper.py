"""Whisper STT processor for pipecat pipelines.

Wraps the existing WhisperProvider as a pipecat FrameProcessor that:
- Accepts AudioRawFrame input
- Buffers audio until VAD detects end of speech
- Yields TranscriptionFrame output
"""

from __future__ import annotations

import asyncio
import io
import logging
import wave
from typing import TYPE_CHECKING, AsyncGenerator, Optional

if TYPE_CHECKING:
    from providers.whisper import WhisperProvider

logger = logging.getLogger(__name__)

# Pipecat imports - gracefully handle if not installed
try:
    from pipecat.frames.frames import (
        AudioRawFrame,
        EndFrame,
        ErrorFrame,
        Frame,
        TranscriptionFrame,
        UserStartedSpeakingFrame,
        UserStoppedSpeakingFrame,
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


class WhisperSTTProcessor(FrameProcessor):
    """Pipecat STT processor using Whisper for speech recognition.

    This processor wraps flute-gateway's WhisperProvider to provide
    speech-to-text in pipecat pipelines. It buffers audio frames and
    sends them for transcription when speech ends (based on VAD).

    Attributes:
        provider: The underlying Whisper provider instance.
        language: Language code for transcription (e.g., "en").
        sample_rate: Expected input audio sample rate.

    Example:
        >>> provider = WhisperProvider(url="http://localhost:8078")
        >>> stt = WhisperSTTProcessor(provider, language="en")
        >>> pipeline = Pipeline([..., stt, ...])
    """

    def __init__(
        self,
        provider: "WhisperProvider",
        language: Optional[str] = None,
        sample_rate: int = 16000,
        channels: int = 1,
        min_audio_length_ms: int = 500,
    ):
        """Initialize Whisper STT processor.

        Args:
            provider: Configured WhisperProvider instance.
            language: Language code for transcription (auto-detect if None).
            sample_rate: Expected audio sample rate in Hz.
            channels: Number of audio channels.
            min_audio_length_ms: Minimum audio length to transcribe.
        """
        if not PIPECAT_AVAILABLE:
            raise ImportError(
                "pipecat-ai is required for WhisperSTTProcessor. "
                "Install with: pip install pipecat-ai[silero]"
            )

        super().__init__()
        self._provider = provider
        self._language = language
        self._sample_rate = sample_rate
        self._channels = channels
        self._min_audio_length_ms = min_audio_length_ms

        # Audio buffer
        self._audio_buffer: list[bytes] = []
        self._is_speaking = False
        self._transcription_task: Optional[asyncio.Task] = None

    @property
    def language(self) -> Optional[str]:
        """Get current language setting."""
        return self._language

    @language.setter
    def language(self, value: Optional[str]) -> None:
        """Set language for transcription."""
        self._language = value

    def _buffer_to_wav(self) -> bytes:
        """Convert audio buffer to WAV format for Whisper.

        Returns:
            WAV-formatted audio bytes.
        """
        audio_data = b"".join(self._audio_buffer)

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(self._channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self._sample_rate)
            wav_file.writeframes(audio_data)

        return wav_buffer.getvalue()

    def _get_audio_duration_ms(self) -> float:
        """Calculate duration of buffered audio in milliseconds."""
        total_bytes = sum(len(chunk) for chunk in self._audio_buffer)
        # 2 bytes per sample (16-bit), mono
        samples = total_bytes // 2
        return (samples / self._sample_rate) * 1000

    async def _transcribe_buffer(self) -> Optional[str]:
        """Send buffered audio to Whisper for transcription.

        Returns:
            Transcription text or None if transcription failed.
        """
        if not self._audio_buffer:
            return None

        duration_ms = self._get_audio_duration_ms()
        if duration_ms < self._min_audio_length_ms:
            logger.debug(
                f"Audio too short ({duration_ms:.0f}ms < {self._min_audio_length_ms}ms), skipping"
            )
            return None

        try:
            wav_data = self._buffer_to_wav()
            result = await self._provider.recognize(
                wav_data, language=self._language
            )

            if result and "text" in result:
                text = result["text"].strip()
                confidence = result.get("confidence", 0.0)
                logger.debug(
                    f"Whisper transcription: '{text[:50]}...' (conf={confidence:.2f})"
                )
                return text

        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")

        return None

    async def process_frame(
        self, frame: Frame, direction: FrameDirection
    ) -> AsyncGenerator[Frame, None]:
        """Process incoming frames and generate transcriptions.

        Args:
            frame: Input frame (AudioRawFrame buffered, VAD frames trigger transcription).
            direction: Frame direction (downstream/upstream).

        Yields:
            TranscriptionFrame: Completed transcriptions.
            ErrorFrame: On transcription errors.
        """
        await super().process_frame(frame, direction)

        if isinstance(frame, AudioRawFrame):
            # Buffer audio while speaking
            if self._is_speaking:
                self._audio_buffer.append(frame.audio)
            yield frame

        elif isinstance(frame, UserStartedSpeakingFrame):
            # Start buffering audio
            self._is_speaking = True
            self._audio_buffer = []
            logger.debug("User started speaking, buffering audio")
            yield frame

        elif isinstance(frame, UserStoppedSpeakingFrame):
            # Stop buffering and transcribe
            self._is_speaking = False
            logger.debug("User stopped speaking, transcribing buffer")

            text = await self._transcribe_buffer()
            self._audio_buffer = []

            if text:
                yield TranscriptionFrame(text=text, user_id="", timestamp="")

            yield frame

        elif isinstance(frame, EndFrame):
            # Transcribe any remaining audio
            if self._audio_buffer:
                text = await self._transcribe_buffer()
                if text:
                    yield TranscriptionFrame(text=text, user_id="", timestamp="")
                self._audio_buffer = []

            yield frame

        else:
            # Pass through other frames
            yield frame

    async def cancel(self) -> None:
        """Cancel ongoing transcription."""
        self._audio_buffer = []
        self._is_speaking = False
        if self._transcription_task and not self._transcription_task.done():
            self._transcription_task.cancel()
        await super().cancel()
