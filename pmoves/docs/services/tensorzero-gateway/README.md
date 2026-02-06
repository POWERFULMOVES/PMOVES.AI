# tensorzero-gateway — Service Guide

Status: Implemented (compose)

Overview
- TensorZero is PMOVES.AI's centralized LLM gateway and observability platform, providing unified access to multiple model providers (OpenAI, Anthropic, Venice, Ollama, Groq, Moonshot, Z.ai, Together, OpenRouter, Cloudflare) with comprehensive metrics collection via ClickHouse.
- The `tensorzero-gateway` container runs the TensorZero gateway server on port 3030 (host) / 3000 (internal), providing OpenAI-compatible `/v1/chat/completions` and `/v1/embeddings` endpoints.
- Integrates with `tensorzero-clickhouse` (port 8123) for observability metrics storage and `tensorzero-ui` (port 4000) for dashboard visualization.
- Supports multi-provider routing, request/response logging, token usage tracking, latency metrics, and error rate monitoring.

Compose
- Service: `tensorzero-gateway`
- Ports: `3030:3000` (gateway API)
- Profiles: `tensorzero`
- Depends on: `tensorzero-clickhouse` (health check)

Environment (core)
- `TENSORZERO_CLICKHOUSE_URL` — ClickHouse connection URL with credentials (default `http://tensorzero:tensorzero@tensorzero-clickhouse:8123/default`).
- `DOCKED_MODE` — Container deployment mode (default `true`).
- `PARENT_SYSTEM` — Parent system identifier (default `PMOVES.AI`).
- `PARENT_VERSION` — Parent system version (default `1.0.0-hardened`).

Environment (model provider keys)
- `OPENAI_API_KEY` — OpenAI API key for GPT models.
- `ANTHROPIC_API_KEY` — Anthropic API key for Claude models.
- `VENICE_API_KEY` — Venice.ai API key for privacy-focused models.
- `GROQ_API_KEY` — Groq API key for high-speed inference.
- `MOONSHOT_API_KEY` — Moonshot API key for long-context models.
- `Z_AI_API_KEY` — Z.ai API key (primary OpenAI-compatible provider).
- `TOGETHER_AI_API_KEY` — Together AI API key for open-source models.
- `OPENROUTER_API_KEY` — OpenRouter API key for model routing.
- `CLOUDFLARE_API_TOKEN` — Cloudflare API token for Workers AI.

Environment (integrations)
- `TENSORZERO_BASE_URL` — Gateway base URL for client services (default `http://tensorzero-gateway:3000`).
- `TENSORZERO_API_KEY` — Optional API key for gateway authentication (default empty).
- `TENSORZERO_EMBED_MODEL` — TensorZero embedding model name format (default `tensorzero::embedding_model_name::gemma_embed_local`).
- `TENSORZERO_GATEWAY_URL` — Gateway URL for UI access (default `http://tensorzero-gateway:3000`).

API Endpoints (gateway)
- `POST /v1/chat/completions` — OpenAI-compatible chat completion endpoint:
  - Request body: `{ "model": "model-name", "messages": [{"role": "user", "content": "..."}] }`.
  - Supports streaming responses.
  - Routes to configured model providers based on model name.
  - Response: OpenAI-compatible format with usage metadata.

- `POST /v1/embeddings` — OpenAI-compatible embedding generation endpoint:
  - Request body: `{ "model": "embedding-model-name", "input": "text to embed" }`.
  - Returns vector embeddings with metadata.
  - Supports multiple embedding providers (Ollama local, Together, OpenAI, OpenRouter, Venice).

- `GET /health` — Gateway health check endpoint:
  - Returns gateway status and dependency health.
  - Checks ClickHouse connectivity.
  - Verifies configuration validity.

- `GET /metrics` — Prometheus metrics endpoint:
  - Exposes request latency histograms.
  - Token usage counters by model.
  - Error rate metrics.
  - Provider-specific metrics.

- `GET /` — API info and available functions:
  - Lists all configured functions (agent_zero, langextract, deepresearch, etc.).
  - Shows available variants for each function.
  - Provides model routing information.

