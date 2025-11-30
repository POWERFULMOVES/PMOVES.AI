# Jellyfin + YouTube Backfill Quickstart

**Goal**: Enable YouTube transcript linking in Jellyfin backfill using existing `pmoves-yt` service

## Prerequisites

- ✅ pmoves-yt running on port 8077 (already deployed)
- ✅ hi-rag-gateway-v2 running on port 8086 (for semantic search)
- ✅ Jellyfin configured with API credentials
- ✅ `studio_board` table with published content

## Step 1: Add Search Endpoint to pmoves-yt

**File**: `pmoves/services/pmoves-yt/yt.py`

Add this endpoint after the existing routes:

```python
@app.post('/yt/search')
def yt_search(body: Dict[str,Any] = Body(...)):
    """Semantic search across YouTube transcript corpus."""
    query = body.get('query')
    if not query:
        raise HTTPException(400, 'query required')
    
    limit = int(body.get('limit', 10))
    threshold = float(body.get('threshold', 0.70))
    namespace = body.get('namespace', DEFAULT_NAMESPACE)
    
    # Query hi-rag for YouTube chunks
    try:
        payload = {'query': query, 'k': limit * 3, 'namespace': namespace}
        r = requests.post(f"{HIRAG_URL}/hirag/query", json=payload, timeout=30)
        r.raise_for_status()
        chunks = r.json().get('chunks', [])
        
        # Filter for YouTube content and format for backfill
        yt_chunks = []
        seen_videos = set()
        
        for chunk in chunks:
            doc_id = chunk.get('doc_id', '')
            if not doc_id.startswith('yt:'):
                continue
            
            video_id = doc_id.split(':')[1]
            if video_id in seen_videos:
                continue
            
            score = chunk.get('score', 0.0)
            if score < threshold:
                continue
            
            seen_videos.add(video_id)
            
            # Fetch video metadata from Supabase
            vid_rows = supa_get('videos', {'video_id': video_id}) or []
            title = vid_rows[0].get('title') if vid_rows else video_id
            
            yt_chunks.append({
                'video_id': video_id,
                'title': title,
                'url': f"https://youtube.com/watch?v={video_id}",
                'similarity': score,
                'excerpt': chunk.get('text', '')[:300],
                'timestamp': chunk.get('payload', {}).get('t_start')
            })
            
            if len(yt_chunks) >= limit:
                break
        
        return {'ok': True, 'query': query, 'results': yt_chunks, 'total': len(yt_chunks)}
    
    except requests.RequestException as e:
        raise HTTPException(502, f"hi-rag query failed: {e}")
```

## Step 2: Update Backfill Script

**File**: `pmoves/scripts/backfill_jellyfin_metadata.py`

Update the `search_youtube_transcripts` function:

```python
async def search_youtube_transcripts(client: httpx.AsyncClient, query: str, limit: int = 5, threshold: float = YOUTUBE_SIMILARITY_THRESHOLD) -> List[Dict[str, Any]]:
    """Search YouTube transcript corpus for semantically similar content via pmoves-yt."""
    try:
        resp = await client.post(
            "/yt/search",  # Use pmoves-yt endpoint
            json={"query": query, "limit": limit, "threshold": threshold},
            timeout=30.0
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
        print(f"⚠️  YouTube search failed: {exc}")
        return []
```

Update the `load_env()` function:

```python
def load_env() -> Dict[str, str]:
    env = {
        "SUPA_REST_URL": os.environ.get("SUPA_REST_URL") or os.environ.get("SUPABASE_REST_URL"),
        "SUPABASE_SERVICE_ROLE_KEY": os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
        "AGENT_ZERO_BASE_URL": os.environ.get("AGENT_ZERO_BASE_URL", "http://localhost:8080").rstrip("/"),
        "JELLYFIN_URL": os.environ.get("JELLYFIN_URL"),
        "JELLYFIN_PUBLIC_BASE_URL": os.environ.get("JELLYFIN_PUBLIC_BASE_URL"),
        "JELLYFIN_API_KEY": os.environ.get("JELLYFIN_API_KEY"),
        "PMOVES_YT_URL": os.environ.get("PMOVES_YT_URL", "http://localhost:8077").rstrip("/"),
    }
    missing = [key for key, value in env.items() if value in (None, "", [])]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
    # ... rest of validation
    return env
```

> Configure `PMOVES_YT_URL` to match the pmoves-yt FastAPI service (default `http://localhost:8077`).
Update the `backfill()` function client initialization:

```python
async def backfill(limit: int, dry_run: bool, sleep: float, start_after: Optional[str], link_youtube: bool, youtube_threshold: float) -> None:
    env = load_env()
    supabase_headers = {
        "apikey": env["SUPABASE_SERVICE_ROLE_KEY"],
        "Authorization": f"Bearer {env['SUPABASE_SERVICE_ROLE_KEY']}",
    }
    async with httpx.AsyncClient(base_url=env["SUPA_REST_URL"], headers=supabase_headers, timeout=15.0) as supa_client, \
        httpx.AsyncClient(base_url=env["JELLYFIN_URL"], headers={"X-Emby-Token": env["JELLYFIN_API_KEY"]}, timeout=10.0) as jellyfin_client, \
        httpx.AsyncClient(base_url=env["AGENT_ZERO_BASE_URL"], timeout=10.0) as agent_client, \
        httpx.AsyncClient(base_url=env["PMOVES_YT_URL"], timeout=30.0) as yt_client:
        # ... rest of function, replace mcp_client with yt_client
```

