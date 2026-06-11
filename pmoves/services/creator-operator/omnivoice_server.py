"""Production OmniVoice voice server — the load-once counterpart to the gradio
try-it demo. Holds k2-fsa/OmniVoice in VRAM and serves `model.generate()` directly
(no gradio HTTP hop, no temp-file shuffle through a UI). The creator-operator's
voice path can target this instead of RealOmniVoiceClient for steady-state serving.

Run (in a venv with `omnivoice`, fastapi, uvicorn installed):
    OMNIVOICE_LOAD_ASR=1 python -m uvicorn omnivoice_server:app --host 127.0.0.1 --port 8002

Env:
    OMNIVOICE_MODEL     HF repo id / checkpoint path (default k2-fsa/OmniVoice)
    OMNIVOICE_DEVICE    device_map target (default cuda:0)
    OMNIVOICE_LOAD_ASR  "1" loads Whisper so ref_text is optional when cloning
"""
import os
import tempfile

import torch
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

MODEL_ID = os.getenv("OMNIVOICE_MODEL", "k2-fsa/OmniVoice")
DEVICE = os.getenv("OMNIVOICE_DEVICE", "cuda:0")
LOAD_ASR = os.getenv("OMNIVOICE_LOAD_ASR", "0") == "1"
SAMPLE_RATE = 24000  # OmniVoice emits 24 kHz waveforms (docs/OmniVoice.ipynb)

app = FastAPI(title="OmniVoice Production Server")
_state = {"model": None}


class SynthRequest(BaseModel):
    text: str
    instruct: str | None = None      # voice design: comma-separated attributes
    ref_audio: str | None = None     # voice clone: reference audio path
    ref_text: str | None = None      # reference transcript (optional if LOAD_ASR)
    duration: float | None = None    # fixed seconds; overrides speed when set
    speed: float | None = None       # >1 faster, <1 slower; ignored if duration set


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
        "sample_rate": SAMPLE_RATE,
    }


@app.post("/synthesize")
def synthesize(req: SynthRequest):
    model = _state["model"]
    if model is None:
        raise HTTPException(status_code=503, detail="model not loaded yet")
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="empty text")
    if req.ref_audio and not LOAD_ASR and not (req.ref_text or "").strip():
        raise HTTPException(
            status_code=400,
            detail="ref_text required when cloning without ASR (set OMNIVOICE_LOAD_ASR=1)",
        )
    # Only forward set knobs so the model applies its documented defaults otherwise.
    kw = {}
    for name in ("instruct", "ref_audio", "ref_text", "duration", "speed"):
        val = getattr(req, name)
        if val is not None:
            kw[name] = val
    try:
        audio = model.generate(text=req.text, **kw)
    except Exception as exc:  # surface model failures as 500 with the reason
        raise HTTPException(status_code=500, detail=f"synthesis failed: {exc}") from exc
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    sf.write(path, audio[0], SAMPLE_RATE)
    return FileResponse(path, media_type="audio/wav", filename="voice.wav")
