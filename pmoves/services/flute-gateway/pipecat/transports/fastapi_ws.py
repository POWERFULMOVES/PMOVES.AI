"""FastAPI WebSocket transport for pipecat pipelines.

Adapts FastAPI WebSocket to pipecat's transport interface for
full-duplex voice agent conversations.

Protocol:
    Client → Server: Binary audio frames (PCM16, 24kHz) or JSON control messages
    Server → Client: Binary audio frames (TTS output) or JSON status messages

Control Messages:
    {"type": "start", "voice": "default", "persona": "assistant"}
    {"type": "interrupt"} - Cancel current generation
    {"type": "stop"} - End conversation

Status Messages:
    {"type": "transcription", "text": "user speech"}
    {"type": "response_start"}
    {"type": "response_end"}
    {"type": "error", "message": "error details"}
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable, Dict, Optional

if TYPE_CHECKING:
    from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Pipecat imports - gracefully handle if not installed
try:
    from pipecat.frames.frames import (
        AudioRawFrame,
        EndFrame,
        Frame,
        StartFrame,
        TextFrame,
        TranscriptionFrame,
        UserStartedSpeakingFrame,
        UserStoppedSpeakingFrame,
    )
    from pipecat.transports.base_transport import BaseTransport, TransportParams

    PIPECAT_AVAILABLE = True
except ImportError:
    PIPECAT_AVAILABLE = False

    # Stub classes for type hints
    class BaseTransport:  # type: ignore[no-redef]
        """Stub BaseTransport for when pipecat not installed."""
        pass

    class TransportParams:  # type: ignore[no-redef]
        """Stub TransportParams for when pipecat not installed."""
        pass

    Frame = object


class FluteFastAPIWebsocketParams:
    """Configuration for FastAPI WebSocket transport.

    Attributes:
        sample_rate: Audio sample rate (default: 24000 Hz).
        audio_format: Audio format (default: pcm16).
        vad_enabled: Enable Voice Activity Detection.
        vad_start_threshold: VAD start threshold (0.0-1.0).
        vad_stop_threshold: VAD stop threshold (0.0-1.0).
        vad_min_speech_ms: Minimum speech duration in ms.
        vad_silence_ms: Silence duration to trigger stop.
    """

    def __init__(
        self,
        sample_rate: int = 24000,
        audio_format: str = "pcm16",
        vad_enabled: bool = True,
        vad_start_threshold: float = 0.5,
        vad_stop_threshold: float = 0.3,
        vad_min_speech_ms: int = 200,
        vad_silence_ms: int = 600,
    ):
        """Initialize transport parameters."""
        self.sample_rate = sample_rate
        self.audio_format = audio_format
        self.vad_enabled = vad_enabled
        self.vad_start_threshold = vad_start_threshold
        self.vad_stop_threshold = vad_stop_threshold
        self.vad_min_speech_ms = vad_min_speech_ms
        self.vad_silence_ms = vad_silence_ms


class FluteFastAPIWebsocketTransport(BaseTransport):
    """FastAPI WebSocket transport for pipecat voice pipelines.

    This transport adapter connects FastAPI WebSocket connections to
    pipecat's frame-based pipeline architecture, enabling full-duplex
    voice conversations.

    Attributes:
        websocket: FastAPI WebSocket connection.
        params: Transport parameters.

    Example:
        >>> @app.websocket("/v1/voice/stream/duplex")
        ... async def duplex(websocket: WebSocket):
        ...     transport = FluteFastAPIWebsocketTransport(websocket, params)
        ...     pipeline = build_voice_pipeline(transport)
        ...     await pipeline.run()
    """

    def __init__(
        self,
        websocket: "WebSocket",
        params: Optional[FluteFastAPIWebsocketParams] = None,
    ):
        """Initialize WebSocket transport.

        Args:
            websocket: FastAPI WebSocket connection.
            params: Transport configuration parameters.
        """
        if not PIPECAT_AVAILABLE:
            raise ImportError(
                "pipecat-ai is required for FluteFastAPIWebsocketTransport. "
                "Install with: pip install pipecat-ai[silero]"
            )

        super().__init__()
        self._websocket = websocket
        self._params = params or FluteFastAPIWebsocketParams()
        self._running = False
        self._is_speaking = False
        self._input_queue: asyncio.Queue[Frame] = asyncio.Queue()
        self._output_queue: asyncio.Queue[Frame] = asyncio.Queue()

        # Callbacks for pipeline events
        self._on_transcription: Optional[Callable[[str], None]] = None
        self._on_response_start: Optional[Callable[[], None]] = None
        self._on_response_end: Optional[Callable[[], None]] = None

    @property
    def sample_rate(self) -> int:
        """Get audio sample rate."""
        return self._params.sample_rate

    async def start(self) -> None:
        """Start the transport (begin processing)."""
        self._running = True
        logger.info("FluteFastAPIWebsocketTransport started")

    async def stop(self) -> None:
        """Stop the transport."""
        self._running = False
        logger.info("FluteFastAPIWebsocketTransport stopped")

    async def input(self) -> AsyncGenerator[Frame, None]:
        """Generate input frames from WebSocket.

        Yields:
            AudioRawFrame: Audio chunks from client.
            UserStartedSpeakingFrame: When VAD detects speech start.
            UserStoppedSpeakingFrame: When VAD detects speech end.
            EndFrame: When client disconnects or sends stop.
        """
        try:
            while self._running:
                try:
                    # Receive with timeout to allow checking _running
                    message = await asyncio.wait_for(
                        self._websocket.receive(),
                        timeout=0.1
                    )
                except asyncio.TimeoutError:
                    continue

                if message["type"] == "websocket.disconnect":
                    yield EndFrame()
                    break

                elif message["type"] == "websocket.receive":
                    if "bytes" in message:
                        # Binary audio data
                        audio_bytes = message["bytes"]
                        yield AudioRawFrame(
                            audio=audio_bytes,
                            sample_rate=self._params.sample_rate,
                            num_channels=1,
                        )

                    elif "text" in message:
                        # JSON control message
                        try:
                            data = json.loads(message["text"])
                            frame = await self._handle_control_message(data)
                            if frame:
                                yield frame
                        except json.JSONDecodeError:
                            logger.warning("Invalid JSON received: %s", message["text"])

        except Exception as e:
            logger.exception("Input error: %s", e)
            yield EndFrame()

    async def output(self, frame: Frame) -> None:
        """Send output frame to WebSocket.

        Args:
            frame: Frame to send (AudioRawFrame → binary, others → JSON).
        """
        try:
            if isinstance(frame, AudioRawFrame):
                # Send binary audio
                await self._websocket.send_bytes(frame.audio)

            elif isinstance(frame, TranscriptionFrame):
                # Send transcription as JSON
                await self._websocket.send_json({
                    "type": "transcription",
                    "text": frame.text,
                    "user_id": frame.user_id,
                    "timestamp": frame.timestamp,
                })
                if self._on_transcription:
                    self._on_transcription(frame.text)

            elif isinstance(frame, TextFrame):
                # LLM text response (for display before TTS)
                await self._websocket.send_json({
                    "type": "llm_text",
                    "text": frame.text,
                })

            elif isinstance(frame, StartFrame):
                await self._websocket.send_json({"type": "response_start"})
                if self._on_response_start:
                    self._on_response_start()

            elif isinstance(frame, EndFrame):
                await self._websocket.send_json({"type": "response_end"})
                if self._on_response_end:
                    self._on_response_end()

        except Exception as e:
            logger.exception("Output error: %s", e)

    async def _handle_control_message(self, data: Dict[str, Any]) -> Optional[Frame]:
        """Handle JSON control messages from client.

        Args:
            data: Parsed JSON message.

        Returns:
            Frame to inject into pipeline, or None.
        """
        msg_type = data.get("type", "")

        if msg_type == "start":
            # Client starting conversation
            logger.info("Client started conversation")
            return StartFrame()

        elif msg_type == "stop":
            # Client ending conversation
            logger.info("Client stopped conversation")
            return EndFrame()

        elif msg_type == "interrupt":
            # Client interrupting (barge-in)
            logger.info("Client interrupted")
            return UserStartedSpeakingFrame()

        elif msg_type == "speech_start":
            # VAD detected speech start (client-side VAD)
            self._is_speaking = True
            return UserStartedSpeakingFrame()

        elif msg_type == "speech_end":
            # VAD detected speech end (client-side VAD)
            self._is_speaking = False
            return UserStoppedSpeakingFrame()

        elif msg_type == "text":
            # Direct text input (skip STT)
            text = data.get("text", "")
            if text:
                return TextFrame(text=text)

        else:
            logger.debug("Unknown control message type: %s", msg_type)

        return None

    async def send_status(self, status: str, **kwargs: Any) -> None:
        """Send status message to client.

        Args:
            status: Status type (e.g., "processing", "ready").
            **kwargs: Additional status fields.
        """
        try:
            await self._websocket.send_json({
                "type": "status",
                "status": status,
                **kwargs
            })
        except Exception as e:
            logger.warning("Failed to send status: %s", e)

    async def send_error(self, message: str) -> None:
        """Send error message to client.

        Args:
            message: Error description.
        """
        try:
            await self._websocket.send_json({
                "type": "error",
                "message": message
            })
        except Exception as e:
            logger.warning("Failed to send error: %s", e)


# Export for convenient imports
__all__ = [
    "FluteFastAPIWebsocketTransport",
    "FluteFastAPIWebsocketParams",
]
