# PMOVES.YT — Channel Monitor & YouTube API Backlog

_Status: Draft • Last updated: 2025-11-08_

This tracker captures the backend milestones required to elevate the PMOVES Channel Monitor from RSS/yt-dlp polling to a YouTube Data API-driven ingestion service with per-user preferences.

## 1. Objectives
- Authenticate against Google APIs per PMOVES user and refresh tokens automatically.
- Discover and ingest playlist, channel, and search content using the YouTube Data API, falling back to RSS/yt-dlp when necessary.
- Respect per-source ingestion preferences (media depth, transcript-only, creator remixes, etc.) when queueing jobs into `pmoves-yt`.
- Provide observability, documentation, and smoketests covering the new API-driven flow.

## 2. Milestone Tracker
| Area | Task | Owner | Target | Status | Notes |
|------|------|-------|--------|--------|-------|
| Auth foundation | Capture Google OAuth client id/secret in `env.shared` and expose to channel-monitor | — | 2025-11-10 | ☑ | Env vars flow through `main.py`; follow-up docs pending. |
| Auth foundation | Implement `/api/oauth/google/token` refresh & storage (access + refresh) | — | 2025-11-10 | ⏳ | Tokens persist with expiry; surface expiry in stats still open. |
| API integration | Implement YouTube playlist ingestion via Data API (`playlistItems`, `videos`) | — | 2025-11-12 | ☑ | `YouTubeAPIClient` hydrates metadata to yt-dlp parity. |
| API integration | Implement channel discovery/search adapters (keyword, related channels, subscriptions) | — | 2025-11-14 | ☐ | Store nextPageToken per source. |
| API integration | Wire API-first fetch path into `ChannelMonitor.check_single_channel`, fallback to RSS | — | 2025-11-14 | ☑ | API fetch preferred with OAuth token; handles resolve via Data API. |
| Preferences & control | Extend `pmoves.user_sources` with ingestion preferences (depth, transcripts, analysis level) | — | 2025-11-16 | ☐ | Add migration + API CRUD. |
| Preferences & control | Pass ingestion directives through to `pmoves-yt` queue payloads | — | 2025-11-16 | ☐ | Ensure pmoves-yt honors transcript-only and remix modes. |
| Observability | Expand `/api/monitor/stats` with API quota, token health, discovery counts | — | 2025-11-17 | ☐ | Add Prometheus counters. |
| Observability | Create `make channel-monitor-smoke` covering OAuth mock + playlist ingest | — | 2025-11-18 | ☐ | Capture evidence for docs/PR. |
| Documentation | Update `CHANNEL_MONITOR_IMPLEMENTATION.md`, `PMOVES_YT.md`, smoketest docs | — | 2025-11-18 | ☐ | Include Google API setup steps. |

## 3. Risk & Dependency Log
- Need Google Cloud project and consent screen in place before OAuth flows can be validated.
- API quotas must be monitored; consider caching responses or batching playlist fetches to stay within daily limits.
- `pmoves-yt` must honor new metadata flags; coordinate with that service before enabling transcript-only ingest.

## 4. Verification Plan
- Local smoke: `make channel-monitor-smoke` with recorded OAuth credentials (or mocked httpx session).
- Integration: Run `make up`, `make up-yt`, `make channel-monitor-up`, trigger `/api/monitor/check-now`, confirm Supabase rows and queue payloads include preference metadata.
- Evidence: Supabase screenshots, queue logs, and API quota dashboards added to `pmoves/docs/logs/`.

## 5. Next Update
Add owners and update status columns after kickoff review. Capture any scope adjustments here so PRs can reference this backlog directly.
