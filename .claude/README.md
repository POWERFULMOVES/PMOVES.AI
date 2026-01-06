# PMOVES.AI Claude Code CLI Configuration

This directory contains configuration and context for **Claude Code CLI** to make it PMOVES-aware.

## Purpose

PMOVES.AI has a sophisticated multi-agent infrastructure (Agent Zero, NATS, Hi-RAG v2, SupaSerch, etc.). This `.claude/` directory enables Claude Code CLI to understand and leverage that infrastructure when developers use it for coding tasks.

## Directory Structure

```
.claude/
├── CLAUDE.md                     # Always-on context (12KB) - loaded automatically
├── README.md                     # This file
├── settings.local.json           # 131 allowed bash command patterns
├── test-self-hosting.sh          # NATS + Hi-RAG integration test
│
├── commands/                     # 50 custom slash commands
│   ├── agents/ (2)               # Agent Zero orchestration
│   │   ├── status.md             # /agents:status - service health
│   │   └── mcp-query.md          # /agents:mcp-query - MCP API calls
│   ├── botz/ (4)                 # Bot configuration & CHIT
│   │   ├── init.md               # /botz:init - initialize bot
│   │   ├── profile.md            # /botz:profile - CHIT profiles
│   │   ├── secrets.md            # /botz:secrets - secret management
│   │   └── mcp.md                # /botz:mcp - MCP integration
│   ├── crush/ (2)                # Compression utilities
│   ├── db/ (3)                   # Database operations (backup, migrate, query)
│   ├── deploy/ (3)               # Service deployment (up, services, smoke)
│   ├── github/ (4)               # GitHub integration (actions, issues, PR, security)
│   ├── health/ (2)               # Health monitoring (check-all, metrics)
│   ├── k8s/ (3)                  # Kubernetes operations (deploy, logs, status)
│   ├── search/ (3)               # Knowledge retrieval
│   │   ├── hirag.md              # /search:hirag - Hi-RAG v2 queries
│   │   ├── supaserch.md          # /search:supaserch - holographic research
│   │   └── deepresearch.md       # /search:deepresearch - LLM planner
│   ├── workitems/ (3)            # BoTZ work tracking (claim, complete, list)
│   ├── worktree/ (4)             # Git worktree / TAC patterns
│   │   ├── create.md             # /worktree:create - new worktree
│   │   ├── switch.md             # /worktree:switch - change context
│   │   ├── list.md               # /worktree:list - show all
│   │   └── cleanup.md            # /worktree:cleanup - remove stale
│   ├── test/ (1)                 # Testing workflow
│   │   └── pr.md                 # /test:pr - PR testing workflow
│   └── yt/ (10)                  # YouTube pipeline
│       ├── ingest-video.md       # /yt:ingest-video - download + transcript
│       ├── status.md             # /yt:status - pipeline health
│       ├── list-channels.md      # /yt:list-channels - monitored channels
│       ├── add-channel.md        # /yt:add-channel - add channel to monitor
│       ├── remove-channel.md     # /yt:remove-channel - remove channel
│       ├── toggle-channel.md     # /yt:toggle-channel - enable/disable
│       ├── add-playlist.md       # /yt:add-playlist - add playlist
│       ├── check-now.md          # /yt:check-now - force check
│       ├── pending.md            # /yt:pending - show pending items
│       └── help.md               # /yt:help - command reference
│
├── context/                      # Reference documentation (8 files)
│   ├── services-catalog.md       # Complete service listing with ports
│   ├── tensorzero.md             # TensorZero LLM gateway deep dive
│   ├── testing-strategy.md       # Testing workflow & PR requirements
│   ├── evoswarm.md               # Evolutionary optimization system
│   ├── chit-geometry-bus.md      # Structured multimodal data format
│   ├── nats-subjects.md          # NATS event subject catalog
│   ├── mcp-api.md                # Agent Zero MCP API reference
│   └── git-worktrees.md          # TAC (Tactical Agentic Coding) workflows
│
└── hooks/                        # Security & observability (4 files)
    ├── pre-tool.sh               # Security validation gate
    │                             # Blocks: rm -rf /, DROP DATABASE, etc.
    ├── post-tool.sh              # NATS observability publisher
    │                             # Publishes: claude.code.tool.executed.v1
    ├── README.md                 # Hook configuration guide
    └── TEST_RESULTS.md           # Validation test results
```

### Slash Command Categories Summary

| Category | Commands | Primary Use |
| --- | --- | --- |
| `/agents:*` | 2 | Agent Zero health and MCP queries |
| `/botz:*` | 4 | CHIT profile management, secrets |
| `/search:*` | 3 | Hi-RAG, SupaSerch, DeepResearch |
| `/test:*` | 1 | PR testing workflow |
| `/yt:*` | 10 | YouTube ingestion pipeline |
| `/tts:*` | 3 | Text-to-speech synthesis |
| `/pipecat:*` | 2 | Voice communication sessions |
| `/deploy:*` | 3 | Service deployment and smoke tests |
| `/worktree:*` | 4 | TAC parallel development |
| `/health:*` | 2 | Platform-wide health checks |
| `/k8s:*` | 3 | Kubernetes operations |
| `/db:*` | 3 | Database backup, migrate, query |
| `/github:*` | 4 | Actions, issues, PRs, security |
| `/crush:*` | 2 | Compression utilities |
| `/workitems:*` | 3 | BoTZ work item tracking |

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

# Text-to-Speech synthesis
/tts:status              # Check TTS service health
/tts:voices              # List available voices
/tts:synthesize          # Generate speech from text

# Real-time voice sessions
/pipecat:status          # Check Pipecat health
/pipecat:connect         # Create voice session
```

### 3. Reference Context Documentation

Detailed references in `.claude/context/`:
- **services-catalog.md** - Every service, port, API, dependency
- **nats-subjects.md** - All NATS event subjects with examples
- **mcp-api.md** - Agent Zero MCP API documentation
- **flute-gateway.md** - Voice/TTS API and Pipecat integration
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

## Hooks (Active)

The `.claude/hooks/` directory contains security and observability hooks:

### Pre-Tool Hook (`pre-tool.sh`)
Validates commands before execution. **Blocks dangerous operations:**
- `rm -rf /` - Disk wipes
- `DROP DATABASE` - Database destruction
- `docker system prune -a` - Container mass deletion
- Force push to protected branches

### Post-Tool Hook (`post-tool.sh`)
Publishes tool executions to NATS for observability:
```bash
# Events published to:
claude.code.tool.executed.v1

# Payload includes:
# - tool: Tool name
# - status: success/failure
# - timestamp: ISO 8601
# - user: Current user
# - session_id: Claude session
```

Fallback logging to `~/.claude/logs/tool-events.jsonl` when NATS unavailable.

See: `.claude/hooks/README.md` for configuration details

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
