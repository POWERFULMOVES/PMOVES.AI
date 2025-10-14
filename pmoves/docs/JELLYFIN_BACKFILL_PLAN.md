# Jellyfin Metadata Backfill Plan
_Last updated: 2025-10-14_

## Goal
Retrofit historic `content.published` records so every asset in the PMOVES catalog exposes the enriched Jellyfin metadata fields (`jellyfin_public_url`, `thumbnail_url`, duration, tags, etc.). The backfill ensures Discord embeds, Agent Zero clients, and downstream analytics receive consistent payloads regardless of when the item was published.

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
