# Gateway Agent Architecture

This document describes the architecture of the PMOVES Gateway Agent, the central orchestrator for 100+ MCP tools in the PMOVES.AI infrastructure.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GATEWAY AGENT (8100)                        │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                    FastAPI Application                        │ │
│  │  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐ │ │
│  │  │  Tool          │  │   Secrets      │  │    Health     │ │ │
│  │  │  Registry      │  │   Manager      │  │    Check      │ │ │
│  │  └────────────────┘  └────────────────┘  └───────────────┘ │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────┬─────────────────────┬─────────────────────┬────────────────┘
         │                     │                     │
    ┌────▼────────┐     ┌─────▼────────┐     ┌─────▼────────┐
    │ Agent Zero   │     │  Cipher Memory    │  │  TensorZero  │
    │   (8080)     │     │    (3025)         │  │   (3030)     │
    │  MCP API     │     │  Skills Store     │  │   LLM Gateway│
    └──────────────┘     └───────────────────┘  └──────────────┘
           │
    ┌──────┴────────────────────────────────────────────┐
    │            MCP Tool Catalog (100+ tools)           │
    ├───────────────┬──────────────┬────────────────────┤
    │   Hostinger   │   n8n-agent  │    Docling MCP     │
    │   (VPS/DNS)   │ (workflows)  │   (documents)      │
    ├───────────────┼──────────────┼────────────────────┤
    │   E2B Runner  │ VL Sentinel  │   Postman MCP      │
    │  (code exec)  │  (vision)    │   (API testing)    │
    └───────────────┴──────────────┴────────────────────┘
```

## Component Architecture

### Core Components

| Component | Description | Key Responsibilities |
|-----------|-------------|---------------------|
| **FastAPI Application** | Main HTTP server | Request handling, API endpoints, async execution |
| **ToolRegistry** | Tool discovery service | Discover, cache, and categorize MCP tools |
| **SecretManager** | Credential management | Retrieve and mask GitHub Secrets |
| **HealthChecker** | Dependency monitoring | Verify upstream service availability |

### Data Flow

#### Tool Discovery Flow

```
1. Startup Event
   ↓
2. ToolRegistry.discover_tools(force_refresh=True)
   ↓
3. HTTP GET → Agent Zero /mcp/commands
   ↓
4. Parse response → ToolDefinition[]
   ↓
5. Cache with TTL (default: 300s)
   ↓
6. Return categorized tools
```

#### Tool Execution Flow

```
1. POST /tools/execute
   ↓
2. Validate request (tool_name, parameters)
   ↓
3. Lookup tool in registry
   ↓
4. Route to upstream:
   ├─ Container-based MCP → Agent Zero MCP proxy
   └─ HTTP-based MCP → Direct HTTP call
   ↓
5. Normalize response
   ↓
6. Log execution to TensorZero ClickHouse
   ↓
7. Return {success, result, error, execution_time_ms}
```

#### Skill Storage Flow

```
1. POST /skills/store
   ↓
2. Validate skill data
   ↓
3. Add metadata (created_at, id)
   ↓
4. HTTP POST → Cipher /skills/store
   ↓
5. Store in Supabase skills_registry table
   ↓
6. Return skill ID
```

## Tool Discovery

### Sources

1. **Agent Zero MCP API** (Primary)
   - Endpoint: `GET /mcp/commands`
   - Returns: Command registry with tool definitions
   - Cached for: 5 minutes (configurable via `TOOL_CACHE_TTL`)

2. **MCP Catalog** (Secondary)
   - Endpoint: `GET /mcp/catalog`
   - Returns: Server-to-tool mappings
   - Used for: Category inference and routing

3. **Fallback Tools** (Tertiary)
   - Hardcoded definitions for critical tools
   - Activated when: Agent Zero unreachable
   - Ensures: Basic functionality during outages

### Category Inference

Tools are automatically categorized based on name patterns:

```python
CATEGORY_MAP = {
    'infrastructure': ['vps', 'dns', 'hostinger', 'tailscale', 'server'],
    'automation': ['workflow', 'n8n', 'schedule', 'cron'],
    'execution': ['sandbox', 'exec', 'e2b', 'run'],
    'vision': ['image', 'video', 'vl', 'vision', 'analyze'],
    'documents': ['document', 'pdf', 'docling', 'convert', 'extract'],
    'memory': ['cipher', 'memory', 'store', 'recall', 'search'],
    'api': ['postman', 'collection', 'api', 'request'],
    'research': ['hirag', 'supaserch', 'research', 'search', 'query']
}
```

## Security Model

### Credential Management

```
GitHub Secrets Repository
         ↓ (injected at runtime)
