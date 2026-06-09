"""OmniVoice client abstraction. The voice operator depends on the OmniVoiceClient
interface (synthesize -> audio file path); tests inject FakeOmniVoiceClient, and
production uses RealOmniVoiceClient (gradio_client to the OmniVoice demo at :8001).
The transport is validated only at the live test (CREATOR_VOICE_TEST)."""
from pathlib import Path


class OmniVoiceError(Exception):
    """Raised when synthesis cannot be performed."""


class FakeOmniVoiceClient:
    """Deterministic, no-server client for unit tests: writes a stub .wav."""

    def __init__(self, out_dir):
        self.out_dir = Path(out_dir)

    def synthesize(self, *, text: str, voice_ref: str = None, voice_design: str = None) -> str:
        if not text.strip():
            raise OmniVoiceError("empty text")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / "voice.wav"
        # Minimal valid WAV header (44 bytes) + no samples — enough to prove a file.
        path.write_bytes(b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
                         b"\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
        return str(path)


class RealOmniVoiceClient:  # pragma: no cover - requires live OmniVoice at :8001
    """Calls the OmniVoice demo via gradio_client. Validated only at the live test."""

    def __init__(self, base_url: str = "http://127.0.0.1:8001", out_dir: str = "."):
        self.base_url = base_url
        self.out_dir = Path(out_dir)

    def synthesize(self, *, text: str, voice_ref: str = None, voice_design: str = None) -> str:
        if not text.strip():
            raise OmniVoiceError("empty text")
        from gradio_client import Client
        client = Client(self.base_url)
        # The exact endpoint name is confirmed at the live test; assemble_result
        # records whatever path OmniVoice returns.
        result = client.predict(text, voice_ref or voice_design or "", api_name="/tts")
        return str(result)
