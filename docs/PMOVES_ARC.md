PMOVES: A Self-Improving Multi-Agent AI Architecture

The PMOVES (POWERFULMOVES) system is an advanced, distributed multi-agent architecture designed for continuous self-improvement and research, emphasizing autonomous learning and local control over data and models [1-3]. This ecosystem integrates various specialized AI and data management tools to handle complex tasks, from financial analysis to content creation [3]. Below are several Mermaid diagrams illustrating different architectural, configuration, and workflow aspects of the PMOVES system.

--------------------------------------------------------------------------------

## 1. High-Level PMOVES Architecture

This diagram provides a top-level view of the PMOVES system, categorizing its main components into functional layers as described in the sources [4-7].

```mermaid
graph TD
    subgraph Central Brain (Primary Orchestration)
        A[Agent Zero: Core Decision-Maker & Orchestrator]
    end

    subgraph Support Systems (Agent Building, Knowledge & Workflow)
        B[Archon: Specialized Agent Builder & Knowledge/Task Mgmt]
        C[n8n: Workflow Orchestration & MCP Hub]
    end

    subgraph Specialized AI "Muscles" (Deep Processing & Generation)
        D[HiRAG: Hierarchical RAG for Deep Reasoning]
        E[LangExtract: Structured Information Extraction]
        F[ComfyUI: Sophisticated Content Creation]
    end

    subgraph Data & Operational Backbones
        G[Firefly III: Personal Finance Manager]
        H[Supabase: Unified Database with Vector Capabilities]
        I[Local Models: Ollama, NVIDIA NIM, Nemo]
    end

    subgraph Underlying Infrastructure
        J[Distributed Computing: Workstations & Edge Devices]
        K[Docker: Component Isolation & Deployment]
    end

    A -- Manages & Delegates Tasks --> C
    A -- Utilizes Capabilities --> B
    B -- Manages Knowledge & Builds Agents --> D
    B -- Ingests Data --> E
    E -- Feeds Structured Data --> D
    C -- Orchestrates Workflows --> F
    C -- Integrates with --> G
    D -- Enhances RAG --> H
    E -- Stores Data --> H
    F -- Utilizes Models --> I
    G -- Stores Data --> H
    H -- Serves Data to --> A, B, D, E, F
    I -- Powers --> A, B, D, E, F
    J -- Hosts All Components --> K
    K -- Enables Deployment of --> A, B, C, D, E, F, G, I
```

**Explanation:**

The PMOVES system is envisioned with a Central Brain managed by Agent Zero, acting as the primary orchestrator across the network, making decisions, and managing the overall system [1, 4, 7]. This "brain" is dynamic, learning, and can create subordinate agents [7, 8].

Supporting Agent Zero are the Support Systems. Archon serves as the knowledge and task management backbone, an integrated environment for all context engineering, and a specialized agent builder [4, 7, 9]. It offers robust knowledge management, including smart web crawling, document processing, and code example extraction, with advanced RAG strategies like vector search [7, 10]. n8n acts as the automation and workflow orchestration layer, facilitating multi-agent task delegation and seamless communication between components via the Model Context Protocol (MCP) [1, 4, 7].

Specialized AI "Muscles" provide deep processing and generation capabilities. HiRAG offers hierarchical retrieval-augmented generation for deeper, fact-based reasoning on complex, multi-layered knowledge structures, overcoming traditional RAG limitations [5, 7, 11]. LangExtract is a Python library for extracting structured information from unstructured text documents with precise source grounding, often powered by LLMs like Gemini [5, 7, 11]. ComfyUI handles sophisticated content creation workflows, such as text-to-image and video generation [1, 5, 7].

The Data & Operational Backbones include Firefly III, a self-hosted personal finance manager [5, 12]. Supabase is the unified database with vector capabilities for the entire PMOVES system, serving as the backend for Archon and storing vector embeddings for semantic search [1, 5, 7]. Local Models (Ollama, NVIDIA NIM, Nemo) are a suite of LLMs distributed across the hardware network, providing the underlying language model capabilities for various agents, ensuring data privacy and efficient local processing [1, 5, 7].

