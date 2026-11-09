# clip-embed (:8109)

Stateless deterministic CLIP embedder for images and text. Loads
`openai/clip-vit-large-patch14` (MIT) and returns 768-d embeddings.

- `GET  /healthz` — model id/rev, dim.
- `POST /embed/image` (multipart `file`) → `{embedding:[768], model_rev}`.
- `POST /embed/text` (`{texts:[...]}`) → `{embeddings:[[768],...]}`.
- `GET  /metrics` — Prometheus.

Deterministic: L2-normalised, rounded to 7 dp. Same image + revision → identical embedding.

Env: `CLIP_MODEL_ID`, `CLIP_MODEL_REVISION`, `CLIP_DEVICE` (cpu|cuda|mps),
`CLIP_EMBED_PORT` (8109), `MODEL_REGISTRY_URL`.

Test: `python -m pytest tests/ -v` (model tests gated by `CLIP_RUN_MODEL_TESTS=1`).
