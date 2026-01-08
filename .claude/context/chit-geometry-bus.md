# CHIT Geometry Bus - Structured Data Exchange for Multimodal Workflows

**CHIT Geometry Bus** is PMOVES.AI's advanced structured data exchange system for multimodal agent workflows. It provides a common format for representing complex, multi-dimensional data across services.

## Purpose

Traditional message buses (like NATS) excel at event passing, but struggle with:
- **Structured multimodal data** - Combining text, vectors, graphs, and metadata
- **Semantic relationships** - Representing connections between data points
- **Geometric representations** - Spatial/dimensional relationships in data

CHIT Geometry Bus solves this by providing:
- **Structured schemas** for complex data types
- **Geometric transformations** for data representation
- **Type-safe** message passing
- **Multimodal coordination** across services

## Integration in PMOVES

### Services Using CHIT Geometry Bus

**Hi-RAG Gateway v2** [Primary Consumer]
- Uses CHIT for structured output representation
- Combines vector, graph, and text results into unified CHIT format
- Emits telemetry events on Geometry Bus
- **Why:** RAG results include vectors (Qdrant), graphs (Neo4j), text (Meilisearch) - needs structured representation

**SupaSerch** [Primary Consumer]
- Uses CHIT Geometry Bus for structured research output
- Coordinates multi-tool results (DeepResearch, Hi-RAG, MCP tools)
- **Why:** Research involves multiple data types that need unified representation

## CHIT Data Structures

### Core Concepts

**CHIT (Context-Hybrid Information Token)**
- Represents a single unit of contextual information
- Can contain: text, embeddings, metadata, relationships
- Type-safe schema for validation

**Geometry Bus**
- Transport layer for CHIT messages
- Handles geometric transformations between representation spaces
- Ensures semantic consistency across services

### Example CHIT Structure

```json
{
  "chit_id": "unique-chit-identifier",
  "type": "hybrid_retrieval_result",
  "version": "1.0",
  "created_at": "2025-12-06T12:00:00Z",
  "source_service": "hi-rag-v2",

  "data": {
    "text_content": "Retrieved text chunk...",
    "embedding": [0.123, 0.456, ...],  // Vector representation
    "metadata": {
      "source_document": "doc-id",
      "chunk_index": 5,
      "confidence": 0.92
    }
  },

  "relationships": [
    {
      "type": "semantic_similarity",
      "target_chit_id": "another-chit-id",
      "strength": 0.85
    },
    {
      "type": "graph_connection",
      "target_chit_id": "graph-node-chit-id",
      "relation": "mentions"
    }
  ],

  "geometry": {
    "vector_space": "sentence-transformers/all-MiniLM-L6-v2",
    "dimensions": 384,
    "normalized": true
  }
}
```

## Hi-RAG v2 CHIT Integration

When you query Hi-RAG v2, results are structured as CHITs:

```bash
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "...", "top_k": 10, "rerank": true, "output_format": "chit"}'
```

**Response includes:**
- **text_chits** - Text chunks with embeddings
- **graph_chits** - Neo4j nodes/relationships
- **vector_chits** - Qdrant results
- **unified_ranking** - Cross-modal reranked results

## SupaSerch CHIT Integration

SupaSerch coordinates multiple tools and unifies results into CHIT format:

```json
{
  "research_result": {
    "query_chit": {
      "text": "original query",
      "embedding": [...]
    },
    "findings": [
      {
        "chit_id": "finding-1",
        "source": "deepresearch",
        "data": {...},
        "confidence": 0.95
      },
      {
        "chit_id": "finding-2",
        "source": "hirag",
        "data": {...},
        "confidence": 0.88
      }
    ],
    "synthesis": {
      "chit_id": "synthesis",
      "text": "Combined answer...",
      "supporting_chits": ["finding-1", "finding-2"]
    }
  }
}
```

## Telemetry on Geometry Bus

Hi-RAG v2 emits telemetry events:

