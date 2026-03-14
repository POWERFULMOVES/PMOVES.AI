# YouTube to Persona Pipeline

**Pipeline ID:** `youtube-to-persona`
**Status:** Production Ready
**Purpose:** Build persona profiles from YouTube channel content

---

## Overview

This pipeline ingests YouTube content, processes transcripts through media analysis, extracts consciousness theories, and builds geometric persona profiles via the CONCH pipeline.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {
  'primaryColor': '#3ecf8e',
  'primaryBorderColor': '#3ecf8e',
  'secondaryColor': '#9333ea',
  'secondaryBorderColor': '#a855f7',
  'tertiaryColor': '#fbbf24',
  'tertiaryBorderColor': '#d97706',
  'background': 'transparent'
}}}%%
flowchart LR
    classDef ingest fill:#3ecf8e,stroke:#2db380,color:#000
    classDef process fill:#9333ea,stroke:#7c2d12,color:#fff
    classDef output fill:#fbbf24,stroke:#d97706,color:#000
    classDef storage fill:#404040,stroke:#525252,color:#ededed

    YT["📺 YouTube Channel"]:::ingest
    PM["PMOVES.YT :8077"]:::ingest
    MIO["📦 MinIO"]:::storage
    MW["FFmpeg-Whisper :8078"]:::process
    EW["Extract Worker :8083"]:::process
    HR["Hi-RAG v2 :8086"]:::process
    CS["consciousness :8096"]:::process
    NATS["🔀 NATS Geometry Bus"]:::output
    HD["🎨 Hyperdimensions"]:::output
    PG["🚪 PersonaGate"]:::output

    YT --> PM
    PM --> MIO
    PM --> MW
    MW --> EW
    EW --> HR
    HR --> CS
    CS --> NATS
    NATS --> HD
    NATS --> PG
```

> **📊 Diagram Source:** [diagrams/youtube-to-persona.mmd](../diagrams/youtube-to-persona.mmd)

---

## Pipeline Stages

### Stage 1: YouTube Ingestion

**Service:** PMOVES.YT (8077)

**Action:** Monitor YouTube channels for new content

```bash
# Add channel for monitoring
/yt:add-channel "https://www.youtube.com/@channel"

# Check channels now
/yt:check-now

# List all channels
/yt:list-channels

# Ingest specific video
/yt:ingest-video "VIDEO_ID"
```

**Events:**
- `ingest.file.added.v1` - New video downloaded to MinIO
- `ingest.transcript.ready.v1` - Transcript retrieved

**Storage:**
- Videos: `minio://outputs/videos/`
- Transcripts: `minio://outputs/transcripts/`

---

### Stage 2: Media Processing

**Services:**
- FFmpeg-Whisper (8077) - Transcription
- Media-Video Analyzer (8079) - YOLOv8 frame analysis
- Media-Audio Analyzer (8082) - Emotion/speaker detection

**Processing Flow:**

```bash
# Transcript processing (automatic)
curl http://localhost:8078/transcribe \
  -d '{"video_path": "minio://outputs/videos/VIDEO_ID.mp4"}'

# Video frame analysis (automatic)
curl http://localhost:8079/analyze \
  -d '{"video_path": "minio://outputs/videos/VIDEO_ID.mp4"}'

# Audio analysis (automatic)
curl http://localhost:8082/analyze \
  -d '{"audio_path": "minio://outputs/videos/VIDEO_ID.mp3"}'
```

**Outputs:**
- Transcript text: `minio://outputs/transcripts/VIDEO_ID.txt`
- Frame embeddings: Supabase `pmoves_core.video_frames`
- Audio features: Supabase `pmoves_core.audio_features`

---

### Stage 3: Embedding & Indexing

**Service:** Extract Worker (8083)

**Action:** Generate embeddings and index to vector/graph stores

```bash
# Trigger extraction (usually automatic)
curl http://localhost:8083/ingest \
  -d '{"text": "transcript content...", "namespace": "youtube"}'
```

**Indexes:**
- Qdrant: `pmoves_chunks` (vector search)
- Neo4j: Entity nodes (graph traversal)
- Meilisearch: Full-text keyword search

---

### Stage 4: Theory Extraction

**Service:** Hi-RAG v2 (8086)

**Action:** Query for consciousness-related content

```python
import httpx

async def extract_theories(transcript_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8086/hirag/query",
            json={
                "query": "consciousness theories philosophy mind materialism dualism",
                "top_k": 10,
                "rerank": True,
                "filters": {"namespace": "youtube"}
            }
        )
        return response.json()
```

**Extraction:**
- Identify theory mentions
- Extract proponents
- Categorize by taxonomy
- Build text units for CHR

---

### Stage 5: CONCH Processing

**Service:** consciousness-service (8096)

**Action:** Run CHR algorithm on extracted theories

```bash
# Run CHR on extracted theories
curl -X POST http://localhost:8096/chr/run \
  -H "Content-Type: application/json" \
  -d '{
    "units": [
      {
        "id": "theory-001",
        "text": "Materialism is the theory that...",
        "namespace": "pmoves.consciousness",
        "metadata": {"source": "youtube", "video_id": "VIDEO_ID"}
      }
    ],
    "publish_to_nats": true
  }'
```

**Output:**
- CGP packet with geometric clustering
- MHEP quality metric
- Constellation assignments

---

### Stage 6: Persona Evaluation

**Service:** consciousness-service (8096) - PersonaGate

