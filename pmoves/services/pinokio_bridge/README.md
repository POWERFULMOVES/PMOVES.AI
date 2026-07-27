# pinokio_bridge

PMOVES bridge to the Pinokio 8 managed surfaces. Companion service to
the `pinokio-bridge` skill (`pmoves/skills/pinokio-bridge-skill/SKILL.md`).

## What it does

Exposes Pinokio 8's four new managed surfaces as HTTP JSON so PMOVES
agents (and the P7 room-orchestrator) can read/write them without
shelling out to Pinokio directly:

- **Autolaunch** — `GET/POST /v1/apps/{slug}/autolaunch`
- **Orchestration** — `GET /v1/apps/{slug}/dependencies`, `GET /v1/orchestration/graph`
- **Managed skills** — `GET /v1/skills`, `POST /v1/skills/{slug}/sync`, `GET /v1/skills/conflicts`
- **GPU/VRAM templates** — `GET /v1/gpu/detect`, `GET /v1/gpu/match`

Plus a passthrough app-management surface (`GET /v1/apps`,
`GET /v1/apps/{slug}/status`, `POST /v1/apps/{slug}/launch`) that
mirrors `pterm list` / `pterm status` / `pterm start` but as structured
JSON.

## How it works

The service reads Pinokio 8 state from the on-disk JSON layout in
`~/pinokio/` (configurable via `PINOKIO_HOME` env var):

```
~/pinokio/
  apps/index.json                   - app metadata
  autolaunch/state.json             - per-app autolaunch + global disabled
  orchestration/graph.json          - dependency graph + launch order
  skills/library.json               - managed skill library
  skills/sync_state.json            - last sync + conflicts
  gpu/state.json                    - detected GPU + VRAM
  version.json                      - Pinokio version
```

Reads are open. Writes require the `X-PMOVES-Bridge-Token` header
(loaded from `PMOVES_BRIDGE_TOKEN` at service start; fail-closed with
503 if not configured).

## Running

### Production

```bash
# Set the token (generate with: openssl rand -hex 32)
export PMOVES_BRIDGE_TOKEN=<random-32-byte-hex>
export PINOKIO_HOME=/path/to/pinokio
cd pmoves
python -m uvicorn pmoves.services.pinokio_bridge.app:app \
  --host 0.0.0.0 --port 8130
```

Or via the Docker image:

```bash
docker build -t pmoves-pinokio-bridge -f pmoves/services/pinokio_bridge/Dockerfile .
docker run -d -p 8130:8130 \
  -e PMOVES_BRIDGE_TOKEN=<token> \
  -e PINOKIO_HOME=/pinokio \
  -v /path/to/host/pinokio:/pinokio:ro \
  --name pmoves-pinokio-bridge \
  pmoves-pinokio-bridge
```

### Tests

```bash
cd pmoves
python -m pytest services/pinokio_bridge/tests/ -q
```

The tests use an in-memory `PinokioState` fixture (no Pinokio install
required). All endpoints are exercised through `fastapi.testclient.TestClient`.

## Token rotation

The `PMOVES_BRIDGE_TOKEN` is the only credential. Rotation procedure:

1. Generate a new token (`openssl rand -hex 32`).
2. Update the secret in your secret store (Vault, K8s secret, etc.).
3. Update `PMOVES_BRIDGE_TOKEN` in the bridge service environment.
4. Restart the bridge service.

No client action required — the next request with the new token
authenticates; the old token stops working as soon as the service
restarts.

## Cross-references

- `pmoves/skills/pinokio-bridge-skill/SKILL.md` — the surface contract
  (use this to understand what the endpoints return and how PMOVES
  agents call them)
- `pmoves/configs/tac_trees/pinokio-p8.tac.yaml` — the audit tree
  that catches drift on the state files this service reads
- `pmoves/services/p7-room-orchestrator/` — the consumer that uses
  `/v1/gpu/match` and `/v1/apps/{slug}/dependencies` during
  room-session-open
- Pinokio 8 docs: https://cocktailpeanutlabs.github.io/p8/
