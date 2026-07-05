# clap-embed (:8108)

Stateless deterministic CLAP embedder (MOF lattice node). Loads
`laion/larger_clap_music` (Apache-2.0) and returns 512-d audio/text embeddings.

- `GET  /healthz` — model id/rev, sr, clip params, dim.
- `POST /embed/audio` (multipart `file`) → `{embedding:[512], model_rev, sr}`.
- `POST /embed/text` (`{texts:[...]}`) → `{embeddings:[[512],...]}`.
- `GET  /metrics` — Prometheus.
- Optional NATS: `audio.embed.request.v1` → `audio.embed.result.v1` (set `NATS_URL`).

Deterministic: fixed 10 s non-overlapping windows, mean-pooled, L2-normalised,
rounded to 7 dp. Same audio + revision → identical embedding.

Env: `CLAP_MODEL_ID`, `CLAP_MODEL_REVISION`, `CLAP_SAMPLE_RATE`, `CLAP_CLIP_SECONDS`,
`CLAP_HOP_SECONDS`, `CLAP_DEVICE` (cpu|cuda|mps), `CLAP_EMBED_PORT` (8108), `NATS_URL`,
`MODEL_REGISTRY_URL`.

Test: `python -m pytest tests/ -v` (model tests gated by `CLAP_RUN_MODEL_TESTS=1`).
