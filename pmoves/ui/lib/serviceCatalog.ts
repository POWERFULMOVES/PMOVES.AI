/* ═══════════════════════════════════════════════════════════════════════════
   PMOVES Multi-Stack Service Catalog
   Comprehensive catalog of 100+ services across all stacks organized by tier/category
   Stacks: PMOVES Main, PMOVES-DoX, BotZ Gateway, Cataclysm
   Cataclysm Studios Inc.
   ═══════════════════════════════════════════════════════════════════════════ */

export type ServiceCategory =
  | 'observability'
  | 'database'
  | 'data'
  | 'bus'
  | 'workers'
  | 'agents'
  | 'gpu'
  | 'media'
  | 'llm'
  | 'ui'
  | 'integration'
  | 'dox';  // PMOVES-DoX document intelligence
  | 'mcp';  // Model Context Protocol servers

export type ServiceColor = 'cyan' | 'ember' | 'gold' | 'forest' | 'violet';

export interface ServiceEndpoint {
  name: string;
  port: string;
  path: string;
  type: 'api' | 'ui' | 'health' | 'metrics' | 'ws';
}

export interface ServiceDefinition {
  slug: string;
  title: string;
  summary: string;
  category: ServiceCategory;
  color: ServiceColor;
  endpoints: ServiceEndpoint[];
  healthCheck?: string; // URL path for health check
  metricsPath?: string; // Prometheus metrics path
  external?: boolean; // Opens in new tab
  description?: string; // Extended description
  capabilities?: string[]; // Feature highlights
  dependencies?: string[]; // Required services
  profile?: string; // Docker compose profile
  status?: 'healthy' | 'unhealthy' | 'starting' | 'unknown';
}

// Color mapping for categories
const CATEGORY_COLORS: Record<ServiceCategory, ServiceColor> = {
  observability: 'cyan',
  database: 'violet',
  data: 'forest',
  bus: 'gold',
  workers: 'ember',
  agents: 'cyan',
  gpu: 'forest',
  media: 'ember',
  llm: 'gold',
  ui: 'violet',
  integration: 'cyan',
  dox: 'forest',  // Document intelligence (green)
  mcp: 'gold',    // MCP servers (yellow)
};

/* ═══════════════════════════════════════════════════════════════════════════
   Service Catalog - All 100+ Services
   ═══════════════════════════════════════════════════════════════════════════ */

