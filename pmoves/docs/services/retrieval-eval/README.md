# retrieval-eval — Service Guide

Status: Implemented (compose)

Overview
- Evaluation dashboard/tests targeting the RAG gateway.

Compose
- Service: `retrieval-eval`
- Port: `8090:8090`
- Profiles: `workers`
- Depends on: `hi-rag-gateway-v2`

Environment
- `HIRAG_URL` (default `http://hi-rag-gateway-v2:8086`)
- `EVAL_HTTP_PORT` (default 8090)

Smoke
```
docker compose up -d hi-rag-gateway-v2 retrieval-eval
docker compose ps retrieval-eval
curl -sS http://localhost:8090/ | head -c 200 || true
docker compose logs -n 50 retrieval-eval
```
