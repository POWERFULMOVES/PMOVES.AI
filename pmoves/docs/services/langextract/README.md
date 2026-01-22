# langextract — Service Guide

Status: Implemented (compose)

Overview
- Text/XML extraction to normalized chunks with error capture.

Compose
- Service: `langextract`
- Port: `8084:8084`
- Profiles: `workers`, `orchestration`

Smoke
```
docker compose up -d langextract
docker compose ps langextract
curl -sS http://localhost:8084/ | head -c 200 || true
docker compose logs -n 50 langextract
```

Docs
- [LANGEXTRACT](../../PMOVES.AI%20PLANS/LANGEXTRACT.md)