export const SERVICE_CATALOG: ServiceDefinition[] = [
  // ============================================================================
  // OBSERVABILITY TIER
  // ============================================================================
  {
    slug: 'prometheus',
    title: 'Prometheus',
    summary: 'Metrics collection and alerting for all services',
    category: 'observability',
    color: 'cyan',
    endpoints: [
      { name: 'Web UI', port: '9090', path: '/', type: 'ui' },
      { name: 'API', port: '9090', path: '/api/v1', type: 'api' },
      { name: 'Health', port: '9090', path: '/-/ready', type: 'health' },
    ],
    healthCheck: 'http://localhost:9090/-/ready',
    metricsPath: '/metrics',
    capabilities: ['Metrics scraping', 'Alerting', 'Service discovery'],
  },
  {
    slug: 'grafana',
    title: 'Grafana',
    summary: 'Dashboard visualization for Prometheus metrics',
    category: 'observability',
    color: 'cyan',
    endpoints: [
      { name: 'Web UI', port: '3002', path: '/', type: 'ui' },
      { name: 'API', port: '3002', path: '/api', type: 'api' },
      { name: 'Health', port: '3002', path: '/api/health', type: 'health' },
    ],
    healthCheck: 'http://localhost:3002/api/health',
    external: true,
    capabilities: ['Dashboards', 'Visualization', 'Alert panels'],
  },
  {
    slug: 'loki',
    title: 'Loki',
    summary: 'Log aggregation system with Promtail agents',
    category: 'observability',
    color: 'cyan',
    endpoints: [
      { name: 'API', port: '3100', path: '/', type: 'api' },
      { name: 'Health', port: '3100', path: '/ready', type: 'health' },
    ],
    healthCheck: 'http://localhost:3100/ready',
    capabilities: ['Log aggregation', 'Label-based queries'],
  },
  {
    slug: 'cadvisor',
    title: 'cAdvisor',
    summary: 'Container metrics for Prometheus',
    category: 'observability',
    color: 'cyan',
    endpoints: [
      { name: 'Web UI', port: '8080', path: '/', type: 'ui' },
      { name: 'Metrics', port: '8080', path: '/metrics', type: 'metrics' },
    ],
    capabilities: ['Container stats', 'Resource usage'],
  },

  // ============================================================================
  // DATABASE TIER
  // ============================================================================
  {
    slug: 'postgres',
    title: 'PostgreSQL',
    summary: 'Primary database with Supabase extensions',
    category: 'database',
    color: 'violet',
    endpoints: [
      { name: 'Database', port: '5432', path: '/', type: 'api' },
    ],
    capabilities: ['pgvector', 'RLS', 'Supabase schema'],
  },
  {
    slug: 'postgrest',
    title: 'PostgREST',
    summary: 'RESTful API for PostgreSQL',
    category: 'database',
    color: 'violet',
    endpoints: [
      { name: 'REST API', port: '3010', path: '/rest/v1', type: 'api' },
    ],
    capabilities: ['Auto-generated REST', 'JWT auth'],
  },
  {
    slug: 'supabase-studio',
    title: 'Supabase Studio',
    summary: 'Database management UI',
    category: 'database',
    color: 'violet',
    endpoints: [
      { name: 'Web UI', port: '65433', path: '/', type: 'ui' },
    ],
    external: true,
    capabilities: ['Table editor', 'SQL editor', 'Auth UI'],
  },

  // ============================================================================
  // DATA TIER
  // ============================================================================
  {
    slug: 'qdrant',
    title: 'Qdrant',
    summary: 'Vector database for semantic search',
    category: 'data',
    color: 'forest',
    endpoints: [
      { name: 'API', port: '6333', path: '/', type: 'api' },
      { name: 'Web UI', port: '6333', path: '/dashboard', type: 'ui' },
      { name: 'Health', port: '6333', path: '/', type: 'health' },
    ],
    healthCheck: 'http://localhost:6333/',
    capabilities: ['Vector search', 'Embeddings storage', 'Filtering'],
  },
  {
    slug: 'neo4j',
    title: 'Neo4j',
    summary: 'Graph database for knowledge relationships',
    category: 'data',
    color: 'forest',
    endpoints: [
      { name: 'HTTP API', port: '7474', path: '/', type: 'api' },
      { name: 'Bolt Protocol', port: '7687', path: '/', type: 'api' },
      { name: 'Web UI', port: '7474', path: '/', type: 'ui' },
    ],
    healthCheck: 'http://localhost:7474/',
    capabilities: ['Graph traversal', 'Cypher queries', 'Relationships'],
  },
  {
    slug: 'meilisearch',
    title: 'Meilisearch',
    summary: 'Full-text search with typo tolerance',
    category: 'data',
    color: 'forest',
    endpoints: [
      { name: 'API', port: '7700', path: '/', type: 'api' },
      { name: 'Health', port: '7700', path: '/health', type: 'health' },
    ],
    healthCheck: 'http://localhost:7700/health',
    capabilities: ['Full-text search', 'Typo tolerance', 'Faceted search'],
  },
  {
    slug: 'minio',
    title: 'MinIO',
    summary: 'S3-compatible object storage',
    category: 'data',
    color: 'forest',
    endpoints: [
      { name: 'API', port: '9000', path: '/', type: 'api' },
      { name: 'Console', port: '9001', path: '/', type: 'ui' },
      { name: 'Health', port: '9000', path: '/minio/health/live', type: 'health' },
    ],
    healthCheck: 'http://localhost:9000/minio/health/live',
    external: true,
    capabilities: ['Object storage', 'Buckets', 'Presigned URLs'],
  },

  // ============================================================================
  // BUS TIER
  // ============================================================================
  {
    slug: 'nats',
    title: 'NATS',
    summary: 'Message bus with JetStream persistence',
    category: 'bus',
    color: 'gold',
    endpoints: [
      { name: 'Client', port: '4222', path: '/', type: 'api' },
      { name: 'Monitoring', port: '8222', path: '/', type: 'api' },
    ],
    capabilities: ['Pub/Sub', 'JetStream', 'Request/Reply'],
  },

  // ============================================================================
  // AGENTS TIER
  // ============================================================================
  {
    slug: 'agent-zero',
    title: 'Agent Zero',
    summary: 'Control-plane orchestrator with MCP gateway',
    category: 'agents',
    color: 'cyan',
    endpoints: [
      { name: 'API', port: '8080', path: '/', type: 'api' },
      { name: 'MCP API', port: '8080', path: '/mcp', type: 'api' },
      { name: 'Health', port: '8080', path: '/healthz', type: 'health' },
      { name: 'UI', port: '8081', path: '/', type: 'ui' },
    ],
    healthCheck: 'http://localhost:8080/healthz',
    capabilities: ['MCP gateway', 'Task delegation', 'NATS coordination'],
    dependencies: ['nats', 'postgres'],
  },
  {
    slug: 'archon',
    title: 'Archon',
    summary: 'Supabase-driven prompt and persona studio',
    category: 'agents',
    color: 'violet',
    endpoints: [
      { name: 'API', port: '8091', path: '/', type: 'api' },
      { name: 'Health', port: '8091', path: '/healthz', type: 'health' },
    ],
    healthCheck: 'http://localhost:8091/healthz',
    capabilities: ['Prompt management', 'Persona studio', 'Form generation'],
    dependencies: ['agent-zero', 'postgres'],
  },
  {
    slug: 'archon-ui',
    title: 'Archon UI',
    summary: 'Web interface for Archon prompt studio',
    category: 'agents',
    color: 'violet',
    endpoints: [
      { name: 'Web UI', port: '3737', path: '/', type: 'ui' },
    ],
    external: true,
    capabilities: ['Prompt editor', 'Persona management'],
  },
  {
    slug: 'deepresearch',
    title: 'DeepResearch',
    summary: 'LLM-based research planning service',
    category: 'agents',
    color: 'gold',
    endpoints: [
      { name: 'API', port: '8098', path: '/', type: 'api' },
      { name: 'Health', port: '8098', path: '/healthz', type: 'health' },
      { name: 'Metrics', port: '8098', path: '/metrics', type: 'metrics' },
    ],
    healthCheck: 'http://localhost:8098/healthz',
    capabilities: ['Research planning', 'Multi-step reasoning', 'Auto-publish'],
  },
  {
    slug: 'supaserch',
    title: 'SupaSerch',
    summary: 'Multimodal holographic deep research orchestrator',
    category: 'agents',
    color: 'cyan',
    endpoints: [
      { name: 'API', port: '8099', path: '/', type: 'api' },
      { name: 'Health', port: '8099', path: '/healthz', type: 'health' },
      { name: 'Metrics', port: '8099', path: '/metrics', type: 'metrics' },
    ],
    healthCheck: 'http://localhost:8099/healthz',
    capabilities: ['Deep search', 'Multi-source', 'NATS coordination'],
    dependencies: ['deepresearch', 'agent-zero'],
  },
  {
    slug: 'mesh-agent',
    title: 'Mesh Agent',
    summary: 'Multi-host orchestrator announcer',
    category: 'agents',
    color: 'gold',
    endpoints: [],
    capabilities: ['Host discovery', 'Capability announcement'],
  },
  {
    slug: 'consciousness-service',
    title: 'Consciousness Service',
    summary: 'Agent reflection and state management',
    category: 'agents',
    color: 'violet',
    endpoints: [
      { name: 'API', port: '8096', path: '/', type: 'api' },
      { name: 'Health', port: '8096', path: '/healthz', type: 'health' },
    ],
    healthCheck: 'http://localhost:8096/healthz',
  },
  {
    slug: 'botz-gateway',
    title: 'BotZ Gateway',
    summary: 'MCP server for BotZ agent system',
    category: 'agents',
    color: 'cyan',
    endpoints: [
      { name: 'API', port: '8054', path: '/', type: 'api' },
      { name: 'Health', port: '8054', path: '/healthz', type: 'health' },
    ],
    healthCheck: 'http://localhost:8054/healthz',
  },

  // ============================================================================
  // WORKERS TIER
  // ============================================================================
  {
    slug: 'extract-worker',
    title: 'Extract Worker',
    summary: 'Text embedding and indexing service',
    category: 'workers',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8083', path: '/', type: 'api' },
      { name: 'Health', port: '8083', path: '/healthz', type: 'health' },
    ],
    healthCheck: 'http://localhost:8083/healthz',
    capabilities: ['Embeddings', 'Qdrant indexing', 'Meilisearch indexing'],
    dependencies: ['qdrant', 'meilisearch'],
  },
  {
    slug: 'langextract',
    title: 'LangExtract',
    summary: 'Language detection and NLP preprocessing',
    category: 'workers',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8084', path: '/', type: 'api' },
      { name: 'Health', port: '8084', path: '/healthz', type: 'health' },
    ],
    healthCheck: 'http://localhost:8084/healthz',
    capabilities: ['Language detection', 'Text preprocessing'],
  },
  {
    slug: 'notebook-sync',
    title: 'Notebook Sync',
    summary: 'SurrealDB Open Notebook synchronizer',
    category: 'workers',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8095', path: '/', type: 'api' },
      { name: 'Health', port: '8095', path: '/healthz', type: 'health' },
    ],
    healthCheck: 'http://localhost:8095/healthz',
    capabilities: ['Notebook sync', 'Change detection'],
  },
  {
    slug: 'pdf-ingest',
    title: 'PDF Ingest',
    summary: 'Document ingestion orchestrator',
    category: 'workers',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8092', path: '/', type: 'api' },
    ],
    capabilities: ['PDF parsing', 'Text extraction'],
  },
  {
    slug: 'session-context-worker',
    title: 'Session Context Worker',
    summary: 'Session state and context management',
    category: 'workers',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8100', path: '/', type: 'api' },
    ],
  },
  {
    slug: 'chat-relay',
    title: 'Chat Relay',
    summary: 'Chat message routing and relay',
    category: 'workers',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8102', path: '/', type: 'api' },
    ],
  },
  {
    slug: 'messaging-gateway',
    title: 'Messaging Gateway',
    summary: 'Cross-service message routing',
    category: 'workers',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8101', path: '/', type: 'api' },
    ],
  },
  {
    slug: 'presign',
    title: 'Presign',
    summary: 'MinIO URL presigner for secure downloads',
    category: 'workers',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8088', path: '/', type: 'api' },
      { name: 'Health', port: '8080', path: '/healthz', type: 'health' },
    ],
    capabilities: ['URL presigning', 'Secure downloads'],
  },
  {
    slug: 'render-webhook',
    title: 'Render Webhook',
    summary: 'ComfyUI render callback handler',
    category: 'workers',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8085', path: '/comfy/webhook', type: 'api' },
    ],
    capabilities: ['Render callbacks', 'Supabase writes'],
  },
  {
    slug: 'comfy-watcher',
    title: 'ComfyWatcher',
    summary: 'ComfyUI output directory watcher',
    category: 'workers',
    color: 'ember',
    endpoints: [],
    capabilities: ['Directory watching', 'Event triggering'],
  },
  {
    slug: 'publisher-discord',
    title: 'Publisher Discord',
    summary: 'Discord notification bot',
    category: 'workers',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8094', path: '/', type: 'api' },
    ],
    capabilities: ['Discord publishing', 'Event notifications'],
  },
  {
    slug: 'jellyfin-bridge',
    title: 'Jellyfin Bridge',
    summary: 'Jellyfin metadata webhook helper',
    category: 'workers',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8093', path: '/', type: 'api' },
    ],
    capabilities: ['Metadata sync', 'Event handling'],
  },
  {
    slug: 'retrieval-eval',
    title: 'Retrieval Eval',
    summary: 'RAG retrieval evaluation service',
    category: 'workers',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8090', path: '/', type: 'api' },
    ],
    capabilities: ['Retrieval testing', 'Quality metrics'],
  },
  {
    slug: 'bgutil-pot-provider',
    title: 'BgUtil Pot Provider',
    summary: 'Background utility provider service',
    category: 'workers',
    color: 'ember',
    endpoints: [],
  },
  {
    slug: 'pmz-e2b-runner',
    title: 'PMZ E2B Runner',
    summary: 'E2B sandbox execution environment',
    category: 'workers',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '7071', path: '/', type: 'api' },
    ],
    capabilities: ['Sandboxed code execution'],
  },

  // ============================================================================
  // GPU TIER
  // ============================================================================
  {
    slug: 'gpu-orchestrator',
    title: 'GPU Orchestrator',
    summary: 'VRAM management and model lifecycle',
    category: 'gpu',
    color: 'forest',
    endpoints: [
      { name: 'API', port: '8200', path: '/', type: 'api' },
      { name: 'Health', port: '8200', path: '/healthz', type: 'health' },
      { name: 'Metrics', port: '8200', path: '/metrics', type: 'metrics' },
    ],
    healthCheck: 'http://localhost:8200/healthz',
    capabilities: ['VRAM tracking', 'Model loading', 'GPU mesh'],
  },
  {
    slug: 'hi-rag-gateway-v2',
    title: 'Hi-RAG v2 CPU',
    summary: 'Hybrid RAG with cross-encoder reranking (CPU)',
    category: 'gpu',
    color: 'forest',
    endpoints: [
      { name: 'API', port: '8086', path: '/', type: 'api' },
      { name: 'Health', port: '8086', path: '/hirag/admin/stats', type: 'health' },
    ],
    healthCheck: 'http://localhost:8086/hirag/admin/stats',
    capabilities: ['Vector search', 'Graph traversal', 'Reranking'],
    dependencies: ['qdrant', 'neo4j', 'meilisearch'],
  },
  {
    slug: 'hi-rag-gateway-v2-gpu',
    title: 'Hi-RAG v2 GPU',
    summary: 'Hybrid RAG with GPU acceleration',
    category: 'gpu',
    color: 'forest',
    endpoints: [
      { name: 'API', port: '8087', path: '/', type: 'api' },
      { name: 'Health', port: '8087', path: '/hirag/admin/stats', type: 'health' },
    ],
    healthCheck: 'http://localhost:8087/hirag/admin/stats',
    capabilities: ['GPU-accelerated RAG', 'Fast embeddings'],
  },
  {
    slug: 'hi-rag-gateway-gpu',
    title: 'Hi-RAG GPU (Legacy)',
    summary: 'Legacy Hi-RAG with GPU support',
    category: 'gpu',
    color: 'forest',
    endpoints: [
      { name: 'API', port: '8110', path: '/', type: 'api' },
    ],
    capabilities: ['GPU RAG (legacy)'],
  },
  {
    slug: 'hi-rag-gateway',
    title: 'Hi-RAG (Legacy)',
    summary: 'Legacy Hi-RAG gateway',
    category: 'gpu',
    color: 'forest',
    endpoints: [
      { name: 'API', port: '8089', path: '/', type: 'api' },
    ],
    capabilities: ['RAG (legacy)'],
  },
  {
    slug: 'ultimate-tts-studio',
    title: 'Ultimate TTS Studio',
    summary: 'Multi-engine TTS with 7 engines',
    category: 'gpu',
    color: 'forest',
    endpoints: [
      { name: 'Web UI', port: '7861', path: '/', type: 'ui' },
      { name: 'Health', port: '7861', path: '/gradio_api/info', type: 'health' },
    ],
    healthCheck: 'http://localhost:7861/gradio_api/info',
    external: true,
    capabilities: ['Kokoro', 'F5-TTS', 'KittenTTS', 'Voice cloning'],
  },
  {
    slug: 'flute-gateway',
    title: 'Flute Gateway',
    summary: 'Multimodal voice communication layer',
    category: 'gpu',
    color: 'forest',
    endpoints: [
      { name: 'HTTP API', port: '8055', path: '/', type: 'api' },
      { name: 'WebSocket', port: '8056', path: '/', type: 'ws' },
      { name: 'Health', port: '8055', path: '/healthz', type: 'health' },
      { name: 'Metrics', port: '8055', path: '/metrics', type: 'metrics' },
    ],
    healthCheck: 'http://localhost:8055/healthz',
    capabilities: ['Prosodic TTS', 'WebSocket streaming', 'Pipecat'],
  },

  // ============================================================================
  // MEDIA TIER
  // ============================================================================
  {
    slug: 'pmoves-yt',
    title: 'PMOVES.YT',
    summary: 'YouTube ingestion service',
    category: 'media',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8077', path: '/', type: 'api' },
      { name: 'Ingest', port: '8077', path: '/yt/ingest', type: 'api' },
    ],
    capabilities: ['YouTube download', 'Metadata sync', 'Transcript trigger'],
  },
  {
    slug: 'channel-monitor',
    title: 'Channel Monitor',
    summary: 'YouTube channel watcher',
    category: 'media',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8097', path: '/api/monitor/stats', type: 'api' },
    ],
    capabilities: ['Channel watching', 'New video detection'],
  },
  {
    slug: 'ffmpeg-whisper',
    title: 'FFmpeg Whisper',
    summary: 'Media transcription with Whisper',
    category: 'media',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8078', path: '/', type: 'api' },
    ],
    capabilities: ['Transcription', 'Faster-Whisper', 'GPU support'],
  },
  {
    slug: 'media-video',
    title: 'Media Video Analyzer',
    summary: 'Object/frame analysis with YOLOv8',
    category: 'media',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8079', path: '/', type: 'api' },
      { name: 'Health', port: '8079', path: '/healthz', type: 'health' },
    ],
    healthCheck: 'http://localhost:8079/healthz',
    capabilities: ['YOLO detection', 'Frame sampling'],
  },
  {
    slug: 'media-audio',
    title: 'Media Audio Analyzer',
    summary: 'Audio emotion and speaker detection',
    category: 'media',
    color: 'ember',
    endpoints: [
      { name: 'API', port: '8082', path: '/', type: 'api' },
      { name: 'Health', port: '8082', path: '/healthz', type: 'health' },
    ],
    healthCheck: 'http://localhost:8082/healthz',
    capabilities: ['Emotion detection', 'Speaker diarization'],
  },

  // ============================================================================
  // LLM TIER
  // ============================================================================
  {
    slug: 'tensorzero-gateway',
    title: 'TensorZero Gateway',
    summary: 'Centralized LLM gateway with observability',
    category: 'llm',
    color: 'gold',
    endpoints: [
      { name: 'API', port: '3030', path: '/v1', type: 'api' },
      { name: 'Health', port: '3030', path: '/healthz', type: 'health' },
    ],
    healthCheck: 'http://localhost:3030/healthz',
    capabilities: ['Multi-provider', 'OpenAI-compatible', 'Observability'],
  },
  {
    slug: 'tensorzero-ui',
    title: 'TensorZero UI',
    summary: 'Metrics dashboard for LLM gateway',
    category: 'llm',
    color: 'gold',
    endpoints: [
      { name: 'Web UI', port: '4000', path: '/', type: 'ui' },
    ],
    external: true,
    capabilities: ['Request logs', 'Usage analytics'],
  },
  {
    slug: 'tensorzero-clickhouse',
    title: 'TensorZero ClickHouse',
    summary: 'Observability metrics storage',
    category: 'llm',
    color: 'gold',
    endpoints: [
      { name: 'HTTP', port: '8123', path: '/', type: 'api' },
      { name: 'Health', port: '8123', path: '/ping', type: 'health' },
    ],
    healthCheck: 'http://localhost:8123/ping',
    capabilities: ['Metrics storage', 'Analytics queries'],
  },
  {
    slug: 'pmoves-ollama',
    title: 'PMOVES Ollama',
    summary: 'Local LLM inference engine',
    category: 'llm',
    color: 'gold',
    endpoints: [
      { name: 'API', port: '11434', path: '/', type: 'api' },
    ],
    capabilities: ['Local inference', 'Model management'],
  },

  // ============================================================================
  // UI TIER
  // ============================================================================
  {
    slug: 'pmoves-ui',
    title: 'PMOVES UI',
    summary: 'Centralized dashboard for all services',
    category: 'ui',
    color: 'violet',
    endpoints: [
      { name: 'Web UI', port: '4482', path: '/', type: 'ui' },
      { name: 'Health', port: '4482', path: '/api/health', type: 'health' },
    ],
    healthCheck: 'http://localhost:4482/api/health',
    external: true,
    capabilities: ['Service catalog', 'Health monitoring', 'Branded portal'],
  },

  // ============================================================================
  // INTEGRATION TIER
  // ============================================================================
  {
    slug: 'n8n',
    title: 'n8n',
    summary: 'Workflow automation platform',
    category: 'integration',
    color: 'cyan',
    endpoints: [
      { name: 'Web UI', port: '5678', path: '/', type: 'ui' },
    ],
    external: true,
    capabilities: ['Workflow automation', '200+ integrations'],
  },
  {
    slug: 'invidious',
    title: 'Invidious',
    summary: 'Privacy-focused YouTube frontend',
    category: 'integration',
    color: 'cyan',
    endpoints: [
      { name: 'Web UI', port: '8095', path: '/', type: 'ui' },
    ],
    external: true,
    capabilities: ['YouTube frontend', 'Privacy'],
  },
  {
    slug: 'grayjay',
    title: 'Grayjay',
    summary: 'Multi-platform video client',
    category: 'integration',
    color: 'cyan',
    endpoints: [
      { name: 'Plugin Host', port: '7860', path: '/', type: 'api' },
      { name: 'Server', port: '7860', path: '/', type: 'api' },
    ],
    capabilities: ['Multi-platform', 'Plugin system'],
  },

  // ============================================================================
  // PMOVES-DOX TIER (Document Intelligence)
  // ============================================================================
  {
    slug: 'dox-backend',
    title: 'DoX Backend',
    summary: 'Document intelligence API for PDF analysis and extraction',
    category: 'dox',
    color: 'forest',
    endpoints: [
      { name: 'API', port: '8484', path: '/', type: 'api' },
      { name: 'Health', port: '8484', path: '/health', type: 'health' },
      { name: 'Search', port: '8484', path: '/search', type: 'api' },
      { name: 'Ingest', port: '8484', path: '/ingest', type: 'api' },
    ],
    healthCheck: 'http://localhost:8484/health',
    capabilities: ['PDF parsing', 'Vector search', 'QA engine', 'CHR pipeline'],
    dependencies: ['tensorzero-gateway', 'neo4j', 'nats'],
  },
  {
    slug: 'dox-frontend',
    title: 'DoX Frontend',
    summary: 'Next.js UI for document analysis and visualization',
    category: 'dox',
    color: 'forest',
    endpoints: [
      { name: 'Web UI', port: '3001', path: '/', type: 'ui' },
    ],
    external: true,
    capabilities: ['Document viewer', 'Search interface', 'Visualization'],
  },
  {
    slug: 'dox-nats',
    title: 'DoX NATS',
    summary: 'Dedicated message bus for DoX geometry events',
    category: 'dox',
    color: 'gold',
    endpoints: [
      { name: 'Client', port: '4223', path: '/', type: 'api' },
      { name: 'Monitoring', port: '8223', path: '/varz', type: 'api' },
      { name: 'WebSocket', port: '9223', path: '/', type: 'ws' },
    ],
    capabilities: ['Geometry bus', 'CHIT packets', 'Event streaming'],
  },
  {
    slug: 'dox-neo4j',
    title: 'DoX Neo4j',
    summary: 'Local knowledge graph for DoX document relationships',
    category: 'dox',
    color: 'violet',
    endpoints: [
      { name: 'HTTP API', port: '17474', path: '/', type: 'api' },
      { name: 'Bolt Protocol', port: '17687', path: '/', type: 'api' },
      { name: 'Web UI', port: '17474', path: '/', type: 'ui' },
    ],
    capabilities: ['Document graph', 'Relationship mapping', 'Cypher queries'],
  },
  {
    slug: 'dox-ollama',
    title: 'DoX Ollama',
    summary: 'Local LLM inference for DoX document processing',
    category: 'dox',
    color: 'gold',
    endpoints: [
      { name: 'API', port: '11435', path: '/', type: 'api' },
    ],
    capabilities: ['Local inference', 'Tag extraction', 'Embeddings'],
  },
  {
    slug: 'dox-cipher',
    title: 'DoX Cipher Service',
    summary: 'CHIT geometry protocol for mathematical visualization',
    category: 'dox',
    color: 'violet',
    endpoints: [
      { name: 'API', port: '3000', path: '/', type: 'api' },
      { name: 'Health', port: '3000', path: '/health', type: 'health' },
    ],
    capabilities: ['CHIT protocol', 'Geometry packets', 'Manifold detection'],
  },

  // ============================================================================
  // MCP TIER (Model Context Protocol Servers)
  // ============================================================================
  {
    slug: 'mcp-cipher',
    title: 'MCP Cipher',
    summary: 'CHIT geometry and mathematical protocol server',
    category: 'mcp',
    color: 'gold',
    endpoints: [
      { name: 'MCP API', port: '3025', path: '/', type: 'api' },
      { name: 'Health', port: '3025', path: '/health', type: 'health' },
    ],
    healthCheck: 'http://localhost:3025/health',
    capabilities: ['CHIT protocol', 'Geometry encoding', 'Memory framework'],
  },
  {
    slug: 'mcp-docling',
    title: 'MCP Docling',
    summary: 'Document parsing MCP server with OCR and table extraction',
    category: 'mcp',
    color: 'gold',
    endpoints: [
      { name: 'MCP API', port: '3020', path: '/', type: 'api' },
      { name: 'Health', port: '3020', path: '/health', type: 'health' },
    ],
    healthCheck: 'http://localhost:3020/health',
    capabilities: ['PDF parsing', 'OCR', 'Table extraction', 'Document understanding'],
  },
  {
    slug: 'mcp-postman',
    title: 'MCP Postman',
    summary: 'Postman API collection testing MCP server',
    category: 'mcp',
    color: 'gold',
    endpoints: [
      { name: 'MCP API', port: '3026', path: '/', type: 'api' },
    ],
    capabilities: ['API testing', 'Collection runner', 'Request validation'],
  },

  // ============================================================================
  // CATACLYSM STACK (Health, Wealth, Notes)
  // ============================================================================
  {
    slug: 'cataclysm-firefly',
    title: 'Firefly III',
    summary: 'Personal finance manager (Cataclysm stack)',
    category: 'integration',
    color: 'violet',
    endpoints: [
      { name: 'Web UI', port: '8080', path: '/', type: 'ui' },
      { name: 'API', port: '8080', path: '/api/v1', type: 'api' },
    ],
    external: true,
    capabilities: ['Budget tracking', 'Transaction management', 'Financial reports'],
  },
  {
    slug: 'cataclysm-jellyfin',
    title: 'Jellyfin (Cataclysm)',
    summary: 'Media server (Cataclysm stack)',
    category: 'media',
    color: 'ember',
    endpoints: [
      { name: 'Web UI', port: '8096', path: '/', type: 'ui' },
    ],
    external: true,
    capabilities: ['Media streaming', 'Video library', 'Music'],
  },
  {
    slug: 'cataclysm-open-notebook',
    title: 'Open Notebook (Cataclysm)',
    summary: 'SurrealDB note-taking and knowledge base',
    category: 'integration',
    color: 'violet',
    endpoints: [
      { name: 'API', port: '5055', path: '/', type: 'api' },
      { name: 'WebSocket', port: '8503', path: '/', type: 'ws' },
    ],
    capabilities: ['Note-taking', 'Knowledge base', 'SurrealDB'],
  },
  {
    slug: 'cataclysm-wger',
    title: 'Wger',
    summary: 'Workout and fitness tracker (Cataclysm stack)',
    category: 'integration',
    color: 'ember',
    endpoints: [
      { name: 'Web UI', port: '8002', path: '/', type: 'ui' },
    ],
    external: true,
    capabilities: ['Workout tracking', 'Exercise library', 'Nutrition'],
  },
];

