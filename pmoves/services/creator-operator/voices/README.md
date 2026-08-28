# OmniVoice reference-voice catalog

Drop approved reference clips here (wav/m4a/mp3). The filename (without
extension) is the catalog id passed as `voice_ref` → `ref_audio` to
POST /synthesize — the server resolves ids under this dir only, never raw paths.

Naming contract: a catalog id is a single path component — no `/`, `\`, or
`..`. The voice-sampler worker enforces this at the publication boundary
(rejects, doesn't sanitize) and writes `<catalog-id>.wav`; the same id is what
`pmoves_core.voice_profiles.name` / `ref_audio_path` will reference once the
DB-backed profile registry lands. Manual drops should follow the same rule.

Population path (set, not preset): media source (PMOVES.YT / Jellyfin) →
media-audio diarization → operator approves segments in the room pub-gate →
clips land here + in JuiceFS `rooms/<room>/creator/references/voice/`.

This dir ships empty on purpose: no voice exists until its owner approves one.
