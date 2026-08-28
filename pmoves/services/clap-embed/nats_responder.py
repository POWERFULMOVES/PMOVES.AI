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
        b64 = msg["audio_b64"]
        cap = Config.MAX_UPLOAD_BYTES
        if isinstance(b64, str) and (len(b64) * 3) // 4 > cap:
            raise ValueError("audio payload too large")
        audio_bytes = base64.b64decode(b64)
        if len(audio_bytes) > cap:
            raise ValueError("audio payload too large")
        audio, sr = librosa.load(io.BytesIO(audio_bytes), sr=None, mono=True)
        vec = embedder.embed_audio(np.asarray(audio, dtype="float32"), int(sr))
        return json.dumps({
            "ok": True,
            "context_id": msg.get("context_id"),
            "embedding": vec,
            "model_rev": Config.MODEL_REVISION,
        }).encode()
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}).encode()


async def run_responder(get_embedder_fn, max_retries=3):
    """Start NATS responder. Accepts a callable that returns the embedder (lazy loading)."""
    import asyncio
    import nats
    last_exc = None
    for attempt in range(max_retries):
        try:
            nc = await nats.connect(Config.NATS_URL, connect_timeout=5)

            async def _cb(m):
                try:
                    embedder = get_embedder_fn()
                    result = handle_request(m.data, embedder)
                except Exception as exc:
                    result = json.dumps({"ok": False, "error": f"embedder not ready: {exc}"}).encode()
                reply = m.reply or SUBJECT_RESULT
                await nc.publish(reply, result)

            await nc.subscribe(SUBJECT_REQUEST, cb=_cb)
            return nc
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                await asyncio.sleep(2 * (attempt + 1))
    raise last_exc