All these components are deployed and run on Underlying Infrastructure comprising a Distributed Computing network of workstations and edge devices, with Docker used for isolating and deploying components across this infrastructure [1, 6, 7].

--------------------------------------------------------------------------------

## 2. Detailed PMOVES Functional Layers and Interactions

This diagram illustrates the interactions and data flow across different functional layers within the PMOVES system, detailing how components collaborate to achieve autonomous operations and self-improvement [13-16].

```mermaid
graph TD
    subgraph Layer 1: User Interaction & Interfaces
        UI_AZ[Agent Zero UI: Interactive Terminal] --> L2_AZ
        UI_ARCHON[Archon UI: Web Interface (Knowledge/Tasks)] --> L3_ARCHON
        UI_FIREFLY[Firefly III UI: Web Interface (Finance)] --> L4_FIII
    end

    subgraph Layer 2: Primary Orchestration & Adaptive Learning
        L2_AZ[Agent Zero: Primary Orchestrator]
        L2_N8N[n8n: Workflow Orchestrator & MCP Hub]
        L2_AZ -- "Receives User Tasks" --> L2_N8N
        L2_AZ -- "Decision-Making & Task Delegation" --> L2_N8N
        L2_AZ -- "Online Search (YouTube, GitHub)" --> L3_LE
        L2_AZ -- "Online Search (YouTube, GitHub)" --> L3_ARCHON
        L2_AZ -- "Persistent Memory & Learning" --> L4_SB
        L2_AZ -- "Self-Learning (UR2 Principles)" --> L4_LM
    end

    subgraph Layer 3: Specialized Knowledge & Agent Services
        L3_ARCHON[Archon: Agent Builder & Knowledge Mgmt]
        L3_LE[LangExtract: Structured Info Extraction]
        L3_HRAG[HiRAG: Hierarchical RAG]
        L3_ARCHON -- "Designs Sub-agents" --> L2_AZ
        L3_ARCHON -- "Ingests Knowledge (Web Crawling, Docs)" --> L3_LE
        L3_ARCHON -- "Advanced RAG Strategies" --> L3_HRAG
        L3_LE -- "Extracts Entities/Relationships" --> L3_HRAG
        L3_HRAG -- "Builds Hierarchical Indices" --> L4_SB
    end

    subgraph Layer 4: External Services & Data Storage
        L4_FIII[Firefly III: Personal Finance Manager]
        L4_CUI[ComfyUI: Content Creation Workflows]
        L4_SB[Supabase: Unified DB w/ Vector Capabilities]
        L4_LM[Local Models (Ollama, NVIDIA NIM, Nemo)]
        L2_N8N -- "Automates Workflows" --> L4_FIII
        L2_N8N -- "Automates Workflows" --> L4_CUI
        L3_ARCHON -- "Manages Data" --> L4_SB
        L3_LE -- "Stores Extracted Data" --> L4_SB
        L4_SB -- "Provides Vector Embeddings" --> L3_ARCHON
        L4_SB -- "Provides Vector Embeddings" --> L3_HRAG
        L4_LM -- "LLM Inference" --> L2_AZ
        L4_LM -- "LLM Inference" --> L3_ARCHON
        L4_LM -- "LLM Inference" --> L3_LE
        L4_LM -- "LLM Inference" --> L3_HRAG
        L4_LM -- "LLM Inference" --> L4_CUI
    end

    subgraph Layer 5: Hardware & Infrastructure
        L5_DOCKER[Docker Runtime]
        L5_HARDWARE[Distributed Hardware Network]
        L5_DOCKER -- "Isolates & Deploys" --> L2_AZ
        L5_DOCKER -- "Isolates & Deploys" --> L2_N8N
        L5_DOCKER -- "Isolates & Deploys" --> L3_ARCHON
        L5_DOCKER -- "Isolates & Deploys" --> L3_LE
        L5_DOCKER -- "Isolates & Deploys" --> L3_HRAG
        L5_DOCKER -- "Isolates & Deploys" --> L4_FIII
        L5_DOCKER -- "Isolates & Deploys" --> L4_CUI
        L5_DOCKER -- "Isolates & Deploys" --> L4_LM
        L5_HARDWARE -- "Hosts" --> L5_DOCKER
    end
```

