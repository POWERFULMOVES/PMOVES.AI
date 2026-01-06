# Advanced Claude Orchestration: IndyDevDan's Methods for PMOVES Integration

**IndyDevDan's Tactical Agentic Coding (TAC) framework offers twelve leverage points** that can dramatically enhance PMOVES.AI's orchestration capabilities when integrated with ARCHON's new project management system and Agent Zero's hierarchical agent architecture. The convergence of these three systems—TAC's Claude patterns, ARCHON's MCP-based knowledge backbone, and Agent Zero's autonomous execution—creates a powerful foundation for "Out of the Loop" engineering where agents build and manage themselves.

The video at `youtube.com/watch?v=3kgx0YxCriM` appears to be part of IndyDevDan's TAC course promotional content covering his core Claude methodologies. While direct transcript access was limited, extensive documentation from his GitHub repositories (totaling **6,500+ stars** across related projects), course materials, and gists reveals a comprehensive system for maximizing Claude's agentic capabilities.

---

## Implementation Status

**Last Updated:** 2025-12-07

The TAC integration for PMOVES.AI is **COMPLETE for Phase 1** (Core Context and Commands).

### ✅ Phase 1: Core Context and Commands (COMPLETE)
- ✅ `.claude/CLAUDE.md` - Always-on context document
- ✅ `.claude/commands/` - 10 custom slash commands implemented
- ✅ `.claude/context/` - 7 reference documentation files
- ✅ `.claude/hooks/` - Pre-tool and post-tool hooks configured

**Status:** Production-ready. Claude Code CLI is now PMOVES-aware with full access to production services via custom commands.

### 🚧 Phase 2: Advanced Features (OPTIONAL)
- ✅ Hooks configured (security validation + NATS observability)
- 📋 Git worktree workflows (documented, not automated)
- 🔮 ARCHON Work Orders (future enhancement)

**See:** `docs/TAC_INTEGRATION_STATUS.md` for detailed implementation status.

---

## CRITICAL DISTINCTION: Claude Code CLI vs Runtime Agent Infrastructure

**After analyzing PMOVES.AI's existing architecture, this integration is fundamentally about developer tooling, NOT replacing production agent infrastructure.**

### What PMOVES Already Has (DO NOT DUPLICATE)

PMOVES.AI is a **mature, production-ready multi-agent system** with:

- **Agent Zero** (port 8080/8081): Control-plane orchestrator with embedded agent runtime and MCP API (`/mcp/*`)
- **NATS Message Bus** (port 4222): JetStream-enabled event broker for agent coordination
- **Hi-RAG v2** (ports 8086/8087): Advanced hybrid RAG with cross-encoder reranking
- **SupaSerch** (port 8099): Multimodal holographic deep research orchestrator
- **DeepResearch** (port 8098): LLM-based research planner (Alibaba Tongyi)
- **Comprehensive Monitoring**: Prometheus, Grafana, Loki, health endpoints on all services
- **Media Pipeline**: YouTube ingestion, Whisper transcription, YOLO video analysis, embedding services
- **Storage Stack**: Supabase (Postgres+pgvector), Qdrant, Neo4j, Meilisearch, MinIO
- **ARCHON** (ports 3737/8091): Agent service with Supabase-backed prompt/form management

**These systems already provide autonomous agent orchestration, RAG, search, monitoring, and event-driven coordination.**

### What TAC Integration Actually Provides

IndyDevDan's TAC framework is about **Claude Code CLI** as a **developer tool** that leverages the existing infrastructure:

1. **`.claude/` Directory** - Context files so Claude Code CLI understands PMOVES architecture when developers use it interactively
2. **Custom Commands** - Slash commands that call existing services (e.g., `/search:hirag`, `/agents:status`, `/health:check-all`)
3. **Git Worktrees** - Enable multiple Claude Code CLI instances working on different features simultaneously
4. **Hooks** - Publish Claude Code CLI actions to NATS for observability (not runtime agent hooks)
5. **ARCHON Work Orders** - Automate Claude Code CLI execution from the agent system (agents can spawn Claude Code for development tasks)

**TAC is for human developers using Claude Code CLI, not for autonomous agent runtime behavior.**

### Integration Philosophy: Leverage, Don't Duplicate