/* ═══════════════════════════════════════════════════════════════════════════
   Category Grouping
   ═══════════════════════════════════════════════════════════════════════════ */

export const SERVICES_BY_CATEGORY: Record<ServiceCategory, ServiceDefinition[]> = {
  observability: SERVICE_CATALOG.filter((s) => s.category === 'observability'),
  database: SERVICE_CATALOG.filter((s) => s.category === 'database'),
  data: SERVICE_CATALOG.filter((s) => s.category === 'data'),
  bus: SERVICE_CATALOG.filter((s) => s.category === 'bus'),
  workers: SERVICE_CATALOG.filter((s) => s.category === 'workers'),
  agents: SERVICE_CATALOG.filter((s) => s.category === 'agents'),
  gpu: SERVICE_CATALOG.filter((s) => s.category === 'gpu'),
  media: SERVICE_CATALOG.filter((s) => s.category === 'media'),
  llm: SERVICE_CATALOG.filter((s) => s.category === 'llm'),
  ui: SERVICE_CATALOG.filter((s) => s.category === 'ui'),
  integration: SERVICE_CATALOG.filter((s) => s.category === 'integration'),
  dox: SERVICE_CATALOG.filter((s) => s.category === 'dox'),
  mcp: SERVICE_CATALOG.filter((s) => s.category === 'mcp'),
};

/* ═══════════════════════════════════════════════════════════════════════════
   Utility Functions
   ═══════════════════════════════════════════════════════════════════════════ */

export function getServiceBySlug(slug: string): ServiceDefinition | undefined {
  return SERVICE_CATALOG.find((s) => s.slug === slug);
}

export function getServicesByCategory(category: ServiceCategory): ServiceDefinition[] {
  return SERVICES_BY_CATEGORY[category] || [];
}

export function getCategoryColor(category: ServiceCategory): ServiceColor {
  return CATEGORY_COLORS[category];
}

export function getServiceUrl(service: ServiceDefinition, endpointType?: 'api' | 'ui' | 'health'): string {
  const endpoint = endpointType
    ? service.endpoints.find((e) => e.type === endpointType)
    : service.endpoints.find((e) => e.type === 'ui') || service.endpoints.find((e) => e.type === 'api');

  if (!endpoint) return '#';

  return `http://localhost:${endpoint.port}${endpoint.path}`;
}
