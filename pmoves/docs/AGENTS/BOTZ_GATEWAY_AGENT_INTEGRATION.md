# BoTZ Gateway & Gateway Agent Integration Analysis

**Document Version:** 1.0.0
**Analysis Date:** 2026-02-08
**Author:** PMOVES.AI Architecture Review

---

## Executive Summary

This analysis examines the relationship between two distinct but complementary services:

1. **BoTZ Gateway (port 8054)** - Work item distribution service for PMOVES-BoTZ CLI instances
2. **Gateway Agent (port 8100)** - MCP tool orchestration service for 100+ tools

**Finding:** These are **complementary, not duplicate** services. They serve different layers of the agentic stack and should be integrated rather than consolidated.

---

## 1. Service Comparison Matrix

| Aspect | BoTZ Gateway (8054) | Gateway Agent (8100) |
|--------|---------------------|----------------------|
| **Primary Purpose** | Work item distribution across BoTZ CLI instances | MCP tool discovery and execution |
| **Port** | 8054 | 8100 |
| **Main API** | FastAPI (workitems, botz instances) | FastAPI (tools, skills, secrets) |
| **Data Source** | Supabase `integration_work_items` table | Agent Zero MCP API |
| **NATS Subjects** | `botz.heartbeat.v1`, `botz.register.v1`, `botz.workitem.*` | None (HTTP-based only) |
| **Skill Level Awareness** | Yes (basic, tac_enabled, mcp_augmented, agentic) | No (tool-agnostic) |
| **Thread-Based Engineering** | No (work item focused) | No (tool execution focused) |
| **Storage Backend** | Supabase (PostgREST) | Cipher Memory |
| **Credential Management** | None | SecretManager (GitHub Secrets) |
| **Orchestration Model** | Pull-based (CLI claims work) | Push-based (execute on demand) |

---

## 2. Integration Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PMOVES.AI AGENTIC LAYER                            │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────────┐
                              │   User Intent    │
                              │   (Human / AI)   │
                              └────────┬─────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │                                     │
            ┌───────▼────────┐                   ┌────────▼─────────┐
            │  BoTZ Gateway  │                   │  Gateway Agent   │
            │     (8054)     │                   │     (8100)       │
            │  Work Dist.    │                   │  Tool Orch.      │
            └───────┬────────┘                   └────────┬─────────┘
                    │                                     │
        ┌───────────┼───────────┐             ┌──────────┼──────────┐
        │           │           │             │          │          │
    ┌───▼───┐  ┌───▼───┐  ┌───▼───┐     ┌────▼────┐ ┌──▼───┐ ┌──▼────┐
    │ Supa- │  │ NATS  │  │Tensor-│     │Agent    │ │Cipher│ │100+   │
    │ base  │  │       │  │ Zero │     │ Zero    │ │      │ │MCP    │
    └───────┘  │ 4222  │  │ 3030 │     │  8080   │ │ 3025 │ │Tools  │
               └───────┘  └──────┘     └─────────┘ └──────┘ └───────┘
                    │
    ┌───────────────┼───────────────┐
    │               │               │
┌───▼────┐    ┌────▼─────┐    ┌───▼───────┐
│BoTZ CLI│    │BoTZ CLI  │    │BoTZ CLI    │
│Instance│    │Instance  │    │Instance    │
│Level 1 │    │Level 2   │    │Level 3     │
└────────┘    └──────────┘    └────────────┘
    │               │               │
    └───────────────┴───────────────┘
                    │
            ┌───────▼────────┐
            │  mprocs        │
            │  Orchestration │
            │  (port 4050)   │
            └────────────────┘
