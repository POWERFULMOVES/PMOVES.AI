# cast-tts-gateway — Subsystem Context

> Subsystem-specific CLAUDE.md. Load on demand when working inside `pmoves/services/cast-tts-gateway/`. README covers the operator surface; this doc captures developer-facing rules.

## Role

Synthesize TTS audio (via Flute-Gateway or Ultimate-TTS-Studio) and cast it to Google Cast devices (Nest, Chromecast, Android TV). Sits BETWEEN voice agents and the physical speaker mesh.

## Pairing rules

This service is one of a **3-service voice pipeline**:
```
voice agent → flute-gateway (prosodic TTS)
                    │
                    ▼
              cast-tts-gateway (this) ──► Google Cast devices
                    │
                    ▼
            ultimate-tts-studio (engine selection / advanced)
```

Don't fork the TTS synthesis logic here. Always call out to flute-gateway (`:8055`/`:8056`) or Ultimate-TTS-Studio (`:7860`/`:7861`). This service's job is **device discovery + transport + casting**, not synthesis.

## Device discovery

Uses mDNS/SSDP via `pychromecast`-equivalent. Discovery is LAN-bound — services running across Tailscale require the cast destination on the same broadcast domain (or a Tailscale exit node with multicast forwarding configured, which is non-trivial).

When adding remote-cast support, do NOT silently fall back to a different transport. Surface the limitation explicitly.

## NATS subjects

- Publishes: `voice.cast.started.v1`, `voice.cast.finished.v1` (lifecycle events for downstream coordination)
- Subscribes: `voice.cast.request.v1` (cast a TTS clip to a device)

Register new subjects via `.claude/context/nats-subjects.md` + `nats-subject-auditor` subagent.

## Prometheus metrics

Standard service metrics + per-device cast count, latency to-first-audio, error counts by device class (Nest Audio vs Chromecast vs TV).

## CHIT integration

**Status: Partial** per `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md`. cast events are logged but not yet CHIT-signed. Raising to Full tier is a Wave-2 followup.

## Common tasks

- **Add support for a new Cast device class**: extend device-class enum + add device fingerprinting in discovery; document in README.
- **Debug a stuck cast**: check device discovery logs first (mDNS is fragile); fall back to direct IP+port if discovery fails.
- **Coordinate with flute-gateway**: changes to the TTS pairing must be sequenced in a single PR with the consumer side.

## Cross-references

- README: this directory.
- TAC tree: pairs with `pmoves/docs/TAC/TAC_FLUTE.md` and `TAC_VOICE_AGENTS.md`.
- Flute-Gateway: `pmoves/services/flute-gateway/`.
- Ultimate-TTS-Studio: external (Pinokio launcher; see `.claude/PINOKIO_LAUNCHER_GUIDE.md`).
- Known Roads: `make -C pmoves up-flute-gateway` (cast-tts-gateway has no dedicated up-* target; comes up via `bringup-with-ui` or full mesh).
