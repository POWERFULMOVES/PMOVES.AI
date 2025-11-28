# TensorZero Gateway Observability (ClickHouse)

The 2025.10.7 gateway release moved ClickHouse settings under `gateway.observability.clickhouse`. The legacy `[clickhouse]` table no longer parses and results in `clickhouse: unknown field` during boot.

## Current status (local bundles)
- Observability is **disabled by default** so the gateway can start without ClickHouse credentials. ClickHouse still runs alongside the gateway profile (`make -C pmoves up-tensorzero`) so metrics can be enabled later.
- The `gateway.observability.clickhouse` table now ships populated with PMOVES defaults that match the self-hosted ClickHouse launched by the profile (URL/user/password/database all `tensorzero` against `http://tensorzero-clickhouse:8123`). Override the env vars if you point the gateway at a remote ClickHouse.
- Enable observability by supplying credentials (or relying on the bundled defaults) and flipping `observability.enabled` to `true` in `pmoves/tensorzero/config/tensorzero.toml`.

## Enabling metrics
1. The `[gateway.observability.clickhouse]` block already lives in `pmoves/tensorzero/config/tensorzero.toml` with PMOVES-branded defaults.
2. Populate the secrets in your environment (the bundled profile pre-populates PMOVES defaults in `env.shared.example`; override as needed for remote ClickHouse):
   - `TENSORZERO_OBS_CLICKHOUSE_URL` (default `http://tensorzero-clickhouse:8123`)
   - `TENSORZERO_OBS_CLICKHOUSE_DB` (default `tensorzero`)
   - `TENSORZERO_OBS_CLICKHOUSE_USER` (default `tensorzero`)
   - `TENSORZERO_OBS_CLICKHOUSE_PASSWORD` (default `tensorzero`)
3. Flip `observability.enabled` to `true` and restart: `make -C pmoves up-tensorzero`.
1. Update `pmoves/tensorzero/config/tensorzero.toml` with the new `gateway.observability.clickhouse.*` block from the official docs.
2. Add credentials via env vars (`TENSORZERO_CLICKHOUSE_URL`, etc.) as documented upstream.
3. Rebuild/restart the gateway profile: `make up-tensorzero`.

```toml
[gateway]
observability.enabled = true

[gateway.observability.clickhouse]
url = "env::TENSORZERO_OBS_CLICKHOUSE_URL"
database = "env::TENSORZERO_OBS_CLICKHOUSE_DB"
username = "env::TENSORZERO_OBS_CLICKHOUSE_USER"
password = "env::TENSORZERO_OBS_CLICKHOUSE_PASSWORD"
```

If you prefer hard-coded values for local-only testing, replace the `env::` entries with static strings (e.g., `url = "http://tensorzero-clickhouse:8123"`, `database = "tensorzero"`).

## Verification steps
- Run `curl http://127.0.0.1:8123/ping` to confirm ClickHouse is reachable.
- Start the gateway and check for `observability exporter configured` in the logs; errors about unknown fields should disappear once the new table is present.
- Query recent points to confirm ingestion (example for traces table will vary with the upstream schema). Until we finalize the table names, expect write errors if the block is omitted or credentials are missing.
