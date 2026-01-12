# Functional Test Architecture

Visual guide to how functional tests integrate with PMOVES.AI services.

## Test Coverage Map

```
┌─────────────────────────────────────────────────────────────────┐
│                    PMOVES.AI Architecture                        │
└─────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│  MODEL GATEWAY LAYER                                              │
│  ┌──────────────────────────────────────────────┐                │
│  │  TensorZero Gateway (port 3030)              │                │
│  │  ✓ test_tensorzero_inference.sh              │                │
│  │    - Chat completions                         │                │
│  │    - Inference endpoint                       │                │
│  │    - Embeddings                               │                │
│  │    - ClickHouse observability                 │                │
│  └──────────────────────────────────────────────┘                │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│  AGENT ORCHESTRATION LAYER                                        │
│  ┌──────────────────────────────────────────────┐                │
│  │  Agent Zero (port 8080)                      │                │
│  │  ✓ test_agent_zero_mcp.sh                    │                │
│  │    - MCP API (describe, execute, commands)   │                │
│  │    - Health checks                            │                │
│  │    - NATS integration                         │                │
│  └──────────────────────────────────────────────┘                │
│                                                                   │
│  ┌──────────────────────────────────────────────┐                │
│  │  Archon (port 8091)                          │                │
│  │  ✓ test_agent_zero_mcp.sh                    │                │
│  │    - Prompts management                       │                │
│  │    - Agent forms                              │                │
│  └──────────────────────────────────────────────┘                │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│  KNOWLEDGE RETRIEVAL LAYER                                        │
│  ┌──────────────────────────────────────────────┐                │
│  │  Hi-RAG v2 Gateway (port 8086)               │                │
│  │  ✓ test_hirag_query.sh                       │                │
│  │    - Hybrid query execution                   │                │
│  │    - Cross-encoder reranking                  │                │
│  │    - Filter-based queries                     │                │
│  │                                               │                │
│  │  Backend Services:                            │                │
│  │  ├─ Qdrant (port 6333) - Vector search       │                │
│  │  ├─ Neo4j (port 7474) - Graph traversal      │                │
│  │  └─ Meilisearch (port 7700) - Full-text      │                │
│  └──────────────────────────────────────────────┘                │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│  MESSAGE BUS LAYER                                                │
│  ┌──────────────────────────────────────────────┐                │
│  │  NATS Server (port 4222)                     │                │
│  │  ✓ test_nats_pubsub.sh                       │                │
│  │    - Server connectivity                      │                │
│  │    - JetStream streams                        │                │
│  │    - Pub/Sub messaging                        │                │
│  │    - Critical subject routing:                │                │
│  │      • research.deepresearch.*                │                │
│  │      • supaserch.*                            │                │
│  │      • ingest.*                               │                │
│  │      • claude.code.tool.executed.*            │                │
│  └──────────────────────────────────────────────┘                │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│  MEDIA PROCESSING LAYER                                           │
│  ┌──────────────────────────────────────────────┐                │
│  │  PMOVES.YT (port 8077)                       │                │
│  │  ✓ test_media_ingestion.sh                   │                │
│  │    - YouTube ingestion                        │                │
│  │    - Video info retrieval                     │                │
│  │    - Ingestion status                         │                │
│  └──────────────────────────────────────────────┘                │
│                                                                   │
│  ┌──────────────────────────────────────────────┐                │
│  │  Whisper (port 8078)                         │                │
│  │  ✓ test_media_ingestion.sh                   │                │
│  │    - Transcription service                    │                │
│  └──────────────────────────────────────────────┘                │
│                                                                   │
│  ┌──────────────────────────────────────────────┐                │
│  │  Video Analyzer (port 8079)                  │                │
│  │  ✓ test_media_ingestion.sh                   │                │
│  │    - YOLOv8 object detection                  │                │
│  └──────────────────────────────────────────────┘                │
│                                                                   │
│  ┌──────────────────────────────────────────────┐                │
│  │  Audio Analyzer (port 8082)                  │                │
│  │  ✓ test_media_ingestion.sh                   │                │
│  │    - Emotion detection                        │                │
│  └──────────────────────────────────────────────┘                │
│                                                                   │
│  ┌──────────────────────────────────────────────┐                │
│  │  Extract Worker (port 8083)                  │                │
│  │  ✓ test_media_ingestion.sh                   │                │
│  │    - Embedding generation                     │                │
│  │    - Indexing to Qdrant/Meilisearch          │                │
│  └──────────────────────────────────────────────┘                │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│  STORAGE LAYER                                                    │
│  ┌──────────────────────────────────────────────┐                │
│  │  MinIO (port 9000)                           │                │
│  │  ✓ test_media_ingestion.sh                   │                │
│  │    - Object storage                           │                │
│  │    - Health checks                            │                │
│  └──────────────────────────────────────────────┘                │
└───────────────────────────────────────────────────────────────────┘
```