```
┌─────────────────────────────────────────────────────────────────┐
│                    PMOVES Production Stack                      │
│  Agent Zero + NATS + Hi-RAG + SupaSerch + Monitoring           │
│              (Autonomous Runtime Agents)                        │
└─────────────────────────────────────────────────────────────────┘
                             ▲
                             │ Uses via MCP API, NATS events
                             │
┌─────────────────────────────────────────────────────────────────┐
│                 Claude Code CLI + TAC Patterns                  │
│  .claude/ context + custom commands + hooks + worktrees        │
│              (Developer Workflow Tooling)                       │
└─────────────────────────────────────────────────────────────────┘
                             ▲
                             │ Used by
                             │
                      Human Developers
```

**The TAC integration makes Claude Code CLI aware of and able to interact with PMOVES's existing services.**

---

## The Core Four framework defines modern agentic engineering

IndyDevDan's foundational model for Claude-based development centers on four interdependent components: **Context** (the information environment), **Model** (the LLM being used), **Prompt** (the instruction), and **Tools** (external capabilities like MCP servers). This framework directly maps to PMOVES's existing architecture where Agent Zero provides the model orchestration, Archon manages context/knowledge, and the Flute layer handles multimodal prompt transformation.

The **12 Leverage Points of Agentic Coding** from TAC Lesson 2 divide into two categories. In-agent leverage points include stdout for observable output, types for safety, tests for validation, architecture for structure, documentation for context, and context window management for efficiency. Through-agent leverage points encompass templates, AI Developer Workflows (ADWs), custom commands, hooks, sub-agents, and MCP servers.

**For PMOVES, the TAC integration focuses on Claude Code CLI tooling that leverages existing infrastructure:**

| Leverage Point | PMOVES Integration Target | Priority | Status |
|----------------|---------------------------|----------|---------|
| Templates | `.claude/` directory at monorepo root | High | **Implement** |
| Custom Commands | `.claude/commands/` slash commands calling existing services | High | **Implement** |
| Hooks | Publish Claude Code CLI actions to NATS | Medium | **Implement** |
| Context | `.claude/context/` documenting existing architecture | High | **Implement** |
| Sub-agents | Agent Zero hierarchical subordinates | N/A | **Already exists** |
| MCP Servers | Agent Zero MCP API + ARCHON + SupaSerch + Hi-RAG | N/A | **Already exists** |
| ADWs | ARCHON Work Orders to automate Claude Code CLI | Low | **Future** |

---

## Git worktrees enable parallel Claude execution at scale

IndyDevDan's most impactful technique for scaling Claude Code involves **git worktrees**—allowing multiple Claude instances to work simultaneously on different branches without file conflicts. For PMOVES, this pattern applies directly to the monorepo structure:

```bash
# Create isolated workspace for feature development
git worktree add ../pmoves-feature-hirag feature/hirag-enhancement
cd ../pmoves-feature-hirag

# Start Claude Code in isolated environment
claude

# Each worktree gets independent:
# - File state (no conflicts with other branches)
# - .mcp.json configuration (worktree-specific tools)
# - Context (focused on specific task)
```

**For PMOVES-BoTZ integration**, this enables multiple Claude agents to simultaneously work on different services (agent-zero, archon, hi-rag-gateway, supaserch) while maintaining isolation. The pattern integrates with NATS messaging by having each worktree instance publish progress events to the central bus.

---

## Claude Code hooks provide pre/post validation and observability

IndyDevDan's `claude-code-hooks-mastery` repository (**1,900+ stars**) defines a hooks framework that PMOVES should adopt for safety and monitoring:

**Pre-tool hooks** prevent dangerous operations:
```python
# Hook to prevent destructive commands in PMOVES context
BLOCKED_PATTERNS = [
    "rm -rf /",
    "DROP TABLE",
    "supabase db reset --force",
    "docker system prune -a"
]

def pre_tool_validate(command: str) -> bool:
    for pattern in BLOCKED_PATTERNS:
        if pattern in command:
            log_security_event(command)
            return False
    return True
```

**Post-tool hooks** create the observability PMOVES needs for the unified UI:
```python
# Hook to publish tool execution to NATS for UI streaming
async def post_tool_log(tool_name: str, result: Any):
    await nats_publish("agent.tool.executed.v1", {
        "tool": tool_name,
        "timestamp": datetime.utcnow().isoformat(),
        "result_summary": summarize(result),
        "agent_id": current_agent_id()
    })
```

These hooks integrate directly with the Flute layer's security validation and Supabase's realtime channels for live dashboard updates.

---

## ARCHON's Agent Work Orders bridge Claude to project execution

