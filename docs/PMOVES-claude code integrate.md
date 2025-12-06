# Advanced Claude Orchestration: IndyDevDan's Methods for PMOVES Integration

**IndyDevDan's Tactical Agentic Coding (TAC) framework offers twelve leverage points** that can dramatically enhance PMOVES.AI's orchestration capabilities when integrated with ARCHON's new project management system and Agent Zero's hierarchical agent architecture. The convergence of these three systems—TAC's Claude patterns, ARCHON's MCP-based knowledge backbone, and Agent Zero's autonomous execution—creates a powerful foundation for "Out of the Loop" engineering where agents build and manage themselves.

The video at `youtube.com/watch?v=3kgx0YxCriM` appears to be part of IndyDevDan's TAC course promotional content covering his core Claude methodologies. While direct transcript access was limited, extensive documentation from his GitHub repositories (totaling **6,500+ stars** across related projects), course materials, and gists reveals a comprehensive system for maximizing Claude's agentic capabilities.

---

## The Core Four framework defines modern agentic engineering

IndyDevDan's foundational model for Claude-based development centers on four interdependent components: **Context** (the information environment), **Model** (the LLM being used), **Prompt** (the instruction), and **Tools** (external capabilities like MCP servers). This framework directly maps to PMOVES's existing architecture where Agent Zero provides the model orchestration, Archon manages context/knowledge, and the Flute layer handles multimodal prompt transformation.

The **12 Leverage Points of Agentic Coding** from TAC Lesson 2 divide into two categories. In-agent leverage points include stdout for observable output, types for safety, tests for validation, architecture for structure, documentation for context, and context window management for efficiency. Through-agent leverage points encompass templates, AI Developer Workflows (ADWs), custom commands, hooks, sub-agents, and MCP servers—all of which PMOVES can implement.

| Leverage Point | PMOVES Integration Target | Priority |
|----------------|---------------------------|----------|
| Templates | `.claude/` directory in agent-zero service | High |
| ADWs | n8n workflows + Agent Zero event system | High |
| Custom Commands | Agent Zero's `/commands` implementation | Medium |
| Hooks | Pre/post tool validation in Flute layer | High |
| Sub-agents | Agent Zero hierarchical subordinates | Already exists |
| MCP Servers | ARCHON MCP + Supaserch + Hi-RAG gateway | Critical |

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

## Concrete integration architecture for PMOVES.AI

Based on the research, here's the recommended integration pattern:

### Phase 1: Claude hooks in Flute layer

Modify `services/flute-gateway/` to implement IndyDevDan's hook patterns:

```python
# flute-gateway/hooks/claude_hooks.py
from typing import Callable, Any
import nats

class ClaudeHookManager:
    def __init__(self, nats_client):
        self.nc = nats_client
        self.pre_hooks: list[Callable] = []
        self.post_hooks: list[Callable] = []
    
    def register_pre_hook(self, hook: Callable):
        """IndyDevDan pre-tool pattern for validation"""
        self.pre_hooks.append(hook)
    
    async def execute_with_hooks(self, tool: str, params: dict) -> Any:
        # Pre-validation (block dangerous ops)
        for hook in self.pre_hooks:
            if not await hook(tool, params):
                raise SecurityException(f"Blocked: {tool}")
        
        result = await self.execute_tool(tool, params)
        
        # Post-logging for observability (stream to UI)
        await self.nc.publish(
            "agent.tool.executed.v1",
            json.dumps({"tool": tool, "result": summarize(result)})
        )
        return result
```

### Phase 2: ARCHON MCP integration with Agent Zero

Configure Agent Zero to use ARCHON as knowledge/task MCP:

```json
// agent-zero/config/mcp_servers.json
{
  "archon": {
    "type": "http",
    "url": "http://archon-mcp:8051",
    "tools": [
      "query_knowledge_base",
      "get_project_tasks",
      "update_task_status",
      "search_documents"
    ]
  },
  "supaserch": {
    "type": "http", 
    "url": "http://supaserch:8080",
    "tools": ["semantic_search", "hybrid_search"]
  },
  "hirag": {
    "type": "http",
    "url": "http://hi-rag-gateway:8000",
    "tools": ["retrieve_context", "rerank_results"]
  }
}
```

### Phase 3: Custom commands via `.claude/` directory

Implement IndyDevDan's command structure in the PMOVES monorepo:

