"""Gemini Voice processor for Pipecat pipelines.

Generates native Multi-Modal voice audio using Google GenAI (Gemini)
and pipes it to local audio output and/or Google Cast Edge devices
(like Google Home and Pixel 10 Pro) via the NATS Cast Gateway.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import AsyncGenerator, Optional

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

    class FrameProcessor:  # type: ignore[no-redef]
        async def process_frame(self, frame: object, direction: object) -> None:
            pass
        async def cancel(self) -> None:
            pass

    Frame = object
    FrameDirection = None


class GeminiVoiceProcessor(FrameProcessor):
    """Pipecat TTS Processor generating voice natively with Gemini.

    Compatible with Gemini 1.5 Pro and Gemini 2.0 Flash audio modalities.
    Automatically supports Google Home and Pixel edge casting via the
    PMOVES NATS Event bus or direct API requests to Cast TTS Gateway.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash",
        voice_name: str = "Puck",  # Gemini voice options: Puck, Aoede, Charon, Fenrir, Kore
        sample_rate: int = 24000,
        cast_gateway_url: Optional[str] = None,
        default_cast_device: Optional[str] = None, # e.g., "Google Home" or "Pixel 10 Pro"
    ):
        if not PIPECAT_AVAILABLE:
            raise ImportError(
                "pipecat-ai is required for GeminiVoiceProcessor. "
                "Install with: uv pip install pipecat-ai"
            )

        # Lazy import google-genai to avoid crash when package is not installed
        try:
            from google import genai
            from google.genai import types
            self._genai = genai
            self._types = types
        except ImportError as e:
            raise ImportError(
                "google-genai SDK required for GeminiVoiceProcessor. "
                "Install with: uv pip install 'google-genai>=1.0.0,<2.0.0'"
            ) from e

        super().__init__()

        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set! GeminiVoiceProcessor will fail.")

        self.model = model
        self.voice_name = voice_name
        self.sample_rate = sample_rate
        self._cast_gateway_url = (
            cast_gateway_url
            or os.environ.get("CAST_GATEWAY_URL", "http://localhost:8060")
        ).rstrip("/")
        self._default_cast_device = default_cast_device

        # Initialize the GenAI client
        self.client = self._genai.Client(api_key=self.api_key) if self.api_key else None

    async def process_frame(
        self, frame: Frame, direction: FrameDirection
    ) -> AsyncGenerator[Frame, None]:
        await super().process_frame(frame, direction)

        if isinstance(frame, TextFrame):
            text = frame.text.strip()
            if not text:
                yield frame
                return

            yield TTSStartedFrame()

            try:
                # 1. Generate Audio via Gemini
                audio_bytes = await asyncio.to_thread(self._generate_audio, text)

                if audio_bytes:
                    # 2. Yield local playback frame
                    yield TTSAudioRawFrame(
                        audio=audio_bytes,
                        sample_rate=self.sample_rate,
                        num_channels=1
                    )

                    # 3. Cast to Google Home / Edge Devices (if configured)
                    if self._default_cast_device:
                        await self._cast_audio_bytes(audio_bytes)

            except Exception as e:
                logger.error(f"Gemini Voice generation error: {e}")
                yield ErrorFrame(error=str(e))

            finally:
                yield TTSStoppedFrame()

        else:
            yield frame

    def _generate_audio(self, text: str) -> Optional[bytes]:
        """Synchronous call to Gemini to generate audio bytes."""
        if not self.client:
            return None

        system_instruction = "You are a helpful voice assistant. Speak naturally."

        response = self.client.models.generate_content(
            model=self.model,
            contents=text,
            config=self._types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_modalities=["AUDIO"],
                speech_config=self._types.SpeechConfig(
                    voice_config=self._types.VoiceConfig(
                        prebuilt_voice_config=self._types.PrebuiltVoiceConfig(
                            voice_name=self.voice_name
                        )
                    )
                )
            )
        )

        # Extract audio bytes from the response
        try:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("audio/"):
                    return part.inline_data.data
        except Exception as e:
            logger.error(f"Failed to extract audio from Gemini response: {e}")

        return None

    async def _cast_audio_bytes(self, audio_bytes: bytes) -> None:
        """Route generated Gemini audio direct to Cast Edge Devices."""
        try:
            import httpx
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                f.write(audio_bytes)
                temp_path = f.name

            url = f"{self._cast_gateway_url}/cast/audio"
            payload = {
                "audio_path": temp_path,
                "device": self._default_cast_device
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                logger.debug(f"Casted Gemini Voice to edge device: {self._default_cast_device}")

        except Exception as e:
            logger.warning(f"Failed to cast Gemini audio to edge device: {e}")
