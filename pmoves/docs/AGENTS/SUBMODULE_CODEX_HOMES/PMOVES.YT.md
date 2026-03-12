# Codex Home Overlay: PMOVES.YT

Scope:
- YouTube ingest, transcript acquisition, and media-to-knowledge routing parity.
- Authoritative runtime now lives in the PMOVES.YT submodule package `pmoves_yt_service/`.

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
- `git submodule status -- PMOVES.YT`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES.YT`
- `make -C pmoves submodule-branch-policy-check`
- `curl -fsS http://localhost:8077/healthz`
- `curl -fsS http://localhost:8077/yt/docs/catalog`
- `curl -fsS -X POST http://localhost:8077/yt/docs/sync`
- `make -C pmoves channel-monitor-smoke`
- `make -C pmoves yt-jellyfin-smoke`

Related parity tokens:
- `/yt:status`
- `/yt:list-channels`
- `/yt:ingest-video`
- `/yt:check-now`
- `/worktree:status`
- `/github:checks`
- `/deploy:status`

Related docs:
- `pmoves/docs/AGENTS/CODEX_ECOSYSTEM_TRAVERSAL.md`
- `.claude/commands/yt/help.md`
- `.claude/context/services-catalog.md`