Environment Variables
         ↓ (read by SecretManager)
SecretManager.get_credential(service)
         ↓ (masked)
GET /secrets → {service: "key123..."}
```

### Network Segmentation

Services are isolated by Docker network tiers:

| Tier | Network | Services | Access Pattern |
|------|---------|----------|----------------|
| API Tier | `pmoves_api` | Gateway, Agent Zero | Public HTTP |
| App Tier | `pmoves_app` | Cipher, TensorZero | Internal |
| Data Tier | `pmoves_data` | Supabase, Qdrant | Database |
| Monitoring | `pmoves_monitoring` | Prometheus, Grafana | Metrics |

### Row-Level Security

Supabase RLS policies on `skills_registry`:

```sql
-- Service role (full access)
CREATE POLICY service_full_access ON skills_registry
  FOR ALL TO service_role
  USING (true);

-- Public read-only (with restrictions)
CREATE POLICY public_read_skills ON skills_registry
  FOR SELECT TO public
  USING (enabled = true);
```

## Observability

### Health Monitoring

Each service dependency is probed every 30 seconds:

```
GET /healthz
  ↓
{
  "status": "healthy|degraded",
  "timestamp": "ISO-8601",
  "services": {
    "agent_zero": "healthy|unreachable",
    "cipher": "healthy|unreachable",
    "tensorzero": "healthy|unreachable"
  }
}
```

### Metrics Exposed

| Metric | Type | Description |
|--------|------|-------------|
| `gateway_tools_discovered` | Gauge | Number of tools in registry |
| `gateway_tools_executed_total` | Counter | Total tool executions |
| `gateway_execution_duration_ms` | Histogram | Tool execution latency |
| `gateway_cache_hits_total` | Counter | Cache hit count |
| `gateway_cache_misses_total` | Counter | Cache miss count |

### Logging

Structured JSON logs to Loki:

```json
{
  "level": "INFO",
  "timestamp": "2025-12-26T12:00:00Z",
  "service": "gateway-agent",
  "message": "Tool execution completed",
  "tool_name": "n8n_agent:list_workflows",
  "execution_time_ms": 123,
  "success": true
}
```

## Data Models

### ToolDefinition

```python
class ToolDefinition(BaseModel):
    name: str              # Unique tool identifier
    description: str       # Human-readable description
    category: str          # Categorical grouping
    mcp_server: str        # Upstream MCP server
    parameters: Dict[str, Any] = {}  # Expected parameters
    enabled: bool = True   # Availability flag
```

### ToolExecuteRequest

```python
class ToolExecuteRequest(BaseModel):
    tool_name: str                    # Tool to execute
    parameters: Dict[str, Any] = {}   # Tool parameters
    timeout: int = 30                 # Execution timeout (seconds)
```

### SkillStoreRequest

```python
class SkillStoreRequest(BaseModel):
    name: str          # Unique skill name
    description: str   # What the skill does
    category: str      # Skill category
    pattern: str       # Pattern to replicate
    outcome: str       # Expected outcome
    mcp_tool: str      # Related MCP tool
```

## Deployment Architecture

### Container Resources

```yaml
gateway-agent:
  deploy:
    resources:
      limits:
        cpus: '1.0'
        memory: 512M
      reservations:
        cpus: '0.25'
        memory: 128M
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8100/healthz"]
    interval: 30s
    timeout: 10s
    retries: 3
```

### Scalability Considerations

- **Horizontal Scaling**: Multiple Gateway instances can share cache via Redis (future)
- **Vertical Scaling**: Increase memory for larger tool registries
- **Cache Tuning**: Adjust `TOOL_CACHE_TTL` based on discovery frequency

## Error Handling

### Retry Strategy

| Error Type | Retry | Backoff | Max Attempts |
|------------|-------|---------|--------------|
| Connection Error | Yes | Exponential | 3 |
| Timeout | Yes | Linear | 2 |
| 4xx Client Error | No | - | 1 |
| 5xx Server Error | Yes | Exponential | 3 |

### Fallback Behavior

```
Primary Discovery (Agent Zero)
    ↓ (fails)
Fallback Tools (hardcoded)
    ↓ (fails)
Error Response + Degraded Status
```

## Future Enhancements

1. **WebSocket Support** for real-time tool execution updates
2. **Redis Caching** for multi-instance deployments
3. **Circuit Breaker** for failing upstream services
4. **Tool Batching** for parallel executions
5. **Skill Templates** for common patterns
6. **GraphQL API** as alternative to REST
