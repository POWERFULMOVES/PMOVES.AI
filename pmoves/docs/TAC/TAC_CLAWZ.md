# TAC Tree: ClawZ (OpenClaw)

> Technology-Architecture-Context tree for ClawZ — a multi-channel messaging gateway that connects 20+ messaging platforms (47 total extensions) to a unified AI-powered chat interface.

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | ClawZ (OpenClaw Gateway) |
| **Port** | 18789 (Gateway, configurable via `OPENCLAW_GATEWAY_PORT`) |
| **Health** | `GET /healthz` (liveness), `GET /readyz` (readiness) |
| **Metrics** | Optional (via `diagnostics-otel` extension) |
| **Submodule** | `PMOVES-ClawZ` |
| **Docker Profile** | N/A (local-first app, Docker optional) |
| **Tier** | ui |
| **Class** | Standard |
| **Evolution** | Pre-Stage |

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| TensorZero (3030) / Ollama | LLM for chat responses | Yes |
| Agent Zero (8080) | Agent runtime for complex tasks | Optional |
| NATS (4222) | Event publishing (planned) | Planned |
| Node.js 22+ | Runtime | Yes |
| pnpm / Bun | Package manager | Yes |

## Downstream Consumers

| Consumer | Interface | Description |
|----------|-----------|-------------|
| 47 extensions | WebSocket / HTTP | Message routing to/from chat platforms |
| Canvas host | Web UI | Browser-based chat interface |
| Mobile apps (iOS, Android) | WebSocket | Native mobile clients |
| Webhook receivers | HTTP | Inbound messages from platforms |

## Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| Gateway `:18789` | WS/HTTP | Primary gateway for all channel communication |
| Canvas host | HTTP | Web-based chat UI |
| Webhook receiver | POST | Inbound platform webhooks (Telegram, Discord, etc.) |

## NATS Subjects

NATS integration via the `nats-bridge` extension (`extensions/nats-bridge/`). Fire-and-forget publishing — failures are logged but never block message routing.

| Subject | Direction | Description |
|---------|-----------|-------------|
| `openclaw.message.received.v1` | Publishes | Inbound message from any channel (channel, author, content_length) |
| `openclaw.message.sent.v1` | Publishes | Outbound message to any channel (channel, content_length) |
| `openclaw.channel.connected.v1` | Publishes | Channel adapter connected/disconnected (channel, status) |

## CHIT Integration Status

