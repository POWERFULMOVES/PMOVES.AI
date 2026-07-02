---
graphiti_mark: handoff.flute-omnivoice-wiring.2026-06-26
branch: chore/omnivoice-4090-bringup
pr_numbers: [1885]
scope: Wire flute-gateway → OmniVoice — add OMNIVOICE_URL/TOKEN/TIMEOUT to the
  flute-gateway env and flip the default TTS provider (env template + compose) to omnivoice.
risks: Flips the fleet default vibevoice→omnivoice (env-reversible via DEFAULT_VOICE_PROVIDER);
  touches z890's vibevoice lane (path intact). Joint host deploy needs OMNIVOICE_BIND=0.0.0.0 + token.
next_actions: Joint-deploy bring OmniVoice up 0.0.0.0+OMNIVOICE_TOKEN; add OMNIVOICE_TOKEN to secrets pipeline; z890 awareness of default flip.
chit_artifact_path: n/a (docs + compose wiring; no CHIT artifact)
agent_signature: 4090-claude
---

# Flute-Gateway → OmniVoice Wiring (2026-06-26)

**By:** 4090-CLAUDE. **Known Road handoff** authorizing the compose edit
(`KNOWN_ROAD=compose:handoff:flute-omnivoice-wiring-2026-06-26.md`). Operator
authorized this wiring directly ("wire flute-gateway + run a TTS smoke" → yes).

## Context

OmniVoice is **activated + healthy on the 4090** (`pmoves-omnivoice:latest`,
cuda:0, :8002 — see `[[project_omnivoice_activation]]`). Two TTS smokes passed:
- **Direct:** `POST /synthesize {"text":...}` → 215 KB RIFF WAV.
- **Provider:** the flute-gateway `OmniVoiceProvider` (`health_check` + `synthesize`)
  drove the live server → 192 KB RIFF WAV. The integration code path is proven.

The remaining gap was **deployed config**: flute-gateway's env had
`DEFAULT_VOICE_PROVIDER` (default `vibevoice`) but **no `OMNIVOICE_URL`/`OMNIVOICE_TOKEN`**,
so a deployed flute-gateway would hit its own container loopback, not OmniVoice.

## Edit (source of truth = ROOT `docker-compose.yml`, NOT the overlay)

`pmoves/docker-compose.media.yml` is **generated** from `pmoves/docker-compose.yml`
by `scripts/split_compose.py` (editing the overlay alone is dropped on regen).
So the flute-gateway env is edited in the root compose, then overlays are
regenerated with `make -C pmoves compose-split` (drift-gated by `compose-split-check`
/ the `ci/compose-split-gate` CI job, #1881).

flute-gateway `environment:` changes:
- add `OMNIVOICE_URL=${OMNIVOICE_URL:-http://host.docker.internal:8002}`
  (host-gateway resolves to the host where OmniVoice listens; flute-gateway
  `main.py` already normalizes a 127.0.0.1 OmniVoice URL → host.docker.internal).
- add `OMNIVOICE_TOKEN=${OMNIVOICE_TOKEN:-}` (sent as `X-OmniVoice-Token`).
- add `OMNIVOICE_TIMEOUT_SEC=${OMNIVOICE_TIMEOUT_SEC:-300}`.
- flip `DEFAULT_VOICE_PROVIDER` default `vibevoice` → **`omnivoice`** (the wiring
  intent; OmniVoice is the license-clean creator-pipeline TTS). **Still overridable**
  — `DEFAULT_VOICE_PROVIDER=vibevoice` restores the prior default.

## Runtime requirement (for joint deployment — not in this PR)

When flute-gateway and OmniVoice run on the **same host**, bring OmniVoice up with
`OMNIVOICE_BIND=0.0.0.0` (+ set `OMNIVOICE_TOKEN`) so the flute-gateway container
can reach it via `host.docker.internal:8002` — a `127.0.0.1` bind is host-loopback
only and unreachable from sibling containers on Linux/bridge. The 4090 validation
ran OmniVoice host-only (`127.0.0.1`) deliberately; the provider smoke ran from the
host. Token is required once bound to 0.0.0.0 (tailnet-exposed).

## Lane note

`vibevoice` is **z890's** voice lane (`z890-compose-voice-vibevoice-media-profile.md`).
Flipping the *default* to omnivoice is reversible via env and doesn't remove the
vibevoice path — flagged for z890 awareness. See `[[reference_creator_pipeline_models]]`.
