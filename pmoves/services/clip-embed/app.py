"""clip-embed FastAPI service — stateless deterministic CLIP image/text embedder (port 8109)."""
from __future__ import annotations

import io
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlsplit, urlunsplit

import numpy as np
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

from config import Config
from embedder import ClipHFModel, Embedder

logger = logging.getLogger("clip-embed")


try:
    from services.common.redact import redact_url
except ImportError:  # image ships without services/common; copy of services/common/redact.py
    import re as _re

    def redact_url(url):
        if url is None:
            return ""
        text = str(url)
        spans = []
        prev_at = -1
        for match in _re.finditer("@", text):
            at = match.start()
            scheme = text.find("://", prev_at + 1, at)
            if scheme >= 0:
                spans.append([scheme + 3, at])
            elif spans:
                spans[-1][1] = at
            else:
                spans.append([0, at])
            prev_at = at
        out = []
        pos = 0
        for start, end in spans:
            out.append(text[pos:start] + "***")
            pos = end
        out.append(text[pos:])
        return _re.sub(
            r"(?i)([?&;#][\w.\-]*(?:password|passwd|pwd|pass|secret|token|api[_\-]?key|auth|signature|sig)[\w.\-]*=)[^&#;\s]*",
            r"\1***",
            "".join(out),
        )


# Former private redactor; fail-open on unencoded / # ? , in passwords (PR #3244).
_redact_url = redact_url


REQUESTS = Counter("clip_embed_requests_total", "Total requests", ["endpoint"])
LATENCY = Histogram("clip_embed_seconds", "Embed latency seconds", ["endpoint"])

_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        model = ClipHFModel(Config.MODEL_ID, Config.MODEL_REVISION, Config.DEVICE)
        _embedder = Embedder(model)
    return _embedder


class TextRequest(BaseModel):
    texts: list[str]


@asynccontextmanager
async def _lifespan(app: FastAPI):
    import httpx
    payload = {
        "service": "clip-embed",
        "model_id": Config.MODEL_ID,
        "revision": Config.MODEL_REVISION,
        "license": "MIT",
        "provenance": "openai/clip-vit-large-patch14",
        "endpoint": f"http://clip-embed:{Config.PORT}",
    }
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            await c.post(f"{Config.REGISTRY_URL}/api/deployments", json=payload)
    except Exception:
        pass

    try:
        yield
    finally:
        pass


def create_app() -> FastAPI:
    app = FastAPI(title="clip-embed", version="1.0.0", lifespan=_lifespan)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "model_id": Config.MODEL_ID, "model_rev": Config.MODEL_REVISION,
                "dim": Config.EMBED_DIM}

    @app.post("/embed/image")
    async def embed_image(
        request: Request,
        file: UploadFile = File(...),
        emb: Embedder = Depends(get_embedder),
    ):
        REQUESTS.labels("embed_image").inc()
        with LATENCY.labels("embed_image").time():
            cap = Config.MAX_UPLOAD_BYTES
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) > cap:
                        raise HTTPException(status_code=413, detail="image upload too large")
                except ValueError:
                    pass
            raw = await file.read(cap + 1)
            if len(raw) > cap:
                raise HTTPException(status_code=413, detail="image upload too large")
            from PIL import Image
            img = await run_in_threadpool(lambda: np.array(Image.open(io.BytesIO(raw)).convert("RGB")))
            vec = await run_in_threadpool(emb.embed_image, img)
        return {"embedding": vec, "model_rev": Config.MODEL_REVISION}

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
