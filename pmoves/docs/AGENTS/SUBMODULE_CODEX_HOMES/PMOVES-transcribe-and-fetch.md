# Codex Home Overlay: PMOVES-transcribe-and-fetch

Scope:
- YouTube/transcription ingestion parity and channel monitor interoperability.
- Auxiliary transcript, fetch, and repair lane that should stay aligned with PMOVES.YT rather than
  competing with it as a primary runtime.

Use this when:
- PMOVES.YT needs transcript/fetch augmentation
- Channel Monitor has discovered content that needs extraction or transcript repair
- a creator workflow depends on transcript quality, fallback fetch, or recovery from upstream rate limits

PMOVES companions:
- `PMOVES.YT` for authoritative YouTube runtime and metadata
- `Channel Monitor` for source discovery and scheduling
- `Discord` and `BoTZ` for operator interaction
- `Jellyfin` for downstream packaging and playback
- `local/remote model tiers` for transcript cleanup, summarization, and embedding

Core checks:
- `make -C pmoves yt-jellyfin-smoke`
- `make -C pmoves channel-monitor-smoke`
- `curl -fsS http://localhost:8077/healthz`
- `curl -fsS http://localhost:8097/api/monitor/status | jq .`

Worktree review:
- use `pmoves/docs/AGENTS/PMOVES_YT_CONTROL_WORKTREE_REVIEW.md` when the task spans
  PMOVES.YT, channel-monitor, Jellyfin, Discord, or model-routing parity

Operating rules:
- do not fork behavior away from PMOVES.YT without documenting why the auxiliary lane is needed
- preserve metadata that lets downstream services track source, model family, and transcript provenance
- align transcript/fetch outputs with Discord, Jellyfin, retrieval, and Tokenism consumers

Related parity tokens:
- `/yt:ingest-video`
- `/yt:pending`
- `/yt:list-channels`