Configuration
- Config file: `/app/config/tensorzero.toml` (mounted from `pmoves/tensorzero/config/tensorzero.toml`).
- Models defined in `[models.*]` sections with provider routing.
- Functions defined in `[functions.*]` sections with variants.
- Embeddings defined in `[embedding_models.*]` sections.
- Tools defined in `[tools.*]` sections with JSON schemas.

Key configuration sections:
- `[gateway.observability]` — Enable/disable metrics collection (`enabled = true`, `async_writes = true`).
- `[gateway.export.otlp.traces]` — OpenTelemetry trace export (`enabled = true`, `format = "opentelemetry"`).
- `[models.*]` — Model definitions with provider routing.
- `[functions.*]` — Function definitions with variants for A/B testing.
- `[embedding_models.*]` — Embedding model definitions.

Smokes & tests
- Minimal container smoke:
  ```bash
  docker compose --profile tensorzero up -d tensorzero-clickhouse tensorzero-gateway tensorzero-ui
  docker compose ps tensorzero-gateway
  curl -sS http://localhost:3030/health | jq .
  docker compose logs -n 50 tensorzero-gateway
  ```

- Test chat completion:
  ```bash
  curl -X POST http://localhost:3030/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
      "model": "agent_zero_phi3_mini_local",
      "messages": [{"role": "user", "content": "Hello from TensorZero!"}]
    }'
  ```

- Test embedding generation:
  ```bash
  curl -X POST http://localhost:3030/v1/embeddings \
    -H "Content-Type: application/json" \
    -d '{
      "model": "gemma_embed_local",
      "input": "Text to embed"
    }'
  ```

- Check ClickHouse connectivity:
  ```bash
  curl http://localhost:8123/ping
  ```

- Verify metrics collection:
  ```bash
  curl http://localhost:3030/metrics | grep tensorzero
  ```

Make-based health checks
- `make -C pmoves health-tensorzero` — Verify TensorZero stack health:
  - Checks ClickHouse ping response.
  - Verifies gateway /health endpoint.
  - Tests UI accessibility.

- `make -C pmoves up-tensorzero` — Start TensorZero stack:
  - Brings up `tensorzero-clickhouse`, `tensorzero-gateway`, `tensorzero-ui`, `pmoves-ollama`.
  - Creates necessary volumes and networks.

Available functions (from config)
- `agent_zero` — Agent Zero orchestration (variants: local_qwen14b, local_mistral7b, local_phi3_mini, hosted_openai, hosted_moonshot, hosted_venice, hosted_together, etc.).
- `agent_zero_subordinate` — Subordinate agent routing (lighter models for cost efficiency).
- `langextract` — Language detection and NLP preprocessing (variants: local_qwen7b, local_phi3, edge_mistral7b, hosted_openai, hosted_moonshot, etc.).
- `hirag_rerank` — Hi-RAG cross-encoder reranking (variants: local_reranker, local_qwen14b).
- `deepresearch` — Research planning and synthesis (variants: nemotron_mini).
- `archon_work_orders` — Archon autonomous workflow execution (variants: local_qwen32b, local_qwen14b, hosted_openrouter, hosted_together).
- `archon_code_review` — Archon PR review function (variants: local_qwen32b, hosted_openrouter).
- `pmoves_media_processor` — Media transcription analysis (variants: local_qwen14b, local_mistral7b, hosted_together).
- `pmoves_log_analyzer` — Metrics and monitoring analysis (variants: local_qwen14b, local_mistral7b, hosted_together).
- `pmoves_research_coordinator` — Complex research synthesis (variants: local_qwen32b, local_qwen14b, hosted_openrouter, hosted_together).
- `pmoves_knowledge_manager` — RAG and indexing operations (variants: local_qwen14b, local_mistral7b, hosted_together).
- `coding` — Code generation and analysis (variants: primary_local, specialized_local, fallback_cloud).
- `orchestrator` — Multi-agent orchestration with web search tools.
- `vl_sentinel` — Vision-language model for image analysis.