```

---

## 3. Overlap Analysis

### 3.1 Redundant Capabilities

| Capability | BoTZ Gateway | Gateway Agent | Recommendation |
|------------|--------------|---------------|----------------|
| **Tool Discovery** | No (relies on CLI registration) | Yes (Agent Zero MCP) | **Gateway Agent owns** |
| **Credential Management** | No | Yes (SecretManager) | **Gateway Agent owns** |
| **Health Monitoring** | Basic (heartbeat) | Advanced (service checks) | **Merge to Gateway Agent** |
| **Skill Level Tracking** | Yes (4 levels) | No (tool categories) | **Keep separate** |

### 3.2 Complementary Capabilities

| Function | BoTZ Gateway | Gateway Agent | Integration Point |
|----------|--------------|---------------|-------------------|
| **Work Distribution** | Claims work items | Executes tools | BoTZ Gateway calls Gateway Agent |
| **MCP Tool Access** | Indirect (via CLI) | Direct (via Agent Zero) | Gateway Agent provides tools to BoTZ CLI |
| **Memory/Persistence** | Supabase | Cipher Memory | Dual storage pattern |
| **Event Coordination** | NATS pub/sub | HTTP polling | Gateway Agent subscribes to NATS |

---

## 4. NATS Subject Coordination

### 4.1 Current NATS Subjects

**BoTZ Gateway Subjects:**
```
botz.heartbeat.v1          # CLI instance presence
botz.register.v1           # New instance registration
botz.registered.v1         # Registration confirmation
botz.workitem.claimed.v1   # Work item claimed
botz.workitem.completed.v1 # Work item finished
```

**BoTZ Framework Internal Subjects (from PMOVES-BoTZ):**
```
botz.agent.heartbeat.v1    # Agent presence (every 30s)
botz.agent.started.v1      # Agent initialization
botz.work.available.v1     # Work broadcast
botz.work.claimed.v1       # Work claimed
botz.work.completed.v1     # Task completion with result
botz.work.progress.v1      # Progress updates
botz.mcp.tool.executed.v1  # MCP tool execution
botz.cipher.memory.stored.v1   # Memory storage event
botz.cipher.memory.recalled.v1 # Memory retrieval event
botz.gateway.task.dispatched.v1 # Gateway task dispatch
botz.agent.thread.*.v1     # Thread lifecycle events
```

### 4.2 Subject Gap Analysis

| Missing Subject | Purpose | Owner Recommendation |
|-----------------|---------|---------------------|
| `botz.gateway.agent.discovered.v1` | Tool discovery events | Gateway Agent |
| `botz.gateway.tool.executed.v1` | Tool execution metrics | Gateway Agent |
| `botz.gateway.skill.stored.v1` | Skill storage events | Gateway Agent |

---

## 5. Work Item Distribution Flow

### 5.1 Current Flow (BoTZ Gateway)

```
1. Integration creates work item in Supabase
   ↓
2. BoTZ Gateway polls Supabase for ready items
   ↓
3. BoTZ CLI instances register with skill levels
   ↓
4. BoTZ Gateway matches work item to appropriate skill level
   ↓
5. BoTZ CLI claims work item via API
   ↓
6. BoTZ CLI executes (potentially using MCP tools)
   ↓
7. BoTZ CLI marks work item complete
```

### 5.2 Proposed Integrated Flow

```
1. Integration creates work item in Supabase
   ↓
2. BoTZ Gateway publishes to NATS: botz.work.available.v1
   ↓
3. Gateway Agent receives work available event
   ↓
4. Gateway Agent evaluates required tools via Agent Zero MCP
   ↓
5. Gateway Agent assigns to appropriate BoTZ CLI based on:
   - Skill level (from BoTZ Gateway registry)
   - Available MCP tools (from Agent Zero)
   - Resource availability
   ↓
6. BoTZ CLI executes with MCP tool routing via Gateway Agent
   ↓
7. Gateway Agent publishes tool execution metrics to NATS
   ↓
