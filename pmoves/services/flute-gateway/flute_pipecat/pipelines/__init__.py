"""Pre-built pipecat pipelines for common voice agent use cases.

Pipelines:
    build_voice_agent_pipeline: Standard VAD → STT → LLM → TTS pipeline
    build_tts_only_pipeline: Text-to-speech streaming only
    build_stt_only_pipeline: Speech-to-text streaming only
"""

from .voice_agent import (
    VoiceAgentConfig,
    build_voice_agent_pipeline,
    build_tts_only_pipeline,
    build_stt_only_pipeline,
)

__all__ = [
    "VoiceAgentConfig",
    "build_voice_agent_pipeline",
    "build_tts_only_pipeline",
    "build_stt_only_pipeline",
]
