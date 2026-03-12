# Codex Home Overlay: PMOVES.YT

Scope:
- YouTube ingest, transcript acquisition, and media-to-knowledge routing parity.
- Authoritative runtime now lives in the PMOVES.YT submodule package `pmoves_yt_service/`.
- This is also the creator control lane for owned channels, watched sources, playlist management,
  fallback extraction, and operator-facing YouTube workflows.

Use this when:
- the task starts from YouTube URLs, channels, playlists, captions, or transcript fallback
- Codex needs the media ingest lane that feeds retrieval, notebook, or publish workflows
- the traversal question involves `ingest.file.added.v1` or `ingest.transcript.ready.v1`

PMOVES companions:
- `Channel Monitor` for discovery
- `PMOVES-transcribe-and-fetch` for auxiliary transcript/fetch workflows
- `PMOVES-HiRAG` and `Extract Worker` for downstream retrieval/indexing
- `PMOVES-Jellyfin` for playback/publishing
- `Invidious` and `invidious-companion` for fallback reachability and PO token support
- `Discord` and `BoTZ` for creator/operator interaction
- `Tokenism` for attribution and value tracking

Operator intent classes:
- owned sources: manage channel, playlists, metadata, and PMOVES-origin publishing
- watched sources: monitor creators, ingest references, and prepare attribution-aware follow-up
- candidate sources: scout adjacent creators and queue for review rather than auto-engage

Preferred traversal:
- start with `pmoves/docs/PMOVES.AI PLANS/CREATOR_NETWORK_CONTROL_PLANE.md`
- then verify the PMOVES.YT service and its downloader posture
- then inspect Channel Monitor and transcribe-and-fetch if the task spans discovery or transcript fallback
- only use direct downloader overrides when the default PMOVES.YT strategy is insufficient

Core checks:
- `git submodule status -- PMOVES.YT`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES.YT`
- `make -C pmoves submodule-branch-policy-check`
- `curl -fsS http://localhost:8077/healthz`
- `curl -fsS http://localhost:8077/yt/docs/catalog`
- `curl -fsS -X POST http://localhost:8077/yt/docs/sync`
- `curl -fsS "http://localhost:8077/yt/search?q=pmoves"`
- `make -C pmoves channel-monitor-smoke`
- `make -C pmoves yt-jellyfin-smoke`

Implementation notes:
- prefer the modern client chain and current yt-dlp defaults rather than hardcoded legacy Android assumptions
- prefer companion-fetched PO tokens and current client-context formatting when tokenized access is needed
- keep root compose wiring for `INVIDIOUS_BASE_URL` and `INVIDIOUS_COMPANION_URL` aligned with the submodule runtime
- public comments or creator outreach actions should be human-approved by default unless the workflow explicitly declares autonomous behavior

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