> **Embedding note:** the Supabase table now persists three vector columns:
> - `embedding_st` (384 dims) for MiniLM/sentence-transformers models
> - `embedding_gemma` (768 dims) for `google/embeddinggemma-300m` and related Gecko models
> - `embedding_qwen` (2560 dims) for `Qwen/Qwen3-Embedding-4B` and Matryoshka variants  
> Configure `YOUTUBE_EMBEDDING_MODEL`, optional `YOUTUBE_EMBEDDING_COLUMN`, and `YOUTUBE_EMBEDDING_DIM`
> in `services/mcp_youtube_adapter.py` to pick the correct column when running semantic search.

## Step 3: Rebuild and Restart pmoves-yt

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Rebuild with new endpoint
docker-compose build pmoves-yt

# Restart service
docker-compose restart pmoves-yt

# Verify service is healthy
curl http://localhost:8077/healthz
```

## Step 4: Test YouTube Search

```bash
# Test search endpoint
curl -X POST http://localhost:8077/yt/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning tutorial",
    "limit": 5,
    "threshold": 0.70
  }'
```

Expected response:
```json
{
  "ok": true,
  "query": "machine learning tutorial",
  "results": [
    {
      "video_id": "abc123",
      "title": "Introduction to Machine Learning",
      "url": "https://youtube.com/watch?v=abc123",
      "similarity": 0.856,
      "excerpt": "In this video, we cover the basics of machine learning...",
      "timestamp": 42.5
    }
  ],
  "total": 1
}
```

## Step 5: Test Backfill with YouTube Linking

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Dry run first
python3 scripts/backfill_jellyfin_metadata.py \
  --limit 3 \
  --dry-run \
  --link-youtube \
  --youtube-threshold 0.75

# If successful, run for real (small batch first)
python3 scripts/backfill_jellyfin_metadata.py \
  --limit 5 \
  --sleep 2 \
  --link-youtube \
  --youtube-threshold 0.70
```

## Step 6: Verify Enriched Metadata

Check that `studio_board` rows now have YouTube links:

```sql
-- In Supabase SQL editor
select 
  id,
  title,
  meta->>'jellyfin_public_url' as jellyfin_url,
  meta->'jellyfin_meta'->'related_youtube' as youtube_links,
  meta->>'youtube_linked_count' as yt_count
from studio_board
where status = 'published'
  and (meta->>'backfill_version') = '2025-10-17'
limit 5;
```

## Troubleshooting

### No YouTube Results Found

**Problem**: Search returns empty results

**Diagnosis**:
```bash
# Check if any YouTube content is indexed
curl http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "k": 10, "namespace": "pmoves"}'
```

**Solution**: Ingest YouTube videos first:
```bash
# Ingest a test video
curl -X POST http://localhost:8077/yt/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
    "namespace": "pmoves"
  }'

# Emit to hi-rag for indexing
curl -X POST http://localhost:8077/yt/emit \
  -H "Content-Type: application/json" \
  -d '{"video_id": "dQw4w9WgXcQ", "namespace": "pmoves"}'
```

### pmoves-yt Build Fails

**Problem**: Docker build fails with import errors

**Solution**:
```bash
# Check if services/common/events.py exists
ls -la /home/pmoves/PMOVES.AI/pmoves/services/common/events.py

# If missing, pmoves-yt has a fallback envelope function
# Just rebuild and restart
docker-compose build pmoves-yt --no-cache
docker-compose restart pmoves-yt
```

### Backfill Script Can't Connect

**Problem**: `httpx.ConnectError` when calling pmoves-yt

**Solution**:
```bash
# Check service is running
docker ps | grep pmoves-yt

# Check port is accessible
curl http://localhost:8077/healthz

# If using Docker network, update URL
export PMOVES_YT_URL="http://pmoves-yt:8077"
```

## Next Steps

1. **Add more YouTube content**: Use `/yt/playlist` or `/yt/channel` to bulk ingest
2. **Scheduled backfills**: Add cron job to run backfill weekly
3. **Monitor Discord embeds**: Verify enriched payloads appear in Discord
4. **Tune similarity threshold**: Adjust `--youtube-threshold` based on results

## Environment Variables Summary

```bash
# Required for backfill
JELLYFIN_URL=http://localhost:9096
JELLYFIN_API_KEY=your-api-key
AGENT_ZERO_BASE_URL=http://localhost:8080
SUPA_REST_URL=http://localhost:54321
SUPABASE_SERVICE_ROLE_KEY=your-service-key

# Optional (defaults provided)
PMOVES_YT_URL=http://localhost:8077
JELLYFIN_PUBLIC_BASE_URL=http://172.21.119.177:9096
YOUTUBE_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2   # override for Qwen/Gemma support
YOUTUBE_EMBEDDING_COLUMN=embedding_st                            # embedding_st | embedding_gemma | embedding_qwen
YOUTUBE_EMBEDDING_DIM=384                                         # match selected embedding model
YOUTUBE_EMBEDDING_API_URL=                                        # optional remote embedding endpoint
```

## Reference

- [Jellyfin Backfill Plan](./JELLYFIN_BACKFILL_PLAN.md)
- [pmoves-yt Service Documentation](./PMOVES.yt/PMOVES_YT.md)
- [Jellyfin + YouTube Integration](./JELLYFIN_YOUTUBE_INTEGRATION.md)