| Capability | Status | Notes |
|------------|--------|-------|
| CGP packet generation | Planned (P4) | See [CHIT Attribution Plan](#chit-attribution-plan-e4) below |
| Attribution tracking | Planned (P4) | Which channel, which agent responded |
| Message routing attribution | Planned (P4) | Track message provenance across channels |
| BPM capable | No | Text-based messaging, not prosodic |

### CHIT Attribution Plan (E4)

> **Status:** Plan only — requires NATS bridge (E2) as prerequisite. Target: P4 priority.

**Goal:** Generate CGP packets for message routing attribution so every cross-channel message has provenance tracking.

**Architecture:**
```text
Message arrives on channel (e.g. Discord)
  → nats-bridge emits openclaw.message.received.v1
  → [NEW] CHIT attributor generates CGP packet
  → openclaw.message.attributed.v1 emitted with CGP envelope
  → Agent processes message, response routed back
  → [NEW] Response CGP packet links to inbound attribution
```

**Implementation steps (when ready):**
1. Add `@pmoves/chit-sdk` dependency to `nats-bridge` extension
2. Import `sign_cgp()` or equivalent TypeScript CHIT signer
3. Wrap inbound/outbound message events in CGP envelopes
4. New subject: `openclaw.message.attributed.v1` with CGP payload
5. Update TAC CHIT Integration table from "Planned" to "Active"

**Prerequisites:**
- NATS bridge extension must be stable (E2 / PR 3)
- CHIT TypeScript SDK available (`PMOVES-ToKenism-Multi/integrations/contracts/chit/`)
- CGP schema v1.0 finalized

**Decision:** Defer implementation until NATS adapter has been running in production for at least 2 weeks and event volume/reliability are proven.

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| `/healthz` endpoint | GREEN | Implemented with `/readyz` alias |
| `/metrics` (Prometheus) | MISSING | No metrics endpoint |
| Auth (JWT/Bearer) | Partial | DM pairing model + bootstrap tokens |
| Docker hardening | Partial | Dockerfile exists but sandbox variants are experimental |
| NATS auth | N/A | No NATS integration yet |
| `env.shared` format | N/A | Uses `openclaw.podman.env` |

## Security Stance

| Finding | Severity | Status |
|---------|----------|--------|
| No Prometheus `/metrics` | P3 | **Open** — uses optional OTEL diagnostics extension instead |
| DM pairing model security | P3 | Review needed — verify bootstrap token lifecycle |
| OAuth fallback paths | P3 | Review per-channel OAuth implementations |

## Channel Adapter Catalog

ClawZ supports 25+ messaging platforms through core channels and extensions:

### Core Channels (built-in)

| Channel | Transport | Status |
|---------|-----------|--------|
| Telegram | Bot API + webhook | Active |
| Discord | Bot + gateway | Active |
| Slack | Bot + events API | Active |
| Signal | Signal CLI bridge | Active |
| iMessage | AppleScript bridge | Active (macOS) |
| WhatsApp (Web) | Web protocol | Active |
| Web UI (Canvas) | WebSocket | Active |

### Extension Channels (plugins)

| Channel | Transport | Status |
|---------|-----------|--------|
| Microsoft Teams | Bot Framework | Extension |
| Matrix | Matrix SDK | Extension |
| Zalo | API | Extension |
| Voice Call | WebRTC/SIP | Extension |
| BlueBubbles | HTTP API | Extension |
| And more... | Various | See `extensions/` |

### Mobile Apps

| Platform | Status |
|----------|--------|
| iOS | Active (`apps/ios/`) |
| Android | Active (`apps/android/`) |

## Project Structure

```text
PMOVES-ClawZ/
├── src/                    # Core source (CLI, commands, infra, media, routing)
│   ├── cli/                # CLI wiring
│   ├── commands/           # Command handlers
│   ├── telegram/           # Telegram channel
│   ├── discord/            # Discord channel
│   ├── slack/              # Slack channel
│   ├── signal/             # Signal channel
│   ├── imessage/           # iMessage channel
│   ├── web/                # WhatsApp web channel
│   ├── channels/           # Channel abstractions
│   ├── routing/            # Message routing
│   └── media/              # Media pipeline
├── extensions/             # Plugin/extension channels
├── apps/                   # Mobile apps (iOS, Android)
├── packages/               # Shared packages
├── docs/                   # Documentation
├── docker-compose.yml      # Docker setup
└── openclaw.mjs            # Entry point
```

## Cross-Links

- **Submodule:** `PMOVES-ClawZ/`
- **Upstream:** [openclaw/openclaw](https://github.com/openclaw/openclaw) (fork origin)
- **Integration Topology:** [`TAC_INTEGRATION_TOPOLOGY.md`](./TAC_INTEGRATION_TOPOLOGY.md)
- **Flute Gateway TAC:** [`TAC_FLUTE.md`](./TAC_FLUTE.md) — potential outbound TTS via channels
- **BoTZ TAC:** [`TAC_BOTZ.md`](./TAC_BOTZ.md) — skills invocable from chat
- **Cipher TAC:** [`TAC_CIPHER.md`](./TAC_CIPHER.md) — conversation persistence

## Open Items

- ~~No `/healthz` endpoint~~ → **Implemented** (`/healthz` liveness + `/readyz` readiness — see Audit Checklist above)
- No `/metrics` endpoint — invisible to Prometheus (uses optional OTEL diagnostics instead)
- ~~No NATS integration — all 47 extensions could emit events to the event bus~~ → **Implemented** (`nats-bridge` extension publishes message and channel events)
- ~~No CHIT attribution — message routing lacks provenance tracking~~ → **Planned** (see [CHIT Attribution Plan](#chit-attribution-plan-e4), depends on E2 NATS bridge)
- Integration with Flute Gateway for outbound voice TTS via channels (planned)
- Integration with BoTZ skills for chat-invoked skill execution (planned)
- Integration with Cipher Memory for cross-channel conversation persistence
- DM pairing security model needs production hardening review
- Docker setup is optional/experimental — primary use is local-first

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-DEEP-DIVE::2026-03-15 -->
