"""clap-embed FastAPI service — stateless deterministic CLAP embedder (port 8108)."""
from __future__ import annotations

import io

import librosa
import numpy as np
from fastapi import Depends, FastAPI, File, UploadFile
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

from config import Config
from embedder import ClapHFModel, Embedder

REQUESTS = Counter("clap_embed_requests_total", "Total requests", ["endpoint"])
LATENCY = Histogram("clap_embed_seconds", "Embed latency seconds", ["endpoint"])

_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        model = ClapHFModel(Config.MODEL_ID, Config.MODEL_REVISION, Config.DEVICE)
        _embedder = Embedder(model, Config.SR, Config.CLIP_SECONDS, Config.HOP_SECONDS)
    return _embedder


class TextRequest(BaseModel):
    texts: list[str]


def create_app() -> FastAPI:
    app = FastAPI(title="clap-embed", version="1.0.0")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "model_id": Config.MODEL_ID, "model_rev": Config.MODEL_REVISION,
                "sr": Config.SR, "clip_seconds": Config.CLIP_SECONDS, "dim": Config.EMBED_DIM}

    @app.post("/embed/audio")
    async def embed_audio(file: UploadFile = File(...), emb: Embedder = Depends(get_embedder)):
        REQUESTS.labels("embed_audio").inc()
        with LATENCY.labels("embed_audio").time():
            raw = await file.read()
            audio, sr = librosa.load(io.BytesIO(raw), sr=None, mono=True)
            vec = emb.embed_audio(np.asarray(audio, dtype="float32"), int(sr))
        return {"embedding": vec, "model_rev": Config.MODEL_REVISION, "sr": Config.SR}

    @app.post("/embed/text")
    def embed_text(req: TextRequest, emb: Embedder = Depends(get_embedder)):
        REQUESTS.labels("embed_text").inc()
        with LATENCY.labels("embed_text").time():
            vecs = emb.embed_text(req.texts)
            out = [[round(float(x), 7) for x in row] for row in np.asarray(vecs)]
        return {"embeddings": out, "model_rev": Config.MODEL_REVISION}

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.on_event("startup")
    async def _register():
        import httpx
        payload = {
            "service": "clap-embed",
            "model_id": Config.MODEL_ID,
            "revision": Config.MODEL_REVISION,
            "license": "Apache-2.0",
            "provenance": "laion/larger_clap_music",
            "endpoint": f"http://clap-embed:{Config.PORT}",
        }
        try:
            async with httpx.AsyncClient(timeout=4) as c:
                await c.post(f"{Config.REGISTRY_URL}/api/deployments", json=payload)
        except Exception:
            pass  # registry offline is non-fatal; service still serves

    return app


app = create_app()
