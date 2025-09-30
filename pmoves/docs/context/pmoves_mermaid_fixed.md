# PMOVES v5.12 Architecture - Updated Mermaid Diagrams

## 1. High-Level PMOVES v5.12 Architecture

```mermaid
graph TD
    subgraph central_brain["Central Brain - Primary Orchestration"]
        A[Agent Zero: Core Decision-Maker and Orchestrator]
    end

    subgraph support_systems["Support Systems - Agent Building, Knowledge and Workflow"]
        B[Archon: Specialized Agent Builder and Knowledge/Task Management]
        C[n8n: Workflow Orchestration and MCP Hub]
        D[Crush CLI: Interactive Software Engineering Agent]
    end

    subgraph specialized_ai_muscles["Specialized AI Muscles - Deep Processing and Generation"]
        E[HiRAG: Hierarchical RAG with Reranker]
        F[LangExtract: Structured Information Extraction]
        G[ComfyUI: Sophisticated Content Creation]
        H[Jellyfin AI Media Stack: Media Analysis]
    end

    subgraph geometry_services["CHIT Geometry Services - First-Class"]
        I[Geometry Gateway: API and ShapeStore Cache]
        J[Geometry Decoder: Text/Image/Audio]
        K[Geometry Calibration: Metrics and Reports]
    end

    subgraph data_backbones["Data and Operational Backbones"]
        L[Firefly III: Personal Finance Manager]
        M[Supabase: Unified Database with pgvector and Realtime]
        N[Local Models: Ollama, NVIDIA NIM, Nemo]
        O[Neo4j: Knowledge Graph]
        P[Meilisearch: Full-Text Search]
    end

    subgraph infrastructure["Underlying Infrastructure"]
        Q[Distributed Computing: Workstations and Edge Devices]
        R[Docker Compose: Component Isolation with Profiles]
        S[MinIO: S3-Compatible Object Storage]
    end

    A -->|Manages and Delegates Tasks| C
    A -->|Utilizes Capabilities| B
    A -->|Uses Geometry Tools| I
    B -->|Manages Knowledge and Builds Agents| E
    B -->|Ingests Data| F
    B -->|Uses Personas and Packs| E
    C -->|Orchestrates Workflows| G
    C -->|Integrates with| L
    C -->|Triggers| H
    D -->|Integrates via MCP| B
    D -->|Integrates via MCP| A
    E -->|Pack-Scoped Retrieval| M
    E -->|Graph Blend| O
    E -->|BM25 Search| P
    F -->|Feeds Structured Data| E
    F -->|Creates Entities| O
    G -->|Publishes Assets| M
    H -->|Emits CGP Events| I
    H -->|Stores Media Metadata| M
    I -->|Broadcasts Realtime| M
    I -->|Caches Shapes| M
    J -->|Decodes Modalities| I
    K -->|Reports Metrics| I
    M -->|Serves Data to All| A
    M -->|Vector Embeddings| E
    M -->|Stores Assets and Chunks| E
    N -->|Powers LLM Inference| A
    N -->|Powers LLM Inference| B
    N -->|Powers LLM Inference| E
    S -->|Stores Assets| M
    Q -->|Hosts All Components| R
    R -->|Deploys Services| A
    R -->|Deploys Services| B
    R -->|Deploys Services| C
    R -->|Deploys Services| E
    R -->|Deploys Services| G
    R -->|Deploys Services| H
    R -->|Deploys Services| I
```

---

## 2. v5.12 Data Model - Grounded Personas and Library