```json
{
  "event_type": "retrieval_telemetry",
  "timestamp": "2025-12-06T12:00:00Z",
  "service": "hi-rag-v2",
  "metrics": {
    "query_latency_ms": 234,
    "vector_search_time_ms": 45,
    "graph_search_time_ms": 89,
    "rerank_time_ms": 100,
    "total_results": 10,
    "reranked": true
  },
  "geometry": {
    "input_dimensions": 384,
    "output_dimensions": 768,
    "transformation": "cross_encoder_rerank"
  }
}
```

## Development Patterns

### When to Use CHIT Geometry Bus

**Use CHIT when:**
- Combining results from multiple modalities (text + vectors + graphs)
- Need to maintain semantic relationships across services
- Require type-safe structured data exchange
- Working with geometric/spatial data representations

**Use plain NATS when:**
- Simple event notifications
- Unstructured or single-modal data
- Fire-and-forget messaging
- Existing event patterns (ingest.*, research.*)

### Consuming CHIT Results

When a service returns CHIT-formatted data:

1. **Parse the structure** - Validate against CHIT schema
2. **Extract relevant fields** - Get text, embeddings, metadata
3. **Follow relationships** - Traverse connected CHITs if needed
4. **Use metadata** - Confidence scores, sources, timestamps

Example in Python:
```python
import requests

response = requests.post(
    "http://localhost:8086/hirag/query",
    json={
        "query": "your question",
        "output_format": "chit"
    }
)

chit_results = response.json()

for chit in chit_results["results"]:
    print(f"Text: {chit['data']['text_content']}")
    print(f"Confidence: {chit['data']['metadata']['confidence']}")
    print(f"Relationships: {len(chit['relationships'])}")
```

### Creating CHIT Messages

If implementing a new service that should output CHITs:

```python
def create_chit(text, embedding, metadata):
    return {
        "chit_id": generate_unique_id(),
        "type": "custom_result",
        "version": "1.0",
        "created_at": datetime.utcnow().isoformat(),
        "source_service": "your-service-name",
        "data": {
            "text_content": text,
            "embedding": embedding.tolist(),
            "metadata": metadata
        },
        "relationships": [],
        "geometry": {
            "vector_space": "your-embedding-model",
            "dimensions": len(embedding),
            "normalized": True
        }
    }
```

## Geometry Transformations

The Geometry Bus can transform between representation spaces:

**Example transformations:**
- **384D → 768D** - Upsampling embeddings for cross-encoder
- **Text → Vector** - Embedding generation
- **Graph → Vector** - Node embedding
- **Multi-modal fusion** - Combining text, image, audio embeddings

**Transformation metadata** is included in CHIT:
```json
{
  "geometry": {
    "input_space": "all-MiniLM-L6-v2",
    "output_space": "bge-reranker-base",
    "transformation_applied": "cross_encoder_projection",
    "preserves_semantics": true
  }
}
```

## Monitoring CHIT Traffic

### Via Hi-RAG v2 Telemetry

```bash
# Check if CHIT format is being used
curl http://localhost:8086/metrics | grep chit
```

### Via SupaSerch Metrics

```bash
curl http://localhost:8099/metrics | grep chit_coordination
```

## Best Practices

1. **Always validate CHIT schema** - Ensure type safety
2. **Include confidence scores** - Help downstream services make decisions
3. **Preserve relationships** - Maintain semantic connections
4. **Document geometry** - Specify vector space and dimensions
5. **Use versioning** - CHIT format may evolve

## Future Extensions

CHIT Geometry Bus is designed for:
- **Multi-agent collaboration** - Agents exchange structured context
- **Cross-modal retrieval** - Text, image, audio unified search
- **Semantic caching** - CHIT-based result caching
- **Distributed knowledge graphs** - CHITs as graph nodes

## Developer Notes

**For Claude Code CLI users:**
- When querying Hi-RAG v2, CHIT format provides richer context
- SupaSerch results include CHIT relationships for deeper analysis
- Custom services can adopt CHIT for better integration
- CHIT is optional - plain JSON still supported for simple use cases

**Integration points:**
- Hi-RAG v2 API supports `output_format: "chit"` parameter
- SupaSerch always uses CHIT internally for coordination
- CHIT schemas are evolving - check service docs for latest version
