# Jellyfin Metadata Backfill Plan
_Last updated: 2025-10-14_

## Goal
Retrofit historic `content.published` records so every asset in the PMOVES catalog exposes the enriched Jellyfin metadata fields (`jellyfin_public_url`, `thumbnail_url`, duration, tags, etc.). The backfill ensures Discord embeds, Agent Zero clients, and downstream analytics receive consistent payloads regardless of when the item was published.

For local smoke runs, make sure the Jellyfin overlay contains at least one media asset (`python scripts/seed_jellyfin_media.py` drops a lightweight tone clip under `pmoves/jellyfin-ai/media/music`) so the bridge can mint playback URLs even on fresh machines.

## Data Sources
| Source | Purpose |
| --- | --- |
| `studio_board` (Supabase) | Source of truth for publish status, `meta.publish_event_sent_at`, and the original asset payload. |
| `publisher_rollup` / `publisher_discord_metrics` | Audit tables that identify already processed publish events and Discord delivery state. |
| Jellyfin API (`/Users/{id}/Items`, `/Items/{id}`) | Used to resolve canonical Jellyfin IDs, duration, and thumbnails when missing from historical payloads. |
| Object storage (`s3://outputs/*`) | Provides fallback thumbnails when Jellyfin metadata cannot be located. |

## High-Level Approach
1. **Identify candidate rows**  
   ```sql
   select id, title, content_url, meta
   from studio_board
   where status = 'published'
     and (meta->>'jellyfin_public_url') is null;
   ```
   Record the list of `id`s that require a refresh.

2. **Batch fetch Jellyfin metadata**  
   - Use the service account (`JELLYFIN_API_KEY`) to call `/Items/{id}`.  
   - If the Jellyfin item is missing, fall back to a search on `Name` + `PremiereDate`.  
   - Capture: `Id`, `Path`, `RunTimeTicks`, `UserData`, `ImageTags.Primary`, `ProductionYear`.

3. **Construct enriched payloads**  
   For each candidate, build a payload that mirrors the current `content.published.v1` schema. Key fields:
   - `jellyfin_item_id`
   - `jellyfin_public_url` (use `JELLYFIN_PUBLIC_BASE_URL` from bootstrap)
   - `duration` (convert `RunTimeTicks` to seconds)
   - `thumbnail_url` (prefer Jellyfin primary image, fall back to storage artifact)
   - `tags` / `namespace` (reuse existing metadata, append a `"backfill"` tag)

4. **Republish via Agent Zero**  
   - Call `POST /events/publish` with the enriched payload (`topic=content.published.v1`, `source=backfill`).  
   - Ensure NATS JetStream and `publisher-discord` are running so updated embeds are emitted.  
   - Record returned envelope IDs for traceability.

5. **Persist audit markers**  
   - Update `studio_board.meta.publish_event_sent_at` when missing.  
   - Store `meta.jellyfin_public_url`, `meta.jellyfin_item_id`, and `meta.backfill_version="2025-10-14"`.

6. **Verification**  
   - Use `docker logs publisher-discord` (or a mock webhook) to confirm embeds contain duration, thumbnail, and Jellyfin deep link.  
   - Run `python pmoves/tools/realtime_listener.py --topics content.published.v1 --max 5` to verify envelopes.  
   - Snapshot Supabase rows before/after for the runbook.

## Automation Script Outline
Skeleton for `pmoves/scripts/backfill_jellyfin_metadata.py`:

```python
import asyncio
import httpx
import os

SUPABASE_URL = os.environ["SUPA_REST_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
AGENT_ZERO_URL = os.environ.get("AGENT_ZERO_BASE_URL", "http://localhost:8080")
JELLYFIN_URL = os.environ["JELLYFIN_URL"].rstrip("/")
PUBLIC_BASE = os.environ.get("JELLYFIN_PUBLIC_BASE_URL", JELLYFIN_URL)
API_KEY = os.environ["JELLYFIN_API_KEY"]

async def fetch_candidates(client):
    resp = await client.get(
        f"{SUPABASE_URL}/studio_board",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"},
        params={"status": "eq.published", "meta->>jellyfin_public_url": "is.null"},
    )
    resp.raise_for_status()
    return resp.json()

async def fetch_jellyfin(item_id):
    async with httpx.AsyncClient(timeout=10.0, headers={"X-Emby-Token": API_KEY}) as client:
        resp = await client.get(f"{JELLYFIN_URL}/Items/{item_id}")
        resp.raise_for_status()
        return resp.json()

async def publish(payload):
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{AGENT_ZERO_URL}/events/publish",
            json={"topic": "content.published.v1", "payload": payload, "source": "backfill"},
        )
        resp.raise_for_status()
        return resp.json()["id"]

async def main():
    async with httpx.AsyncClient(timeout=10.0) as client:
        rows = await fetch_candidates(client)
    for row in rows:
        item = await fetch_jellyfin(row["meta"].get("jellyfin_item_id"))
        payload = build_payload(row, item, PUBLIC_BASE)
        env_id = await publish(payload)
        print("republished", env_id)

if __name__ == "__main__":
    asyncio.run(main())
```

