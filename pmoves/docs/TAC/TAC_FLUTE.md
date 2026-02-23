# TAC Tree: Flute Gateway

> Technology-Architecture-Context tree for the Flute prosodic voice mesh gateway.

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | Flute Gateway |
| **Ports** | 8055 (HTTP), 8056 (WebSocket) |
| **Health** | `GET /healthz` |
| **Metrics** | `GET /metrics` |
| **Service Path** | `pmoves/services/flute-gateway` |
| **Docker Profile** | `agents` |
| **Tier** | agent |

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| TensorZero (3030) | LLM for voice agent conversations | Yes |
| Pipecat | Voice pipeline library | Yes (when enabled) |
| NATS (4222) | Voice event publishing | Yes |
| Ultimate-TTS-Studio (7861) | TTS backend | Optional |
| FFmpeg-Whisper (8078) | STT backend | Optional |

## Downstream Consumers

| Consumer | Interface | Description |
|----------|-----------|-------------|
| PBnJ | Health check | Voice gateway status |
| ESP32 Edge Nodes (future) | WebRTC signaling | Edge mesh voice sessions |
| Agent Zero | Voice events via NATS | Agent awareness of voice sessions |
| Hi-RAG v2 | `tokenism.geometry.event.v1` | Voice attribution tracking |
| ToKenism | `tokenism.prosodic.bpm.v1` | BPM-encoded prosodic events |

## Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Health check |
| `/metrics` | GET | Prometheus metrics |
| `/v1/voice/synthesize/prosodic` | POST | Prosodic TTS synthesis |
| WebSocket `:8056` | WS | Real-time audio streaming |

## NATS Subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| `tokenism.geometry.event.v1` | Publishes | Voice synthesis attribution events |
| `tokenism.prosodic.bpm.v1` | Publishes | BPM-encoded prosodic timeline events |
| `geometry.packet.decoded.v1` | Subscribes | Decoded geometry packets for voice rendering |

## CHIT Integration Status

| Capability | Status | Notes |
|------------|--------|-------|
| CGP packet generation | Active | Via `tokenism.geometry.event.v1` |
| BPM prosodic encoding | **NEW** | Via `tokenism.prosodic.bpm.v1` |
| Voice persona attribution | Active | `voice_persona_id` in CGP packets |
| Hz sensitivity | Enabled | `chit_toggles.hz_sensitive: true` |

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| `/healthz` endpoint | GREEN | Implemented |
| `/metrics` (Prometheus) | GREEN | Implemented |
| Auth (JWT/Bearer) | Partial | `FLUTE_API_KEY` for API auth |
| Docker hardening | GREEN | Non-root (UID 65532), hash-verified requirements.lock |
| NATS auth | GREEN | Uses authenticated NATS connection |
| `env.shared` format | GREEN | No `export` syntax issues |

## Docked vs Undocked

- **Docked**: Central voice gateway serving all clients
- **Undocked**: WebRTC signaling for edge mesh nodes (Phase 5)

## Pipecat Configuration

| Setting | Default | Env Var |
|---------|---------|---------|
| Enabled | false | `PIPECAT_ENABLED` |
| Sample Rate | 24000 Hz | `PIPECAT_SAMPLE_RATE` |
| VAD Threshold | 0.5 | `PIPECAT_VAD_THRESHOLD` |
| Transport | websocket | `PIPECAT_DEFAULT_TRANSPORT` |
| LLM Model | claude-sonnet-4-5 | `PIPECAT_DEFAULT_LLM_MODEL` |

## Cross-Links

- **Architecture:** [`pmoves/docs/FLUTE_PROSODIC_ARCHITECTURE.md`](../FLUTE_PROSODIC_ARCHITECTURE.md)
- **BPM Bridge:** [`pmoves/docs/AGENTS/AGNOTE4482.BEATS.md`](../AGENTS/AGNOTE4482.BEATS.md)
- **API Reference:** `.claude/context/flute-gateway.md`
- **Integration Topology:** [`TAC_INTEGRATION_TOPOLOGY.md`](./TAC_INTEGRATION_TOPOLOGY.md)

## Open Items

- ESP32 WebRTC signaling (Phase 5)
- ~~Prosodic BPM encoding for CHIT attribution~~ → **RESOLVED** (see BPM-Prosodic Bridge)
- Edge mesh node protocol

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-TOPOLOGY-AUDIT::2026-02-20 -->