```mermaid
erDiagram
    ASSETS ||--o{ DOCUMENTS : "source for"
    ASSETS ||--o{ PACK_MEMBERS : "included in"
    ASSETS {
        uuid asset_id PK
        text uri
        text type
        text mime
        text title
        text source
        text license
        text checksum
        bigint size_bytes
        text language
        text transcript_uri
        text thumbnail_uri
        timestamptz created_at
    }
    
    DOCUMENTS ||--o{ SECTIONS : "contains"
    DOCUMENTS ||--o{ CHUNKS : "chunked into"
    DOCUMENTS {
        uuid doc_id PK
        uuid asset_id FK
        text title
        jsonb meta
        timestamptz created_at
    }
    
    SECTIONS ||--o{ CHUNKS : "contains"
    SECTIONS {
        uuid section_id PK
        uuid doc_id FK
        int idx
        text heading
        jsonb meta
    }
    
    CHUNKS {
        uuid chunk_id PK
        uuid doc_id FK
        uuid section_id FK
        uuid pack_id FK
        text text
        int tokens
        vector embedding
        int idx
        int window
        int overlap
        jsonb md
        timestamptz created_at
    }
    
    GROUNDING_PACKS ||--o{ PACK_MEMBERS : "has"
    GROUNDING_PACKS ||--o{ PERSONAS : "used by"
    GROUNDING_PACKS {
        uuid pack_id PK
        text name
        text version
        text owner
        text description
        jsonb policy
        timestamptz created_at
    }
    
    PACK_MEMBERS {
        uuid pack_id PK,FK
        uuid asset_id PK,FK
        jsonb selectors
        real weight
        text notes
    }
    
    PERSONAS ||--o{ PERSONA_EVAL_GATES : "has gates"
    PERSONAS {
        uuid persona_id PK
        text name
        text version
        text description
        jsonb runtime
        text_array default_packs
        jsonb boosts
        jsonb filters
        timestamptz created_at
    }
    
    PERSONA_EVAL_GATES {
        uuid persona_id PK,FK
        text dataset_id PK
        text metric PK
        real threshold
        timestamptz last_run
        boolean pass
    }
    
    SHAPE_INDEX {
        uuid shape_id PK
        text summary
        jsonb anchor_meta
        timestamptz updated_at
    }
```

---

## 3. Creator Pipeline - Presign to Publish Workflow

```mermaid
sequenceDiagram
    participant User as Creator/User
    participant API as Gateway API
    participant MinIO as MinIO S3
    participant Indexer as Indexer Worker
    participant Publisher as Publisher Worker
    participant Supabase as Supabase DB
    participant Discord as Discord Webhook
    participant Jellyfin as Jellyfin Server

    User->>API: POST /presign (filename, type)
    API->>MinIO: Generate presigned PUT URL
    MinIO-->>API: Presigned URL
    API-->>User: Return presigned URL

    User->>MinIO: PUT file to presigned URL
    MinIO->>MinIO: Store asset
    MinIO->>API: Webhook: asset uploaded
    
    API->>Supabase: Emit kb.ingest.asset.created.v1
    Note over Supabase: Event published to NATS/queue

    Indexer->>Supabase: Subscribe to kb.ingest.asset.created.v1
    Indexer->>Indexer: Create documents/sections/chunks
    Indexer->>Indexer: Generate embeddings
    Indexer->>Supabase: Store chunks with embeddings
    Indexer->>Supabase: Push to Meilisearch
    Indexer->>Supabase: Emit kb.index.completed.v1

    Note over User,API: Approval Gate
    User->>API: POST /approve/{asset_id}
    API->>Supabase: Update asset status = approved

    Publisher->>Supabase: Listen for approved assets
    Publisher->>Publisher: Run quality checks
    Publisher->>Supabase: Emit content.published.v1
    
    Publisher->>Discord: POST webhook (title, thumbnail, URL)
    Discord-->>Publisher: 200 OK
    
    Publisher->>Jellyfin: POST /Library/Refresh
    Jellyfin->>Jellyfin: Scan and index new content
    Jellyfin-->>Publisher: 200 OK
    
    Publisher->>Supabase: Log to publisher_audit table
```

---

## 4. CHIT Geometry System - First-Class Integration

