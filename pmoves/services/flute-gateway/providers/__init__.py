"""Voice provider integrations for Flute Gateway."""

from .base import VoiceProvider
from .vibevoice import VibeVoiceBusyError, VibeVoiceNoAudioError, VibeVoiceProvider
from .voicebox import (
    VoiceboxBusyError,
    VoiceboxError,
    VoiceboxNoProfileError,
    VoiceboxProvider,
)
from .omnivoice import (
    OmniVoiceBusyError,
    OmniVoiceError,
    OmniVoiceProvider,
)
from .whisper import WhisperProvider
from .ultimate_tts import UltimateTTSError, UltimateTTSProvider
from .cloning import VoiceCloningProvider, CloningSynthesisProvider

__all__ = [
    "VoiceProvider",
    "VibeVoiceProvider",
    "VibeVoiceNoAudioError",
    "VibeVoiceBusyError",
    "VoiceboxProvider",
    "VoiceboxError",
    "VoiceboxBusyError",
    "VoiceboxNoProfileError",
    "OmniVoiceProvider",
    "OmniVoiceError",
    "OmniVoiceBusyError",
    "WhisperProvider",
    "UltimateTTSProvider",
    "UltimateTTSError",
    "VoiceCloningProvider",
    "CloningSynthesisProvider",
]
