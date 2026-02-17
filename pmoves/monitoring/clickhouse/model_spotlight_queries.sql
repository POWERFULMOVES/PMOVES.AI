-- =============================================================================
-- Model Spotlight: ClickHouse Aggregation Queries
-- =============================================================================
-- Reference queries for extracting per-model analytics from TensorZero's
-- ClickHouse OTLP store. Run manually or wire into n8n / cron to populate
-- the Supabase pmoves_core.model_metrics table.
--
-- Data source: TensorZero gateway with observability.enabled = true
-- ClickHouse tables: Depends on TensorZero's OTLP export schema.
-- Adjust table/column names to match your TensorZero ClickHouse schema.
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Requests per model per hour
-- ─────────────────────────────────────────────────────────────────────────────
-- Counts inference requests grouped by model name and hour bucket.
-- Use this to populate model_metrics.request_count.

SELECT
  toStartOfHour(Timestamp) AS hour,
  SpanAttributes['gen_ai.request.model'] AS model_name,
  count() AS request_count
FROM otel_traces
WHERE SpanName = 'tensorzero.inference'
  AND Timestamp >= now() - INTERVAL 1 HOUR
GROUP BY hour, model_name
ORDER BY hour DESC, request_count DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Token usage per model per hour
-- ─────────────────────────────────────────────────────────────────────────────
-- Sums input and output tokens per model per hour.
-- Use this to populate model_metrics.token_input and token_output.

SELECT
  toStartOfHour(Timestamp) AS hour,
  SpanAttributes['gen_ai.request.model'] AS model_name,
  sum(toUInt64OrZero(SpanAttributes['gen_ai.usage.input_tokens'])) AS token_input,
  sum(toUInt64OrZero(SpanAttributes['gen_ai.usage.output_tokens'])) AS token_output,
  sum(toUInt64OrZero(SpanAttributes['gen_ai.usage.input_tokens']))
    + sum(toUInt64OrZero(SpanAttributes['gen_ai.usage.output_tokens'])) AS total_tokens
FROM otel_traces
WHERE SpanName = 'tensorzero.inference'
  AND Timestamp >= now() - INTERVAL 1 HOUR
GROUP BY hour, model_name
ORDER BY hour DESC, total_tokens DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Latency percentiles per model
-- ─────────────────────────────────────────────────────────────────────────────
-- Computes p50, p95, p99 latency in milliseconds per model.
-- Use this to populate model_metrics.avg_latency_ms and p95_latency_ms.

SELECT
  toStartOfHour(Timestamp) AS hour,
  SpanAttributes['gen_ai.request.model'] AS model_name,
  avg(Duration / 1000000) AS avg_latency_ms,
  quantile(0.50)(Duration / 1000000) AS p50_latency_ms,
  quantile(0.95)(Duration / 1000000) AS p95_latency_ms,
  quantile(0.99)(Duration / 1000000) AS p99_latency_ms
FROM otel_traces
WHERE SpanName = 'tensorzero.inference'
  AND Timestamp >= now() - INTERVAL 1 HOUR
GROUP BY hour, model_name
ORDER BY hour DESC, avg_latency_ms ASC;


-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Error rates per model
-- ─────────────────────────────────────────────────────────────────────────────
-- Counts failed requests per model (status code != OK).
-- Use this to populate model_metrics.error_count.

SELECT
  toStartOfHour(Timestamp) AS hour,
  SpanAttributes['gen_ai.request.model'] AS model_name,
  countIf(StatusCode = 'STATUS_CODE_ERROR') AS error_count,
  count() AS total_count,
  round(countIf(StatusCode = 'STATUS_CODE_ERROR') / count() * 100, 2) AS error_rate_pct
FROM otel_traces
WHERE SpanName = 'tensorzero.inference'
  AND Timestamp >= now() - INTERVAL 1 HOUR
GROUP BY hour, model_name
ORDER BY hour DESC, error_rate_pct DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Function affinity per model
-- ─────────────────────────────────────────────────────────────────────────────
-- Shows which TensorZero functions route to which models most often.
-- Use this to populate model_metrics.function_breakdown (as JSONB).

SELECT
  SpanAttributes['gen_ai.request.model'] AS model_name,
  SpanAttributes['tensorzero.function_name'] AS function_name,
  count() AS request_count
FROM otel_traces
WHERE SpanName = 'tensorzero.inference'
  AND Timestamp >= now() - INTERVAL 24 HOUR
GROUP BY model_name, function_name
ORDER BY model_name, request_count DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- 6. Combined hourly snapshot (single query for model_metrics insert)
-- ─────────────────────────────────────────────────────────────────────────────
-- All-in-one query producing one row per model per hour, suitable for
-- direct INSERT into Supabase model_metrics via n8n HTTP node.

SELECT
  toStartOfHour(Timestamp) AS hour,
  SpanAttributes['gen_ai.request.model'] AS model_name,
  count() AS request_count,
  sum(toUInt64OrZero(SpanAttributes['gen_ai.usage.input_tokens'])) AS token_input,
  sum(toUInt64OrZero(SpanAttributes['gen_ai.usage.output_tokens'])) AS token_output,
  round(avg(Duration / 1000000), 2) AS avg_latency_ms,
  round(quantile(0.95)(Duration / 1000000), 2) AS p95_latency_ms,
  countIf(StatusCode = 'STATUS_CODE_ERROR') AS error_count
FROM otel_traces
WHERE SpanName = 'tensorzero.inference'
  AND Timestamp >= now() - INTERVAL 1 HOUR
GROUP BY hour, model_name
ORDER BY hour DESC, request_count DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- 7. All-time model leaderboard
-- ─────────────────────────────────────────────────────────────────────────────
-- Lifetime stats per model. Use to seed or refresh model_strengths table.

SELECT
  SpanAttributes['gen_ai.request.model'] AS model_name,
  count() AS total_requests,
  sum(toUInt64OrZero(SpanAttributes['gen_ai.usage.input_tokens']))
    + sum(toUInt64OrZero(SpanAttributes['gen_ai.usage.output_tokens'])) AS total_tokens_served,
  round(avg(Duration / 1000000), 2) AS avg_latency_ms,
  round(quantile(0.95)(Duration / 1000000), 2) AS p95_latency_ms,
  round(countIf(StatusCode = 'STATUS_CODE_ERROR') / count() * 100, 2) AS error_rate_pct,
  min(Timestamp) AS first_seen,
  max(Timestamp) AS last_seen
FROM otel_traces
WHERE SpanName = 'tensorzero.inference'
GROUP BY model_name
ORDER BY total_requests DESC;
