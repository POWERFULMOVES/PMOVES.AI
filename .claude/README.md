# PMOVES.AI Claude Code CLI Configuration

This directory contains configuration and context for **Claude Code CLI** to make it PMOVES-aware.

## Purpose

PMOVES.AI has a sophisticated multi-agent infrastructure (Agent Zero, NATS, Hi-RAG v2, SupaSerch, etc.). This `.claude/` directory enables Claude Code CLI to understand and leverage that infrastructure when developers use it for coding tasks.

## Directory Structure

```
.claude/
├── CLAUDE.md                      # Always-on context - READ THIS FIRST
├── README.md                      # This file
├── commands/                      # Custom slash commands
│   ├── agents/
│   │   ├── status.md              # /agents:status - Check Agent Zero
│   │   └── mcp-query.md           # /agents:mcp-query - Call MCP API
│   ├── search/
│   │   ├── hirag.md               # /search:hirag - Query Hi-RAG v2
│   │   ├── supaserch.md           # /search:supaserch - Deep research
│   │   └── deepresearch.md        # /search:deepresearch - LLM research
│   ├── health/
│   │   ├── check-all.md           # /health:check-all - Verify all services
│   │   └── metrics.md             # /health:metrics - Prometheus queries
│   └── deploy/
│       ├── smoke-test.md          # /deploy:smoke-test - Run integration tests
│       └── services.md            # /deploy:services - Docker status
└── context/                       # Reference documentation
    ├── services-catalog.md        # Complete service listing
    ├── nats-subjects.md           # NATS event catalog
    ├── mcp-api.md                 # Agent Zero MCP reference
    ├── chit-geometry-bus.md       # CHIT structured data format
    └── evoswarm.md                # Evolutionary optimization system
```

## Quick Start

### 1. Read CLAUDE.md

**`.claude/CLAUDE.md`** is the always-on context that Claude Code CLI reads automatically. It contains:
- PMOVES architecture overview
- Service catalog (all ports and endpoints)
- NATS subject catalog
- Common development tasks
- Integration patterns

**This is the most important file** - it makes Claude understand PMOVES when you start coding.

### 2. Use Custom Commands

Slash commands provide quick access to production services:

```bash
# Check if all services are healthy
/health:check-all

# Query the knowledge base
/search:hirag "How does Agent Zero work?"

# Check Agent Zero status
/agents:status

# Run smoke tests
/deploy:smoke-test
```

### 3. Reference Context Documentation

Detailed references in `.claude/context/`:
- **services-catalog.md** - Every service, port, API, dependency
- **nats-subjects.md** - All NATS event subjects with examples
- **mcp-api.md** - Agent Zero MCP API documentation
- **chit-geometry-bus.md** - Structured data format for multimodal workflows
- **evoswarm.md** - Evolutionary optimization for CHIT parameters

## Integration Philosophy

**PMOVES.AI already has production infrastructure.** The `.claude/` directory makes Claude Code CLI:
- **Aware** of existing services (don't duplicate Hi-RAG, SupaSerch, etc.)
- **Able** to interact with services via APIs
- **Informed** about NATS events, MCP integration, CHIT format
- **Aligned** with development patterns and best practices

## Development Patterns

### Leverage, Don't Duplicate

✅ **DO:**
- Use Hi-RAG v2 for knowledge retrieval (`/search:hirag`)
- Publish to NATS for event coordination
- Call Agent Zero MCP API for orchestration
- Store artifacts in MinIO
- Use existing embeddings and indexing (Qdrant, Meilisearch, Neo4j)

❌ **DON'T:**
- Build new RAG systems
- Create new message buses
- Duplicate monitoring/observability
- Rebuild agent orchestration

### Service Discovery

All services expose:
- **`/healthz`** - Health check endpoint
- **`/metrics`** - Prometheus metrics (most services)

Check health before using: `curl http://localhost:<port>/healthz`

### Event-Driven Communication

Use NATS for async coordination:
```bash
# Publish event
nats pub "subject.name.v1" '{"key": "value"}'

# Subscribe to events
nats sub "subject.name.v1"
```

See `.claude/context/nats-subjects.md` for all subjects.

## Custom Command Development

To add new commands, create a markdown file in `.claude/commands/<category>/<name>.md`:

```markdown
Brief description of what this command does.

## Usage

When to use this command...

## Implementation

1. Step-by-step implementation
2. Include curl examples or code snippets
3. Explain expected results

## Notes

Additional context, gotchas, tips
```

Commands are automatically discovered by Claude Code CLI.

## Hooks (Optional)

Hooks can be configured to:
- **Pre-tool validation** - Block dangerous operations
- **Post-tool logging** - Publish Claude actions to NATS for observability

See integration plan: `docs/PMOVES-claude code integrate.md`

## Git Worktrees (Advanced)

For parallel development with multiple Claude instances:

```bash
# Create worktree for feature
git worktree add ../pmoves-feature-name feature/name

# Each worktree gets independent .claude/ context
cd ../pmoves-feature-name
claude
```

## Resources

- **Integration Plan:** `docs/PMOVES-claude code integrate.md`
- **Services Documentation:** `docs/PMOVES.AI Services and Integrations.md`
- **PMOVES Architecture:** See CLAUDE.md and context/ files

## Contributing

When adding new services or capabilities:
1. Update **CLAUDE.md** with service overview
2. Add detailed docs to **context/** if complex
3. Create slash commands in **commands/** for common operations
4. Document NATS subjects in **context/nats-subjects.md**

Keep this directory synchronized with production capabilities so Claude Code CLI stays PMOVES-aware!
