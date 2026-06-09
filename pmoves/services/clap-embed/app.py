"""clap-embed FastAPI service — stateless deterministic CLAP embedder (port 8108)."""
from __future__ import annotations

import io
import logging
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


def create_app() -> FastAPI:
    app = FastAPI(title="clap-embed", version="1.0.0")

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
            # starved on the event loop.
            audio, sr = await run_in_threadpool(librosa.load, io.BytesIO(raw), sr=None, mono=True)
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

    @app.on_event("startup")
    async def _start_nats():
        # When NATS_URL is configured, subscribe the responder to
        # audio.embed.request.v1 so the advertised NATS path actually works.
        # NATS is optional — failure to connect must not break the HTTP service.
        app.state.nats_conn = None
        if not Config.NATS_URL:
            return
        try:
            from nats_responder import run_responder
            app.state.nats_conn = await run_responder(get_embedder())
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

    @app.on_event("shutdown")
    async def _stop_nats():
        nc = getattr(app.state, "nats_conn", None)
        if nc is not None:
            try:
                await nc.drain()
            except Exception:
                pass

    return app


app = create_app()
