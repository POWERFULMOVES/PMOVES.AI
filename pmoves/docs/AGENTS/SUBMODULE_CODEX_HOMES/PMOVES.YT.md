# Codex Home Overlay: PMOVES.YT

Scope:
- YouTube ingest, transcript acquisition, and media-to-knowledge routing parity.

Use this when:
- the task starts from YouTube URLs, channels, playlists, captions, or transcript fallback
- Codex needs the media ingest lane that feeds retrieval, notebook, or publish workflows
- the traversal question involves `ingest.file.added.v1` or `ingest.transcript.ready.v1`

PMOVES companions:
- `Channel Monitor` for discovery
- `PMOVES-transcribe-and-fetch` for auxiliary transcript/fetch workflows
- `PMOVES-HiRAG` and `Extract Worker` for downstream retrieval/indexing
- `PMOVES-Jellyfin` for playback/publishing
- `Invidious` for fallback reachability

Core checks:
- `curl -fsS http://localhost:8077/healthz`
- `make -C pmoves channel-monitor-smoke`
- `make -C pmoves yt-jellyfin-smoke`

Related parity tokens:
- `/yt:status`
- `/yt:list-channels`
- `/yt:ingest-video`
- `/yt:check-now`

Related docs:
- `pmoves/docs/AGENTS/CODEX_ECOSYSTEM_TRAVERSAL.md`
- `.claude/commands/yt/help.md`
- `.claude/context/services-catalog.md`
