"""OmniVoice client abstraction. The voice operator depends on the OmniVoiceClient
interface (synthesize -> audio file path); tests inject FakeOmniVoiceClient, and
production uses RealOmniVoiceClient (gradio_client to the OmniVoice demo at :8001).

The RealOmniVoiceClient transport was confirmed against a live OmniVoice 0.1.5 demo
on 2026-06-10 (4090): the demo exposes two named gradio endpoints, NOT a "/tts" call.
  /_design_fn(text, lang, ns, gs, dn, sp, du, pp, po, gender, age, pitch,
              whisper, accent, dialect) -> (audio_path, status)
  /_clone_fn(text, lang, ref_aud, ref_text, instruct, ns, gs, dn, sp, du, pp, po)
              -> (audio_path, status)
`du` is Duration (seconds); du<=0 means auto-estimate. Both return a (audio, status)
tuple whose first element is a server temp .wav path, copied into out_dir to persist."""
import shutil
from pathlib import Path


class OmniVoiceError(Exception):
    """Raised when synthesis cannot be performed."""


class FakeOmniVoiceClient:
    """Deterministic, no-server client for unit tests: writes a stub .wav."""

    def __init__(self, out_dir):
        self.out_dir = Path(out_dir)

    def synthesize(self, *, text: str, voice_ref: str | None = None, voice_design: str | None = None) -> str:
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

    def synthesize(self, *, text: str, voice_ref: str | None = None, voice_design: str | None = None) -> str:
        if not text.strip():
            raise OmniVoiceError("empty text")
        from gradio_client import Client, handle_file
        client = Client(self.base_url)
        if voice_ref:
            # /_clone_fn args: (text, lang, ref_aud, ref_text, instruct, ns, gs, dn,
            # sp, du, pp, po). ref_aud = the reference audio file. Per OmniVoice docs,
            # `instruct` is the comma-separated speaker-attribute string (e.g.
            # "female, british accent") and stabilises the clone, so voice_design maps
            # to instruct. ref_text is the reference *transcript* (left empty here; the
            # demo's ASR fills it when enabled, or pass it explicitly in a later rev).
            result = client.predict(
                text, "Auto", handle_file(voice_ref), "", voice_design or "",
                32, 2.0, True, 1.0, 0, True, True,
                api_name="/_clone_fn",
            )
        else:
            # /_design_fn args: (text, lang, ns, gs, dn, sp, du, pp, po, + 6 attribute
            # dropdowns). The dropdowns default to "Auto" (model-chosen voice); a
            # structured voice_design can be threaded through them in a later rev.
            result = client.predict(
                text, "Auto", 32, 2.0, True, 1.0, 0, True, True,
                "Auto", "Auto", "Auto", "Auto", "Auto", "Auto",
                api_name="/_design_fn",
            )
        # Endpoints return (audio_path, status); persist the temp .wav into out_dir.
        audio = result[0] if isinstance(result, (tuple, list)) else result
        if not audio:
            raise OmniVoiceError("OmniVoice returned no audio")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        dest = self.out_dir / "voice.wav"
        try:
            shutil.copy(audio, dest)
        except (FileNotFoundError, PermissionError) as exc:
            raise OmniVoiceError(f"failed to persist audio from {audio}: {exc}") from exc
        return str(dest)