```mermaid
graph TD
    subgraph analysis_workers["Analysis Workers - CGP Producers"]
        A[Audio AI: Whisper, Pyannote]
        B[Video AI: YOLO, ViT, CLIP]
        C[Text Analysis: LangExtract]
        D[ComfyUI: Content Generation]
    end

    subgraph geometry_core["CHIT Geometry Services"]
        E[Geometry Gateway v0.2]
        F[ShapeStore Cache In-Memory]
        G[Geometry Decoder: Text/Image/Audio]
        H[Geometry Calibration: Metrics]
    end

    subgraph persistence["Geometry Persistence - Supabase"]
        I[anchors table]
        J[constellations table]
        K[shape_points table]
        L[shape_index table]
        M[Realtime Broadcast Channel]
    end

    subgraph consumers["Geometry Consumers"]
        N[Agent Zero: geometry.jump, geometry.decode_text]
        O[Archon: geometry.query, geometry.publish_cgp]
        P[UI Canvas: Live Visualization]
        Q[n8n Workflows: Polling Fallback]
    end

    A -->|Emit geometry.cgp.v1| E
    B -->|Emit geometry.cgp.v1| E
    C -->|Emit geometry.cgp.v1| E
    D -->|Emit geometry.cgp.v1| E
    
    E -->|HMAC Verify| F
    E -->|Store Anchors| I
    E -->|Store Constellations| J
    E -->|Store Points| K
    E -->|Update Index| L
    E -->|Broadcast| M
    
    F -->|Cache Hit| E
    F -->|Warm from DB| I
    F -->|Warm from DB| J
    
    G -->|Decode Request| E
    H -->|Calibration Report| E
    
    M -->|WebSocket Subscribe| P
    M -->|Realtime Update| N
    M -->|Realtime Update| O
    
    Q -->|Poll shape_points| K
    Q -->|GET /v0/shape/{id}| E
    
    I -->|Provides| F
    J -->|Provides| F
    K -->|Jump Locators| E
```

---

## 5. Pack-Scoped Retrieval with Reranker

```mermaid
graph TD
    subgraph query_ingress["Query Ingress"]
        A[User Query]
        B[Persona: Archon@1.0]
        C[Packs: pmoves-architecture@1.0]
    end

    subgraph retrieval_stage["Multi-Stage Retrieval"]
        D[Pack Filter: pack_id IN packs]
        E[Vector Search: pgvector HNSW/IVFFLAT]
        F[BM25 Search: Meilisearch]
        G[Graph Walk: Neo4j Entities]
        H[Fusion: RRF Reciprocal Rank Fusion]
    end

    subgraph reranking["Reranking - Enabled by Default"]
        I[Reranker Model: Cross-Encoder]
        J[Top-K Selection: 12 to 5]
    end

    subgraph context_assembly["Context Assembly"]
        K[HiRAG Hierarchical Context]
        L[Bridges: Local to Global]
        M[Communities: Thematic Groups]
    end

    subgraph llm_inference["LLM Inference"]
        N[Local Models or API]
        O[Generated Response with Citations]
    end

    A --> D
    B --> D
    C --> D
    D --> E
    D --> F
    D --> G
    E --> H
    F --> H
    G --> H
    H --> I
    I --> J
    J --> K
    K --> L
    K --> M
    L --> N
    M --> N
    N --> O
```

---

## 6. Event Bus Architecture - NATS/Supabase Realtime

```mermaid
graph LR
    subgraph producers["Event Producers"]
        A[Indexer Worker]
        B[Publisher Worker]
        C[Geometry Gateway]
        D[ComfyUI Webhook]
    end

    subgraph event_bus["Event Bus - Supabase Realtime / NATS"]
        E[kb.ingest.asset.created.v1]
        F[kb.index.completed.v1]
        G[kb.pack.published.v1]
        H[persona.published.v1]
        I[geometry.cgp.v1]
        J[content.published.v1]
    end

    subgraph consumers["Event Consumers"]
        K[Indexer Worker]
        L[Gateway Cache Warmer]
        M[ShapeStore Cache]
        N[Discord Notifier]
        O[Jellyfin Refresher]
        P[Analytics]
        Q[Audit Logger]
    end

    subgraph dlq["Dead Letter Queue"]
        R[event_dlq table]
    end

    A -->|Publish| E
    A -->|Publish| F
    B -->|Publish| G
    B -->|Publish| H
    B -->|Publish| J
    C -->|Publish| I
    D -->|Trigger| E
    
    E -->|Subscribe| K
    F -->|Subscribe| L
    G -->|Subscribe| L
    I -->|Subscribe| M
    J -->|Subscribe| N
    J -->|Subscribe| O
    F -->|Subscribe| P
    J -->|Subscribe| Q
    
    K -->|On Failure| R
    N -->|On Failure| R
    O -->|On Failure| R
```

