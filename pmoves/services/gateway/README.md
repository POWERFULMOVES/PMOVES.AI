# PMOVES Gateway

FastAPI service bundling the CHIT geometry API, visualization endpoints, event bus, and a web UI.

## Quick Start

```bash
# Run locally
cd pmoves/services/gateway
uvicorn gateway.main:app --host 127.0.0.1 --port 8000

# Or via Docker Compose
docker compose --profile agents up -d gateway
```

Open `http://localhost:8000/web/client.html` to use the CHIT web client.

## Service & Ports

| Port | Description |
|------|-------------|
| 8000 | HTTP API + static web UI |

Compose service: `gateway` (in the `agents` profile).

## CHIT Geometry Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/geometry/event` | Ingest a CGP packet into ShapeStore + Supabase |
| GET | `/shape/point/{pid}/jump` | Cross-modal jump locator (video/audio/text) |
| POST | `/geometry/decode/text` | Decode constellation spectra to text via codebook |
| POST | `/geometry/calibration/report` | KL/JS divergence calibration report |

## Visualization Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/viz/constellation.svg` | Render constellation as SVG polar plot |
| GET | `/viz/shape/{shape_id}.svg` | Render saved shape constellation SVG |
| POST | `/viz/preview/decode` | Preview decode without saving |
| POST | `/viz/mix/decode` | Interpolate two constellations and decode |
| GET | `/viz/recent` | List recently saved shape IDs |
| GET | `/viz/shape/{shape_id}/constellations` | List constellations in a shape |
| POST | `/viz/preview/calibration` | Preview calibration for a single constellation |
| POST | `/viz/mix/calibration` | Interpolate two constellations and calibrate |

## Other API Routers

| Prefix | Module | Description |
|--------|--------|-------------|
| `/consciousness` | `api/consciousness.py` | Consciousness service CGP mapping |
| `/events` | `api/events.py` | NATS event bus bridge |
| `/mindmap` | `api/mindmap.py` | Mind map generation |
| `/signaling` | `api/signaling.py` | WebRTC signaling |
| `/workflow` | `api/workflow.py` | Workflow orchestration |

## Web UI Pages

| Path | Description |
|------|-------------|
| `/web/client.html` | CHIT web client (publish, decode, calibrate) |
| `/web/playground.html` | Interactive CHIT playground |
| `/web/demo_shapes_webrtc.html` | WebRTC shapes demo |

Static mounts: `/web/` (HTML/JS), `/data/` (saved CGP JSON), `/artifacts/` (reports).

## Environment Variables

### CHIT Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CHIT_REQUIRE_SIGNATURE` | `false` | Require HMAC-SHA256 on all CGPs |
| `CHIT_DECRYPT_ANCHORS` | `false` | Enable AES-GCM anchor decryption |
| `CHIT_PASSPHRASE` | `change-me` | Shared secret for HMAC/scrypt |
| `CHIT_CODEBOOK_PATH` | `tests/data/codebook.jsonl` | Default codebook path |
| `CHIT_LEARNED_TEXT` | `false` | Enable learned text decode |
| `CHIT_T5_MODEL` | (none) | HuggingFace T5 model for summaries |

### Integrations

| Variable | Default | Description |
|----------|---------|-------------|
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | NATS message bus URL |
| `SUPA_REST_URL` | (none) | Supabase PostgREST URL |
| `SUPABASE_SERVICE_ROLE_KEY` | (none) | Supabase API key |

## Architecture

- **ShapeStore** (`pmoves/services/common/shape_store.py`): In-memory LRU cache (10k entries) with Supabase warm loading
- **Event Bus** (`event_bus.py`): NATS JetStream publisher/subscriber
- **Security**: HMAC signatures, AES-GCM anchor encryption, codebook path sandboxing, XSS-safe web client

## Related Documentation

- **[CHIT Gateway API Reference](../../docs/PMOVESCHIT/CHIT_GATEWAY_API.md)** - Comprehensive HTTP API docs with examples
- **[CHIT Specification](../../docs/PMOVESCHIT/PMOVESCHIT.md)** - Core spec and CGP v0.1
- **[Decoder Spec](../../docs/PMOVESCHIT/PMOVESCHIT_DECODERv0.1.md)** - Text decoder algorithm
- **[Multi-modal Decoder](../../docs/PMOVESCHIT/PMOVESCHIT_DECODER_MULTIv0.1.md)** - CLIP/CLAP decoder
- **[Implementation Status](../../docs/PMOVESCHIT/IMPLEMENTATION_STATUS.md)** - Component tracking
- **[GEOMETRY BUS Integration](../../docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md)** - NATS subjects
- **[Smoke Tests](../../docs/SMOKETESTS.md)** - End-to-end geometry checks