8. BoTZ CLI marks work item complete
```

---

## 6. Integration Recommendations

### 6.1 High Priority

1. **Gateway Agent NATS Integration**
   - Add NATS subscription to Gateway Agent
   - Publish tool execution events to `botz.gateway.tool.executed.v1`
   - Subscribe to `botz.work.available.v1` for proactive work routing

2. **Unified Skill Level Mapping**
   - Map Gateway Agent tool categories to BoTZ skill levels:
     ```
     basic          → [memory, documents]
     tac_enabled    → [automation, execution]
     mcp_augmented  → [infrastructure, api, research]
     agentic        → [vision, fusion operations]
     ```

3. **Credential Sharing**
   - Gateway Agent SecretManager should expose credentials to BoTZ CLI instances
   - Implement secure credential proxy endpoint

### 6.2 Medium Priority

1. **Health Check Consolidation**
   - Gateway Agent becomes health aggregator for all agent services
   - BoTZ Gateway reports to Gateway Agent health endpoint

2. **Metrics Unification**
   - Both services expose Prometheus metrics
   - Gateway Agent aggregates BoTZ Gateway metrics

3. **mprocs Integration**
   - Gateway Agent can spawn BoTZ CLI instances via mprocs API (port 4050)
   - Enables dynamic scaling of worker instances

### 6.3 Low Priority

1. **Storage Convergence**
   - Evaluate merging Supabase and Cipher Memory storage patterns
   - Consider Supabase as primary, Cipher as local cache

2. **API Standardization**
   - Adopt A2A (Agent2Agent) protocol for inter-service communication
   - Implement /.well-known/agent.json endpoints

---

## 7. Production Deployment Pattern

### 7.1 Docker Compose Configuration

```yaml
services:
  # ==================================================
  # BoTZ Gateway - Work Item Distribution
  # ==================================================
  botz-gateway:
    build: ./services/botz-gateway
    image: pmoves/botz-gateway:latest
    container_name: pmoves-botz-gateway
    ports:
      - "8054:8054"
    environment:
      - NATS_URL=nats://nats:4222
      - SUPABASE_URL=http://supabase-kong:8000
      - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
      - TENSORZERO_URL=http://tensorzero-gateway:3030
      - BOTZ_HEARTBEAT_INTERVAL=30
      - BOTZ_STALE_THRESHOLD=5
    networks:
      - api_tier
    depends_on:
      - nats
      - supabase-kong
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8054/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
    profiles: ["botz", "agents"]

  # ==================================================
  # Gateway Agent - MCP Tool Orchestration
  # ==================================================
  gateway-agent:
    build: ./services/gateway-agent
    image: pmoves/gateway-agent:latest
    container_name: pmoves-gateway-agent
    ports:
      - "8100:8100"
    environment:
      - AGENT_ZERO_URL=http://agent-zero:8080
      - CIPHER_URL=http://pmoves-botz-cipher:8000
      - TENSORZERO_URL=http://tensorzero-gateway:3030
      - SUPABASE_URL=http://supabase-kong:8000
      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
      - NATS_URL=nats://nats:4222
      - GATEWAY_API_KEY=${GATEWAY_API_KEY}
      - TOOL_CACHE_TTL=300
    networks:
      - api_tier
    depends_on:
      - agent-zero
      - nats
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8100/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
    profiles: ["gateway", "agents"]

  # ==================================================
  # Agent Zero - MCP API Provider
  # ==================================================
  agent-zero:
    image: pmoves/agent-zero:latest
    container_name: pmoves-agent-zero
    ports:
      - "8080:8080"
    environment:
      - MCP_ENABLED=true
    networks:
      - api_tier
    profiles: ["agents"]

  # ==================================================
  # Cipher Memory - Local Knowledge Store
  # ==================================================
  pmoves-botz-cipher:
    image: pmoves/cipher-memory:latest
    container_name: pmoves-botz-cipher
    ports:
      - "8000:8000"
    environment:
      - VENICE_API_KEY=${VENICE_API_KEY}
    volumes:
      - cipher_data:/app/data
    networks:
      - api_tier
    profiles: ["botz", "agents"]

  # ==================================================
  # NATS - Event Bus
  # ==================================================
  nats:
    image: nats:latest
    container_name: pmoves-nats
    ports:
      - "4222:4222"
      - "8222:8222"
    command: "-js"
    networks:
      - api_tier
    profiles: ["infrastructure"]

