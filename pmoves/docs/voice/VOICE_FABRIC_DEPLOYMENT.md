# Voice Fabric Deployment — Expressive TTS Across the Fleet

**Status:** doctrine (confirmed 2026-07-11). **Scope:** how the expressive TTS engine
(Ultimate TTS Studio + omnivoice/vibevoice) runs across PMOVES nodes and how CHIT-sign
casts route to it. Pairs with the live CHIT-sign→voice loop (PRs #2059 / #2060 / #2063).

## The principle: runtime is per-node, routing is unified

The engine is a **capability**, not a fixed service on one box. Each node runs the TTS
engine in the way that fits its OS/GPU, and **Flute-Gateway `host_affinity`** routes each
cast to whichever node currently has the engine up — self-healing when a node drops. This
is the MOF "every node is a pore" model: nodes reflect and transform within their
capabilities to form the fabric; if one GPU node is down, others carry the load until it
returns.

## Per-node runtime (how the engine actually runs on each node)

| Node class | Runtime | Why |
|------------|---------|-----|
| **Windows / desktop GPU** (4090, 5090, Z890) | **Pinokio 8 per-node** — the `PMOVES-Pinokio-Ultimate-TTS-Studio` launcher fork (hardened) | Host-native, GPU-direct, **sidesteps the Docker Desktop vpnkit `:7861` port-reservation leak** entirely. Matches "run local on multiple nodes." |
| **Headless Linux fleet** (SPARK arm64, KVMs) | **Docker / GHCR** — `ghcr.io/powerfulmoves/pmoves-ultimate-tts-studio:pmoves-latest` (engine fork `PMOVES-Ultimate-TTS-Studio`) via `make up-tts-studio` | Reproducible, portable, no Windows vpnkit issue. |
| **CPU-only nodes** (cheap KVMs) | **kokoro-tts** (`make kokoro-*`, #2024) | CPU floor only — the self-heal fallback, never the designated expressive voice. |

Two forks, **do not cross them** (different upstream lineages):
- **Launcher** `PMOVES-Pinokio-Ultimate-TTS-Studio` (upstream `pinokiofactory/Ultimate-TTS-Studio`) — tracks `PMOVES.AI-Edition-Hardened`, currently **9 ahead / 0 behind = clean**. Leave alone.
- **Engine** `PMOVES-Ultimate-TTS-Studio` (upstream `SUP3RMASS1VE/Ultimate-TTS-Studio-SUP3R-Edition`) — `PMOVES.AI-Edition-Hardened` **12 ahead / 5 behind = diverged**; sync is deferred, merge-not-squash, mirror lane, **Fish Speech S2 Pro license-gated** before promotion.

## Fleet routing (how a cast reaches the right node)

`Flute-Gateway` resolves `intent`/`persona` → engine → **node** via the `host_affinity`
table in `pmoves/configs/tts-engine-capabilities.yaml` (PR #2037). Node affinity is a
property of the engine's hardware needs (CPU-viable vs GPU/VRAM), so it's keyed by engine;
a preferred node is used when up, else the first eligible node that is up, else the CPU
floor. The CHIT-sign→voice subscriber (`tools/voice_cast_on_sign.py`) POSTs to Flute-Gateway;
Flute does the node selection. **Self-healing is the routing layer, not the engine.**

> **Implementation status:** Host-affinity routing is **wired into the synthesis path**
> and **opt-in**. `resolve_engine_target()` (persona_selector) is called by
> `/v1/voice/synthesize` for the `ultimate_tts` and `omnivoice` providers: when
> `VOICE_HOST_AFFINITY=1`, it resolves the engine's node via `resolve_engine_host()`
> and host-swaps the configured URL to that node's Tailscale hostname
> (`pmoves-<node>`, scheme/port/path preserved), routing the cast to a transient
> provider bound to that URL. The chosen node is returned in the response `node` field.
>
> **Fail-open by default.** With `VOICE_HOST_AFFINITY` unset (the default), or when the
> engine has no `host_affinity` row / no eligible node is up, casts fall back to the
> single configured provider URL (`ULTIMATE_TTS_URL`/`OMNIVOICE_URL`) — unchanged
> behaviour. `VOICE_FLEET_NODES` (comma-separated up-node ids) restricts routing to
> nodes currently up; unset means "assume the preferred node is up".

## The reachability rule (localhost vs Docker)

Pinokio's Gradio binds **`127.0.0.1:7860` only** (`demo.launch(share=False)` — no
`server_name`). Flute-Gateway runs in Docker today and reaches TTS at
`host.docker.internal:7860`, which will **not** hit a localhost-only bind. Resolve per node,
in order of preference (privacy/mesh-first):

1. **Preferred — flute-relay native per node.** Run a Flute-Gateway (or a thin relay) as a
   host-native process on each Pinokio GPU node so `http://127.0.0.1:7860` works directly.
   Keeps the TTS UI bound to localhost — no host-network exposure.
2. **Pinokio local-share proxy** (`PINOKIO_SHARE_LOCAL=true`) — Pinokio's own Caddy proxy
   (`https://7860.localhost`, Tailscale share) instead of raw LAN.
3. **Last resort — `GRADIO_SERVER_NAME=0.0.0.0`** + `host.docker.internal:7860`. Exposes the
   TTS UI on the host network → **must be mesh-only / firewalled** (privacy-first rule). Only
   on nodes where 1 and 2 aren't viable.

Never bind `0.0.0.0` on a node reachable from an untrusted network.

## Bring-up (per Pinokio GPU node)

1. `make up-voice` — flute-gateway (+ nats, voice-relay) for that node.
2. Launch the Ultimate TTS Studio via Pinokio (Install → Start) → Gradio `127.0.0.1:7860`.
   - First install builds `tts_env` (conda `python=3.10.20`). If it aborts at "Verifying
     transaction" on a corrupted cache package, purge that package from
     `<PINOKIO_HOME>/bin/miniforge/pkgs/` and delete the half-built `app/tts_env`, then
     re-Install (see the 2026-07-11 openssl-cache incident).
3. Point `ULTIMATE_TTS_URL` per the reachability rule above.
4. `make voice-cast-up` + `make voice-cast-smoke` — confirm the CHIT-sign→voice loop casts a
   WAV. `intent=dramatic` uses the expressive engine; self-heals to the kokoro floor if it's down.

## TAC coverage

- `pmoves/configs/tac_trees/voice-cast-loop.tac.yaml` — the CHIT-sign→voice loop, vibevoice, omnivoice (go-time).
- `pmoves/configs/tac_trees/voice-agents.tac.yaml` — TTS Studio native (Pinokio), Flute integration.
- `pmoves/configs/tac_trees/pinokio-p7.tac.yaml` — Ultimate-TTS-Studio discovery.
