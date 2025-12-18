"""Pipecat integration for flute-gateway multimodal voice agents.

This module provides pipecat-based real-time voice pipelines that wrap
flute-gateway's existing TTS/STT providers (VibeVoice, Ultimate-TTS, Whisper)
and integrate with TensorZero for LLM processing.

Key Components:
    processors/ - Frame processors wrapping existing providers
    transports/ - WebSocket and WebRTC transport adapters
    pipelines/  - Pre-built voice agent pipelines
    edge/       - ESP32 and IoT device bridges

Example:
    >>> from pipecat import build_voice_agent_pipeline
    >>> pipeline = await build_voice_agent_pipeline(transport, persona="default")
    >>> await PipelineRunner().run(pipeline)
"""

from .config import PipecatConfig, get_pipecat_config

__all__ = [
    "PipecatConfig",
    "get_pipecat_config",
]

__version__ = "0.1.0"