Runbook
- Start TensorZero stack:
  ```bash
  cd pmoves && make up-tensorzero
  ```

- Restart gateway after config changes:
  ```bash
  docker compose restart tensorzero-gateway
  ```

- View gateway logs:
  ```bash
  docker compose logs -f tensorzero-gateway
  ```

- Access UI dashboard:
  - Open browser to `http://localhost:4000`
  - Browse request/response logs
  - Analyze token usage by model
  - Monitor latency distributions

- Query ClickHouse metrics:
  ```bash
  docker exec -it tensorzero-clickhouse clickhouse-client \
    --user tensorzero --password tensorzero \
    --query "SELECT model, COUNT(*) FROM requests GROUP BY model"
  ```

Troubleshooting
- Gateway won't start:
  - Check ClickHouse logs: `docker compose logs tensorzero-clickhouse`
  - Verify ClickHouse ping: `curl http://localhost:8123/ping`
  - Check config syntax: `docker compose logs tensorzero-gateway | grep "error\|unknown field"`

- Observability not working:
  - Verify `observability.enabled = true` in config
  - Check ClickHouse URL in environment: `docker compose exec tensorzero-gateway env | grep TENSORZERO`
  - Verify ClickHouse tables exist: `docker exec -it tensorzero-clickhouse clickhouse-client --user tensorzero --password tensorzero --query "SHOW TABLES"`

- Model routing failures:
  - Check provider API keys in environment variables
  - Verify model names in config match provider expectations
  - Test provider connectivity directly (e.g., `curl https://api.openai.com/v1/models`)

- High latency:
  - Check Prometheus metrics: `curl http://localhost:9090/api/v1/query?query=tensorzero_request_duration_seconds`
  - Query ClickHouse for slow requests: `docker exec -it tensorzero-clickhouse clickhouse-client --user tensorzero --password tensorzero --query "SELECT model, AVG(latency_ms), MAX(latency_ms) FROM requests WHERE timestamp > now() - INTERVAL 1 HOUR GROUP BY model ORDER BY AVG(latency_ms) DESC"`

Ops Quicklinks
- TensorZero GitHub: https://github.com/tensorzero/tensorzero
- Official docs: https://docs.tensorzero.com
- Config reference: https://docs.tensorzero.com/gateway/configuration
- Observability guide: https://docs.tensorzero.com/gateway/observability
- PMOVES TensorZero context: `.claude/context/tensorzero.md`
- Config file: `pmoves/tensorzero/config/tensorzero.toml`
- Observability notes: `pmoves/docs/services/open-notebook/TENSORZERO_OBSERVABILITY_NOTES.md`
- Venice integration: `pmoves/docs/venice-tensorzero-integration/`
- Model management: `pmoves/model-management/README.md`

Integration notes
- All PMOVES services use TensorZero for LLM calls (via `TENSORZERO_BASE_URL` environment variable).
- Hi-RAG v2 uses TensorZero for embeddings when `TENSORZERO_EMBED_MODEL` is configured.
- Agent Zero uses TensorZero for agent orchestration via the `agent_zero` function.
- DeepResearch uses TensorZero for research planning via the `deepresearch` function.
- Prometheus scrapes TensorZero metrics at `/metrics` endpoint (job: `tensorzero-gateway`).
- Grafana datasource configured at `http://tensorzero-gateway:3000` for metrics visualization.

Best practices
1. Use TensorZero for all production LLM calls to enable centralized observability.
2. Enable ClickHouse observability to track all model usage and costs.
3. Monitor token usage via ClickHouse queries or TensorZero UI dashboard.
4. Configure function variants for A/B testing and model fallbacks.
5. Use local models (Ollama) for cost-sensitive workloads.
6. Rotate ClickHouse logs periodically to prevent disk space issues.
7. Use UI at `http://localhost:4000` for debugging individual requests.
8. Export metrics to Prometheus for integration with existing monitoring.
9. Test model routing via `/` endpoint to verify configuration.
10. Keep API keys in environment files, not in tensorzero.toml config.
