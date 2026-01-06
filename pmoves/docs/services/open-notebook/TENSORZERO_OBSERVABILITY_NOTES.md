# TensorZero Gateway Observability (ClickHouse)

**IMPORTANT:** As of TensorZero version 2025.11.6, ClickHouse configuration has been moved entirely to environment variables. The `[clickhouse]` and `[gateway.observability.clickhouse]` TOML sections are no longer valid and will cause configuration errors.

## Current status (local bundles)
- Observability is **disabled by default** so the gateway can start without ClickHouse credentials.
- ClickHouse still runs alongside the gateway profile (`make -C pmoves up-tensorzero`) so metrics can be enabled later.
- ClickHouse connection is configured via the `TENSORZERO_CLICKHOUSE_URL` environment variable (not in tensorzero.toml).
- Enable observability by setting `observability.enabled = true` in `pmoves/tensorzero/config/tensorzero.toml`.

## Enabling metrics

1. **Set the ClickHouse connection URL** via environment variable:
   ```bash
   # In docker-compose.yml or .env file:
   TENSORZERO_CLICKHOUSE_URL=http://tensorzero:tensorzero@tensorzero-clickhouse:8123/default
   ```

2. **Enable observability** in `pmoves/tensorzero/config/tensorzero.toml`:
   ```toml
   [gateway]
   observability.enabled = true
   ```

3. **Restart the gateway**:
   ```bash
   make -C pmoves up-tensorzero
   ```

## Configuration format

**Valid configuration (tensorzero.toml):**
```toml
[gateway]
observability.enabled = true
# Optional: observability.async_writes = true
# Optional: observability.batch_writes = { enabled = true, flush_interval_ms = 100 }
```

**ClickHouse connection (environment variable only):**
```bash
TENSORZERO_CLICKHOUSE_URL=http://username:password@hostname:port/database
# Example for local development:
TENSORZERO_CLICKHOUSE_URL=http://tensorzero:tensorzero@tensorzero-clickhouse:8123/default
```

**INVALID configurations (will cause errors):**
```toml
# ❌ DO NOT USE - These sections are no longer valid:
[clickhouse]  # Invalid in 2025.11.6+
url = "..."

[gateway.observability.clickhouse]  # Invalid in 2025.11.6+
url = "..."
```

## Verification steps
- Run `curl http://127.0.0.1:8123/ping` to confirm ClickHouse is reachable.
- Start the gateway and check for `observability exporter configured` in the logs; errors about unknown fields should disappear once the new table is present.
- Query recent points to confirm ingestion (example for traces table will vary with the upstream schema). Until we finalize the table names, expect write errors if the block is omitted or credentials are missing.