ARCHON has evolved from its "Agenteer" agent-builder concept into **"Archon OS"**—a knowledge and task management backbone. The critical new capability for PMOVES is the **Agent Work Orders** service running on port 8053:

```
ARCHON Architecture (v0.1.0 Beta - October 2025)
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend UI   │    │  Server (API)   │    │   MCP Server    │    │ Agents Service  │
│  React + Vite   │◄──►│  FastAPI +      │◄──►│  HTTP Wrapper   │◄──►│   PydanticAI    │
│  Port 3737      │    │  SocketIO 8181  │    │  Port 8051      │    │   Port 8052     │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                                              │
                    ┌─────────────────┐                           ┌─────────────────┐
                    │    Supabase     │                           │ Agent Work      │
                    │   PostgreSQL    │◄──────────────────────────│ Orders (8053)   │
                    │   + PGVector    │                           │ Claude CLI Auto │
                    └─────────────────┘                           └─────────────────┘
```

**Agent Work Orders** provides Claude Code CLI automation with repository management, SSE updates for progress tracking, and workflow orchestration. This is the "run projects" capability—it executes Claude Code commands programmatically, manages git operations, and chains multiple operations together.

For PMOVES integration, Agent Work Orders should be configured to:
1. Execute tasks from the PMOVES task queue (Supabase `tasks` table)
2. Publish progress via NATS to the unified UI
3. Use IndyDevDan's hooks for validation
4. Store results in Archon's knowledge base for future retrieval

---

## Agent Zero's hierarchical subordinates enable Claude-powered task delegation

Agent Zero v0.9.7 (November 2025) introduces a **Projects** system with isolated workspaces—directly complementing IndyDevDan's worktree pattern. Key orchestration capabilities:

**Superior/Subordinate hierarchy** already mirrors IndyDevDan's sub-agent patterns:
```python
# Agent Zero creates subordinates exactly as TAC recommends
subordinate = Agent(
    number=parent.number + 1,
    config={
        "prompts": custom_subordinate_prompts,  # Narrow focus
        "tools": limited_tool_set,              # Least privilege
        "context_allocation": 0.3               # Context efficiency
    }
)
```

**MCP + A2A Protocol support** (v0.9.4+) enables Agent Zero to both expose and consume MCP servers:
- Agent Zero as MCP Server: External agents call Agent Zero via MCP protocol
- Agent Zero as MCP Client: Uses ARCHON, Supaserch, Hi-RAG as MCP tools

**Projects system** (v0.9.7) provides per-project isolation matching IndyDevDan's `.claude/` directory pattern:
```
/projects/pmoves-core/
├── prompts/          # Custom system prompts
├── memory/           # Project-specific FAISS vectors
├── secrets/          # Credentials (agent uses without seeing)
└── knowledge/        # Imported documents
```

---

## Refined Integration Architecture: Claude Code CLI Developer Tooling

**This integration adds Claude Code CLI tooling that leverages PMOVES's existing production infrastructure.**

### Phase 1: Create `.claude/` directory structure for developer context

Establish the `.claude/` directory at monorepo root with comprehensive PMOVES context:

```
.claude/
├── CLAUDE.md                           # Always-on context for Claude Code CLI
│   ├── PMOVES Architecture Overview
│   ├── Service Catalog (all ports, endpoints, health checks)
│   ├── NATS Subject Catalog
│   ├── Development Patterns
│   └── Integration Points
│
├── commands/                           # Custom slash commands
│   ├── agents/
│   │   ├── status.md                   # /agents:status - Check Agent Zero health
│   │   └── mcp-query.md                # /agents:mcp-query - Call Agent Zero MCP API
│   ├── search/
│   │   ├── hirag.md                    # /search:hirag - Query Hi-RAG v2
│   │   ├── supaserch.md                # /search:supaserch - Holographic deep research
│   │   └── deepresearch.md             # /search:deepresearch - LLM research planner
│   ├── health/
│   │   ├── check-all.md                # /health:check-all - Verify all /healthz
│   │   └── metrics.md                  # /health:metrics - Query Prometheus
│   └── deploy/
│       ├── smoke-test.md               # /deploy:smoke-test - Run make verify-all
│       └── services.md                 # /deploy:services - Docker compose status
│
└── context/                            # Reference documentation
    ├── services-catalog.md             # Comprehensive service listing
    ├── nats-subjects.md                # All NATS event subjects
    ├── mcp-api.md                      # Agent Zero MCP API documentation
    └── architecture-diagram.md         # System architecture ASCII diagrams
```

