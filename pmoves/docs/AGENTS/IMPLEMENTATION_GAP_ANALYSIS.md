# AGENTS Documentation Implementation Gap Analysis

**Date:** 2026-04-10 (updated from 2026-03-01)
**Branch:** PMOVES.AI-Edition-Hardened / main
**Purpose:** Identify gaps between AGENTS documentation and current hardened branch implementation
**Cross-References:**
- [CODEX_RUNTIME_PROTOCOL.md](./CODEX_RUNTIME_PROTOCOL.md) — Operating modes and validation standards
- [CODEX_OPERATOR_HOME.md](./CODEX_OPERATOR_HOME.md) — Active endpoint catalog
- [AGENT_RESILIENCE_PATTERNS.md](./AGENT_RESILIENCE_PATTERNS.md) — Recovery patterns born from Phase C

---

## Executive Summary

The AGENTS documentation in `pmoves/docs/AGENTS/` describes a sophisticated agentic architecture for PMOVES.AI that includes Agent2Agent (A2A) protocol integration, advanced thread-based engineering patterns, and geometric cognitive architectures. This analysis identifies the gaps between the documented vision and the current hardened branch implementation.

---

## Current Implementation Status

### ✅ Already Implemented

| Component | Status | Notes |
|-----------|--------|-------|
| **Agent Zero** | ✅ Implemented | Located at `pmoves/services/agent-zero/` with Dockerfile and main.py |
| **Archon** | ✅ Implemented | Located at `pmoves/services/archon/` with README |
| **MCP Integration** | ✅ Partial | MCP adapters exist in `pmoves/integrations/archon/`; Agent Zero exposes `/mcp/*` |
| **NATS Message Bus** | ✅ Implemented | Core infrastructure for agent communication (auth hardened 2026-02-16) |
| **Gateway Agent** | ✅ Implemented | Located at `pmoves/services/gateway-agent/` |
| **BotZ Gateway** | ✅ Implemented | Located at `pmoves/services/botz-gateway/` |
| **Distributed Compute Services** | ✅ Implemented | Node Registry, vLLM Orchestrator, GPU Orchestrator |

### ✅ Completed Since Last Analysis (Phase 1 — Feb 2026)

| Component | Status | Notes |
|-----------|--------|-------|
| **Security Patterns** | ✅ Implemented | `security/patterns.yaml` with damage-control hooks (deterministic + probabilistic) |
| **Cipher Memory** | ✅ Implemented | Port 8105, Neo4j backend, MCP bridge at `pmoves-cipher-mcp/`, `agent_plan/checkpoint/completion` categories |
| **Codex Runtime Protocol** | ✅ Implemented | `CODEX_RUNTIME_PROTOCOL.md` with focus/scout modes, confidence gates, PR sweep |
| **KRISS KROSS Accord** | ✅ Ratified | Collision-safe multi-agent traversal with Graphiti trail + CHIT attestation (2026-02-25) |
| **Agent Resilience Patterns** | ✅ Implemented | 3-layer model (preventive → Cipher recovery → registry systemic) |
| **Agent Class Taxonomy** | ✅ v1.4.0 | 60 agents registered in `agent_registry.yaml` with types, tiers, NATS, CHIT toggles |
| **Persona Seeds** | ✅ Implemented | 8 standard personas seeded via `17_persona_seed.sql` with model preferences |
| **Model Registry** | ✅ Implemented | `gpu-models.yaml` reconciled with SQL registry (Anthropic, TTS, expanded mappings) |
| **CHIT Geometry Bus** | ⚠️ Partial | Endpoints exist (`/geometry/calibration/report` on Hi-RAG), NATS subjects active (`geometry.cgp.v1`), but full CGP encode/decode pipeline incomplete |
| **Codex-Claude Parity** | ✅ 100% | 113/113 CLI tokens mapped (see `CODEX_CLAUDE_PARITY_GAPS.md`) |

---

## Critical Gaps Requiring Implementation

### 1. Agent2Agent (A2A) Protocol Integration

**Documented In:** `AI Agent Integration and Best Practices.md`

**Status: ⚠️ Foundation exists, full A2A server NOT exposed (updated 2026-03-01)**

