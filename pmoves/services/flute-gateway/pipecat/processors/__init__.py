"""Pipecat frame processors wrapping flute-gateway providers.

These processors adapt existing flute-gateway TTS/STT providers to the
pipecat frame-based pipeline architecture.

Processors:
    VibeVoiceTTSProcessor: Streaming TTS via VibeVoice WebSocket
    UltimateTTSProcessor: Multi-engine TTS via Gradio API
    WhisperSTTProcessor: Speech-to-text via ffmpeg-whisper
    TensorZeroLLMProcessor: LLM via TensorZero gateway
"""

from .vibevoice import VibeVoiceTTSProcessor
from .whisper import WhisperSTTProcessor
from .tensorzero import TensorZeroLLMProcessor

__all__ = [
    "VibeVoiceTTSProcessor",
    "WhisperSTTProcessor",
    "TensorZeroLLMProcessor",
]
