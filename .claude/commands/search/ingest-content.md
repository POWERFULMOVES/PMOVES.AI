# Ingest Content to Hi-RAG

Ingest text content into Hi-RAG v2 for knowledge retrieval.

## Pipeline Paths

### Path 1: YouTube → PMOVES.YT → Extract Worker → Qdrant
```bash
# Step 1: Ingest video (downloads + transcribes)
curl -X POST http://localhost:8077/yt/ingest \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'

# Step 2: Push transcript to extract-worker (chunks + embeds + indexes)
curl -X POST http://localhost:8083/ingest \
  -H "Content-Type: application/json" \
  -d '{"chunks": [{"text": "...", "chunk_id": "unique-id"}]}'

# Step 3: Query via Hi-RAG
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "search terms", "top_k": 5}'
```

### Path 2: Direct text → Extract Worker
```bash
curl -X POST http://localhost:8083/ingest \
  -H "Content-Type: application/json" \
  -d '{"chunks": [{"text": "content here", "chunk_id": "doc-1"}]}'
```

## Known Issues

- Extract-worker requires TensorZero + Ollama for Qwen3 embeddings
- If TensorZero embedding fails (500), fall back to `EXTRACT_WORKER_EMBEDDING_BACKEND=sentence-transformers`
- `QDRANT_COLLECTION` must match between extract-worker and Hi-RAG (both should be `pmoves_chunks_qwen3`)
- PMOVES.YT downloads + transcribes but does NOT auto-trigger extract-worker — manual POST required

## Dependencies

| Service | Port | Role |
|---------|------|------|
| PMOVES.YT | 8077 | YouTube download + transcribe |
| Extract Worker | 8083 | Chunk + embed + index |
| Hi-RAG v2 | 8086 | Query (hybrid search) |
| Qdrant | 6333 | Vector storage (Docker internal) |
| Meilisearch | 7700 | Full-text search (Docker internal) |
| TensorZero | 3030 | Embedding model routing |
| Ollama | 11434 | Local embedding model (qwen3-embedding:4b) |

## HuggingFace Alternatives (No TensorZero dependency)

For environments without TensorZero/Ollama, use direct HuggingFace models:
- `BAAI/bge-large-en-v1.5` (1024d, high quality)
- `sentence-transformers/all-MiniLM-L6-v2` (384d, fast)
- `Alibaba-NLP/gte-Qwen2-1.5B-instruct` (1536d, multilingual)

Set `EXTRACT_WORKER_EMBEDDING_BACKEND=sentence-transformers` in env to bypass TensorZero.

## Make Targets

```bash
make -C pmoves up-hirag       # Start Hi-RAG v2
make -C pmoves up-workers     # Start extract-worker + media workers
make -C pmoves brand-defaults # Set QDRANT_COLLECTION default
```
