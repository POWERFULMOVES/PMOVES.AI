# pmoves-hirag-mcp

Thin stdio MCP bridge over existing PMOVES retrieval APIs. Covers the Notion/Confluence/knowledge-search lanes that the Cowork `engineering`/`productivity` plugins expect from SaaS connectors — see `pmoves/docs/operations/COWORK_CONNECTOR_MAP.md`. Mirrors the `pmoves-nats-mcp` pattern. No retrieval is rebuilt (Integration Rule).

## Tools

| Tool | Backs onto | Notes |
|------|-----------|-------|
| `hirag_query` | Hi-RAG v2 `POST /hirag/query` (`:8086` CPU, `:8087` GPU) | Qdrant + Neo4j + Meilisearch hybrid, cross-encoder rerank |
| `notebook_search` | Open Notebook API (`$OPEN_NOTEBOOK_API_URL` + `$OPEN_NOTEBOOK_API_TOKEN`) | Returns error with guidance if env unset |
| `service_health` | Catalog `/healthz` endpoints (Cipher: `/health`) | Single service or full sweep |

## Run

```bash
uv run --directory ./pmoves-hirag-mcp python -m hirag_mcp.server
```

## Test (no live services needed — httpx mocked)

```bash
uv run --directory ./pmoves-hirag-mcp --extra dev pytest tests/ -v
```

## Register — `.claude/mcp.json`

```json
"pmoves-hirag": {
  "command": "uv",
  "args": ["--directory", "./pmoves-hirag-mcp", "run", "python", "-m", "hirag_mcp.server"],
  "env": {
    "HIRAG_URL": "http://localhost:8086",
    "HIRAG_GPU_URL": "http://localhost:8087"
  }
}
```

Open Notebook credentials flow through `pmoves/env.tier-*` + `make -C pmoves secrets-funnel` — never inline in mcp.json.

## Env

| Var | Default | Purpose |
|-----|---------|---------|
| `HIRAG_URL` | `http://localhost:8086` | Hi-RAG v2 CPU gateway |
| `HIRAG_GPU_URL` | `http://localhost:8087` | Hi-RAG v2 GPU gateway (`gpu: true`) |
| `OPEN_NOTEBOOK_API_URL` | — | Open Notebook base URL |
| `OPEN_NOTEBOOK_API_TOKEN` | — | Bearer token |

<!-- GRAPHITI_MARK: COWORK-CLAUDE::HIRAG-MCP-BRIDGE::2026-06-11 -->
