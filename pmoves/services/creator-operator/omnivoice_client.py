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
import os
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


class ServerOmniVoiceClient:
    """Routes synthesis to the production OmniVoice FastAPI server (omnivoice_server.py,
    default http://127.0.0.1:8002) over HTTP — the load-once steady-state path, as
    opposed to RealOmniVoiceClient's gradio try-it demo. Same OmniVoiceClient interface
    (`synthesize -> wav path`), so run_voice / the voice operator are unchanged.

    Contract mapping onto POST /synthesize {text, instruct?, ref_audio?, ...}:
      - voice_design -> instruct   (comma-separated speaker-attribute string)
      - voice_ref    -> ref_audio  (opaque catalog id; the server resolves it under
                                    OMNIVOICE_REFERENCE_VOICE_DIR — never a raw path)
    The X-OmniVoice-Token header is sent from env OMNIVOICE_TOKEN when set (matching the
    server's gate). The returned wav body is written to out_dir/voice.wav.

    The httpx transport is injectable (`transport=`) so unit tests drive a fake
    httpx.MockTransport with no live server; the default live path is pragma-excluded.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8002", out_dir: str = ".",
                 token: str | None = None, transport=None, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.out_dir = Path(out_dir)
        # Explicit token wins; otherwise read the server's shared-secret env at call time
        # of construction. None means "send no header" (loopback dev with no gate).
        self.token = token if token is not None else os.getenv("OMNIVOICE_TOKEN")
        self._transport = transport
        self._timeout = timeout

    def synthesize(self, *, text: str, voice_ref: str | None = None, voice_design: str | None = None) -> str:
        if not text.strip():
            raise OmniVoiceError("empty text")
        payload: dict = {"text": text}
        if voice_design:
            payload["instruct"] = voice_design       # voice design -> instruct
        if voice_ref:
            payload["ref_audio"] = voice_ref          # catalog id -> ref_audio
        headers = {}
        if self.token:
            headers["X-OmniVoice-Token"] = self.token

        import httpx

        client = self._build_client()
        try:
            resp = client.post(
                f"{self.base_url}/synthesize", json=payload, headers=headers,
            )
        except httpx.HTTPError as exc:  # pragma: no cover - live transport failure
            raise OmniVoiceError(f"OmniVoice request failed: {exc}") from exc
        finally:
            client.close()

        if resp.status_code != 200:
            raise OmniVoiceError(
                f"OmniVoice server returned {resp.status_code}: {resp.text[:200]}"
            )
        body = resp.content
        if not body:
            raise OmniVoiceError("OmniVoice server returned empty body")

        self.out_dir.mkdir(parents=True, exist_ok=True)
        dest = self.out_dir / "voice.wav"
        dest.write_bytes(body)
        return str(dest)

    def _build_client(self):
        """httpx.Client factory. Tests inject a fake httpx.MockTransport; the default
        (real network) branch is pragma-excluded as it needs the live :8002 server."""
        import httpx

        if self._transport is not None:
            return httpx.Client(transport=self._transport, timeout=self._timeout)
        return httpx.Client(timeout=self._timeout)  # pragma: no cover - live HTTP path
