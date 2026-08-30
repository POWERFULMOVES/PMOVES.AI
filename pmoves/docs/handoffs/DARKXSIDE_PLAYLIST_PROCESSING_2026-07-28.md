# DARKXSIDE Playlist Processing Handoff

**Created:** 2026-07-28
**Node:** Knuckles (B850, AMD, residential egress)
**Branch:** `feat/upstream-sync-2026.07` (PMOVES.YT submodule)

## Context

The YouTube ingestion pipeline is fully operational with a 1-2 punch architecture:
1. **Metadata** via YouTube Data API v3 (IP-agnostic, works from datacenter)
2. **File download** via yt-dlp 2026.07.04 + Deno 2.3.3 (works on residential IP)

The DARKXSIDE playlist (`PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8`) has 102 videos
covering AI, energy, tech, and community topics. This content should be processed
to ground personas, enrich the content creator pipeline, and populate the
Fordham Hill website tenant page.

## Prerequisites

Before starting, verify the pipeline is healthy:

```bash
# 1. Ensure residential egress (NOT datacenter)
make -C pmoves yt-direct
make -C pmoves yt-egress-check
# Expected: Exit node: none, Container IP shows residential

# 2. Verify metadata path works
python3 -c "
import httpx
r = httpx.post('http://localhost:8077/yt/info',
    json={'url': 'https://www.youtube.com/watch?v=fb2BaANfCLg'}, timeout=30)
print(r.json())
"
# Expected: source=data_api, title returned

# 3. Verify download works (short video)
python3 -c "
import httpx
r = httpx.post('http://localhost:8077/yt/download',
    json={'url': 'https://www.youtube.com/watch?v=k7Fq5gx2dmA'}, timeout=120)
print(r.status_code, r.text[:200])
"
```

## Processing Plan

### Phase 1: Playlist Crawl (Data API)

Fetch full metadata for all 102 videos using the Data API. This does NOT
download files — it builds the content catalog.

```python
# Use the channel-monitor's YouTubeAPIClient or direct Data API calls.
# The refresh token is at: /app/config/cookies/yt-refresh-token.txt
# (shared volume from cookie-writer)

import requests

# Exchange refresh token for access token
resp = requests.post("https://oauth2.googleapis.com/token", data={
    "client_id": GOOGLE_CLIENT_ID,
    "client_secret": GOOGLE_CLIENT_SECRET,
    "grant_type": "refresh_token",
    "refresh_token": refresh_token,
})
token = resp.json()["access_token"]

# Fetch playlist items
resp = requests.get("https://www.googleapis.com/youtube/v3/playlistItems", params={
    "part": "snippet,contentDetails",
    "playlistId": "PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8",
    "maxResults": 50,
}, headers={"Authorization": f"Bearer {token}"})
# Paginate with pageToken for remaining videos

# Then fetch video details (duration, stats, tags)
video_ids = [item["contentDetails"]["videoId"] for item in items]
resp = requests.get("https://www.googleapis.com/youtube/v3/videos", params={
    "part": "snippet,contentDetails,statistics",
    "id": ",".join(video_ids[:50]),
}, headers={"Authorization": f"Bearer {token}"})
```

Store results in Supabase `pmoves_core.youtube_videos` or a new staging table.

### Phase 2: Selective Download

Based on Phase 1 metadata, select videos for full ingestion (download +
transcription). Prioritize:

- Videos matching persona domains (AI/ML, energy, community, creator economy)
- Shorter videos (< 30 min) for faster processing
- Videos with high view counts (signals relevance)

```python
# Download + transcribe selected videos
import httpx
r = httpx.post("http://localhost:8077/yt/ingest", json={
    "url": f"https://www.youtube.com/watch?v={video_id}",
    "namespace": "darkxside",
}, timeout=3600)
```

### Phase 3: Persona Grounding

Map processed videos to PMOVES personas:

| Persona | Content Domains | Playlist Keywords |
|---------|----------------|-------------------|
| DARKXSIDE | cocreation, media synthesis | AI art, music, creative |
| POWERFULMOVES | vision, doctrine | strategy, community, DAO |
| Crush | terminal gateway, onboarding | dev tools, automation |
| Fordham Steward | community, cost-saving | energy, food co-op, mesh |

Use Hi-RAG v2 to index transcript segments and link them to persona manifests
in `pmoves/config/personas/`.

### Phase 4: Website Enrichment

Update the Fordham Hill tenant page (`website/tenant-template/data/fordham-hill.json`)
with real content references:

- Featured videos from the playlist (embedded players)
- Topic clusters as "community knowledge" cards
- Creator guild showcase items
- Timeline events from video publish dates

## Key Files

| File | Purpose |
|------|---------|
| `PMOVES.YT/pmoves_yt_service/yt.py` | `/yt/info` (Data API), `/yt/download`, `/yt/ingest` |
| `pmoves/services/channel-monitor/channel_monitor/youtube_api.py` | `YouTubeAPIClient` with playlist fetching |
| `website/tenant-template/data/fordham-hill.json` | Fordham tenant data (enrichment target) |
| `pmoves/config/personas/` | Persona manifests for grounding |
| `pmoves/docs/operations/YT_EGRESS_RUNBOOK.md` | Egress mode guide |
| `pmoves/docs/operations/YT_COOKIES_RUNBOOK.md` | Cookie pipeline guide |

## Important Notes

- **Egress**: Use `make -C pmoves yt-direct` to ensure residential IP. Datacenter
  IPs get bot-checked by YouTube. Data API metadata works from any IP.
- **Rate limits**: Data API v3 quota is 10,000 units/day. Playlist listing costs
  1 unit per page (50 videos). Video details cost 1 unit per 50 videos. Full
  crawl of 102 videos costs ~5 units total.
- **Download**: Each video download + transcription takes 2-10 minutes depending
  on length. Process in batches of 5-10 to avoid timeouts.
- **Branch**: PMOVES.YT submodule is on `feat/upstream-sync-2026.07`. The parent
  repo is on `feat/fordham-cataclysm-enrichment`. Commit results to the
  appropriate branch.

## Verification

After processing, verify:

```bash
# Check ingested videos in Supabase
python3 -c "
import httpx
key = open('pmoves/env.tier-supabase').read().split('SERVICE_ROLE_KEY=')[1].split('\n')[0]
r = httpx.get('http://localhost:8000/rest/v1/videos?namespace=eq.darkxside&select=video_id,title,duration&limit=10',
    headers={'apikey': key, 'Authorization': f'Bearer {key}'})
print(r.json())
"
```
