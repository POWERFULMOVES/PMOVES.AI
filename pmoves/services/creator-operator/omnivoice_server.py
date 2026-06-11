"""Production OmniVoice voice server — the load-once counterpart to the gradio
try-it demo. Holds k2-fsa/OmniVoice in VRAM and serves `model.generate()` directly
(no gradio HTTP hop, no temp-file shuffle through a UI). The creator-operator's
voice path can target this instead of RealOmniVoiceClient for steady-state serving.

Security posture (loopback/mesh service, but hardened — internal endpoints are
common IDOR/SSRF targets):
  - `ref_audio` is an opaque catalog id resolved under OMNIVOICE_REFERENCE_VOICE_DIR,
    never a raw client-supplied filesystem path (path-traversal guard).
  - /synthesize is gated by an X-OmniVoice-Token header when OMNIVOICE_TOKEN is set.
  - errors return a generic message + correlation id; full detail is logged server-side.
  - the __main__ guard binds 127.0.0.1 by default.

Run (in a venv with `omnivoice`, fastapi, uvicorn installed):
    OMNIVOICE_LOAD_ASR=1 OMNIVOICE_TOKEN=... python omnivoice_server.py
    # or: ... python -m uvicorn omnivoice_server:app --host 127.0.0.1 --port 8002

Env:
    OMNIVOICE_MODEL                HF repo id / checkpoint path (default k2-fsa/OmniVoice)
    OMNIVOICE_DEVICE               device_map target (default cuda:0)
    OMNIVOICE_LOAD_ASR             "1" loads Whisper so ref_text is optional when cloning
    OMNIVOICE_REFERENCE_VOICE_DIR  catalog root for ref_audio ids (clone disabled if unset)
    OMNIVOICE_TOKEN                if set, required as X-OmniVoice-Token on /synthesize
    OMNIVOICE_HOST / OMNIVOICE_PORT  bind for the __main__ guard (default 127.0.0.1:8002)
"""
import logging
import os
import tempfile
import uuid
from pathlib import Path

import torch
import soundfile as sf
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger("omnivoice_server")

MODEL_ID = os.getenv("OMNIVOICE_MODEL", "k2-fsa/OmniVoice")
DEVICE = os.getenv("OMNIVOICE_DEVICE", "cuda:0")
LOAD_ASR = os.getenv("OMNIVOICE_LOAD_ASR", "0") == "1"
REFERENCE_VOICE_DIR = os.getenv("OMNIVOICE_REFERENCE_VOICE_DIR")  # catalog root for ref_audio
AUTH_TOKEN = os.getenv("OMNIVOICE_TOKEN")  # if set, required on /synthesize
SAMPLE_RATE = 24000  # OmniVoice emits 24 kHz waveforms (docs/OmniVoice.ipynb)

app = FastAPI(title="OmniVoice Production Server")
_state = {"model": None}


class SynthRequest(BaseModel):
    text: str
    instruct: str | None = None      # voice design: comma-separated attributes
    ref_audio: str | None = None     # voice clone: catalog id under REFERENCE_VOICE_DIR
    ref_text: str | None = None      # reference transcript (optional if LOAD_ASR)
    duration: float | None = None    # fixed seconds; overrides speed when set
    speed: float | None = None       # >1 faster, <1 slower; ignored if duration set


def _require_auth(token: str | None) -> None:
    """Constant-ish shared-secret gate. No-op only when OMNIVOICE_TOKEN is unset
    (loopback-only dev); production should always set it."""
    if AUTH_TOKEN and token != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


def _resolve_ref_audio(name: str) -> str:
    """Resolve a client-supplied ref_audio as an opaque id INSIDE the configured
    reference-voice catalog — never as a raw path. Rejects traversal/absolute/NUL
    and verifies the resolved path stays under the catalog root."""
    if not REFERENCE_VOICE_DIR:
        raise HTTPException(
            status_code=400,
            detail="ref_audio not supported (no OMNIVOICE_REFERENCE_VOICE_DIR configured)",
        )
    if (
        not name
        or "\x00" in name
        or ".." in Path(name).parts
        or Path(name).is_absolute()
        or (len(name) >= 2 and name[1] == ":")  # Windows drive letter
    ):
        raise HTTPException(status_code=400, detail="invalid ref_audio")
    base = Path(REFERENCE_VOICE_DIR).resolve()
    target = (base / name).resolve()
    if target != base and base not in target.parents:
        raise HTTPException(status_code=400, detail="invalid ref_audio")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="ref_audio not found")
    return str(target)


@app.on_event("startup")
def _load_model() -> None:
    from omnivoice import OmniVoice
    _state["model"] = OmniVoice.from_pretrained(
        MODEL_ID, device_map=DEVICE, dtype=torch.float16, load_asr=LOAD_ASR,
    )


@app.get("/healthz")
def healthz() -> dict:
    return {
        "status": "ok" if _state["model"] is not None else "loading",
        "model": MODEL_ID,
        "device": DEVICE,
        "asr": LOAD_ASR,
        "auth": bool(AUTH_TOKEN),
        "catalog": bool(REFERENCE_VOICE_DIR),
        "sample_rate": SAMPLE_RATE,
    }


@app.post("/synthesize")
def synthesize(req: SynthRequest, x_omnivoice_token: str | None = Header(default=None)):
    _require_auth(x_omnivoice_token)
    model = _state["model"]
    if model is None:
        raise HTTPException(status_code=503, detail="model not loaded yet")
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="empty text")
    # Only forward set knobs so the model applies its documented defaults otherwise.
    kw = {}
    if req.instruct is not None:
        kw["instruct"] = req.instruct
    if req.ref_audio is not None:
        if not LOAD_ASR and not (req.ref_text or "").strip():
            raise HTTPException(
                status_code=400,
                detail="ref_text required when cloning without ASR (set OMNIVOICE_LOAD_ASR=1)",
            )
        kw["ref_audio"] = _resolve_ref_audio(req.ref_audio)  # validated catalog path
    if req.ref_text is not None:
        kw["ref_text"] = req.ref_text
    if req.duration is not None:
        kw["duration"] = req.duration
    if req.speed is not None:
        kw["speed"] = req.speed
    try:
        audio = model.generate(text=req.text, **kw)
    except Exception as exc:
        # Log full detail server-side; return a generic message + correlation id so
        # an untrusted caller can't fingerprint internals via error text.
        err_id = uuid.uuid4().hex[:8]
        logger.exception("synthesis failed [%s]", err_id)
        raise HTTPException(status_code=500, detail=f"synthesis failed (ref {err_id})") from exc
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    sf.write(path, audio[0], SAMPLE_RATE)
    return FileResponse(path, media_type="audio/wav", filename="voice.wav")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("OMNIVOICE_HOST", "127.0.0.1"),  # loopback by default
        port=int(os.getenv("OMNIVOICE_PORT", "8002")),
    )