Add `--dry-run` and batching before production use.

## Rollout Checklist
1. Refresh env secrets via `make bootstrap`.  
2. Run the backfill script in dry-run mode; review sample payloads.  
3. Execute the script in batches (e.g., `--limit 25 --sleep 2`) to respect Discord rate limits.  
4. Collect evidence (listener transcript, Discord embed, Supabase diff).  
5. Update `pmoves/docs/NEXT_STEPS.md` with the completion timestamp.

## Open Questions
- Should we log backfill runs in a dedicated audit table?  
- How do we handle assets that no longer exist in Jellyfin?  
- Do we resend Discord embeds for every backfilled asset or only update Supabase metadata?

---

## Implementation Status

**Updated: 2025-10-17**

### Completed

- ✅ Jellyfin server operational (v10.11.0) on port 8096
- ✅ Invidious + companion stack online (launch via `make -C pmoves up-invidious`)
- ✅ Device ID persisted correctly in `jellyfin-ai/config/data/data/device.txt`
- ✅ Published server URL configured via `JELLYFIN_PUBLISHED_URL`
- ✅ Web UI accessible and cache clear utility created
- ✅ Docker compose volume mounts configured for persistence
- ✅ API credentials configured (JELLYFIN_API_KEY, JELLYFIN_USER_ID)
- ✅ Backfill script implemented with YouTube transcript linking
- ✅ MCP YouTube adapter service created (`mcp_youtube_adapter.py`)

### In Progress

- 🔄 PMOVES.yt batch processor deployment (for YouTube corpus population)
- 🔄 YouTube transcript table schema in Supabase
- 🔄 Test content creation in studio_board for backfill validation

### Next Steps

1. **Deploy PMOVES.yt infrastructure**:
   ```bash
   cd pmoves
   docker-compose -f docker-compose.yml -f docker-compose.n8n.yml up -d
   # Add YouTube batch processor from docs/PMOVES.yt/batch_docker_coolify.md
   ```

2. **Create YouTube transcript table in Supabase**:
   ```sql
   create table if not exists youtube_transcripts (
     video_id text primary key,
     title text not null,
     description text,
     channel text,
     url text not null,
     published_at timestamptz,
     duration float,
     transcript text,
     embedding_st vector(384),          -- sentence-transformers / MiniLM
     embedding_gemma vector(768),       -- google/embeddinggemma-* family
     embedding_qwen vector(2560),       -- Qwen/Qwen3-Embedding-* (full dimension)
     meta jsonb default '{}'::jsonb,
     created_at timestamptz default now(),
     updated_at timestamptz default now()
   );
   
   -- Enable vector similarity search for each embedding family
   create index youtube_embedding_st_idx on youtube_transcripts 
     using ivfflat (embedding_st vector_cosine_ops) with (lists = 100);
   create index youtube_embedding_gemma_idx on youtube_transcripts 
     using ivfflat (embedding_gemma vector_cosine_ops) with (lists = 100);
   create index youtube_embedding_qwen_idx on youtube_transcripts 
     using ivfflat (embedding_qwen vector_cosine_ops) with (lists = 100);
   ```
   > Set `YOUTUBE_EMBEDDING_MODEL`, `YOUTUBE_EMBEDDING_COLUMN`, and optional `YOUTUBE_EMBEDDING_DIM`
   > in the MCP adapter when switching between MiniLM, Qwen, or EmbeddingGemma vectors.

3. **Start MCP YouTube adapter**:
   ```bash
   cd pmoves
   MCP_DOCKER_URL=http://localhost:8081 \
   uvicorn services.mcp_youtube_adapter:app --host 0.0.0.0 --port 8081
   ```

4. **Test backfill with YouTube linking**:
   ```bash
   cd pmoves
   python scripts/backfill_jellyfin_metadata.py \
     --limit 5 \
     --dry-run \
     --link-youtube \
     --youtube-threshold 0.75
   ```

5. **Execute production backfill**:
   ```bash
   python scripts/backfill_jellyfin_metadata.py \
     --limit 25 \
     --sleep 2 \
     --link-youtube
   ```
