"""Voice agent pipeline builder for pipecat.

Composes STT → LLM → TTS pipelines for conversational voice agents
using flute-gateway providers.

Pipelines:
    build_voice_agent_pipeline: Standard duplex voice conversation
    build_tts_only_pipeline: Text-to-speech only (no STT/LLM)
    build_stt_only_pipeline: Speech-to-text only (no LLM/TTS)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.processors.frame_processor import FrameProcessor

logger = logging.getLogger(__name__)

# Pipecat imports - gracefully handle if not installed
try:
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineTask
    from pipecat.processors.aggregators.llm_response import LLMResponseAggregator
    from pipecat.processors.aggregators.sentence import SentenceAggregator
    from pipecat.services.silero_vad import SileroVAD

    PIPECAT_AVAILABLE = True
except ImportError:
    PIPECAT_AVAILABLE = False

    # Stub classes
    class Pipeline:  # type: ignore[no-redef]
        """Stub Pipeline for when pipecat not installed."""
        pass

    class PipelineRunner:  # type: ignore[no-redef]
        """Stub PipelineRunner for when pipecat not installed."""
        pass

    class PipelineTask:  # type: ignore[no-redef]
        """Stub PipelineTask for when pipecat not installed."""
        pass


# Import our processors
from ..processors.vibevoice import VibeVoiceTTSProcessor
from ..processors.whisper import WhisperSTTProcessor
from ..processors.tensorzero import TensorZeroLLMProcessor
from ..transports.fastapi_ws import FluteFastAPIWebsocketTransport


class VoiceAgentConfig:
    """Configuration for voice agent pipeline.

    Attributes:
        persona: Name of persona to use (determines system prompt).
        voice: TTS voice name (default: "default").
        llm_model: Model name for TensorZero (default: "claude-sonnet-4-5").
        max_tokens: Maximum LLM response tokens.
        temperature: LLM sampling temperature.
        vad_threshold: Voice Activity Detection threshold.
        enable_interruption: Allow user to interrupt agent speech.
        system_prompt: Optional override for persona system prompt.
    """

    def __init__(
        self,
        persona: str = "assistant",
        voice: str = "default",
        llm_model: str = "claude-sonnet-4-5",
        max_tokens: int = 256,
        temperature: float = 0.7,
        vad_threshold: float = 0.5,
        enable_interruption: bool = True,
        system_prompt: Optional[str] = None,
    ):
        """Initialize voice agent configuration."""
        self.persona = persona
        self.voice = voice
        self.llm_model = llm_model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.vad_threshold = vad_threshold
        self.enable_interruption = enable_interruption
        self.system_prompt = system_prompt


async def build_voice_agent_pipeline(
    transport: FluteFastAPIWebsocketTransport,
    config: Optional[VoiceAgentConfig] = None,
    vibevoice_provider: Optional[Any] = None,
    whisper_provider: Optional[Any] = None,
    tensorzero_url: str = "http://localhost:3030",
) -> "Pipeline":
    """Build a complete voice agent pipeline.

    Creates a duplex conversation pipeline:
    VAD → STT → LLM → TTS → Audio Output

    Args:
        transport: WebSocket transport for audio I/O.
        config: Voice agent configuration.
        vibevoice_provider: Optional VibeVoice provider instance.
        whisper_provider: Optional Whisper provider instance.
        tensorzero_url: TensorZero gateway URL.

    Returns:
        Pipeline ready for execution.

    Raises:
        ImportError: If pipecat not installed.
        ValueError: If required providers not available.

    Example:
        >>> transport = FluteFastAPIWebsocketTransport(websocket, params)
        >>> config = VoiceAgentConfig(persona="assistant", voice="default")
        >>> pipeline = await build_voice_agent_pipeline(transport, config)
        >>> await PipelineRunner().run(pipeline)
    """
    if not PIPECAT_AVAILABLE:
        raise ImportError(
            "pipecat-ai is required for voice agent pipelines. "
            "Install with: pip install pipecat-ai[silero]"
        )

    config = config or VoiceAgentConfig()

    # Build processor chain
    processors: List["FrameProcessor"] = []

    # 1. Voice Activity Detection (Silero)
    try:
        vad = SileroVAD(threshold=config.vad_threshold)
        processors.append(vad)
        logger.info("Added Silero VAD (threshold=%.2f)", config.vad_threshold)
    except Exception as e:
        logger.warning("Failed to initialize Silero VAD: %s", e)

    # 2. Speech-to-Text (Whisper)
    if whisper_provider:
        stt = WhisperSTTProcessor(provider=whisper_provider)
        processors.append(stt)
        logger.info("Added Whisper STT processor")
    else:
        logger.warning("No Whisper provider - STT disabled")

    # 3. Sentence aggregation (buffer transcription until sentence complete)
    try:
        sentence_aggregator = SentenceAggregator()
        processors.append(sentence_aggregator)
    except Exception:
        logger.debug("SentenceAggregator not available")

    # 4. LLM (TensorZero)
    llm = TensorZeroLLMProcessor(
        base_url=tensorzero_url,
        model=config.llm_model,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        stream=True,
    )
    processors.append(llm)
    logger.info("Added TensorZero LLM (model=%s)", config.llm_model)

    # 5. LLM response aggregation (for context management)
    try:
        llm_aggregator = LLMResponseAggregator()
        processors.append(llm_aggregator)
    except Exception:
        logger.debug("LLMResponseAggregator not available")

    # 6. Text-to-Speech (VibeVoice)
    if vibevoice_provider:
        tts = VibeVoiceTTSProcessor(
            provider=vibevoice_provider,
            voice=config.voice,
        )
        processors.append(tts)
        logger.info("Added VibeVoice TTS (voice=%s)", config.voice)
    else:
        logger.warning("No VibeVoice provider - TTS disabled")

    # Create pipeline
    pipeline = Pipeline(processors)

    logger.info(
        "Built voice agent pipeline: %d processors",
        len(processors)
    )

    return pipeline


async def build_tts_only_pipeline(
    transport: FluteFastAPIWebsocketTransport,
    vibevoice_provider: Any,
    voice: str = "default",
) -> "Pipeline":
    """Build a TTS-only pipeline.

    For streaming text-to-speech without STT or LLM.

    Args:
        transport: WebSocket transport.
        vibevoice_provider: VibeVoice provider instance.
        voice: TTS voice name.

    Returns:
        Pipeline for TTS streaming.
    """
    if not PIPECAT_AVAILABLE:
        raise ImportError("pipecat-ai required")

    tts = VibeVoiceTTSProcessor(
        provider=vibevoice_provider,
        voice=voice,
    )

    pipeline = Pipeline([tts])
    logger.info("Built TTS-only pipeline")

    return pipeline


async def build_stt_only_pipeline(
    transport: FluteFastAPIWebsocketTransport,
    whisper_provider: Any,
) -> "Pipeline":
    """Build an STT-only pipeline.

    For streaming speech-to-text without LLM or TTS.

    Args:
        transport: WebSocket transport.
        whisper_provider: Whisper provider instance.

    Returns:
        Pipeline for STT streaming.
    """
    if not PIPECAT_AVAILABLE:
        raise ImportError("pipecat-ai required")

    # VAD
    try:
        vad = SileroVAD(threshold=0.5)
        processors = [vad]
    except Exception:
        processors = []

    # STT
    stt = WhisperSTTProcessor(provider=whisper_provider)
    processors.append(stt)

    pipeline = Pipeline(processors)
    logger.info("Built STT-only pipeline")

    return pipeline


# Export for convenient imports
__all__ = [
    "VoiceAgentConfig",
    "build_voice_agent_pipeline",
    "build_tts_only_pipeline",
    "build_stt_only_pipeline",
]