networks:
  api_tier:
    name: pmoves_api
    external: true

volumes:
  cipher_data:
    driver: local
```

### 7.2 Startup Order

```bash
# 1. Start infrastructure
docker compose --profile infrastructure up -d nats

# 2. Start core services
docker compose --profile agents up -d agent-zero supabase-kong

# 3. Start BoTZ components
docker compose --profile botz up -d botz-gateway pmoves-botz-cipher

# 4. Start Gateway
docker compose --profile gateway up -d gateway-agent
```

---

## 8. Key Questions Answered

### Q1: Are BoTZ Gateway and Gateway Agent duplicate services?

**No.** They serve complementary roles:
- **BoTZ Gateway** manages work items and CLI instance registration (pull model)
- **Gateway Agent** manages tool discovery and execution (push model)

### Q2: How do work items flow between BoTZ skill levels and Gateway Agent tools?

**Current:** Work items are claimed by BoTZ CLI instances based on skill level matching.
**Proposed:** Gateway Agent should subscribe to work availability and provide intelligent routing based on both skill level AND available MCP tools.

### Q3: What is the integration path for Gateway Agent to BoTZ framework?

```
Gateway Agent (8100)
    ├── Discovers tools from Agent Zero MCP (8080)
    ├── Subscribes to NATS subjects (botz.*)
    ├── Provides credential proxy for BoTZ CLI instances
    └── Routes tool execution requests with skill-level awareness
```

### Q4: Which NATS subjects coordinate these services?

**Primary Subjects:**
- `botz.work.available.v1` - Work published, Gateway Agent evaluates
- `botz.work.claimed.v1` - Work claimed by CLI instance
- `botz.work.completed.v1` - Work finished, metrics logged
- `botz.gateway.tool.executed.v1` - **NEW** - Tool execution metrics

---

## 9. Conclusion

The BoTZ Gateway and Gateway Agent are **complementary services** that should be integrated through:

1. **NATS event coordination** - Gateway Agent subscribes to BoTZ work events
2. **Skill level mapping** - Tool categories map to BoTZ skill levels
3. **Credential sharing** - Gateway Agent provides secure credential proxy
4. **Health aggregation** - Gateway Agent becomes health monitor hub

**Do NOT consolidate these services.** Their separation of concerns (work distribution vs. tool orchestration) is architecturally sound and enables independent scaling.

---

## Appendix A: Service Port Reference

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| BoTZ Gateway | 8054 | HTTP | Work item API |
| Gateway Agent | 8100 | HTTP | MCP tool API |
| Agent Zero | 8080 | HTTP | MCP API provider |
| Agent Zero UI | 8081 | HTTP | Web interface |
| NATS | 4222 | TCP | Message bus |
| NATS Monitoring | 8222 | HTTP | NATS dashboard |
| Cipher Memory | 8000 | HTTP | Memory API |
| TensorZero | 3030 | HTTP | LLM gateway |

---

## Appendix B: File Reference

| Component | File Path |
|-----------|-----------|
| BoTZ Gateway | `/home/pmoves/PMOVES.AI/pmoves/services/botz-gateway/main.py` |
| Gateway Agent | `/home/pmoves/PMOVES.AI/pmoves/services/gateway-agent/app.py` |
| BoTZ Orchestrator | `/home/pmoves/PMOVES.AI/PMOVES-BoTZ/skills/botz-orchestrator/SKILL.md` |
| mprocs Config | `/home/pmoves/PMOVES.AI/PMOVES-BoTZ/.mprocs.yaml` |
| Gateway Architecture | `/home/pmoves/PMOVES.AI/docs/services/gateway-agent/ARCHITECTURE.md` |
