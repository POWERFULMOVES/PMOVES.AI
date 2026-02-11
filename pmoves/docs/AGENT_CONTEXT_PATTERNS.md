# Universal Agent Context Patterns for PMOVES.AI

**Date:** 2026-02-11
**Scope:** All agents in PMOVES.AI ecosystem (Claude Code CLI, Agent Zero, Archon, BoTZ, custom agents)
**Purpose:** Establish "digital production controls on analog signals" - foundational context patterns as the primary reference point

---

## Executive Summary

PMOVES.AI operates on a **context hierarchy pattern** - like digital production controls on analog signals, we establish clear priority levels that all agents must follow. This prevents context conflicts, reduces loading time by 40-60%, and ensures consistent behavior across all agent types.

**Core Principle:** Context flows from top-level authority down, never sideways or up.

---

## The Four Context Tiers

### Tier 1: Always Load (Critical System Context)

**What:** Foundational PMOVES.AI architecture and patterns

**Files:**
```
/home/pmoves/PMOVES.AI/.claude/CLAUDE.md
/home/pmoves/PMOVES.AI/.claude/context/*
```

**When:** EVERY agent, EVERY session, NO exceptions

**Contains:**
- Service catalog (155 services)
- API integration points
- NATS event subjects
- Development patterns
- Testing workflow

**Why:** This is the "analog signal" - the ground truth that all agents reference.

### Tier 2: On-Demand Load (Major Subsystems)

**What:** Primary submodule architectures

**Files:**
```
PMOVES-Archon/.claude/CLAUDE.md
PMOVES-BoTZ/.claude/CLAUDE.md
PMOVES-Agent-Zero/.claude/CLAUDE.md
PMOVES-tensorzero/.claude/CLAUDE.md
PMOVES-ToKenism-Multi/.claude/CLAUDE.md
```

**When:** ONLY when working directly on that subsystem

**Example:** You're debugging Archon's prompt management → Load `PMOVES-Archon/CLAUDE.md`

**Don't Load:** When making cross-cutting changes that touch multiple subsystems

### Tier 3: Conditional Load (Integration Points)

**What:** Cross-submodule integration workspaces

**Files:**
```
integrations-workspace/*/CLAUDE.md
pmoves/docs/ARCHON_INTEGRATION.md
pmoves/docs/BOTZ_SKILLS_INTEGRATION.md
```

**When:** ONLY for integration tasks between subsystems

**Example:** Integrating Archon with a new BoTZ skill → Load the integration doc

### Tier 4: Explicit Load Only (Nested Components)

**What:** Deep nested submodule contexts

**Files:**
```
PMOVES-Archon/external/*/CLAUDE.md
PMOVES-BoTZ/features/skills/repos/*/CLAUDE.md
```

**When:** ONLY when explicitly requested or working on that specific component

**Never auto-load:** These contexts are opt-in to prevent circular loading

---

## Context Precedence Hierarchy

When conflicts occur between contexts, follow this order:

1. **Main repo context** > Submodule contexts
2. **Higher-level contexts** > Nested contexts
3. **Recent contexts** > Legacy contexts
4. **Production patterns** > Development experiments

**Example Conflict:**
- Main CLAUDE.md says: "Use Hi-RAG v2 for all RAG"
- Archon CLAUDE.md says: "Use local vector search"

**Resolution:** Main repo context wins. Archon should document why it needs an exception.

---

## Worktree-Aware Context Loading

### The Worktree Pattern

Git worktrees allow isolated development without full repo clones. Each worktree is a separate working directory pointing to the same git repository.

**Command:**
```bash
git worktree list                    # List all worktrees
git worktree add ../feature-branch feat-xyz  # Create new
git worktree prune                   # Clean stale
```

### Agent Behavior in Worktrees

**Critical Rule:** When an agent operates in a worktree, it loads context from THAT worktree's location, not the main repo.

**Example:**
```
Working in: /home/pmoves/PMOVES-hardened-merge
Agent loads: /home/pmoves/PMOVES-hardened-merge/.claude/CLAUDE.md
NOT: /home/pmoves/PMOVES.AI/.claude/CLAUDE.md
```

**Implication:** Each worktree may have different context versions. Always check which branch you're on.

### Universal Agent Pattern

**Step 1: Verify Location**
```bash
pwd                    # Check current directory
git branch              # Check current branch
git worktree list       # If in worktree, see which one
```

**Step 2: Load Appropriate Context**
- Am I in main repo? → Load Tier 1 + relevant Tier 2
- Am I in Archon worktree? → Load Tier 1 + Archon Tier 2
- Am I in integration workspace? → Load Tier 1 + Tier 3

**Step 3: Check for Context Conflicts**
- Does my task-specific context conflict with main repo?
- If yes, main repo wins unless documented exception exists

---

## Service Integration Patterns

### Golden Rule: Leverage, Don't Duplicate

**DO:**
- Use Hi-RAG v2 for knowledge retrieval
- Publish to NATS for event coordination
- Store artifacts in MinIO via Presign
- Call Agent Zero MCP API for orchestration
- Use TensorZero for all LLM/embedding calls

