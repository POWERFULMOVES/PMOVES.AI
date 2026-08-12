# Voice Sampler — media-sourced voice references (spec v1)

> Set, not preset: a voice enters the system only when its owner approves
> segments of their own media. No preset ships. 2026-08-07, 5090 lane.

## Problem

Every piece of the cloning stack exists and none of them connect:

| Piece | Where | State |
|---|---|---|
| Clone API | flute-gateway `providers/cloning.py` (`/v1/voice/clone/register → train → synthesize_cloned`) | idle |
| Ref-audio synth | OmniVoice `:8002` catalog (`OMNIVOICE_REFERENCE_VOICE_DIR=/voices`) | bind enabled 2026-08-07 |
| Diarization | media-audio `:8082` — pyannote/speaker-diarization-3.1 (HF_TOKEN-gated) + whisper-large-v3-turbo | up (workers profile) |
| Media sources | PMOVES.YT (MinIO + transcripts), Jellyfin (`jellyfin-bridge`) | live |
| Agent spine | voice-relay (`voice.agent.response.v1`) | live |

## Flow

```text
[1] SOURCE     operator picks a media item (PMOVES.YT video id / Jellyfin item id)
[2] ANALYZE    media-audio /analyze {analysis_type: diarization} → speaker turns
[3] AUDITION   segments grouped per speaker; operator listens, tags "this is me"
[4] APPROVE    pub-gate decision in the room (owner-only) — nothing proceeds without it
[5] PUBLISH    approved clips →
                 a. JuiceFS  rooms/<room>/creator/references/voice/<persona>/<clip>.wav
                 b. OmniVoice catalog  services/creator-operator/voices/<catalog-id>.wav
                 c. flute /v1/voice/clone/register {persona_id, sample}
[6] ANNOUNCE   NATS voice.reference.published.v1 {persona_id, catalog_id, source, chit_sig}
```

## Components

1. **voice-sampler worker** (new, `pmoves/services/voice-sampler/`): thin
   orchestrator over existing APIs — fetch media (MinIO presign / jellyfin-bridge
   stream), call media-audio diarize, cut segments (pydub, already in the
   media-audio image; the worker can also delegate cutting), stage candidates
   in JuiceFS `.../voice-candidates/`, execute step 5 on approval events.
2. **Voice Vault room app** (manifest `apps[]` entry, route `/voice-vault`):
   source picker → speaker lanes → audition player → approve/reject per segment.
   Renders in OpenRoom via the room adapter; approval posts the pub-gate event.
3. **NATS subjects** (register in catalog):
   - `voice.sample.candidates.v1` — sampler → room (candidates ready)
   - `voice.reference.approved.v1` — room → sampler (owner approved; input only)
   - `voice.reference.published.v1` — sampler → downstream (emitted only after
     all writes succeed). Approval and publication are separate subjects so a
     replayed approval can't masquerade as a completed publish; re-publishing
     the same `catalog_id` overwrites the same `<catalog-id>.wav` (idempotent,
     not duplicative).
4. **Identifier contract** (publication boundary): `room`, `persona_id`, and
   `catalog_id` must be single path components — no `/`, `\`, or `..`; the
   sampler *rejects* (fail-closed), it does not sanitize. The OmniVoice catalog
   file becomes `voices/<catalog-id>.wav`, whose basename is the `voice_ref` id
   OmniVoice resolves (and the future `pmoves_core.voice_profiles.name` /
   `ref_audio_path` values). Same contract documented in
   `pmoves/services/creator-operator/voices/README.md`.

## Gates

- Diarization requires HF_TOKEN + accepted pyannote 3.1 license on the HF account.
- Owner-only: approval events must carry the room owner's identity; the sampler
  refuses to publish references for a persona whose owner didn't sign.
- Voice references are personal data: JuiceFS + local catalog only. Never in git,
  never in artifacts, never on public surfaces.

## Why this closes Gate 4

The operator's voice already exists across their own media. Gate 4 stops being
"record a fresh sample" and becomes "approve which segments represent you" —
a pub-gate decision, in the room, exactly where such decisions live. H3 Omni
(Maestro ≥1.6.0) then consumes the same approved clips as voice conditioning
references for video generation — one approval, every engine.
