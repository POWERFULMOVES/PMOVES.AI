# Ingest YouTube Video

Manually ingest a specific YouTube video through PMOVES.YT.

## Arguments

- `$ARGUMENTS` - YouTube video URL or video ID

## Instructions

1. Parse video URL/ID from arguments
   - If URL: extract video ID from various formats (youtu.be, youtube.com/watch, etc.)
   - If ID: use directly (11 characters)
2. Call PMOVES.YT ingest endpoint:

```bash
curl -X POST http://localhost:8077/yt/ingest \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v={video_id}", "namespace": "pmoves.manual"}'
```

3. Monitor progress:
```bash
docker logs pmoves-pmoves-yt-1 --tail 30 -f
```

4. Report:
   - Download status
   - Transcript extraction status
   - MinIO storage location
   - NATS events published
