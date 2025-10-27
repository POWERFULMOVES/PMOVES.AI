# TensorZero Gateway Observability (Pending)

The 2025.10.7 gateway release changed the configuration schema: the legacy `[clickhouse]` block no longer parses (see gateway logs complaining about `clickhouse: unknown field`).

In this update we disabled the old block so the gateway could boot. To re-enable metrics once we migrate, follow these steps:

1. Update `pmoves/tensorzero/config/tensorzero.toml` with the new `gateway.observability.clickhouse.*` block from the official docs.
2. Add credentials via env vars (`TENSORZERO_OBS_CLICKHOUSE_URL`, etc.) as documented upstream.
3. Rebuild/restart the gateway profile: `make up-tensorzero`.

Until that migration happens, ClickHouse persists but no writes occur (as confirmed by gateway logs).

