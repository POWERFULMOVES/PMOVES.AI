# Creator previews — darkxsides.room staging

Preview artifacts for DARKSIDE room (darkxsides.room, stage: rehearsal,
owner-only per manifest).

- `voice_live_2026-10-11.wav` — first routed synthesis artifact
  (pmoves_voice_router policy -> OmniVoice /synthesize on the Windows/5090
  host, cross-node reachability verified from SPARK over the tailnet same day).

H3 creator pipeline: installers at `pmoves/creator/installers/MINIMAX-H3-*`
(5090-Claude lane, merged); execution test gated on GPU node + HF-token
rotation (pyannote diarization whoami 401 until then).
