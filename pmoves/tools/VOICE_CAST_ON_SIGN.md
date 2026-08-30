# CHIT-Sign-Triggered Expressive Voice (Phase 0)

A signed CHIT trail (`pmoves/tools/sign_trail.py`) becomes an audible,
persona-shaped utterance — no `speak` tool call anywhere in the pipeline.
This doc is the concise flow + env reference for `voice_cast_on_sign.py` and
its sibling `voice_persona_bridge.py`. Landed via PR #2048; follow-ups from
5090-CLAUDE's pair review are called out inline where relevant.

## Flow

```
agent signs a trail                     voice_cast_on_sign.py (daemon)
  sign_trail.py --agent-id ... \           subscribes agent.graphiti.signed.v1
    --summary "..."                          |
    (CHIT_SIGN_PUBLISH=1)                     v
       |                                  discriminator: glyph + agent_id present?
       v                                     |  no -> skip (stray envelope)
  publishes agent.graphiti.signed.v1          v yes
  (raw signature.v1 payload)               voice_persona_bridge.resolve(payload)
       |                                     -> intent, persona_id (FlOO$ suit map)
       v                                     |
     NATS                                    v
                                          Flute-Gateway /healthz check
                                             |  healthy + expressive provider
                                             |     -> POST /v1/voice/synthesize/audio
                                             |  unreachable OR no expressive
                                             |  provider healthy
                                             v     -> POST {KOKORO_URL}/synthesize
                                          WAV bytes
                                             |
                                             v
                                 write pmoves/out/voice_cast_<ts>.wav
                                 optional ffmpeg atempo tempo recovery
                                 best-effort host playback (winsound/afplay/aplay/ffplay)
```

## NATS subject

### `agent.graphiti.signed.v1`

- **Shape:** the raw `signature.v1` payload (see
  `pmoves/contracts/schemas/agent-graphiti/signature.v1.schema.json` and the
  fuller field-level doc at `.claude/context/nats-subjects.md`) — NOT the
  `pmoves-chit-sign` `{schema,tier}` production envelope carried by
  `chit.signed.v1`. Publishing the raw payload onto `chit.signed.v1` would
  collide two shapes on one subject (5090-CLAUDE pair-review PR #2048,
  finding #1) — this is why voice-cast has its own dedicated subject.
- **Published by:** `pmoves/tools/sign_trail.py`, gated on BOTH
  `CHIT_SIGN_PUBLISH=1` and `NATS_URL` being set — a no-op otherwise (does
  not change any existing agent's default trail-sign behavior).
- **Consumed by:** `pmoves/tools/voice_cast_on_sign.py` (this Phase 0
  pipeline). Also documented as consumed by "BoTZ MCP Gateway and agent
  handoff services" per the existing entry in
  `.claude/context/nats-subjects.md` (line ~441) — voice-cast is an
  additional consumer, not the only one.
- **Discriminator:** voice-cast only speaks payloads carrying both `glyph`
  and `agent_id` (defense-in-depth against a stray envelope landing on this
  subject that merely happens to carry a `summary` field — finding #2).

> Note: `pmoves/configs/nats-subjects.md` does not exist yet (the
> comprehensive subject catalog currently lives at
> `.claude/context/nats-subjects.md`, which is guard-protected/read-only for
> agents). This doc is the interim registration point for the voice-cast
> consumer relationship; fold it into a future `pmoves/configs/nats-subjects.md`
> if/when that catalog is split out of `.claude/context/`.

## Environment variables

| Var | Default | Used by | Purpose |
|---|---|---|---|
| `NATS_URL` | — | `sign_trail.py`, `voice_cast_on_sign.py` | NATS connection URL. `voice_cast_on_sign.py` runs on the host by default — `DEFAULT_NATS_URL` targets `localhost`, since the Docker-internal hostname `nats` only resolves inside the compose network (fails opaquely from a host shell). Containers running this daemon inside the compose network must pass `NATS_URL=nats://nats:pmoves@nats:4222` explicitly (finding #6). |
| `VOICE_CAST_NATS_URL` | — | `voice_cast_on_sign.py` | Explicit override, takes precedence over `NATS_URL` translation. |
| `CHIT_SIGN_PUBLISH` | unset (no-op) | `sign_trail.py` | Set to `1` to publish the signed trail to `agent.graphiti.signed.v1` after signing. Requires `NATS_URL` also set. |
| `FLUTE_GATEWAY_URL` | `http://localhost:8055` | `voice_cast_on_sign.py` | Flute-Gateway base URL for the expressive synthesis path (`/healthz`, `/v1/voice/synthesize/audio`). |
| `FLUTE_API_KEY` | unset | `voice_cast_on_sign.py` | `X-API-Key` header for the Flute-Gateway synth endpoint, which sits behind `verify_api_key` on fleet nodes. Omitting it when the gateway requires it produces a silent 401 (finding #3). |
| `KOKORO_URL` | `http://localhost:8004` | `voice_cast_on_sign.py` | Base URL for the standalone Kokoro CPU-floor deploy unit (`pmoves/services/kokoro-tts`, `feat/kokoro-cpu-tts`, #2024). Used as the genuinely independent fallback when Flute-Gateway is unreachable OR reports no expressive provider healthy — NOT a route back through the same `ultimate_tts`/Flute-Gateway stack that just failed (finding #4). |
| `KOKORO_TOKEN` | unset | `voice_cast_on_sign.py` | `X-Kokoro-Token` header for the Kokoro deploy unit, if that unit's `KOKORO_TOKEN` gate is enabled. |

## CLI

```
python pmoves/tools/voice_cast_on_sign.py --subjects agent.graphiti.signed.v1
```

## Demo path

```
CHIT_SIGN_PUBLISH=1 NATS_URL=nats://nats:pmoves@localhost:4222 \
  python pmoves/tools/sign_trail.py --agent-id claude-opus --summary "Completed X"
```

With `voice_cast_on_sign.py` running as a daemon and subscribed to
`agent.graphiti.signed.v1`, the sign above should produce an audible,
persona-shaped utterance within a few seconds — Flute-Gateway if the
expressive stack is up, or the Kokoro CPU floor otherwise.