**Explanation:**

This detailed view shows the PMOVES system operating across five distinct layers.

Layer 1: User Interaction & Interfaces represents the direct points of contact for users. This includes the interactive terminal interface for Agent Zero, the web interface for Archon for managing knowledge and tasks, and the web interface for Firefly III for personal finance management [13].

Layer 2: Primary Orchestration & Adaptive Learning is where Agent Zero reigns as the primary orchestrator. It receives user tasks, makes decisions, and delegates them. Its persistent memory allows it to learn from past experiences, and it uses online search for external information [13]. n8n is the workflow orchestrator, automating connections and facilitating multi-agent task delegation using the MCP (Model Context Protocol) as a central hub [13].

Layer 3: Specialized Knowledge & Agent Services details the core AI services. Archon is crucial for building specialized sub-agents and managing knowledge. It ingests data from web crawling and documents, which is then processed by LangExtract to extract structured information [14]. This structured data, combined with Archon's knowledge base, is fed into HiRAG for hierarchical retrieval-augmented generation, enabling deeper reasoning [14].

Layer 4: External Services & Data Storage includes specific applications and the central data repository. Firefly III offers a REST JSON API for programmatic access to financial data, automated via n8n [15]. ComfyUI executes AI-driven content generation workflows, also automated by n8n [15]. Supabase acts as the unified database, storing vector embeddings and serving as Archon's backend [15]. Local Models provide the underlying LLM capabilities for all other AI components, running on the distributed hardware [15].

Finally, Layer 5: Hardware & Infrastructure underpins the entire system. Docker Runtime ensures isolated and portable environments for all services, while the Distributed Hardware Network comprises various workstations and edge computing devices, optimizing for different workloads [16]. This layered approach enables autonomous upgrading and self-improvement, with Agent Zero orchestrating research, Archon managing knowledge, LangExtract and HiRAG refining information, and Supabase centralizing learned data [17].

--------------------------------------------------------------------------------

## 3. Jellyfin AI Media Stack Integration Workflow

This diagram illustrates the workflow for integrating the Jellyfin AI Media Stack into PMOVES, highlighting its specialized role as an "AI muscle" for media analysis and content creation [18-30].

```mermaid
graph TD
    subgraph Media Ingestion & Processing
        A[YouTube Downloader (yt-dlp)] -->|Downloads Video/Audio & Metadata| B
        B[Local Media Files] --> C
        C[FFmpeg Video Processing] --> D
        D[Jellyfin Media Server]
    end

    subgraph AI Analysis & Extraction
        D -- "Sends Media to" --> E[Audio AI Service (Whisper, Pyannote, Sortformer)]
        D -- "Sends Media to" --> F[Video AI Service (YOLO, ViT, CLIP, Flamingo)]
        E -- "Extracts Audio Features" --> G
        F -- "Extracts Video Features" --> G
        G[Google LangExtract (Gemini-powered)] -- "Structured Information Extraction" --> H
        H[Neo4j Graph Database] -- "Content Relationships" --> K
    end

    subgraph PMOVES Knowledge & Orchestration
        I[Archon Knowledge Management] -- "Ingests Metadata & Structured Data" --> J
        J[HiRAG (Hierarchical RAG)] -- "Deeper Reasoning & Hierarchical Indices" --> K
        K[Supabase (Unified PMOVES Database)] -- "Stores Media Metadata, Analysis Results, Entities & Indices" --> L
        L[Agent Zero (Primary Orchestrator)] -- "Delegates Tasks (e.g., 'Analyze YouTube Content')" --> N
        N[n8n (Workflow Orchestrator)]
        M[ComfyUI (Content Creation Workflows)]
    end

    N -- "Triggers" --> A
    N -- "Coordinates" --> E
    N -- "Coordinates" --> F
    N -- "Coordinates" --> G
    N -- "Coordinates" --> M
    H -- "Feeds Structured Data" --> I
    I -- "Utilizes" --> L
    I -- "Utilizes" --> N
    J -- "Utilizes" --> L
    J -- "Utilizes" --> N
    L -- "Leverages Insights from" --> J
    L -- "Leverages Insights from" --> K
    M -- "Generates Content from" --> G
    M -- "Generates Content from" --> J
    M -- "Generates Content from" --> L
```