---

## 7. Compose Profiles and Service Groups

```mermaid
graph TD
    subgraph profiles["Docker Compose Profiles"]
        A[data: Supabase, Neo4j, Meilisearch]
        B[workers: Indexer, Publisher]
        C[gateway: HiRAG Gateway, API]
        D[geometry: Geometry Gateway, Decoder, Calibration]
        E[comfy: ComfyUI]
        F[n8n: n8n Workflow]
    end

    subgraph deployment_commands["Deployment Commands"]
        G[make up: data + workers + gateway]
        H[make up-all: All profiles]
        I[make up-geometry: data + gateway + geometry]
    end

    subgraph services["Service Dependencies"]
        J[Supabase Postgres + pgvector]
        K[Neo4j Graph DB]
        L[Meilisearch Full-Text]
        M[MinIO S3 Storage]
    end

    A --> J
    A --> K
    A --> L
    A --> M
    B --> J
    C --> J
    D --> J
    E --> M
    F --> J
    
    G --> A
    G --> B
    G --> C
    H --> A
    H --> B
    H --> C
    H --> D
    H --> E
    H --> F
    I --> A
    I --> C
    I --> D
```

---

## 8. Persona Runtime and Eval Gates

```mermaid
flowchart TD
    subgraph persona_definition["Persona Definition - Archon@1.0"]
        A[Name: Archon]
        B[Model: gpt-4o]
        C[Tools: hirag.query, kb.viewer, geometry.jump]
        D[Default Packs: pmoves-architecture@1.0]
        E[Boosts: Hi-RAG, LangExtract, Neo4j]
        F[Filters: exclude_types raw-audio]
    end

    subgraph eval_gates["Eval Gates - Quality Gating"]
        G[Dataset: archon-smoke-10]
        H[Metric: top3_hit@k]
        I[Threshold: 0.80]
        J[Gate Status: pass/fail]
    end

    subgraph runtime_flow["Runtime Query Flow"]
        K[Incoming Query]
        L[Load Persona Config]
        M[Apply Filters and Boosts]
        N[Pack-Scoped Retrieval]
        O[Execute with Tools]
        P[Return Response with Citations]
    end

    subgraph publish_check["Publish Check"]
        Q[All Gates Pass?]
        R[Publish Persona]
        S[Block and Alert]
    end

    A --> L
    B --> L
    C --> L
    D --> L
    E --> M
    F --> M
    
    G --> J
    H --> J
    I --> J
    
    J --> Q
    Q -->|Yes| R
    Q -->|No| S
    
    K --> L
    L --> M
    M --> N
    N --> O
    O --> P
```

---

## Key Changes in v5.12

1. **Grounded Personas**: Personas now have explicit runtime configs, default packs, boosts, and filters with eval gates
2. **Pack-Scoped Retrieval**: Queries are scoped to grounding packs with weighted selectors
3. **CHIT Geometry First-Class**: Geometry services promoted to first-class with dedicated profile, versioned API (v0.2), and Realtime integration
4. **Creator Pipeline**: Complete presign → webhook → approval → index → publish flow with Discord/Jellyfin integration
5. **Reranker Default On**: Cross-encoder reranking enabled by default in retrieval pipeline
6. **Event Bus Maturity**: Structured event contracts with DLQ for failure handling
7. **Compose Profiles**: Modular deployment with profiles for data, workers, gateway, geometry, comfy, n8n

All diagrams use compatible Mermaid syntax and reflect the current v5.12 architecture.