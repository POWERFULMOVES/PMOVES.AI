"""clap-embed FastAPI service — stateless deterministic CLAP embedder (port 8108)."""
from __future__ import annotations

import io
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from urllib.parse import urlsplit, urlunsplit

import librosa
import numpy as np
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

from config import Config
from embedder import ClapHFModel, Embedder

logger = logging.getLogger("clap-embed")


def _redact_url(url: str | None) -> str:
    """Strip userinfo (user:pass@) from a URL so it is safe to log.

    NATS URLs frequently embed credentials (nats://user:pass@host:4222); logging
    them raw would leak secrets into observability pipelines.
    """
    if not url:
        return "<unset>"
    try:
        p = urlsplit(url)
        if p.username or p.password:
            netloc = (p.hostname or "") + (f":{p.port}" if p.port else "")
            return urlunsplit((p.scheme, netloc, p.path, p.query, p.fragment))
    except Exception:
        return "<redacted>"
    return url


REQUESTS = Counter("clap_embed_requests_total", "Total requests", ["endpoint"])
LATENCY = Histogram("clap_embed_seconds", "Embed latency seconds", ["endpoint"])

_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        model = ClapHFModel(Config.MODEL_ID, Config.MODEL_REVISION, Config.DEVICE, Config.SR)
        _embedder = Embedder(model, Config.SR, Config.CLIP_SECONDS, Config.HOP_SECONDS)
    return _embedder


class TextRequest(BaseModel):
    texts: list[str]


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # --- startup: register with the model registry (non-fatal if offline) ---
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

    # --- startup: optional NATS responder (audio.embed.request.v1) ---
    app.state.nats_conn = None
    if Config.NATS_URL:
        try:
            from nats_responder import run_responder
            try:
                get_embedder()
            except Exception:
                pass
            app.state.nats_conn = await run_responder(get_embedder)
        except Exception as exc:
            # HTTP endpoints still serve, but the advertised NATS path is dead —
            # log it so the silent degradation is debuggable. Redact the URL and
            # avoid exc_info: NATS URLs/exceptions can echo embedded credentials.
            logger.warning(
                "clap-embed NATS responder failed to start (NATS_URL=%s): %s; "
                "HTTP endpoints remain available, NATS embed path disabled",
                _redact_url(Config.NATS_URL),
                type(exc).__name__,
            )
            app.state.nats_conn = None

    try:
        yield
    finally:
        # --- shutdown: drain NATS connection if one was established ---
        nc = getattr(app.state, "nats_conn", None)
        if nc is not None:
            try:
                await nc.drain()
            except Exception:
                pass


def create_app() -> FastAPI:
    app = FastAPI(title="clap-embed", version="1.0.0", lifespan=_lifespan)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "model_id": Config.MODEL_ID, "model_rev": Config.MODEL_REVISION,
                "sr": Config.SR, "clip_seconds": Config.CLIP_SECONDS, "dim": Config.EMBED_DIM}

    @app.post("/embed/audio")
    async def embed_audio(
        request: Request,
        file: UploadFile = File(...),
        emb: Embedder = Depends(get_embedder),
    ):
        REQUESTS.labels("embed_audio").inc()
        with LATENCY.labels("embed_audio").time():
            cap = Config.MAX_UPLOAD_BYTES
            # Cheap reject when the client declares an oversized body.
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) > cap:
                        raise HTTPException(status_code=413, detail="audio upload too large")
                except ValueError:
                    pass  # malformed header; fall through to streaming guard
            # Streaming guard: read at most cap+1 bytes so an undeclared or lying
            # Content-Length can't force an unbounded read into memory.
            raw = await file.read(cap + 1)
            if len(raw) > cap:
                raise HTTPException(status_code=413, detail="audio upload too large")
            # Offload blocking decode + inference so concurrent requests aren't
            # starved on the event loop. Write to a temp file so librosa's
            # audioread (ffmpeg) fallback handles m4a/opus/mp3 that soundfile
            # (libsndfile) can't decode from a BytesIO buffer.
            suffix = os.path.splitext(file.filename or ".wav")[1] or ".wav"
            tmp_path = None
            try:
                fd, tmp_path = tempfile.mkstemp(suffix=suffix)
                os.close(fd)
                with open(tmp_path, "wb") as f:
                    f.write(raw)
                audio, sr = await run_in_threadpool(librosa.load, tmp_path, sr=None, mono=True)
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            vec = await run_in_threadpool(
                emb.embed_audio, np.asarray(audio, dtype="float32"), int(sr)
            )
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

    return app


app = create_app()
