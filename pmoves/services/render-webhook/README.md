# Render Webhook

Receives render requests and persists outputs. No direct CHIT integration.

## Service & Ports
- Compose service: `render-webhook`
- Port: `:8085`

## Make / Compose
- Included in `make up`
- Health: `curl http://localhost:8085/healthz`

