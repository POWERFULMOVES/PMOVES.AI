# Presign API

Generates presigned URLs for media and assets. No direct CHIT integration.

## Service & Ports
- Compose service: `presign`
- Port: `:8088` (host) → container `:8080`

## Make / Compose
- Included in `make up`
- Health: `curl http://localhost:8088/healthz`