**Explanation:**

The Jellyfin AI Media Stack is integrated as a specialized AI muscle within the PMOVES architecture, leveraging Google LangExtract powered by Gemini for entity extraction [18].

1. Content Ingestion & Processing: The YouTube Downloader (yt-dlp) ingests media from YouTube, passing video/audio and metadata to FFmpeg for further processing. Jellyfin Media Server then manages and streams this content [19, 20, 26].

2. AI Analysis & Extraction: The media from Jellyfin is routed to dedicated Audio AI Service (utilizing models like Whisper, Pyannote Audio, NVIDIA Sortformer for transcription, diarization, emotion recognition) and Video AI Service (using YOLO v11, Vision Transformers, CLIP, Flamingo for object detection, scene understanding, video-language reasoning) [19-24]. The outputs from these services are then fed into Google LangExtract (Gemini-powered) for structured information and entity extraction, creating data for Neo4j knowledge graphs [19, 24].

3. PMOVES Knowledge & Orchestration: The structured data from LangExtract and Neo4j, along with rich metadata from analysis, is ingested into Archon's knowledge management system [19]. This knowledge is further processed by HiRAG to build hierarchical indices and enable deeper, fact-based reasoning [19]. All this information (media metadata, AI analysis results, extracted entities, and HiRAG indices) is centrally stored in Supabase, the unified PMOVES database [19]. Agent Zero, the primary orchestrator, can delegate tasks to the Jellyfin stack (e.g., finding and analyzing YouTube content) via n8n. n8n acts as the workflow orchestration layer and MCP Hub, facilitating communication and task hand-offs between Agent Zero and the Jellyfin services, as well as orchestrating ComfyUI for content creation based on the generated insights [19].

This integration creates a powerful synergy for research, data processing, and content generation, allowing PMOVES agents to query and retrieve deep insights from analyzed media [18, 19].

--------------------------------------------------------------------------------

## 4. HiRAG Integration Workflow

This diagram details how HiRAG (Hierarchical Retrieval-Augmented Generation) is integrated into PMOVES, showing its role in building hierarchical knowledge structures and enhancing fact-based reasoning capabilities [31-41].

```mermaid
graph TD
    subgraph Data Ingestion & Structuring
        A[Raw Data (Web Crawls, Docs, Transcripts)] --> B[Archon Smart Web Crawling & Document Processing]
        B -- "Ingests & Processes" --> C[LangExtract Structured Information Extraction (Gemini-powered)]
        C -- "Processes Unstructured Text" --> D[Structured Entities & Relationships]
    end

    subgraph Hierarchical Index Building (HiRAG)
        D --> E[HiRAG: Hierarchical Indexing]
        F(Layer Zero Entities)
        G(Layer One Entities)
        H(Layer Two+ Entities)
        I(Communities)
        J(Bridges)
        E -- "Layer Zero (Base Entities)" --> F
        E -- "Layer One (Summary Entities via LLMs)" --> G
        E -- "Layer Two+ (Meta Summary Entities via LLMs)" --> H
        E -- "Community Detection (Louvain algorithm, horizontal groupings)" --> I
        E -- "Bridges (Fact-based reasoning paths linking local to global)" --> J
    end

    subgraph Knowledge Storage & Retrieval
        K[Supabase: Unified Database with Vector Capabilities]
        F -- "Stored in" --> K
        G -- "Stored in" --> K
        H -- "Stored in" --> K
        I -- "Stored in" --> K
        J -- "Stored in" --> K
    end

    subgraph Advanced RAG Strategy (HiRAG in Action)
        L[User Query (Agent Zero)] --> M[HiRAG Query Processing]
        M -- "Selects Info from" --> K
        M -- "Assembles Optimal Context" --> N[LLM (Local Models)]
        N -- "Deeper, Fact-Based Reasoning" --> O[Generated Response (e.g., to Agent Zero)]
    end
```

