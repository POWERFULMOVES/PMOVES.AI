# Codex Home Overlay: PMOVES-transcribe-and-fetch

Scope:
- YouTube/transcription ingestion parity and channel monitor interoperability.

Core checks:
- `make -C pmoves yt-jellyfin-smoke`
- `make -C pmoves channel-monitor-smoke`
- `curl -fsS http://localhost:8077/healthz`

Related parity tokens:
- `/yt:ingest-video`
- `/yt:pending`
- `/yt:list-channels`