## Test Flow Diagrams

### TensorZero Inference Flow

```
┌──────────────────┐
│ Test Script      │
│ test_tensorzero_ │
│ inference.sh     │
└────────┬─────────┘
         │
         ├──► Health Check ──────► TensorZero Gateway :3030
         │
         ├──► Chat Completion ───► /v1/chat/completions
         │                          │
         │                          └──► Claude Sonnet 4.5
         │
         ├──► Inference ──────────► /inference
         │                          │
         │                          └──► Custom Functions
         │
         ├──► Embeddings ─────────► /v1/embeddings
         │                          │
         │                          └──► text-embedding-3-small
         │
         ├──► ClickHouse ─────────► :8123/ping
         │                          │
         │                          └──► Observability Data
         │
         └──► Metrics ────────────► /metrics
```

### Hi-RAG Query Flow

```
┌──────────────────┐
│ Test Script      │
│ test_hirag_      │
│ query.sh         │
└────────┬─────────┘
         │
         ├──► Health Check ──────► Hi-RAG v2 :8086
         │
         ├──► Basic Query ───────► /hirag/query
         │                          │
         │                          ├──► Qdrant (vectors)
         │                          ├──► Neo4j (graph)
         │                          └──► Meilisearch (text)
         │
         ├──► Reranked Query ────► /hirag/query?rerank=true
         │                          │
         │                          └──► Cross-Encoder Reranking
         │
         └──► Filtered Query ────► /hirag/query + filters
```

### NATS Event Flow

```
┌──────────────────┐
│ Test Script      │
│ test_nats_       │
│ pubsub.sh        │
└────────┬─────────┘
         │
         ├──► Server Ping ────────► NATS :4222
         │
         ├──► Pub/Sub Test ───────► test.functional.*
         │                          │
         │                          ├──► Publish
         │                          └──► Subscribe & Verify
         │
         ├──► JetStream ──────────► Create Stream
         │                          │
         │                          ├──► TEST_STREAM
         │                          └──► test.stream.*
         │
         └──► Critical Subjects ──► research.*, ingest.*, etc.
```

### Agent Zero MCP Flow

```
┌──────────────────┐
│ Test Script      │
│ test_agent_zero_ │
│ mcp.sh           │
└────────┬─────────┘
         │
         ├──► Health Check ──────► Agent Zero :8080/healthz
         │
         ├──► MCP Describe ──────► /mcp/describe
         │                          │
         │                          └──► Available Tools/Commands
         │
         ├──► MCP Execute ───────► /mcp/execute
         │                          │
         │                          └──► Command Execution
         │
         ├──► Archon Integration ► Archon :8091
         │                          │
         │                          ├──► /healthz
         │                          └──► /prompts
         │
         └──► NATS Integration ──► Check Streams
```

### Media Ingestion Flow

```
┌──────────────────┐
│ Test Script      │
│ test_media_      │
│ ingestion.sh     │
└────────┬─────────┘
         │
         ├──► YouTube Info ───────► PMOVES.YT :8077
         │                          │
         │                          └──► /yt/info?video_id=...
         │
         ├──► Transcription ──────► Whisper :8078
         │
         ├──► Video Analysis ─────► Video Analyzer :8079
         │                          │
         │                          └──► YOLOv8 Processing
         │
         ├──► Audio Analysis ─────► Audio Analyzer :8082
         │
         ├──► Indexing ───────────► Extract Worker :8083
         │                          │
         │                          ├──► Generate Embeddings
         │                          ├──► Index to Qdrant
         │                          └──► Index to Meilisearch
         │
         ├──► Storage ────────────► MinIO :9000
         │
         └──► NATS Events ────────► ingest.* subjects
```

## Test Execution Order

