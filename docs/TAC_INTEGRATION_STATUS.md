# TAC Integration Status for PMOVES.AI

**Tactical Agentic Coding (TAC) Framework Integration**

Last Updated: 2025-12-07

## Overview

This document tracks the integration status of IndyDevDan's Tactical Agentic Coding (TAC) framework into PMOVES.AI's development workflow. The TAC integration provides Claude Code CLI with comprehensive context and tooling to leverage PMOVES's existing production infrastructure.

### What is TAC Integration?

TAC integration is **developer tooling** that makes Claude Code CLI PMOVES-aware. It enables developers to:
- Understand PMOVES architecture automatically through context files
- Execute common operations via custom slash commands
- Leverage existing services (Agent Zero, Hi-RAG, SupaSerch, NATS) without duplication
- Validate operations for safety via hooks
- Publish developer actions to NATS for observability

### Reference Specification

See: `/home/pmoves/PMOVES.AI/docs/PMOVES-claude code integrate.md`

**Key Principle:** Leverage, Don't Duplicate. PMOVES.AI already has sophisticated multi-agent infrastructure. TAC makes Claude Code CLI aware of and able to interact with these existing services.

---

## Implementation Status

### Phase 1: Core Context and Commands - ✅ COMPLETE

#### 1. Always-On Context - ✅ IMPLEMENTED

**File:** `.claude/CLAUDE.md` (2,500+ lines)

Contains comprehensive PMOVES context loaded automatically by Claude Code CLI:
- Architecture overview (multi-agent orchestration platform)
- Complete service catalog (30+ services with ports, endpoints, APIs)
- NATS event subjects catalog
- Common development tasks with code examples
- Integration patterns and best practices
- Git/CI patterns and submodule structure

**Status:** Fully implemented and maintained. This is the primary context file that makes Claude Code CLI PMOVES-aware.

#### 2. Custom Slash Commands - ✅ IMPLEMENTED (7 commands)

**Directory:** `.claude/commands/`

All commands provide quick access to production services:

| Command | Purpose | Status |
|---------|---------|--------|
| `/agents:status` | Check Agent Zero orchestrator health & NATS connectivity | ✅ Implemented |
| `/health:check-all` | Verify health of all PMOVES services via /healthz endpoints | ✅ Implemented |
| `/search:hirag` | Query Hi-RAG v2 hybrid retrieval (Qdrant + Neo4j + Meilisearch) | ✅ Implemented |
| `/search:supaserch` | Execute multimodal holographic deep research | ✅ Implemented |
| `/deploy:smoke-test` | Run comprehensive integration smoke tests | ✅ Implemented |
| `/deploy:up` | Start PMOVES services using docker compose | ✅ Implemented |
| `/deploy:services` | Check Docker Compose service deployment status | ✅ Implemented |

**Status:** Core commands fully implemented. Commands cover agent orchestration, health monitoring, knowledge retrieval, and deployment workflows.

**Note:** The spec mentioned `/agents:mcp-query`, `/search:deepresearch`, and `/health:metrics` which are not yet implemented but covered by existing commands and `.claude/CLAUDE.md` context.

#### 3. Reference Documentation - ✅ IMPLEMENTED (7 context files)

**Directory:** `.claude/context/`

Comprehensive reference documentation for detailed information:

| File | Size | Purpose | Status |
|------|------|---------|--------|
| `services-catalog.md` | 11 KB | Complete listing of all PMOVES services with detailed specifications | ✅ Implemented |
| `nats-subjects.md` | 8.8 KB | Comprehensive NATS event subjects catalog with examples | ✅ Implemented |
| `mcp-api.md` | 9.7 KB | Agent Zero MCP API reference and integration guide | ✅ Implemented |
| `tensorzero.md` | 12 KB | TensorZero LLM gateway documentation, metrics, and usage | ✅ Implemented |
| `chit-geometry-bus.md` | 8.1 KB | CHIT structured data format for multimodal workflows | ✅ Implemented |
| `evoswarm.md` | 12 KB | Evolutionary optimization system for CHIT parameters | ✅ Implemented |
| `git-worktrees.md` | 11 KB | Advanced git worktree workflows for parallel development | ✅ Implemented |

**Status:** Comprehensive documentation suite fully implemented. Total context documentation: ~73 KB across 7 specialized reference files.