Agent Zero provides an MCP API at `/mcp/*` (port 8080) that serves as the coordination foundation. However, the formal A2A protocol (Google's Agent-to-Agent spec) is not yet implemented:

- ✅ Agent Zero MCP API live at `/mcp/*` — provides command execution and health check
- ✅ Archon connects to Agent Zero MCP for agent coordination
- ❌ `/.well-known/agent.json` Agent Card discovery endpoint not implemented
- ❌ A2A task lifecycle (submitted → working → completed/failed) not implemented
- ❌ Server-Sent Events (SSE) streaming for task updates not implemented
- ❌ A2A client library integration in Archon not implemented

**Action Required:**
1. Add A2A server endpoint to Agent Zero: `python/features/a2a/server.py`
2. Implement Agent Card discovery endpoint (`/.well-known/agent.json`)
3. Add JSON-RPC 2.0 handler for task management
4. Implement SSE streaming for real-time updates
5. Consider whether MCP API already covers A2A use cases sufficiently

### 2. Vertical Slice Architecture Refactoring

**Documented In:** `AI Agent Integration and Best Practices.md`

**Gap:** Agent Zero's `python/api/` directory has a flat API structure. The documentation calls for vertical slices:

**Current Structure:**
```
python/api/
├── chat_create.py
├── chat_load.py
├── upload.py
...
```

**Target Structure:**
```
python/features/
├── chat/
│   ├── api.py
│   ├── service.py
│   └── models.py
├── file_system/
│   ├── api.py
│   └── service.py
├── skills_manager/
│   ├── loader.py
│   └── registry.py
└── a2a/
    ├── server.py
    ├── client.py
    └── mapper.py
```

**Action Required:**
1. Refactor `python/api/` to `python/features/` with vertical slices
2. Group related endpoint, service, and model code together
3. Update imports throughout the codebase

### 3. SKILL.md Pivot File Pattern

**Documented In:** All AGENTS documentation

**Gap:** Current tool structure uses `instruments/` directory without standardized SKILL.md pivot files.

**Current Structure:**
```
data/agent-zero/instruments/default/yt_download/
├── yt_download.py
├── download.sh
└── download.md
```

**Target Structure:**
```
skills/
└── media-downloader/
    ├── SKILL.md          # The Pivot File (required)
    ├── tools/
    │   ├── yt_download.py
    │   └── download.sh
    ├── prompts/
    │   ├── feature-branch.md
    │   └── hotfix.md
    └── cookbook/
        ├── examples.md
        └── troubleshooting.md
```

**Action Required:**
1. Create SKILL.md template with:
   - Version
   - Description
   - Capabilities list
   - Context priming instructions
   - Tools reference
2. Convert existing instruments to skills format
3. Implement skill loader that reads SKILL.md files
4. Add cookbook/ directory for progressive disclosure

### 4. Thread-Based Engineering Patterns

**Documented In:** `AI Agent Integration and Best Practices.md`

**Gap:** Documentation describes six thread types (B, P, C, F, B, L). Currently only Base Threads are fully supported.

| Thread Type | Description | Implementation Status |
|-------------|-------------|----------------------|
| Base (B) | Standard prompt-response | ✅ Implemented |
| Parallel (P) | Multiple agents simultaneously | ❌ Not implemented |
| Chained (C) | Sequential dependencies | ⚠️ Partial (via n8n only) |
| Fusion (F) | Consensus from multiple models | ❌ Not implemented |
| Big (B) | Orchestrator managing sub-agents | ⚠️ Partial (via Archon) |
| Long (L) | Hours/days duration with recovery | ❌ Not implemented |

**Action Required:**
1. Implement P-Thread support in Archon with mprocs integration
2. Add C-Thread chaining in Agent Zero workflow engine
3. Implement F-Thread fusion for consensus (MACA)
4. Add L-Thread persistence and error recovery
5. Create thread templates for common patterns

### 5. Damage Control / Security Hooks

**Documented In:** `AI Agent Integration and Best Practices.md`

**Status: ✅ Implemented (Phase C hardening, 2026-02-16)**

The damage-control hook system is live in the parent PMOVES.AI repo:

- ✅ `security/patterns.yaml` deployed with self-protection (`**/security/patterns.yaml` in `zero_access`)
- ✅ Deterministic hooks: `.env*` file edits blocked (template files use `ask` pattern)
- ✅ Known Roads model: dangerous Docker operations redirected to Make targets (see `.claude/CLAUDE.md`)
- ✅ Adversarial instruction detection (GAN defense) active in pre-execution hooks
- ✅ Template ask-path: `check_path()` returns `(blocked, reason, is_template)`

**Remaining gap: Portability**

Hooks only apply in the parent PMOVES.AI repo. When agents operate in submodule worktrees (e.g., `PMOVES-BoTZ/`), the parent repo's hooks do not apply. See [AGENT_RESILIENCE_PATTERNS.md § Known Limitation](./AGENT_RESILIENCE_PATTERNS.md#known-limitation-hooksettings-portability) for workaround patterns.

**Not implemented:**
- ❌ Probabilistic LLM-based safety checks (Haiku model integration for pre-execution risk scoring)
- ❌ Prompt scan hooks (`security/hooks/prompt_scan.py`)

### 6. Dynamic Context Priming (R&D Framework)

**Documented In:** `AI Agent Integration and Best Practices.md`

**Gap:** Current implementation uses static `_context.md` files. Documentation calls for dynamic priming.

**Current:** Context is loaded into every agent session
**Target:** Context is loaded only when explicitly requested

**Action Required:**
1. Rename `_context.md` to `primers/prime_role.md`
2. Implement `read_primer` tool for on-demand context loading
3. Create modular context fragments instead of monolithic files
4. Update agent system prompts to not include context by default

### 7. Geometric Cognitive Architectures (CHIT)

**Documented In:** `PMOVES.AI Agentic Architecture Deep Dive.md`

**Status: ⚠️ Partially Implemented (updated 2026-03-01)**

CHIT Geometry Bus infrastructure is live but the full CGP pipeline is incomplete:

**Implemented:**
- ✅ Hi-RAG v2 exposes `/geometry/calibration/report` endpoint (port 8086)
- ✅ NATS subjects active: `geometry.cgp.v1`, `geometry.swarm.meta.v1`, `pmoves.geometry.cgp.ready.v1`
- ✅ EvoSwarm Controller (port 8113) publishes `geometry.swarm.meta.v1`
- ✅ Swarm Attribution agent registered, subscribes to `geometry.attribution.request.v1`
- ✅ CHIT toggles defined for all 60 agents in `agent_registry.yaml`
- ✅ `sign_cgp()` available in `chit_security.py` for trail signing

**Still Required:**
1. **Geometry Normalizer** - Standardize inputs to coordinate system
2. **Shape Attributor** - Full implementation (agent registered but runtime not deployed)
3. **Composite Builder** - Merge shapes into constellations
4. **Visualizer** - Render as cymatic patterns (Hyperdimensions placeholder exists)
5. **MACA** - Multi-Agent Consensus Alignment algorithm
6. **CGP version migration** - v0.1 → v0.2 → v1.0 progression undocumented

**See:** [CODEX_OPERATOR_HOME.md](./CODEX_OPERATOR_HOME.md#chit-geometry-bus) for live endpoint catalog

---

## Medium Priority Enhancements

### 8. Expertise Files System

**Documented In:** `AI Agent Integration and Best Practices.md`

**Gap:** No mechanism for agents to update their own "how-to" knowledge base.

**Action Required:**
1. Create `memory/expertise/` directory structure
2. Implement YAML-based expertise files (e.g., `db_troubleshooting.yaml`)
3. Add `write_expertise` tool for agents
4. Create Librarian/Scribe agent role for curation

### 9. Model Selection Strategy

**Documented In:** All AGENTS documentation

**Gap:** Documentation specifies Opus for architecture, Sonnet for building, Haiku for auditing. Current implementation may not follow this pattern consistently.

**Action Required:**
1. Define model routing configuration
2. Implement model selection based on task type
3. Add Haiku integration for safety hooks
4. Create model fallback strategies

### 10. mprocs Orchestration Integration

**Documented In:** `AI Agent Integration and Best Practices.md`

**Gap:** Remote control server integration for spawning new agent processes.

**Action Required:**
1. Create `.mprocs.yaml` orchestration config
2. Implement TCP server for remote control
3. Add agent spawn capability from Gateway
4. Create keymaps for in-loop control

---

## Documentation Updates Required

### Outdated References

1. **Port Numbers:** Some documentation references ports that may have changed
   - GPU Orchestrator: Was 8200, now 8090 ✅ Fixed in current branch
   - vLLM Orchestrator: Documented as 8117, needs verification

2. **Service Paths:** Some documentation references old submodule paths
   - PMOVES-Agent-Zero → Now `pmoves/services/agent-zero/`
   - PMOVES-Archon → Now `pmoves/services/archon/`

3. **Third-Party Services:** Venice.ai integration described but may need environment configuration

### New Documentation Needed

1. **A2A Integration Guide** - Step-by-step for adding A2A to agents
2. **Skill Authoring Guide** - How to create SKILL.md files
3. **Thread Pattern Cookbook** - Examples of each thread type
4. **Security Hook Authoring** - How to add custom hooks

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2) ✅ COMPLETE

1. ✅ Create `security/patterns.yaml` — Deployed with damage-control hooks
2. ✅ Implement deterministic hooks (pre_command.py) — Known Roads + GAN defense active
3. ✅ Create SKILL.md template — BoTZ skill marketplace operational
4. ✅ Convert one instrument to skill format as proof-of-concept
5. ✅ Cipher Memory deployed (port 8105) with agent plan/checkpoint/completion categories
6. ✅ Agent Registry created (`agent_registry.yaml`) with 60 agents, resilience attributes
7. ✅ Codex Runtime Protocol ratified with focus/scout modes
8. ✅ KRISS KROSS Accord ratified for multi-agent collision safety

### Phase 2: Protocol Integration (Week 3-4) — PARTIAL ⚠️ (verified 2026-04-10)

> A2A server.py exists; a2a_client.py for Archon NOT implemented. Low adoption (2 skill instances).

1. ⚠️ Implement A2A server in Agent Zero — server.py exists
2. ⚠️ Add Agent Card endpoint — partial
3. ❌ Integrate A2A client in Archon — NOT implemented
4. ❌ Test basic agent discovery and task submission — blocked on #3

### Phase 3: Architecture Refactoring (Week 5-6) — TEMPLATE COMPLETE ⚠️ (verified 2026-04-10)

> Template + test-skill exist in Agent Zero skills dir; only 2 instances deployed.

1. ⚠️ Refactor Agent Zero API to vertical slices — partial
2. ❌ Implement dynamic context priming
3. ❌ Add expertise file system
4. ⚠️ Create thread pattern templates — templates exist

### Phase 4: Advanced Features (Week 7+) — COMPLETE ✅ (verified 2026-04-10)

> bus.py + subjects.py + schema.py all exist. Event-driven coordination operational.

1. ✅ Implement P-Thread parallel execution — mprocs + gateway operational
2. ✅ Add F-Thread fusion consensus — threads.py + threads_persistent.py
3. ✅ Implement L-Thread persistence — persistent thread store
4. ✅ Begin CHIT geometry integration — CGP subjects active on NATS

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking changes during refactoring | High | Maintain backward compatibility, deprecate gradually |
| A2A protocol changes | Medium | Use official A2A library, version pinning |
| Performance regression with hooks | Medium | Cache hook results, use fast models for checks |
| Agent context pollution | High | Implement strict token limits, dynamic loading |

---

## Related Documentation

- [PMOVES.AI Agentic Architecture Deep Dive](./PMOVES.AI%20Agentic%20Architecture%20Deep%20Dive.md)
- [AI Agent Integration and Best Practices](./AI%20Agent%20Integration%20and%20Best%20Practices.md)
- [Aligning AI Agents with Indy Dev Dan](./Aligning%20AI%20Agents%20with%20Indy%20Dev%20Dan.md)
- [HARDWARE_TTS_REQUIREMENTS](./HARDWARE_TTS_REQUIREMENTS.md)
- [PMOVES_Engine_Templates](./PMOVES_Engine_Templates.md)