**Action:** Evaluate persona against threshold gates

```bash
# Evaluate persona
curl -X POST http://localhost:8096/persona/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": "youtube_channel_X",
    "metrics": {
      "empirical_support": 0.6,
      "philosophical_coherence": 0.7,
      "integration_potential": 0.5,
      "description_length": 120,
      "proponent_count": 3
    }
  }'
```

**Thresholds:**
| Gate | Minimum |
|------|---------|
| `min_empirical_support` | 0.3 |
| `min_philosophical_coherence` | 0.4 |
| `min_integration_potential` | 0.3 |
| `min_description_length` | 50 |
| `min_proponents` | 1 |

---

### Stage 7: GEOMETRY BUS Publishing

**Action:** Publish persona CGP to NATS

**Subjects:**
- `geometry.cgp.v1` - CGP packet for indexing/rendering
- `tokenism.cgp.ready.v1` - Ready signal for Tokenism
- `tokenism.attribution.recorded.v1` - Attribution record

```json
{
  "spec": "chit.cgp.v1.0",
  "summary": "Persona: youtube_channel_X (Consciousness Theories)",
  "super_nodes": [{
    "id": "persona_youtube_channel_X",
    "label": "YouTube Channel Persona",
    "constellations": [...]
  }],
  "meta": {
    "source": "youtube-to-persona.pipeline.v1",
    "persona_id": "youtube_channel_X",
    "tags": ["youtube", "persona", "consciousness"]
  }
}
```

---

## Environment Variables

### Required

| Variable | Purpose | Default |
|----------|---------|---------|
| `NATS_URL` | NATS connection | `nats://nats:pmoves@nats:4222` |
| `SUPABASE_URL` | Supabase API | `http://supabase-kong:8000` |
| `SUPABASE_ANON_KEY` | Supabase auth | - |
| `MINIO_ROOT_USER` | MinIO credentials | - |
| `MINIO_ROOT_PASSWORD` | MinIO credentials | - |

### Optional

| Variable | Purpose | Default |
|----------|---------|---------|
| `YOUTUBE_API_KEY` | YouTube Data API | - |
| `CHR_K` | Constellation count | 8 |
| `CHR_ITERS` | Optimization iterations | 30 |

---

## Docker Compose Profile

```bash
# Start all pipeline services
docker compose --profile yt --profile agents --profile workers up -d

# Services included:
# - PMOVES.YT (8077)
# - FFmpeg-Whisper (8078)
# - Media-Video Analyzer (8079)
# - Media-Audio Analyzer (8082)
# - Extract Worker (8083)
# - Hi-RAG v2 (8086)
# - consciousness-service (8096)
# - NATS
# - Supabase
# - MinIO
# - Qdrant
# - Neo4j
# - Meilisearch
```

---

## Usage Example

### Complete Pipeline Workflow

```bash
# 1. Add YouTube channel
/yt:add-channel "https://www.youtube.com/@PhilosophyChannel"

# 2. Check for new videos
/yt:check-now

# 3. Wait for processing (automatic)
# Transcript → Whisper → Extract → Index

# 4. Extract consciousness theories
/search:hirag "consciousness theories materialism dualism" \
  --namespace "youtube" \
  --top-k 10

# 5. Run CHR on extracted theories
curl -X POST http://localhost:8096/chr/from-supabase \
  -d '{"namespace": "youtube", "limit": 50}'

# 6. Evaluate persona
curl -X POST http://localhost:8096/persona/evaluate \
  -d '{"persona_id": "youtube_philosophy", "metrics": {...}}'

# 7. Monitor NATS for CGP publication
nats sub "geometry.cgp.v1"
```

---

## Monitoring

### Pipeline Health

```bash
# Check all services
/health:check-all

# Check specific services
curl http://localhost:8077/healthz  # PMOVES.YT
curl http://localhost:8078/healthz  # FFmpeg-Whisper
curl http://localhost:8096/healthz  # consciousness-service
curl http://localhost:8086/healthz  # Hi-RAG v2
```

### NATS Events

```bash
# Monitor pipeline events
nats sub "ingest.>"
nats sub "geometry.>"
nats sub "tokenism.>"
```

### Data Flow

```bash
# Check MinIO storage
/minio:status

# Check Supabase records
/db:query "SELECT COUNT(*) FROM pmoves_core.video_frames"
/db:query "SELECT * FROM pmoves_core.consciousness_theories LIMIT 10"

# Check vector index
curl http://localhost:8083/metrics
```

---

## Troubleshooting

### Common Issues

**Issue:** YouTube channel not monitored
```
Solution: Check PMOVES.YT status
/yt:status
/yt:check-now
```

**Issue:** Transcript not retrieved
```
Solution: Verify Whisper service
curl http://localhost:8078/healthz
Check MinIO credentials
```

**Issue:** CHR returns low MHEP
```
Solution: Increase input text units
Adjust CHR parameters (K, iters)
Check theory extraction quality
```

**Issue:** Persona evaluation fails
```
Solution: Verify metrics meet thresholds
Check: /persona/thresholds
Update: PUT /persona/thresholds
```

---

## References

- **Main Docs:** [../README.md](../README.md)
- **CONCH Integration:** [../../CONCH_INTEGRATION_MAP.md](../../CONCH_INTEGRATION_MAP.md)
- **Hi-RAG v2:** `PMOVES-HiRAG/CLAUDE.md`
- **PMOVES.YT:** `.claude/context/services-catalog.md`