#### 4. Supporting Files - ✅ IMPLEMENTED

| File | Purpose | Status |
|------|---------|--------|
| `.claude/README.md` | Developer guide to TAC integration, quick start, patterns | ✅ Implemented |
| `.claude/settings.local.json` | Claude Code CLI permissions and allowed operations | ✅ Implemented |
| `.claude/test-self-hosting.sh` | Self-hosting validation script | ✅ Implemented |

---

### Phase 2: Advanced Features - ✅ HOOKS COMPLETE, 📋 WORKTREES DOCUMENTED

#### 5. Hooks Configuration - ✅ IMPLEMENTED

**Directory:** `.claude/hooks/`

Hooks provide security validation and NATS observability integration:

**Pre-Tool Hook (`pre-tool.sh`)** - ✅ Fully Implemented
- Security gate that validates operations before execution
- Blocks dangerous patterns: `rm -rf /`, `DROP DATABASE`, `docker system prune -a`, etc.
- Total blocked patterns: 11 critical operations
- Warns (doesn't block): writes to `/etc/`, overly permissive chmod, sensitive files
- Logs security events to: `$HOME/.claude/logs/security-events.log`
- **Exit code:** Non-zero blocks Claude from executing

**Post-Tool Hook (`post-tool.sh`)** - ✅ Fully Implemented
- Publishes tool execution events to NATS: `claude.code.tool.executed.v1`
- Event payload includes: tool name, status, timestamp, user, session ID, hostname
- Graceful fallback: logs locally to `$HOME/.claude/logs/tool-events.jsonl` if NATS unavailable
- **Exit code:** Always 0 (never blocks Claude)

**Hook Documentation (`hooks/README.md`)** - ✅ Comprehensive (259 lines)
- Installation instructions (3 methods: settings, environment variables, manual)
- Blocked patterns reference
- NATS configuration guide
- Monitoring and troubleshooting
- Customization examples
- Integration with PMOVES monitoring stack

**Status:** Hooks are fully implemented and production-ready. To enable:
1. Configure Claude Code CLI settings with hook paths, OR
2. Set environment variables, OR
3. Hooks work automatically if Claude Code CLI discovers them

**NATS Subject for Hook Events:**
```
claude.code.tool.executed.v1
```

**Subscribe to events:**
```bash
nats sub "claude.code.tool.executed.v1"
```

#### 6. Git Worktree Workflows - 📋 DOCUMENTED

**File:** `.claude/context/git-worktrees.md` (11 KB)

Comprehensive documentation for parallel development with multiple Claude instances:
- Worktree creation and management patterns
- Isolation benefits (file state, MCP config, context)
- Integration with PMOVES monorepo structure
- Examples for simultaneous service development
- Best practices and cleanup procedures

**Status:** Fully documented. Developers can use worktrees for parallel Claude instances working on different features (e.g., agent-zero, archon, hi-rag-gateway simultaneously).

**Usage:**
```bash
# Create worktree for feature
git worktree add ../pmoves-feature-hirag feature/hirag-enhancement
cd ../pmoves-feature-hirag
claude  # Start isolated Claude instance
```

#### 7. ARCHON Work Orders - 🔮 FUTURE ENHANCEMENT

**Status:** Documented in spec, not yet implemented.

ARCHON Work Orders (port 8053) would enable:
- Agents spawning Claude Code CLI tasks programmatically
- Automated execution in isolated git worktrees
- Progress streaming to NATS for UI visibility
- Results stored in ARCHON knowledge base

**Priority:** Low - This is a future automation capability allowing Agent Zero to delegate development tasks to Claude Code CLI.

---

## Command Catalog

### Agent Orchestration Commands

#### `/agents:status`
**Purpose:** Check Agent Zero orchestrator status and health

**What it does:**
- Queries Agent Zero health endpoint (port 8080)
- Checks NATS message bus connectivity
- Verifies embedded agent runtime status
- Validates MCP API availability

**Implementation:**
```bash
curl http://localhost:8080/healthz
curl http://localhost:8080/mcp/
```

**When to use:** Before delegating tasks to Agent Zero, debugging agent coordination issues

---

### Health & Monitoring Commands

#### `/health:check-all`
**Purpose:** Verify health status of all PMOVES production services

**What it does:**
- Executes comprehensive health checks via `make verify-all`
- Checks `/healthz` endpoints for all 30+ services
- Reports healthy/failing services
- Suggests remediation for failures

**Services checked:**
- Agent Coordination: Agent Zero, Archon, Channel Monitor
- Retrieval: Hi-RAG v2 CPU/GPU, SupaSerch, DeepResearch
- Media: PMOVES.YT, FFmpeg-Whisper, Video/Audio Analyzers, Extract Worker
- Utilities: Presign, Render Webhook, Jellyfin Bridge, Publisher-Discord

**When to use:** Start of development session, debugging issues, before deployments, after bringing up services

---

### Knowledge & Search Commands

#### `/search:hirag`
**Purpose:** Query the Hi-RAG v2 hybrid retrieval system for knowledge and context

**What it does:**
- Queries Hi-RAG v2 at port 8086/8087
- Combines Qdrant (vector), Neo4j (graph), Meilisearch (full-text)
- Applies cross-encoder reranking for relevance
- Returns relevant context with source metadata

**Implementation:**
```bash
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "<user_query>", "top_k": 10, "rerank": true}'
```

**When to use:** Simple knowledge retrieval, semantic search, context gathering

**Note:** Hi-RAG v2 is preferred over v1 (ports 8089/8090) for new queries.

---

#### `/search:supaserch`
**Purpose:** Execute multimodal holographic deep research using SupaSerch

**What it does:**
- Orchestrates complex multi-source research
- Coordinates DeepResearch (LLM planning) + Agent Zero MCP tools + Hi-RAG
- Publishes to NATS: `supaserch.request.v1` / `supaserch.result.v1`
- Stores results in Open Notebook for future reference

**Implementation:**
```bash
# Via NATS (async, recommended)
nats pub "supaserch.request.v1" '{
  "query": "<research_question>",
  "request_id": "<unique_id>",
  "requester": "claude-code-cli"
}'

# Subscribe to results
nats sub "supaserch.result.v1" --max 1
```

**When to use:** Complex multi-faceted research, questions requiring multiple data sources, research needing multi-step planning

**Comparison:** Use `/search:hirag` for simple queries, `/search:supaserch` for complex research.

---

### Deployment & Operations Commands

#### `/deploy:smoke-test`
**Purpose:** Run integration smoke tests to verify PMOVES deployment

**What it does:**
- Executes comprehensive smoke test suite via `make verify-all`
- Validates all services are operational
- Tests integration points (NATS pub/sub, Hi-RAG queries, Agent Zero MCP)
- Reports overall deployment status

**When to use:** Before production deployments, after bringing up services, validating new environments, CI/CD verification

---

#### `/deploy:up`
**Purpose:** Start PMOVES services using docker compose

**What it does:**
- Brings up PMOVES stack with appropriate profiles
- Starts core data services (Supabase, Qdrant, Neo4j, Meilisearch, MinIO, NATS)
- Launches workers (extract, langextract, media analyzers)
- Starts Hi-RAG gateways (v2 CPU and GPU)
- Deploys orchestration services (SupaSerch, DeepResearch, Agent Zero)

**Implementation:**
```bash
cd pmoves && make up              # Core services
cd pmoves && make up-gpu          # With GPU acceleration
cd pmoves && make bringup-with-ui # Full stack + monitoring + UI
```

**Docker Compose Profiles:**
- `data` - Core data services
- `workers` - Processing services
- `gateway` - API gateways
- `agents` - Agent Zero, Archon, Mesh Agent
- `orchestration` - SupaSerch, DeepResearch
- `monitoring` - Prometheus, Grafana, Loki
- `gpu` - GPU-accelerated services

**When to use:** Starting development environment, testing deployments, bringing up full stack

---

#### `/deploy:services`
**Purpose:** Check Docker Compose service deployment status

**What it does:**
- Shows running/stopped/failed services
- Displays container health and status
- Lists port mappings
- Shows resource usage

**Implementation:**
```bash
cd pmoves && docker compose ps       # All services
docker compose ps --filter status=running  # Only running
docker stats --no-stream $(docker compose ps -q)  # Resource usage
```

**When to use:** Identifying stopped/failed services, checking deployment status, viewing port mappings

---

## Context Files Reference

### `services-catalog.md`
**Size:** 11 KB
**Purpose:** Complete listing of all PMOVES services

**Contents:**
- Service name, ports, purpose
- API endpoints and health checks
- Dependencies and connections
- Docker compose profiles
- Environment configuration

**Use cases:** Understanding service architecture, finding service ports, checking dependencies

---

### `nats-subjects.md`
**Size:** 8.8 KB
**Purpose:** Comprehensive NATS event subjects catalog

**Contents:**
- All NATS subjects with descriptions
- Event payload formats
- Publisher/subscriber patterns
- Examples for common operations

**Categories:**
- Research & Search: `research.deepresearch.*`, `supaserch.*`
- Media Ingestion: `ingest.file.added.v1`, `ingest.transcript.ready.v1`
- Agent Observability: `claude.code.tool.executed.v1`

**Use cases:** Publishing NATS events, subscribing to system events, understanding event-driven architecture

---

### `mcp-api.md`
**Size:** 9.7 KB
**Purpose:** Agent Zero MCP API reference and integration guide

**Contents:**
- MCP API endpoints (`/mcp/*` on port 8080)
- Authentication and authorization
- Agent coordination patterns
- Superior/subordinate hierarchy
- Integration examples

**Use cases:** External agent integration, calling Agent Zero from services, understanding MCP protocol

---

### `tensorzero.md`
**Size:** 12 KB
**Purpose:** TensorZero LLM gateway documentation

**Contents:**
- TensorZero architecture overview
- Model provider configuration (OpenAI, Anthropic, Venice, Ollama)
- API usage examples (chat completions, embeddings)
- ClickHouse metrics queries
- Observability and monitoring
- Dashboard access (port 4000)

**Use cases:** Calling LLMs via TensorZero, generating embeddings, querying usage metrics, model provider routing

---

### `chit-geometry-bus.md`
**Size:** 8.1 KB
**Purpose:** CHIT structured data format for multimodal workflows

**Contents:**
- CHIT format specification
- Geometry types (scalar, vector, matrix, tensor, graph, HNSW)
- Security features (encryption, signatures, passphrase protection)
- Integration with Agent Zero and SupaSerch
- Codebook system

**Use cases:** Understanding multimodal data format, working with CHIT payloads, implementing CHIT producers/consumers

---

### `evoswarm.md`
**Size:** 12 KB
**Purpose:** Evolutionary optimization system for CHIT parameters

**Contents:**
- EvoSwarm architecture (CMA-ES + particle swarm optimization)
- Fitness evaluation metrics
- Autonomous optimization workflows
- Integration with Agent Zero
- Performance optimization patterns

**Use cases:** Understanding optimization system, configuring evolution parameters, interpreting fitness metrics

---

### `git-worktrees.md`
**Size:** 11 KB
**Purpose:** Advanced git worktree workflows for parallel development

**Contents:**
- Worktree creation and management
- Isolation benefits (file state, MCP config, context)
- PMOVES monorepo integration
- Multi-instance Claude development
- Best practices and cleanup

**Use cases:** Running multiple Claude instances, parallel feature development, isolated workspaces

---

## Hooks Configuration Details

### Pre-Tool Hook: Security Validation

**File:** `.claude/hooks/pre-tool.sh`

**Blocked Patterns (11 total):**
```bash
rm -rf /                    # Recursive root deletion
DROP DATABASE               # Database destruction
DROP TABLE                  # Table deletion
TRUNCATE TABLE              # Data wiping
supabase db reset --force   # Forced database reset
docker system prune -a      # Remove all Docker resources
docker volume rm            # Volume deletion
> /dev/sda                  # Writing to raw disk
dd if=/dev/zero             # Disk wiping
mkfs.*                      # Filesystem formatting
format c:                   # Windows format (cross-platform safety)
```

**Warning Patterns (not blocked):**
- Writing to `/etc/` directory
- Overly permissive chmod (777, 666)
- Modifying files with `.ssh/`, `.env`, or credential keywords in path

**Security Event Logging:**
```
Location: $HOME/.claude/logs/security-events.log
Format: [2025-12-06T12:00:00Z] BLOCKED: Bash - Pattern: rm -rf / - User: pmoves
```

**Usage:**
```bash
# Test hook manually
./.claude/hooks/pre-tool.sh "Bash" "echo 'safe command'"  # Passes
./.claude/hooks/pre-tool.sh "Bash" "rm -rf /"             # Blocks
```

---

### Post-Tool Hook: NATS Observability

**File:** `.claude/hooks/post-tool.sh`

**NATS Subject:** `claude.code.tool.executed.v1`

**Event Payload Format:**
```json
{
  "tool": "Bash",
  "status": "success",
  "timestamp": "2025-12-06T12:00:00Z",
  "user": "pmoves",
  "session_id": "1733501234",
  "hostname": "pmoves-dev"
}
```

**Configuration:**
```bash
# Environment variables
export NATS_URL="nats://localhost:4222"  # Default
export CLAUDE_SESSION_ID="custom-session-id"  # Optional
```

**Fallback Behavior:**
- If `nats-cli` not installed or NATS unavailable, events log to: `$HOME/.claude/logs/tool-events.jsonl`
- Hook always exits 0 (never blocks Claude)

**Monitoring Events:**
```bash
# Subscribe to all tool events
nats sub "claude.code.tool.executed.v1"

# Filter specific tool
nats sub "claude.code.tool.executed.v1" | grep '"tool":"Bash"'

# View local logs (if NATS unavailable)
tail -f ~/.claude/logs/tool-events.jsonl | jq .
```

---

## Usage Examples

### Example 1: Starting Development Session

```bash
# Start Claude Code CLI
claude

# Check if services are running
/health:check-all

# If services down, bring them up
/deploy:up

# Query knowledge base for context
/search:hirag "How does Agent Zero coordinate tasks?"

# Check Agent Zero status
/agents:status
```

---

### Example 2: Deep Research Task

```bash
claude

# For complex research, use SupaSerch
/search:supaserch "Analyze the integration between Agent Zero, Hi-RAG, and SupaSerch"

# Monitor NATS for results (in separate terminal)
nats sub "supaserch.result.v1" --max 1
```

---

### Example 3: Pre-Deployment Validation

```bash
claude

# Verify service health
/health:check-all

# Run comprehensive smoke tests
/deploy:smoke-test

# Check service deployment status
/deploy:services

# If any issues, check logs
docker compose logs <service-name>
```

---

### Example 4: Hooks in Action

**Scenario: Dangerous operation blocked by pre-hook**

```bash
# Claude attempts: rm -rf /
# Pre-hook intercepts and blocks

❌ BLOCKED: Dangerous operation detected: rm -rf /
   Tool: Bash
   This operation has been blocked for safety.

# Event logged to: ~/.claude/logs/security-events.log
[2025-12-06T12:00:00Z] BLOCKED: Bash - Pattern: rm -rf / - User: pmoves
```

**Scenario: Safe operation logged by post-hook**

```bash
# Claude executes: curl http://localhost:8080/healthz
# Post-hook publishes to NATS

[Hook] Published tool event to claude.code.tool.executed.v1

# NATS subscribers receive:
{
  "tool": "Bash",
  "status": "success",
  "timestamp": "2025-12-06T12:00:00Z",
  "user": "pmoves",
  "session_id": "1733501234",
  "hostname": "pmoves-dev"
}
```

---

## Integration with PMOVES Monitoring

### Current Integration

**NATS Event Bus:**
- Post-tool hook publishes to: `claude.code.tool.executed.v1`
- Events available for any NATS subscriber
- Enables real-time tracking of Claude CLI activity

**Local Logging:**
- Security events: `$HOME/.claude/logs/security-events.log`
- Tool events (fallback): `$HOME/.claude/logs/tool-events.jsonl`

### Future Integration Possibilities

**Supabase Storage:**
- Store tool events for historical analysis
- Query developer activity patterns
- Audit trail for security compliance

**Grafana Dashboard:**
- Visualize Claude CLI activity over time
- Track most-used tools and commands
- Monitor blocked operations

**Discord Notifications:**
- Alert on blocked operations via Publisher-Discord
- Notify team of deployment commands
- Real-time development activity feed

**Prometheus Metrics:**
- `claude_code_tool_executions_total` - Tool execution counter
- `claude_code_pre_hook_blocks_total` - Blocked operations counter
- `claude_code_hook_latency_seconds` - Hook execution time

---

## Next Steps

### For Developers

#### Immediate Actions

1. **Read the context:** Start with `.claude/CLAUDE.md` to understand PMOVES architecture
2. **Try slash commands:** Use `/health:check-all`, `/search:hirag`, `/agents:status`
3. **Reference context files:** Browse `.claude/context/` for detailed documentation

#### Optional Setup

4. **Enable hooks (Optional):**
   - Configure Claude Code CLI settings with hook paths
   - Set environment variables: `CLAUDE_PRE_TOOL_HOOK`, `CLAUDE_POST_TOOL_HOOK`
   - Test hooks manually: `./.claude/hooks/pre-tool.sh "Bash" "echo test"`

5. **Configure NATS (Optional):**
   - Ensure NATS running: `nats server info`
   - Set NATS_URL if non-default
   - Subscribe to events: `nats sub "claude.code.tool.executed.v1"`

6. **Try git worktrees (Advanced):**
   - Create worktree: `git worktree add ../pmoves-feature feature/name`
   - Run parallel Claude instances on different features
   - See `.claude/context/git-worktrees.md` for details

### For System Administrators

#### Monitoring Setup

1. **NATS Observability:**
   - Monitor `claude.code.tool.executed.v1` subject
   - Set up retention policy for tool events
   - Configure NATS JetStream for persistent events

2. **Security Auditing:**
   - Review security events: `~/.claude/logs/security-events.log`
   - Set up log rotation for event logs
   - Consider forwarding to centralized logging (Loki)

3. **Dashboard Integration:**
   - Create Grafana dashboard for Claude CLI metrics
   - Set up alerts for unusual activity
   - Track developer productivity metrics

### Future Enhancements

#### Low Priority

1. **Additional Commands:**
   - `/agents:mcp-query` - Direct MCP API queries
   - `/search:deepresearch` - DeepResearch-specific queries
   - `/health:metrics` - Prometheus metric queries
   - `/debug:logs` - Tail service logs
   - `/nats:pub` - Publish NATS events
   - `/nats:sub` - Subscribe to NATS subjects

2. **Enhanced Hooks:**
   - Pre-hook: ML-based anomaly detection for unusual commands
   - Post-hook: Automatic context summaries published to knowledge base
   - Hooks: Integration with external security scanning tools

3. **ARCHON Work Orders Integration:**
   - Enable Agent Zero to spawn Claude Code CLI tasks
   - Automated execution in git worktrees
   - Progress streaming to UI dashboards
   - Results stored in ARCHON knowledge base

---

## Troubleshooting

### Commands Not Working

**Issue:** Custom slash commands not recognized

**Solutions:**
1. Verify `.claude/commands/` directory exists
2. Check command files are `.md` format
3. Restart Claude Code CLI to reload commands
4. Check Claude Code CLI version supports custom commands

---

### Hooks Not Executing

**Issue:** Hooks don't run or fail silently

**Solutions:**
1. Check file permissions: `ls -l .claude/hooks/*.sh` (must be executable)
2. Make executable: `chmod +x .claude/hooks/*.sh`
3. Verify Claude Code CLI configuration
4. Check hook output in stderr
5. Test hooks manually: `./.claude/hooks/pre-tool.sh "Bash" "test"`

---

### NATS Connection Failed

**Issue:** Post-hook can't connect to NATS

**Solutions:**
1. Check NATS is running: `nats server info`
2. Verify NATS_URL environment variable
3. Check NATS port (default: 4222): `netstat -tlnp | grep 4222`
4. Review fallback logs: `~/.claude/logs/tool-events.jsonl`
5. Install nats-cli: Hooks detect missing CLI and fall back gracefully

**Note:** Post-hook always exits 0 and falls back to local logging if NATS unavailable.

---

### Service Health Checks Failing

**Issue:** `/health:check-all` reports services down

**Solutions:**
1. Check Docker Compose status: `/deploy:services`
2. Bring up services: `/deploy:up`
3. View service logs: `docker compose logs <service-name>`
4. Check specific service: `curl http://localhost:<port>/healthz`
5. Verify ports not conflicting: `netstat -tlnp | grep <port>`

---

## Summary

### TAC Integration: Complete ✅

PMOVES.AI has successfully integrated IndyDevDan's Tactical Agentic Coding framework to provide **comprehensive Claude Code CLI developer tooling**.

**What's Implemented:**

✅ **Phase 1 (Complete):**
- Always-on context (`.claude/CLAUDE.md` - 2,500+ lines)
- 7 custom slash commands covering agents, health, search, deployment
- 7 comprehensive context files (73 KB total documentation)
- Supporting files (README, settings, test script)

✅ **Phase 2 (Hooks Complete, Worktrees Documented):**
- Security validation hook with 11 blocked patterns
- NATS observability hook with graceful fallback
- Comprehensive hooks documentation (259 lines)
- Git worktrees fully documented (11 KB guide)

🔮 **Future Enhancement:**
- ARCHON Work Orders integration (agent-driven Claude CLI automation)

**Key Capabilities:**

1. **Context-Aware Development:** Claude Code CLI understands PMOVES architecture through always-on context
2. **Service Integration:** Direct access to Hi-RAG, Agent Zero, SupaSerch, NATS via slash commands
3. **Safety Validation:** Pre-hook blocks dangerous operations, logs security events
4. **Observability:** Post-hook publishes tool events to NATS for monitoring
5. **Comprehensive Documentation:** 80+ KB of reference material across 8+ files

**Integration Philosophy Achieved:**

> "Leverage, Don't Duplicate"

TAC integration makes Claude Code CLI a **PMOVES-native development tool** that understands and leverages the existing multi-agent orchestration stack without duplicating functionality.

**Developer Experience:**

Developers gain instant access to production capabilities (RAG, research, monitoring, agent coordination) directly from their coding workflow, achieving the TAC vision of "leverage points" while respecting PMOVES's sophisticated infrastructure.

---

## References

### Primary Documentation

- **TAC Spec:** `/home/pmoves/PMOVES.AI/docs/PMOVES-claude code integrate.md`
- **Always-On Context:** `/home/pmoves/PMOVES.AI/.claude/CLAUDE.md`
- **Developer Guide:** `/home/pmoves/PMOVES.AI/.claude/README.md`

### Context Files

- **Services Catalog:** `/home/pmoves/PMOVES.AI/.claude/context/services-catalog.md`
- **NATS Subjects:** `/home/pmoves/PMOVES.AI/.claude/context/nats-subjects.md`
- **MCP API:** `/home/pmoves/PMOVES.AI/.claude/context/mcp-api.md`
- **TensorZero:** `/home/pmoves/PMOVES.AI/.claude/context/tensorzero.md`
- **CHIT Format:** `/home/pmoves/PMOVES.AI/.claude/context/chit-geometry-bus.md`
- **EvoSwarm:** `/home/pmoves/PMOVES.AI/.claude/context/evoswarm.md`
- **Git Worktrees:** `/home/pmoves/PMOVES.AI/.claude/context/git-worktrees.md`

### Hooks

- **Pre-Tool Hook:** `/home/pmoves/PMOVES.AI/.claude/hooks/pre-tool.sh`
- **Post-Tool Hook:** `/home/pmoves/PMOVES.AI/.claude/hooks/post-tool.sh`
- **Hooks README:** `/home/pmoves/PMOVES.AI/.claude/hooks/README.md`

### Commands

- **Agents:** `/home/pmoves/PMOVES.AI/.claude/commands/agents/status.md`
- **Health:** `/home/pmoves/PMOVES.AI/.claude/commands/health/check-all.md`
- **Search (Hi-RAG):** `/home/pmoves/PMOVES.AI/.claude/commands/search/hirag.md`
- **Search (SupaSerch):** `/home/pmoves/PMOVES.AI/.claude/commands/search/supaserch.md`
- **Deploy (Smoke Test):** `/home/pmoves/PMOVES.AI/.claude/commands/deploy/smoke-test.md`
- **Deploy (Up):** `/home/pmoves/PMOVES.AI/.claude/commands/deploy/up.md`
- **Deploy (Services):** `/home/pmoves/PMOVES.AI/.claude/commands/deploy/services.md`

---

**Document Version:** 1.0
**Last Updated:** 2025-12-07
**Status:** TAC Integration Complete (Phase 1 + Phase 2 Hooks)