```
pmoves/
├── .claude/
│   ├── CLAUDE.md                    # Always-on instructions
│   ├── commands/
│   │   ├── pm/
│   │   │   ├── create-task.md       # /pm:create-task
│   │   │   └── sprint-plan.md       # /pm:sprint-plan
│   │   ├── deploy/
│   │   │   ├── staging.md           # /deploy:staging
│   │   │   └── production.md        # /deploy:production
│   │   └── test/
│   │       └── integration.md       # /test:integration
│   ├── agents/
│   │   ├── code-reviewer.yaml       # Specialized reviewer agent
│   │   ├── docs-writer.yaml         # Documentation agent
│   │   └── security-auditor.yaml    # Security scanning agent
│   └── context/
│       ├── architecture.md          # PMOVES system overview
│       └── patterns.md              # Coding conventions
```

### Phase 4: AI Developer Workflows (ADWs) via n8n

Transform IndyDevDan's ADW concept into n8n workflows:

```yaml
# n8n-workflows/adw-feature-pipeline.yaml
name: "Feature Development ADW"
trigger: 
  event: "feature.requested.v1"
  source: "nats://pmoves-nats:4222"

steps:
  - name: "Plan"
    agent: "agent-zero"
    prompt_template: ".claude/commands/pm/create-task.md"
    
  - name: "Implement"  
    agent: "claude-worktree"
    config:
      worktree_branch: "feature/{{feature_id}}"
      hooks: ["pre_tool_validate", "post_tool_log"]
      
  - name: "Review"
    agent: "code-reviewer"
    config:
      prompt: ".claude/agents/code-reviewer.yaml"
      
  - name: "Test"
    command: "moon run test --affected"
    
  - name: "Document"
    agent: "docs-writer"
    config:
      prompt: ".claude/agents/docs-writer.yaml"
      
  - name: "Merge"
    condition: "review.approved AND tests.passed"
    action: "git merge {{worktree_branch}}"
```

---

## Docker Compose modifications for unified orchestration

```yaml
# docker-compose.claude-orchestration.yml
services:
  archon-server:
    image: coleam00/archon-server:latest
    ports:
      - "8181:8181"
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
    depends_on:
      - supabase
      - nats

  archon-mcp:
    image: coleam00/archon-mcp:latest
    ports:
      - "8051:8051"
    environment:
      - ARCHON_SERVER_URL=http://archon-server:8181
    
  archon-work-orders:
    image: coleam00/archon-work-orders:latest
    ports:
      - "8053:8053"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock  # For worktree containers
      - ./pmoves:/workspace
    environment:
      - CLAUDE_API_KEY=${ANTHROPIC_API_KEY}
      - NATS_URL=nats://nats:4222

  agent-zero:
    image: agent0ai/agent-zero:latest
    ports:
      - "50001:80"
    volumes:
      - ./agent-zero-memory:/a0/memory
      - ./.claude:/a0/.claude  # Mount IndyDevDan patterns
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - MCP_SERVERS_CONFIG=/a0/config/mcp_servers.json

  flute-gateway:
    build: ./services/flute-gateway
    ports:
      - "8060:8060"
    environment:
      - NATS_URL=nats://nats:4222
      - ENABLE_CLAUDE_HOOKS=true
      - HOOK_CONFIG=/app/hooks/config.yaml
```

---

## Critical implementation recommendations

**Immediate priorities** for integrating IndyDevDan's methods:

1. **Create `.claude/` directory structure** in the PMOVES monorepo root with CLAUDE.md containing system context, architecture overview, and coding conventions

2. **Implement Claude hooks in Flute** for pre-tool validation (security) and post-tool logging (observability to unified UI)

3. **Configure Agent Zero MCP clients** to connect to ARCHON (knowledge), Supaserch (search), and Hi-RAG (retrieval)

4. **Enable ARCHON Agent Work Orders** service and wire it to NATS for progress streaming

5. **Create specialized subordinate agent configs** following IndyDevDan's narrow-focus pattern—one for code review, one for documentation, one for security scanning

**The meta-principle from IndyDevDan applies directly to PMOVES**: "Don't build your codebase—build your agent pipeline that builds your codebase." With Agent Zero as orchestrator, ARCHON as knowledge backbone, and IndyDevDan's hooks/ADW patterns for Claude, PMOVES can achieve genuine "Out of the Loop" operation where the system autonomously builds, tests, and deploys features while humans focus on high-level direction.

---

## Conclusion

The synthesis of IndyDevDan's Tactical Agentic Coding patterns with ARCHON's project management backbone and Agent Zero's hierarchical execution creates a **complete orchestration stack** for PMOVES.AI. Key innovations include git worktrees for parallel Claude execution, hooks for safety and observability, ADWs for automated workflows, and MCP-based tool integration.

The implementation path is clear: start with `.claude/` directory structure and hooks, then wire ARCHON MCP to Agent Zero, then build ADW workflows in n8n. This transforms PMOVES from a collection of services into a self-improving system where Claude agents autonomously enhance the codebase under human supervision—exactly the vision IndyDevDan articulates as "Zero Touch Engineering."