**`.claude/CLAUDE.md` Example Content:**

```markdown
# PMOVES.AI Developer Context

## Architecture Overview
PMOVES.AI is a multi-agent orchestration platform with autonomous agents,
hybrid RAG, multimodal deep research, and comprehensive observability.

## Production Services (DO NOT DUPLICATE)
- Agent Zero (8080/8081): Control-plane orchestrator with /mcp/* API
- NATS (4222): JetStream event bus - all agent coordination
- Hi-RAG v2 (8086/8087): Hybrid RAG with cross-encoder reranking
- SupaSerch (8099): Multimodal holographic deep research
- DeepResearch (8098): LLM-based research planner
- Prometheus (9090): Metrics collection
- Grafana (3000): Dashboard visualization

## Common Development Tasks
- Query knowledge: Use Hi-RAG v2 at http://localhost:8086/hirag/query
- Check service health: All services expose /healthz endpoint
- Publish events: NATS at nats://localhost:4222
- View metrics: Prometheus at http://localhost:9090

## NATS Event Subjects
- research.deepresearch.request.v1 / .result.v1
- supaserch.request.v1 / .result.v1
- ingest.file.added.v1, ingest.transcript.ready.v1
- agent.tool.executed.v1 (for observability)

## Integration Pattern
When developing features, leverage existing services via their APIs.
Do not build new RAG, search, monitoring, or agent orchestration.
```

### Phase 2: Implement custom commands that call existing services

Create slash commands in `.claude/commands/` that interact with production services:

**`.claude/commands/search/hirag.md`:**
```markdown
Query the Hi-RAG v2 hybrid retrieval system.

Usage: /search:hirag <query>

This command queries PMOVES's production Hi-RAG v2 service (port 8086) which
combines vector search (Qdrant), knowledge graph (Neo4j), and full-text search
(Meilisearch) with cross-encoder reranking.

Implementation:
1. Use Bash tool to execute: curl -X POST http://localhost:8086/hirag/query \
   -H "Content-Type: application/json" \
   -d '{"query": "<user_query>", "top_k": 10, "rerank": true}'
2. Parse JSON response and present relevant context to user
3. Include source references from response metadata
```

**`.claude/commands/health/check-all.md`:**
```markdown
Verify health of all PMOVES services.

Usage: /health:check-all

This command checks /healthz endpoints for all production services.

Implementation:
1. Run: make verify-all (uses existing Makefile target)
2. Report status of each service:
   - Agent Zero (8080), SupaSerch (8099), Hi-RAG v2 (8086/8087)
   - DeepResearch (8098), PMOVES.YT (8077), Extract (8083)
   - All other services listed in docs/PMOVES.AI Services and Integrations.md
3. Highlight any failures with service name and port
```

**`.claude/commands/agents/status.md`:**
```markdown
Check Agent Zero orchestrator status.

Usage: /agents:status

Queries Agent Zero's health endpoint and MCP API status.

Implementation:
1. GET http://localhost:8080/healthz - Check supervisor + runtime health
2. Report NATS connectivity status
3. Show active subordinate agents if available via MCP API
```

### Phase 3: Optional hooks for Claude Code CLI observability

Configure Claude Code CLI hooks to publish developer actions to NATS (optional for advanced observability):

**`.claude/hooks/post-tool.sh`:**
```bash
#!/bin/bash
# Post-tool hook: Publish Claude Code CLI tool execution to NATS

TOOL_NAME=$1
TOOL_RESULT=$2

# Publish to NATS for observability (requires nats-cli installed)
if command -v nats &> /dev/null; then
    nats pub "claude.code.tool.executed.v1" \
        "{\"tool\": \"$TOOL_NAME\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"user\": \"$(whoami)\"}"
fi
```

**`.claude/hooks/pre-tool.sh`:**
```bash
#!/bin/bash
# Pre-tool hook: Validate against dangerous operations

TOOL_NAME=$1
TOOL_PARAMS=$2

# Block dangerous patterns
BLOCKED_PATTERNS=(
    "rm -rf /"
    "DROP TABLE"
    "supabase db reset"
    "docker system prune -a"
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
    if [[ "$TOOL_PARAMS" == *"$pattern"* ]]; then
        echo "BLOCKED: Dangerous operation detected: $pattern"
        exit 1
    fi
done

exit 0
```