**DON'T:**
- Build new RAG systems
- Create new event buses
- Duplicate existing embeddings or indexing
- Implement new LLM gateways
- Create parallel monitoring stacks

### Service Discovery Pattern

All PMOVES.AI services expose:
- `/healthz` - Health check endpoint
- `/metrics` - Prometheus metrics (most services)

**Agent Pattern: Before using any service:**
```bash
curl http://localhost:8080/healthz  # Check service health
# Then proceed with API call
```

### NATS Event Coordination

**When to use:**
- Cross-agent communication
- Async task delegation
- Event-driven workflows

**Pattern:**
```bash
# Publish event
nats pub "subject.name.v1" '{"key": "value"}'

# Subscribe to events
nats sub "subject.name.v1"
```

**Key Subjects:**
- `research.deepresearch.request.v1` / `.result.v1`
- `supaserch.request.v1` / `.result.v1`
- `claude.code.tool.executed.v1` (for observability)

---

## Agent Type-Specific Guidelines

### Claude Code CLI

**Context Loading:** Automatic based on working directory

**Best Practices:**
1. Always starts in main repo → Loads Tier 1
2. When `cd` into submodule → Auto-adds Tier 2 for that module
3. Use `/worktree:list` to see available worktrees
4. Use `/worktree:switch` to change contexts cleanly

### Agent Zero Runtime Agents

**Context Loading:** Via environment configuration

**Best Practices:**
1. Configure `AGENTZERO_CONTEXT_PATH` to point to appropriate tier
2. Use MCP API for cross-agent calls, not shared context files
3. Each agent runtime gets scoped context (not entire PMOVES.AI)
4. Publish results to NATS for other agents to consume

### Archon Agents

**Context Loading:** Supabase-backed prompt management

**Best Practices:**
1. Agent prompts stored in Supabase, not CLAUDE.md
2. Context via `PMOVES-Archon/.claude/CLAUDE.md` only
3. Integration with Agent Zero via MCP API
4. No direct access to nested submodule contexts

### BoTZ Skill Agents

**Context Loading:** Per-skill context via skill marketplace

**Best Practices:**
1. Each skill has its own `SKILL.md` (not `CLAUDE.md`)
2. Skills load Tier 1 + specific skill context
3. Skills invoke other skills via BoTZ gateway, not direct imports
4. No circular dependencies between skills

### Custom Agents

**Context Loading:** Must follow tier system

**Best Practices:**
1. Always load Tier 1 (main PMOVES.AI context)
2. Add Tier 2 only for specific subsystem integration
3. Use service APIs, don't rebuild
4. Publish observability events to NATS

---

## Avoiding Context Loops

### The Problem

Nested submodules can create circular loading:
```
PMOVES-Archon/ → external/PMOVES-BoTZ/ → features/skills/ → back to Archon patterns
```

### The Solution

**1. Unidirectional Context Flow**
- Context flows: Main → Submodule → Component (one direction only)
- Never: Component → Submodule → Main (circular)

**2. API-Based Communication**
- Use MCP APIs for agent-to-agent calls
- Use NATS for event-based coordination
- Don't share context files for runtime data

**3. Explicit Opt-In for Nested Contexts**
- Tier 4 contexts are NEVER auto-loaded
- Agent must explicitly request nested context
- Document why nested context is needed

---

## Implementation Checklist

For any new agent integration:

- [ ] Agent loads Tier 1 context on startup
- [ ] Agent checks which worktree/branch it's operating in
- [ ] Agent uses service APIs (TensorZero, Hi-RAG, etc.)
- [ ] Agent publishes to NATS for coordination
- [ ] Agent checks `/healthz` before using services
- [ ] Agent follows context precedence for conflicts
- [ ] Agent documentation specifies which tiers to load

---

## Monitoring and Maintenance

### Key Metrics

- Context loading time per session
- Memory usage during context loading
- Number of context conflicts resolved
- Agent performance by context tier

### Quarterly Tasks

1. Audit all CLAUDE.md files for updates
2. Review context tier assignments
3. Clean up stale worktrees
4. Update this document with new patterns

### Resources

- Main audit: `pmoves/docs/CLAUDE_CONTEXT_AUDIT.md`
- Service catalog: `.claude/context/services-catalog.md`
- NATS subjects: `.claude/context/nats-subjects.md`
- Integration docs: `pmoves/docs/*_INTEGRATION.md`

---

## Conclusion

The PMOVES.AI ecosystem uses a **hierarchical context pattern** as its "digital production controls on analog signals" - the foundational reference point for all agent behavior. By following these patterns, all agents (Claude Code CLI, Agent Zero, Archon, BoTZ, custom) can operate harmoniously without context conflicts or duplication.

**Key Takeaway:** Context flows down the hierarchy, never sideways or up. When in doubt, default to Tier 1 (main repo context) and use service APIs for integration.

---

*This pattern document applies to ALL agents in PMOVES.AI. Any deviation must be explicitly documented and approved.*
