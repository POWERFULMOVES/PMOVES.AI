# PMOVES.YT n8n Workflow

## Overview
This n8n workflow automates the **complete YouTube ingestion pipeline** using the `pmoves-yt` service with **automatic Jellyfin library mapping**:

1. **Webhook Trigger** - Receives YouTube URLs via HTTP POST
2. **Full Ingest** - Downloads transcript + metadata via `/yt/ingest`
3. **Extract Video ID** - Parses response for video metadata
4. **Emit to Hi-RAG** - Indexes transcript chunks via `/yt/emit` (parallel)
5. **Generate Summary** - Creates AI summary via `/yt/summarize` (parallel)
6. **Auto-Map to Jellyfin** - Links video to Jellyfin library item via title matching
7. **Webhook Response** - Returns success/failure to caller
8. **Discord Notification** - Optional Discord webhook for monitoring

## Architecture

```mermaid
graph LR
    A[Webhook POST] --> B[/yt/ingest]
    B --> C[Extract Video ID]
    C --> D[/yt/emit]
    C --> E[/yt/summarize]
    D --> F[/jellyfin/map-by-title]
    F --> G[Return Success]
    E --> H[Discord Notification]
    D --> F[Return Success]
    E --> G[Discord Notification]
```

## Installation

### 1. Import Workflow to n8n
```bash
# Access n8n UI
open http://localhost:5678

# Import workflow JSON
# Workflows → Import from File → Select n8n_pmoves_yt_workflow.json
```

### 2. Configure Credentials (Optional)
- **Discord Webhook**: Set `DISCORD_WEBHOOK_URL` environment variable for notifications
- **No other credentials needed** - workflow uses internal Docker network

### 3. Activate Workflow
- Click "Activate" toggle in n8n UI
- Webhook will be available at: `http://localhost:5678/webhook/youtube-ingest`

## Usage

### Trigger via HTTP POST
```bash
curl -X POST http://localhost:5678/webhook/youtube-ingest \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
    "namespace": "pmoves",
    "bucket": "assets"
  }'
```

### Expected Response
```json
{
  "success": true,
  "video_id": "dQw4w9WgXcQ",
  "namespace": "pmoves",
  "title": "Rick Astley - Never Gonna Give You Up",
  "video": {
    "video_id": "dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up",
    "namespace": "pmoves",
    "s3_url": "s3://assets/dQw4w9WgXcQ/raw.mp4",
    "thumb": "https://cdn.example.com/dQw4w9WgXcQ.jpg"
  },
  "transcript_ready": true,
  "chunks_indexed": 42,
  "summary_generated": true,
  "jellyfin_mapped": false,
  "jellyfin_item_id": null,
  "message": "YouTube video successfully ingested and indexed"
}
```

## Workflow Nodes Explained

### 1. Webhook Trigger
- **Type**: HTTP POST webhook
- **Path**: `/webhook/youtube-ingest`
- **Input**: `{"url": "...", "namespace": "...", "bucket": "..."}`
- **Purpose**: Entry point for YouTube ingestion requests

### 2. PMOVES.YT - Full Ingest
- **Endpoint**: `POST http://pmoves-yt:8077/yt/ingest`
- **Timeout**: 300 seconds (5 min) for large transcripts
- **Purpose**: Downloads YouTube transcript + metadata to MinIO
- **Output**:
  ```json
  {
    "ok": true,
    "video": {
      "video_id": "dQw4w9WgXcQ",
      "title": "Rick Astley - Never Gonna Give You Up",
      "namespace": "pmoves",
      "s3_url": "s3://assets/dQw4w9WgXcQ/raw.mp4",
      "thumb": "https://cdn.example.com/dQw4w9WgXcQ.jpg"
    },
    "transcript": {
      "ok": true,
      "language": "en",
      "text": "...",
      "s3_uri": "s3://assets/dQw4w9WgXcQ/transcripts/en.json"
    }
  }
  ```

### 3. Extract Video ID
- **Type**: JavaScript code node
- **Purpose**: Parse response and prepare for next steps
- **Output**: Clean JSON with `video` metadata (video_id, namespace, title), plus top-level aliases, transcript readiness flag, and timestamp for downstream nodes