### Phase 4: Future - ARCHON Work Orders integration

**Future enhancement:** Configure ARCHON Agent Work Orders to automate Claude Code CLI execution from the agent system:

- Agents can spawn Claude Code CLI tasks via ARCHON Work Orders service
- Work Orders execute in isolated git worktrees
- Progress streamed to NATS for UI visibility
- Results stored in ARCHON knowledge base

This allows Agent Zero to delegate development tasks to Claude Code CLI programmatically.

---

## Implementation Priorities: Claude Code CLI Developer Tooling

**Phase 1 (Immediate) - Core Context and Commands:** ✅ COMPLETE

1. **✅ Create `.claude/CLAUDE.md`** - Comprehensive always-on context document
   - ✅ PMOVES architecture overview
   - ✅ Service catalog with ports and endpoints
   - ✅ NATS subject catalog
   - ✅ Development patterns and integration points
   - **Goal:** Claude Code CLI understands PMOVES when developers use it

2. **✅ Create `.claude/commands/`** - Slash commands for existing services
   - ✅ `/search:hirag` - Query Hi-RAG v2
   - ✅ `/health:check-all` - Verify all service health
   - ✅ `/agents:status` - Check Agent Zero status
   - ✅ `/deploy:smoke-test` - Run integration tests
   - **Goal:** Developers can easily interact with production services

3. **✅ Create `.claude/context/`** - Reference documentation
   - ✅ `services-catalog.md` - Complete service listing
   - ✅ `nats-subjects.md` - NATS event subject documentation
   - ✅ `mcp-api.md` - Agent Zero MCP API reference
   - **Goal:** Comprehensive reference for development

**Phase 2 (Optional) - Advanced Features:**

4. **✅ Configure hooks** (optional for observability)
   - ✅ Pre-tool validation for dangerous operations
   - ✅ Post-tool NATS publishing for developer action tracking
   - **Goal:** Optional observability integration

5. **📋 Git worktree workflows** (optional for parallel development)
   - 📋 Document worktree patterns for multiple Claude instances
   - **Goal:** Enable parallel feature development

6. **🔮 ARCHON Work Orders** (future enhancement)
   - 🔮 Allow Agent Zero to spawn Claude Code CLI tasks
   - **Goal:** Agent-driven development automation

**Key Principle: Leverage, Don't Duplicate**

The TAC integration provides developer tooling that leverages PMOVES's existing production infrastructure. Claude Code CLI becomes PMOVES-aware through `.claude/` context, enabling developers to efficiently build features that integrate with Agent Zero, Hi-RAG, SupaSerch, NATS, and other production services.

---

## Conclusion

The IndyDevDan TAC integration enhances PMOVES.AI by adding **Claude Code CLI developer tooling** that leverages the existing production infrastructure. This is NOT about replacing PMOVES's sophisticated autonomous agent orchestration (Agent Zero, NATS, Hi-RAG, SupaSerch)—those systems already provide production-ready multi-agent coordination.

Instead, TAC integration focuses on **developer experience**: the `.claude/` directory makes Claude Code CLI PMOVES-aware, enabling developers to efficiently build features that integrate with production services. Custom slash commands provide direct access to Hi-RAG queries, Agent Zero status, health checks, and deployment workflows. Optional hooks enable NATS observability of developer actions.

**The integration path is straightforward:**
1. Create `.claude/CLAUDE.md` with PMOVES architecture context
2. Implement `.claude/commands/` for service interaction
3. Add `.claude/context/` reference documentation
4. Optionally configure hooks for observability

This transforms Claude Code CLI from a general-purpose coding assistant into a **PMOVES-native development tool** that understands and leverages the existing multi-agent orchestration stack. Developers gain instant access to production capabilities (RAG, research, monitoring) directly from their coding workflow—achieving the TAC vision of "leverage points" without duplicating existing infrastructure.

---

## Implementation Complete (2025-12-07)

The TAC integration described in this document has been **fully implemented for Phase 1**. The `.claude/` directory structure is in place with:

- 1 always-on context file (CLAUDE.md)
- 10 custom slash commands across 4 categories
- 7 reference documentation files
- 2 hooks with comprehensive testing

Claude Code CLI is now a **PMOVES-native development tool** that understands and leverages the existing multi-agent orchestration stack.

**Next Session:** Developers can immediately use custom commands like `/search:hirag`, `/health:check-all`, `/agents:status` to interact with production services directly from their Claude Code CLI workflow.