**Explanation:**

HiRAG integration provides hierarchical knowledge structuring and deeper, fact-based reasoning, moving beyond traditional flat RAG approaches within PMOVES [31].

1. Data Ingestion & Structuring: Raw Data from various sources (web crawls, documents, media transcripts) is first ingested and processed by Archon's smart web crawling and document processing capabilities [32]. LangExtract, a core PMOVES component, then processes this unstructured text, extracting structured entities and relationships with precise source grounding, often powered by Gemini [32].

2. Hierarchical Index Building (HiRAG): The structured entities and relationships are fed into HiRAG, which builds hierarchical indices [32]. This involves:

    ◦ Layer Zero: Direct extractions (base entities).

    ◦ Layer One: LLMs cluster and summarize Layer Zero nodes to create higher-level concepts.

    ◦ Layer Two+: Further abstraction and summarization for increasingly complex concepts [32, 35, 36].

    ◦ Community Detection: HiRAG identifies "communities" of related thematic nodes across all layers, representing horizontal groupings of information [32, 36].

    ◦ Bridges: Fact-based reasoning paths are computed, linking local entities to global concepts and communities, reducing hallucination [32, 37].

3. Knowledge Storage & Retrieval: All these hierarchical layers, communities, and bridges are stored within Supabase, the unified PMOVES database, leveraging its vector capabilities for advanced semantic retrieval [32].

4. Advanced RAG Strategy (HiRAG in Action): When a User Query (from Agent Zero) comes in, HiRAG Query Processing dynamically selects information from local entities, communities, and global bridges, assembling an optimal context for the LLM based on query complexity [33]. This rich context enables Local Models (LLMs) to perform deeper, fact-based reasoning, producing generated responses with higher accuracy and reduced contradictions [33]. This enhances Agent Zero's persistent memory and improves online search by formulating more precise queries and learning dynamic policies for knowledge acquisition [42].

--------------------------------------------------------------------------------

## Geometry Cache Persistence & Validation

Hi-RAG's geometry cache mirrors the `geometry.cgp.v1` event stream in Supabase so that agents and UI clients can jump across modalities with sub‑100 ms lookups. The persistence contract is:

- **Tables** – `anchors`, `constellations`, and `shape_points` capture the normalized CGP payload. Each `constellations` row links back to an anchor; `shape_points` rows provide modality-specific jump data (token span, timestamp, frame index, etc.).
- **Packets view** – When present, the `geometry_cgp_packets` materialized view mirrors the full CGP envelope (`{spec, super_nodes[]}`) for quick hydration/debugging. `ShapeStore.warm_from_db` prefers this view and falls back to the normalized join so the cache still warms even if the packets view is not provisioned yet.
- **Warm start** – On service boot the gateway calls `ShapeStore.warm_from_db`, pulling the latest constellations (and their anchors/points) via PostgREST to hydrate the in-memory cache before the first request. A `ShapeStore warmed with … Supabase constellations` log line confirms the warm-up succeeded.
- **Realtime feed** – After the warm, the gateway subscribes to Supabase Realtime (`realtime:geometry.cgp.v1`). Broadcast messages with fresh CGPs are fed back into the cache immediately, so cache coherence is bounded only by WebSocket latency.

**Validation checklist**

1. Confirm persistence: `GET $SUPA_REST_URL/geometry_cgp_packets?select=created_at&order=created_at.desc&limit=5` (or the fallback `constellations` query if the view is absent) should surface the latest payloads.
2. Restart `hi-rag-gateway-v2` and watch the logs for the warm-up message. If the count is `0`, verify the service role key/PostgREST URL in `.env` and ensure at least one of `geometry_cgp_packets` or `constellations` returns rows.
3. Run `python pmoves/tools/realtime_listener.py` (or the browser canvas at `/geometry/`) to see `geometry.cgp.v1` notifications propagate. New inserts should appear in Supabase within seconds and be reflected in ShapeStore lookups immediately.

--------------------------------------------------------------------------------

## 5. Crush CLI Integration Context

This diagram focuses on the Crush interactive CLI agent for software engineering, showing its internal structure, memory, and operational guidelines within the PMOVES ecosystem [43-96].

