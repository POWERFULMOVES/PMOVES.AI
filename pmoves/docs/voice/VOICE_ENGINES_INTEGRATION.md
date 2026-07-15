# Voice-Engines Integration — the no-guess contract for an agent-managed voice fabric

**Status:** framework (2026-07-12). **Scope:** what it means for an expressive TTS
engine to be *integrated* well enough that an **autonomous native agent** (HERMES on
SPARK / 5090) can manage it — start it, route to it, cast through it, and hear back —
**without guessing**. Pairs with the runtime doctrine
[`VOICE_FABRIC_DEPLOYMENT.md`](./VOICE_FABRIC_DEPLOYMENT.md) and the audit
[`voice-engines-integration.tac.yaml`](../../configs/tac_trees/voice-engines-integration.tac.yaml).

## Why "no guess"

Hand-rolled tests and ad-hoc bring-up encode *assumptions* about how an engine
behaves. When an autonomous agent drives the fabric, an assumption that drifted from
reality becomes a silent failure (a cast that never lands, a node that's picked but
can't host the engine). The fix is to ground every engine on a small set of rails that
are each *verifiable against a real artifact* — a config row, an API surface, a
documented road — so the agent follows a road instead of improvising, and the TAC tree
tells us the moment a rail is missing.

## The four rails (every engine must ride all four)

| Rail | The engine has… | Grounded in | Verifies |
|------|-----------------|-------------|----------|
| **1. Contract** | a real API surface an agent calls | `flute-gateway/mcp_bridge.py` (MCP SSE tools) + `main.py` `/v1/voice/synthesize*` | agent can list/load/cast without a mock |
| **2. Routing** | a `host_affinity` row (persona→engine→NODE) | `configs/tts-engine-capabilities.yaml` + `resolve_engine_host()` | fabric self-heals across GPU nodes |
| **3. Runbook** | a documented bring-up / reachability Known Road | `VOICE_FABRIC_DEPLOYMENT.md` | agent stands it up the same way every time |
| **4. License** | upstream attribution tracked | per-engine license registry (PR #2050) | ship only what the license permits |

An engine that is missing any rail is *not integrated* — it may work by luck on one
node and fail the moment routing moves it. The TAC tree audits all four per engine.

## The contract surface (Rail 1, in detail)

Two API surfaces front the engines; both are the *same fabric*, not a mock:

- **MCP SSE bridge** (`mcp_bridge.py`) — the A2A/agent entrypoint. `GET /sse` +
  `POST /messages` (JSON-RPC `initialize` / `tools/list` / `tools/call`). Tools:
  `tts_list_engines`, `tts_synthesize`, `tts_engine_status`, `tts_load_engine`,
  `tts_unload_engine` (+ `tts_list_intents`). This is what HERMES calls to manage VRAM
  and cast.
- **HTTP** (`main.py`) — `/v1/voice/synthesize`, `/v1/voice/synthesize/audio`,
  `/v1/voice/synthesize/prosodic`, `/v1/voice/config`, `/v1/voice/profiles`,
  `/v1/voice/validate`, `/healthz`. This is what the CHIT-sign→voice subscriber POSTs to.

Engine specs live in `configs/tts-engine-capabilities.yaml`; intent→engine mapping in
`configs/tts-engine-expressions.yaml`. **No engine list is hard-coded in code** — both
surfaces read the configs, so adding an engine is a config edit, not a code change.

## How an autonomous agent (HERMES) consumes this

HERMES is a Delivery-Body agent with MCP/NATS bridge privileges
([`.claude/agents/hermes-agent.md`](../../../.claude/agents/hermes-agent.md)). On a
GPU node it:

1. **Discovers** — `tts_list_engines` over the MCP bridge → the roster + VRAM/latency.
2. **Routes** — reads `host_affinity` to know which engines this node should host
   (`resolve_engine_host` picks preferred-if-up, else first-eligible-up, else the
   caller floors to kokoro).
3. **Loads / unloads** — `tts_load_engine` / `tts_unload_engine` to fit VRAM, following
   the runbook, not guessing at model paths.
4. **Casts** — an agent's normal `sign_trail` publishes `agent.graphiti.signed.v1`;
   `voice_cast_on_sign.py` maps the alter→intent (`voice_persona_bridge.py`) and POSTs
   to Flute. **No `speak` tool call** — the sign *is* the trigger.

This is the "native agent manages the voices" goal: the agent never improvises engine
internals; it drives a contracted surface whose gaps the TAC tree makes visible.

## The ears — how info reaches agents (input side)

The voice fabric is only half. The **ears** are how conversation reaches agents so they
can wake and respond — *"other agents wait, then wake based on the convo."*

- **Transcription seam** — `providers/whisper.py` (speech-in), the input counterpart to
  the TTS providers.
- **Prosodic understanding** — `bpm_encoder_worker.py` turns
  `mesh.gpu.inference.result.v1` into `bpm.encoded.v1`: a BPM/boundary timeline so
  *how* something was said (emphasis, breath, pace) is on the geometry bus, not just the
  words.
- **Auto-wake seam** — `pmoves/tools/nats_agent_inbox.py` (persistent node-bound inbox)
  and `pmoves/tools/realtime_listener.py`: agents park on a subject and wake on a
  message. Dormant until the conversation triggers them — *the "aliens on the wall"
  pattern, minus the scary* (a marketing spin worth keeping in a back pocket: the
  friendly xenomorph that finally *talked*).

The A2A loop closes on `voice.agent.response.v1` (`voice_follow_cast_agent.py`): one
agent's cast is another agent's cue.

## Adding / grounding an engine (the checklist)

1. **Capability row** in `tts-engine-capabilities.yaml` (VRAM, latency, category).
2. **host_affinity row** — `requires` (cpu/cuda), `min_vram_mb`, `nodes`, `preferred`.
3. **MCP endpoints** — load/unload handlers in `mcp_bridge.py` `ENGINE_ENDPOINTS`.
4. **Intent mapping** (if it's an expressive default) in `tts-engine-expressions.yaml`.
5. **License** — add the engine to the attribution registry (PR #2050); gate anything
   non-permissive (e.g. `f5_tts` CC-BY-NC, `fish_s2` Pro) before promotion.
6. **Runbook note** — reachability per `VOICE_FABRIC_DEPLOYMENT.md`.
7. **Prove it** — the TAC tree goes green and `make voice-cast-smoke` casts a WAV.

Grounded > hand-rolled: a test asserts the *real contract* (see the 2026-07-12
`_extract_text` fix — the hand-rolled test guessed `"{}"`; the contract is `""`).

## TAC coverage

- `voice-engines-integration.tac.yaml` — this framework (contract · routing · runbook ·
  license · ears), the go-time per-engine audit.
- `voice-cast-loop.tac.yaml` — the CHIT-sign→voice loop, vibevoice, omnivoice.
- `voice-agents.tac.yaml` — TTS Studio native (Pinokio) + Flute integration.
- `pinokio-p7.tac.yaml` — Ultimate-TTS-Studio discovery (expressive dramatic host).
