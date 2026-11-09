# Release Notes — 4090 Local Voice Synthesis (2026-09-03)

**PR:** #2892 · **Suit concern:** `pmoves/config/profiles/laptop-4090.yaml` (§6.4)

## What changed

- `laptop-4090.yaml` `cross_node.channels.voice.endpoint` now declares
  `http://localhost:8055/...` instead of `http://pmoves-5090:8055/...`.
- The 5090 is retained as `peer_endpoint` — recorded, not routed.

## Why it matters

The declared route pointed at a peer whose Flute-Gateway is down. Measured
2026-09-03: `pmoves-5090` is `active; direct` in the tailnet while its `:8055`
answers `000` — node reachable, service absent. Meanwhile this node has an RTX
4090 (16 GB VRAM) sitting idle, because Claude runs in the cloud. Routing
synthesis past a free local GPU to a peer that is down is the wrong default for
a fabric documented as capability-routed and self-healing.

## What this does NOT do

**It declares intent; it activates nothing, and the profile comment says so.**
`pmoves/tools/profile_loader.py` does not read `channels` at all (verified — its
only importer is `mini_cli.py`), so this block is descriptive.

That is stated in the file rather than left implied, because the opposite
assumption is this repo's recurring defect: `gw-priority` applied to 0 of 107
multi-homed services, `pmoves_core.vpn_nodes` with 0 writers and 0 readers,
`gateway-agent` POSTing to a `/skills` route Cipher never mounted, `disabled:
true` on an MCP entry that Claude Code's schema ignores. A config that looks
authoritative and matches nothing is worse than an absent one.

For the same reason the fallback is named `peer_endpoint` rather than
`fallback_endpoint`: nothing reads either field, and a consumed-*looking* name
would repeat exactly the defect the comment warns about.

## Operator follow-up

Activation is separate and operator-side. The engines are Pinokio 8 apps, and
the local voice stack was brought up during this session:

- OmniVoice (`k2-fsa`, Apache-2.0) serving on `cuda:0` at `:8002`
- Flute-Gateway healthy at `:8055` with `DEFAULT_VOICE_PROVIDER=omnivoice`
- Ultimate-TTS Studio (14 engines) installing; `intent=dramatic` routes to
  `kitten_tts` inside it, so expressive intents need it present

## Related

- #2889 — `voice-health`'s NATS row could never be green (probed the client
  protocol port for `/healthz`); now derives the monitor endpoint and discovers
  the broker container rather than assuming the hub's name.
- #2891 — the Pinokio install root is per-node; every `pinokio:*` command
  hardcoded a drive letter that does not exist on this node.