```mermaid
flowchart TD
    subgraph User Interaction
        U[User] -- "Input Query/Task" --> CCLI
    end

    subgraph Crush CLI Agent (Software Engineering "Bestie")
        CCLI[Crush CLI Interface] -- "Processes Input" --> CP
        CP(Crush Core Processing & LLM Integration)
        CP -- "Loads Context from CRUSH.md" --> CMM
        CP -- "Utilizes LLMs (Gemini, Anthropic, OpenAI, Local)" --> LLM_AGENTS
        CP -- "Interprets Prompts (anthropic.md, gemini.md, v2.md)" --> PP
        CP -- "Adheres to Mandates & Guidelines" --> MNG
        CP -- "Selects & Executes Tools" --> T
    end

    subgraph Crush Internal Memory & Prompts
        CMM[CRUSH.md: Stored Commands, Code Style, Codebase Structure]
        PP[Internal Prompts (e.g., anthropic.md, gemini.md): Define Tone, Style, Workflows, Mandates]
        MNG[Core Mandates & Guidelines: Rigorous Conventions, No Comments, No Emojis, No Auto-Commit]
    end

    subgraph Tooling & External Integrations
        T[Crush Tool Executor]
        T -- "File System Tools (view, edit, write, grep, glob)" --> FS(File System)
        T -- "Shell Commands (bash, test, lint, typecheck)" --> SHELL(Operating System Shell)
        T -- "LSP (Language Server Protocol)" --> LSP(LSP Servers: gopls, typescript-language-server)
        T -- "MCP (Model Context Protocol)" --> MCPS(MCP Servers: Archon, Agent Zero)
        LLM_AGENTS[Various LLMs]
    end

    CCLI -- "Outputs Response" --> U
    CMM -- "Proactively Suggests Updates" --> U
    MNG -- "Guides Behavior" --> CP
    LSP -- "Provides Code Context" --> CP
    MCPS -- "Accesses Knowledge/Tasks" --> CP
    FS -- "Codebase Files" --> CP
    SHELL -- "Execution Environment" --> CP

    style CCLI fill:#f9f,stroke:#333,stroke-width:2px
    style CMM fill:#ccf,stroke:#333,stroke-width:2px
    style PP fill:#ddf,stroke:#333,stroke-width:2px
    style MNG fill:#fdd,stroke:#333,stroke-width:2px
```

**Explanation:**

Crush positions itself as an interactive CLI agent, a "coding bestie" for software engineering tasks within PMOVES [43, 45, 53]. It runs each task in a secure, short-lived virtual machine with preinstalled developer tools [45].

1. User Interaction: A User provides queries or tasks directly to the Crush CLI Interface [44].

2. Crush Core Processing: Crush's core processing integrates with multiple LLMs (OpenAI, Anthropic, Gemini, local models), allowing switching mid-session while preserving context [43, 58]. Its behavior is governed by internal prompts (e.g., anthropic.md, gemini.md, v2.md), which define its tone, style, and operational workflows [44, 64, 76, 97].

3. Crush Internal Memory & Prompts:

    ◦ CRUSH.md: A file in the current working directory is automatically added to Crush's context, storing frequently used bash commands, user code style preferences, and codebase structure information. Crush proactively suggests adding useful commands or code style information to CRUSH.md for future reference [46, 65, 77, 98].

    ◦ Core Mandates & Guidelines: Crush rigorously adheres to existing project conventions, never assumes library availability, mimics existing code style, and makes idiomatic changes. Critically, it does not add comments unless explicitly asked, never uses emojis, and never commits changes without explicit user permission [47-49, 73, 76, 79, 84, 99].

4. Tooling & External Integrations: Crush executes tasks using a variety of tools:

    ◦ File System Tools: view, edit, write, grep, glob for interacting with the codebase [48].

    ◦ Shell Commands: bash for running commands like build, test, lint, typecheck [48]. Crush explains critical bash commands that modify the file system before execution [49].

    ◦ LSP (Language Server Protocol): Used for additional code context, enhancing its understanding of the project [43, 54, 62].

    ◦ MCP (Model Context Protocol): Crush adds capabilities via MCPs (http, stdio, sse), allowing it to connect to other MCP servers like Archon or Agent Zero [43, 54, 63].

