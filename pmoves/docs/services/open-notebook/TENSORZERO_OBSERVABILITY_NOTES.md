# TensorZero Gateway Observability (Pending)

The 2025.10.7 gateway release changed the configuration schema: the legacy `[clickhouse]` block no longer parses (see gateway logs complaining about `clickhouse: unknown field`).

In this update we disabled the old block so the gateway could boot. To re-enable metrics once we migrate, follow these steps:

1. Update `pmoves/tensorzero/config/tensorzero.toml` with the new `gateway.observability.clickhouse.*` block from the official docs.
2. Add credentials via env vars (`TENSORZERO_CLICKHOUSE_URL`, etc.) as documented upstream.
3. Rebuild/restart the gateway profile: `make up-tensorzero`.

Until that migration happens, ClickHouse persists but no writes occur (as confirmed by gateway logs).

## 2025-10-27

- Restarted the gateway after confirming the trimmed `tensorzero.toml` ships with no legacy `[clickhouse]` block. Logs now show the 2025.10.7 gateway binding successfully on `0.0.0.0:3000` with observability disabled.
- ClickHouse itself remains healthy (`curl http://127.0.0.1:8123/ping` → `Ok.`); leave the container running so we can re-enable metrics once the gateway schema stabilises.
- Internal services should target `http://tensorzero-gateway:3000` while host-side curls can continue to use `http://localhost:3030`. The OpenAI-compatible embeddings endpoint still resolves the legacy `gemma_embed_local` identifier (backed by Ollama `embeddinggemma:300m`); keep an eye on future releases that enforce the `tensorzero::model::` prefix mentioned in gateway warnings.
- The gateway runs from the upstream `tensorzero/gateway` container published by the TensorZero team; the companion ClickHouse service uses `clickhouse/clickhouse-server`. Remember to `ollama pull embeddinggemma:300m` on the host that serves `OLLAMA_API_BASE` so `gemma_embed_local` can start answering requests immediately after boot.
