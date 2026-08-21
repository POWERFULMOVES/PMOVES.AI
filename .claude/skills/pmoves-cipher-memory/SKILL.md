---
name: pmoves-cipher-memory
description: Enable persistent memory across Claude Code sessions for PMOVES.AI development.
---

# PMOVES Cipher Memory Skill

**Purpose**: Enable persistent memory across Claude Code sessions for PMOVES.AI development.

## Overview

This skill integrates Claude Code with Cipher Memory, providing:
- Persistent storage of code patterns, decisions, and context
- Semantic search across stored memories
- Reasoning trace storage for complex problem-solving
- Submodule knowledge management

## Required on every call: `agentId`

`pmoves_cipher_store` and `pmoves_cipher_search` both **require** `agentId`. This
skill omitted it until 2026-08-21, so every example here was missing a required
field and would have failed.

Use your signing-card `agent_id` from `pmoves/config/signing_identity_cards.yaml`
(`claude-opus`, `crush`, `4090-claude`, ...). The tool's own description suggests
`claude-4090`, which matches **no card** — the card is `4090-claude`.

Search is **per-agent scoped**: it returns only what the same `agentId` stored. Pass
`agentId: "*"` for cross-agent search (advisory mode only). On a cold start, search
the wildcard too or you will miss what other agents on this node recorded.

## Cold start is a requirement, not a health check

Cipher should be running whenever Claude or any registered agent starts. Before
doing work, recall prior state:

```
pmoves_cipher_session_recall  — the purpose-built primitive
pmoves_cipher_search          — with category=agent_checkpoint (prior plan)
                                or category=agent_completion  (what was tried)
```

Verified 2026-08-21: the store was **empty** (scoped and wildcard both returned
`{"results":[]}`). Nothing to inherit yet — which makes writing matter more.

## MCP Tools

Ten tools exist. This skill documented three until 2026-08-21; the other seven —
including both session primitives the cold-start rule depends on — were missing.

| tool | purpose |
|---|---|
| `pmoves_cipher_store` | store knowledge with category + tags |
| `pmoves_cipher_search` | search stored memories |
| `pmoves_cipher_store_reasoning` | store a chain-of-thought trace |
| `pmoves_cipher_reasoning_patterns` | retrieve recurring reasoning patterns |
| `pmoves_cipher_session_save` | persist session state |
| `pmoves_cipher_session_recall` | restore prior session state (cold start) |
| `pmoves_cipher_hybrid_search` | combined vector + text search |
| `pmoves_cipher_graph_expand` | expand a memory's graph neighbourhood |
| `pmoves_cipher_mcp_list` | list registered MCP surfaces |
| `pmoves_cipher_mcp_get` | fetch one MCP surface record |

### Store Memory

Store knowledge for future reference:

```
Use pmoves_cipher_store to remember:
- content: The knowledge to store
- category: code_pattern, decision, context, submodule, architecture, or reasoning
- tags: Optional list of tags for retrieval
```

**Categories (nine — the enum is shared by store and search):**
- `code_pattern`: Reusable code patterns and conventions
- `decision`: Architectural decisions and rationale
- `context`: Project-specific context
- `submodule`: PMOVES submodule knowledge
- `architecture`: System patterns and design
- `reasoning`: Chain-of-thought reasoning traces
- `agent_plan`: A durable plan an agent can resume from
- `agent_checkpoint`: Mid-work state at a phase boundary
- `agent_completion`: What was actually finished, and what was tried

The last three were missing from this skill. They are the ones the cold-start
pattern in `.claude/context/cipher.md` tells agents to filter on, so their absence
here made that guidance unusable.

**Note:** `pmoves_cipher_store` currently returns `embedded: false`, so retrieval
falls back to text match rather than vector similarity. Keep queries close to the
stored wording.

**Example:**
```
Store this pattern: "PMOVES submodules should include pmoves_announcer,
pmoves_health, pmoves_registry, pmoves_common in their root directory."

Category: code_pattern
Tags: submodule, pmoves_framework, integration
```

### Search Memory

Search stored memories:

```
Use pmoves_cipher_search to find:
- query: Search query (semantic search)
- category: Optional filter by category
- tags: Optional filter by tags
- limit: Maximum results (default: 10)
```

**Example:**
```
Search for: "submodule integration patterns"
Category: code_pattern
```

### Store Reasoning

Store complex problem-solving traces:

```
Use pmoves_cipher_store_reasoning to capture:
- question: The problem being solved
- reasoning: Chain of thought
- result: Final solution
```

**Example:**
```
Store reasoning about: "How to handle circular submodule references"

Question: PMOVES-DoX has external/PMOVES-BoTZ but BoTZ is also a root submodule
Reasoning: These are separate instances - DoX uses its own copy for DoX-specific branch
Result: Keep nested submodules but document them as separate instances
```

### Search Reasoning

Find past reasoning patterns:

```
Use pmoves_cipher_reasoning_patterns to find:
- query: Problem description
- limit: Maximum results (default: 5)
```

## PMOVES.AI Memory Patterns

### Submodule Architecture

```
Category: submodule
"PMOVES.AI has 40+ root submodules organized in tiers:
- DATA: Qdrant, Neo4j, NATS (infrastructure)
- API: Hi-RAG, TensorZero (data access)
- LLM: TensorZero (only tier with API keys)
- WORKER: Background processing
- MEDIA: YouTube, Whisper
- AGENT: Archon, Agent-Zero (orchestration)"
Tags: architecture, pmoves, tiers
```

### Integration Patterns

```
Category: code_pattern
"PMOVES services use pmoves_integrations framework:
- pmoves_announcer: NATS service discovery
- pmoves_health: Health check endpoints
- pmoves_registry: Service URL resolution
- pmoves_common: Shared types (ServiceTier, HealthStatus)"
Tags: pmoves_framework, integration, service_mesh
```

### Decision Records

```
Category: decision
"TensorZero is the LLM gateway for all PMOVES services.
It centralizes API key management - only the LLM tier has external API keys.
All other services call TensorZero internally."
Tags: architecture, llm, security, tensorzero
```

### Networking Modes

```
Category: architecture
"PMOVES services support three networking modes:
- Standalone: Run independently with local Ollama/Cipher
- Docked: Connect to parent PMOVES.AI infrastructure (TensorZero, NATS, Qdrant)
- Hybrid: Mix local and parent resources"
Tags: networking, deployment, docker
```

## When to Use This Skill

### Store Memories When:
- You discover an important architectural pattern
- A decision is made about submodule structure
- You find a reusable code pattern
- Complex reasoning leads to a solution
- Documentation is sparse and you discover something

### Search Memories When:
- Working on similar problems
- Need to recall architectural decisions
- Looking for submodule-specific patterns
- Understanding integration approaches

## Session Workflow

1. **Start**: Search for existing context about the task
2. **Work**: Store important discoveries and patterns
3. **Complex Problems**: Store reasoning traces
4. **End**: Store session summary for next time

## Key Principles

- **Store Early**: Don't wait - store patterns as you find them
- **Use Categories**: Organize by type for better retrieval
- **Tag Liberally**: Tags help with filtering
- **Capture Reasoning**: The "why" is as important as the "what"
- **Search First**: Check what's already stored before re-discovering