The workflow emphasizes understanding, planning, incremental implementation, and rigorous verification through testing and linting, all while maintaining a concise and professional CLI interaction style [48, 49].

--------------------------------------------------------------------------------

## 6. Cataclysm Provisioning Workflow

This diagram illustrates how the Cataclysm Provisioning Bundle is used for the mass deployment of Docker Compose stacks and other infrastructure components across the distributed PMOVES hardware network [100-104].

```mermaid
sequenceDiagram
    participant CB as Cataclysm Bundle (Ventoy USB)
    participant WS as Workstations (Ubuntu)
    participant ED as Edge Devices (Jetson Orin Nano)
    participant SCS as Supabase (Config/Secrets)
    participant DCP as Docker Compose Stacks (Jellyfin, Archon, ComfyUI, Agent Zero)

    CB->>WS: Copy Bundle & ISOs
    CB->>ED: Copy Bundle & ISOs

    WS->>WS: Select Ubuntu Server ISO via Ventoy
    Note over WS: Ubuntu autoinstall (cloud-init) uses linux/ubuntu-autoinstall/user-data
    WS->>WS: Automatically sets up Docker & Tailscale
    WS->>DCP: Integrate Docker Compose files for PMOVES components
    WS->>SCS: Populate .env with Supabase credentials & API Keys

    ED->>ED: Flash JetPack as usual
    Note over ED: Run jetson/jetson-postinstall.sh on first boot
    ED->>ED: Bootstraps Docker & NVIDIA runtime (for GPU acceleration)
    ED->>DCP: Selectively deploy Docker Compose files (e.g., Audio/Video AI Services)
    ED->>SCS: Populate .env with necessary secrets

    DCP->>WS: Deploy Docker Compose stacks on Workstations (docker compose up -d)
    DCP->>ED: Deploy Docker Compose stacks on Edge Devices (docker compose up -d)

    Note over DCP: All components (Jellyfin AI Media Stack, Archon, ComfyUI, Agent Zero) are now deployed
```

**Explanation:**

The Cataclysm Provisioning Bundle is a critical tool for the mass deployment and consistent setup of PMOVES components across its distributed hardware [100, 102].

1. Bundle Preparation: The Cataclysm Bundle (typically on a Ventoy USB stick) contains the necessary ISOs, automated installation scripts, and configuration files [102, 103]. This bundle is copied to multiple Workstations (e.g., Ubuntu-based) and Edge Devices (e.g., Jetson Orin Nano Super devices) [103].

2. Workstation Deployment: For Linux-based workstations, the Ubuntu autoinstall process is used. It leverages linux/ubuntu-autoinstall/user-data for unattended installations, which also sets up Docker and Tailscale [101, 103]. These scripts are then extended to integrate the specific Docker Compose files for PMOVES components like Archon, Agent Zero, and ComfyUI. The system populates environment variables (.env) with credentials and API keys, potentially sourced from Supabase or other secure mechanisms [101].

3. Edge Device Deployment: For Jetson Orin Nano devices, after flashing JetPack, the jetson/jetson-postinstall.sh script is run on first boot. This bootstraps Docker and the NVIDIA runtime, which is essential for GPU-accelerated AI models within the Jellyfin AI Media Stack (e.g., Audio AI Service, Video AI Service) [101, 103, 104]. Specific Docker Compose files can be selectively deployed to these edge devices [101].

4. Docker Compose Deployment: Once the base environment is provisioned and configured, the respective Docker Compose stacks for PMOVES components (such as the Jellyfin AI Media Stack, Archon, ComfyUI, and Agent Zero) are brought up using docker compose up -d commands on both workstations and edge devices [101, 104]. This ensures a consistent and efficient deployment of the entire distributed AI ecosystem.

The Cataclysm bundle also handles secrets management through placeholders in .env files, which are populated by the post-install scripts [101, 105]. This automated deployment mechanism is key to scaling and maintaining the PMOVES system.
