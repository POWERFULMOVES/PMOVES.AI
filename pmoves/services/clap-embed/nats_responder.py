"""Optional NATS request/reply bridge for clap-embed.

Subjects: audio.embed.request.v1 -> audio.embed.result.v1.
Enabled only when NATS_URL is set. handle_request is pure (testable)."""
from __future__ import annotations

import base64
import io
import json

import librosa
import numpy as np

from config import Config

SUBJECT_REQUEST = "audio.embed.request.v1"
SUBJECT_RESULT = "audio.embed.result.v1"


def handle_request(data: bytes, embedder) -> bytes:
    try:
        msg = json.loads(data)
        audio_bytes = base64.b64decode(msg["audio_b64"])
        audio, sr = librosa.load(io.BytesIO(audio_bytes), sr=None, mono=True)
        vec = embedder.embed_audio(np.asarray(audio, dtype="float32"), int(sr))
        return json.dumps({
            "ok": True,
            "context_id": msg.get("context_id"),
            "embedding": vec,
            "model_rev": Config.MODEL_REVISION,
        }).encode()
    except Exception as exc:  # never crash the responder; flag the failure
        return json.dumps({"ok": False, "error": str(exc)}).encode()


async def run_responder(embedder):  # pragma: no cover - requires live NATS
    import nats
    nc = await nats.connect(Config.NATS_URL)

    async def _cb(m):
        result = handle_request(m.data, embedder)
        reply = m.reply or SUBJECT_RESULT
        await nc.publish(reply, result)

    await nc.subscribe(SUBJECT_REQUEST, cb=_cb)
    return nc
