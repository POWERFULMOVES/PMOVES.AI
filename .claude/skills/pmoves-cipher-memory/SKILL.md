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

## MCP Tools

### Store Memory

Store knowledge for future reference:

```
Use pmoves_cipher_store to remember:
- content: The knowledge to store
- category: code_pattern, decision, context, submodule, architecture, or reasoning
- tags: Optional list of tags for retrieval
```

**Categories:**
- `code_pattern`: Reusable code patterns and conventions
- `decision`: Architectural decisions and rationale
- `context`: Project-specific context
- `submodule`: PMOVES submodule knowledge
- `architecture`: System patterns and design
- `reasoning`: Chain-of-thought reasoning traces

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