```
┌─────────────────────────────────────────┐
│ run-functional-tests.sh                 │
└───────────────┬─────────────────────────┘
                │
                ├──► 1. Prerequisites Check
                │      ├─ curl installed?
                │      ├─ jq installed?
                │      └─ nats CLI installed? (optional)
                │
                ├──► 2. TensorZero Inference
                │      ├─ Health checks
                │      ├─ Chat completions
                │      ├─ Embeddings
                │      └─ Metrics
                │
                ├──► 3. Hi-RAG Query
                │      ├─ Health checks
                │      ├─ Basic query
                │      ├─ Reranked query
                │      └─ Filtered query
                │
                ├──► 4. NATS Pub/Sub
                │      ├─ Connectivity
                │      ├─ Basic pub/sub
                │      ├─ JetStream
                │      └─ Subject routing
                │
                ├──► 5. Agent Zero MCP
                │      ├─ Health checks
                │      ├─ MCP API
                │      ├─ Archon integration
                │      └─ NATS integration
                │
                ├──► 6. Media Ingestion
                │      ├─ Service health
                │      ├─ YouTube info
                │      ├─ Pipeline status
                │      └─ NATS events
                │
                └──► 7. Summary Report
                       ├─ Total tests
                       ├─ Passed/Failed
                       ├─ Execution time
                       └─ Exit code
```

## Service Dependencies

```
TensorZero Tests
├─ TensorZero Gateway (required)
└─ ClickHouse (optional)

Hi-RAG Tests
├─ Hi-RAG v2 Gateway (required)
├─ Qdrant (optional)
├─ Neo4j (optional)
└─ Meilisearch (optional)

NATS Tests
├─ NATS Server (required)
├─ NATS CLI (required)
└─ JetStream (required)

Agent Zero Tests
├─ Agent Zero (required)
├─ Archon (optional)
└─ NATS (optional)

Media Ingestion Tests
├─ PMOVES.YT (required)
├─ Whisper (optional)
├─ Video Analyzer (optional)
├─ Audio Analyzer (optional)
├─ Extract Worker (optional)
├─ MinIO (optional)
└─ NATS (optional)
```

## Test Output Flow

```
Individual Test
     │
     ├──► log_info() ─────► Green messages
     ├──► log_error() ────► Red messages
     └──► log_warn() ─────► Yellow messages
     │
     └──► Exit Code
           ├─ 0 = Success
           └─ 1 = Failure

Main Runner
     │
     ├──► Collect Results
     │      ├─ PASS/FAIL
     │      └─ Duration
     │
     ├──► Generate Report
     │      ├─ Test-by-test status
     │      ├─ Total counts
     │      └─ Summary message
     │
     └──► Exit Code
           ├─ 0 = All passed
           └─ 1 = One or more failed
```

## Integration with PMOVES.AI

```
PMOVES.AI Platform
       │
       ├──► Development
       │      └─ Run tests locally for validation
       │
       ├──► CI/CD
       │      ├─ GitHub Actions
       │      ├─ Pre-merge validation
       │      └─ Deployment smoke tests
       │
       ├──► Monitoring
       │      └─ Scheduled health checks
       │
       └──► Documentation
              └─ Living system validation
```

## File Organization

```
tests/
│
├── Documentation
│   ├── README.md           - Comprehensive guide
│   ├── QUICKSTART.md       - Quick reference
│   ├── TESTING_SUMMARY.md  - Implementation summary
│   └── ARCHITECTURE.md     - This file
│
├── Test Runner
│   └── run-functional-tests.sh
│
├── Functional Tests
│   ├── test_tensorzero_inference.sh
│   ├── test_hirag_query.sh
│   ├── test_nats_pubsub.sh
│   ├── test_agent_zero_mcp.sh
│   ├── test_media_ingestion.sh
│   └── test_template.sh
│
└── Unit Tests (existing)
    ├── test_*.py
    └── conftest.py
```

## Best Practices Applied

1. **Separation of Concerns**
   - Each test focuses on one service/workflow
   - Clear boundaries between test suites

2. **Graceful Degradation**
   - Critical tests MUST pass
   - Optional tests warn but don't fail

3. **Observability**
   - Color-coded output
   - Clear success/failure messages
   - Execution time tracking

4. **Idempotency**
   - Tests clean up after themselves
   - Can run repeatedly
   - No state dependencies

5. **Configurability**
   - Environment variables for URLs
   - Flexible service discovery
   - Customizable behavior

## Future Enhancements

Potential additions to test suite:

1. **Performance Tests**
   - Load testing
   - Latency measurements
   - Throughput validation

2. **Security Tests**
   - Authentication validation
   - Authorization checks
   - API key handling

3. **End-to-End Workflows**
   - Complete research flow
   - Full ingestion pipeline
   - Multi-agent coordination

4. **Chaos Testing**
   - Service failure scenarios
   - Network issues
   - Recovery validation

## Conclusion

The functional test architecture provides comprehensive validation of PMOVES.AI critical workflows while maintaining simplicity, clarity, and extensibility. Each test layer maps directly to platform services, ensuring complete coverage of production functionality.