### 4. PMOVES.YT - Emit to Hi-RAG (Parallel)
- **Endpoint**: `POST http://pmoves-yt:8077/yt/emit`
- **Timeout**: 180 seconds (3 min) for chunking + embedding
- **Purpose**: Chunk transcript and send to Hi-RAG for indexing
- **Output**: `{"ok": true, "chunks": 42, "namespace": "..."}`

### 5. PMOVES.YT - Generate Summary (Parallel)
- **Endpoint**: `POST http://pmoves-yt:8077/yt/summarize`
- **Timeout**: 120 seconds (2 min) for AI generation
- **Parameters**: `style=long, provider=ollama`
- **Purpose**: Generate AI summary using local Ollama
- **Output**: `{"ok": true, "summary": "...", "provider": "ollama"}`

### 6. Webhook Response
- **Type**: Respond to Webhook
- **Purpose**: Return success JSON to original caller
- **Includes**: video metadata (nested + top-level aliases), namespace, transcript readiness, chunks indexed, summary status, optional Jellyfin mapping details

### 7. Discord Notification (Optional)
- **Type**: HTTP POST
- **Endpoint**: Discord webhook URL (from env var)
- **Purpose**: Send formatted notification to Discord channel
- **Can be disabled**: Set node to disabled if not needed

## Monitoring

### View Executions in n8n
```bash
# Access n8n UI
open http://localhost:5678

# Navigate to:
# Executions → Select workflow → View execution details
```

### Check Service Logs
```bash
# pmoves-yt service
docker logs -f pmoves-pmoves-yt-1 --tail 100

# n8n workflow executor
docker logs -f pmoves-n8n-1 --tail 100

# Hi-RAG indexing
docker logs -f pmoves-hi-rag-gateway-1 --tail 50
```

## Troubleshooting

### Workflow Fails at Ingest Step
- **Check**: Is `pmoves-yt` service running? `docker ps | grep pmoves-yt`
- **Check**: Does YouTube URL have transcript? Test manually: `/yt/has_transcript?url=...`
- **Check**: MinIO storage available? `docker ps | grep minio`

### No Chunks Indexed
- **Check**: Is Hi-RAG gateway running? `docker ps | grep hi-rag`
- **Check**: Ollama embeddings model loaded? `docker exec pmoves-ollama-1 ollama list`
- **Check**: pmoves-yt logs for `/yt/emit` errors

### Summary Generation Fails
- **Check**: Ollama service healthy? `curl http://localhost:11434/api/tags`
- **Check**: Model loaded? `docker exec pmoves-ollama-1 ollama list | grep llama3.2`
- **Fallback**: Change provider to `openai` (requires API key in env)

### Discord Notification Not Sent
- **Check**: `DISCORD_WEBHOOK_URL` set in n8n environment?
- **Option**: Disable node if not needed (node settings → Disabled toggle)

## Integration with Jellyfin Backfill

This workflow can be **triggered programmatically** from the Jellyfin backfill script:

```python
# In backfill_jellyfin_metadata.py
async def trigger_n8n_ingest(youtube_url: str, namespace: str = "pmoves"):
    """Trigger n8n workflow instead of direct pmoves-yt calls"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:5678/webhook/youtube-ingest",
            json={"url": youtube_url, "namespace": namespace, "bucket": "assets"},
            timeout=360.0  # Wait for full pipeline
        )
        return resp.json()
```

## Performance Notes

- **Full pipeline**: ~3-7 minutes per video (depends on transcript length)
- **Parallel execution**: Summary generation runs alongside Hi-RAG indexing
- **Timeouts**: Configured generously to handle large transcripts
- **Rate limiting**: Consider adding delays if processing many videos

## Next Steps

1. **Test with sample video**: Use Rick Astley video (`dQw4w9WgXcQ`) for smoke test
2. **Monitor first execution**: Watch logs and n8n execution view
3. **Integrate with Jellyfin**: Call n8n webhook from backfill script
4. **Add error handling**: Create n8n error workflow for failed ingests
5. **Scale up**: Add batch processing for multiple videos

## Related Documentation

- [pmoves-yt API Reference](../JELLYFIN_YOUTUBE_INTEGRATION.md)
- [Hi-RAG Gateway Documentation](../HI_RAG_GATEWAY.md)
- [n8n Configuration](../../docker-compose.n8n.yml)
- [Smoke Tests](../SMOKETESTS.md)
