# Notebook Sync Worker

Polls Open Notebook API and ships normalized payloads into LangExtract and downstream queues. No direct CHIT integration.

## Service & Ports
- Compose service: `notebook-sync`
- Port: `:8095`

## Make / Compose
- Included when `OPEN_NOTEBOOK_API_URL` is set; start individually: `docker compose up notebook-sync`
- Health: `curl http://localhost:8095/healthz`

