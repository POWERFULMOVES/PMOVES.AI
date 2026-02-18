# Archon External Integration Architecture

## Overview

Archon uses **nested git submodules** in its `external/` directory to provide integration with the PMOVES.AI ecosystem. This design allows Archon to operate standalone while accessing critical services.

## Architecture

```
PMOVES-Archon/
├── external/                    # Nested submodules for PMOVES.AI integration
│   ├── PMOVES-Agent-Zero/    # MCP API for agent orchestration
│   ├── PMOVES-BoTZ/          # BoTZ tools and skills marketplace
│   ├── PMOVES-Deep-Serch/    # Deep research knowledge access
│   └── PMOVES-HiRAG/         # Hybrid RAG knowledge retrieval
├── python/                      # Archon backend
└── archon-ui-main/             # Archon frontend
```

## Integration Points

### 1. PMOVES-Agent-Zero (MCP Protocol)

**Purpose**: Agent orchestration and task delegation
**Protocol**: MCP (Model Context Protocol)
**Endpoint**: `http://agent-zero:8080/mcp/*`

**Usage**: Archon can call Agent Zero's MCP tools for:
- Agent task creation and execution
- Memory storage and retrieval
- Knowledge base queries
- Multi-agent coordination

**Example**:
```typescript
// Archon calls Agent Zero MCP
const result = await mcpClient.callTool({
  name: "agent-zero:delegate_task",
  arguments: { task: "research", context: "..." }
});
```

### 2. PMOVES-BoTZ (Tools & Skills)

**Purpose**: Multi-agent tool execution and skills marketplace
**Services**: Gateway Agent, Tool Catalog, Skills Registry
**Endpoint**: `http://localhost:8054` (BoTZ Gateway)

**Usage**: Archon can access:
- 100+ MCP tools from Gateway Agent
- Skills marketplace with 50+ specialized skills
- Tool execution with proper error handling

**Example**:
```typescript
// Archon calls BoTZ via API
const tools = await fetch('http://botz-gateway:8054/tools');
const result = await fetch('http://botz-gateway:8054/execute', {
  method: 'POST',
  body: JSON.stringify({ tool: 'code-auditor', params })
});
```

### 3. PMOVES-Deep-Serch (Research Knowledge)

**Purpose**: Deep research and knowledge synthesis
**Features**: WebDancer, WebSailor, WebWalker agents
**Endpoint**: `http://deepresearch:8098` (DeepResearch service)

**Usage**: Archon can query deep research results:
- Multi-source research aggregation
- Web crawling and analysis
- Knowledge synthesis

### 4. PMOVES-HiRAG (Hybrid RAG)

**Purpose**: Hybrid retrieval combining vector, graph, and full-text search
**Components**: Qdrant (vectors), Neo4j (graph), Meilisearch (full-text)
**Endpoint**: `http://hi-rag-gateway-v2:8086` (Hi-RAG v2)

**Usage**: Archon performs RAG queries:
```bash
curl -X POST http://hi-rag-gateway-v2:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "...", "top_k": 10, "rerank": true}'
```

## Communication Protocols

| Protocol | Used By | Purpose |
|----------|-----------|---------|
| **MCP** | Agent Zero, BoTZ | Tool invocation, agent coordination |
| **HTTP/REST** | BoTZ Gateway, Deep-Serch | API calls, webhooks |
| **NATS** | All services | Event coordination, pub/sub messaging |
| **WebSocket** | Agent Zero, Flute-Gateway | Real-time communication |

## Submodule Configuration

The external submodules are defined in Archon's `.gitmodules`:

```gitmodules
[submodule "external/PMOVES-Agent-Zero"]
    path = external/PMOVES-Agent-Zero
    url = https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git
    branch = PMOVES.AI-Edition-Hardened

[submodule "external/PMOVES-BoTZ"]
    path = external/PMOVES-BoTZ
    url = https://github.com/POWERFULMOVES/PMOVES-BoTZ.git
    branch = PMOVES.AI-Edition-Hardened

[submodule "external/PMOVES-Deep-Serch"]
    path = external/PMOVES-Deep-Serch
    url = https://github.com/POWERFULMOVES/PMOVES-Deep-Serch.git
    branch = PMOVES.AI-Edition-Hardened

[submodule "external/PMOVES-HiRAG"]
    path = external/PMOVES-HiRAG
    url = https://github.com/POWERFULMOVES/PMOVES-HiRAG.git
    branch = PMOVES.AI-Edition-Hardened
```

## Initialization

When setting up Archon for the first time:

```bash
# Clone Archon with submodules
git clone --recurse-submodules https://github.com/POWERFULMOVES/PMOVES-Archon.git
cd PMOVES-Archon

# Update all submodules
git submodule update --remote --merge

# Initialize external submodules
git submodule foreach --external 'git checkout PMOVES.AI-Edition-Hardened'
```

## Standalone Operation

With these external submodules, **Archon can operate independently**:

✅ **Without PMOVES.AI parent repo running**
✅ **Accessing all PMOVES services via MCP/HTTP**
✅ **Using its own Supabase instance for data storage**
✅ **Coordinating with agents via NATS message bus**

This enables:
- Development and testing without full stack
- Distributed deployment scenarios
- Modular service composition
- Independent scaling per component

## Related Documentation

- [PMOVES.AI Integration](../PMOVES.AI_INTEGRATION.md)
- [BoTZ Integration](../PMOVES-BoTZ/BOTZ_GATEWAY_AGENT_INTEGRATION.md)
- [Agent Zero MCP](../PMOVES-Agent-Zero/MCP_API.md)
- [Hi-RAG v2](../PMOVES-HiRAG/README.md)

## Version History

| Commit | Date | Description |
|--------|------|-------------|
| `5919bb1` | 2026-02-07 | "feat: Sync main to hardened - MCP adapter, CODEOWNERS, nested submodules, persona service" - Added external/ submodules for PMOVES.AI integration |
| `d8eb467` | 2026-02-09 | "feat(credentials): Add universal credential bootstrap scripts" - Added credential management |
| `9963665` | 2026-02-08 | "feat(pmoves-ai): Add PMOVES.AI integration patterns" - Documentation updates |

---

**Document Version**: 1.0
**Last Updated**: 2026-02-11
**Maintainer**: PMOVES.AI Team
