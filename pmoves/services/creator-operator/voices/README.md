# OmniVoice reference-voice catalog

Drop approved reference clips here (wav/m4a/mp3). The filename (without
extension) is the catalog id passed as `voice_ref` → `ref_audio` to
POST /synthesize — the server resolves ids under this dir only, never raw paths.

Population path (set, not preset): media source (PMOVES.YT / Jellyfin) →
media-audio diarization → operator approves segments in the room pub-gate →
clips land here + in JuiceFS `rooms/<room>/creator/references/voice/`.

This dir ships empty on purpose: no voice exists until its owner approves one.
