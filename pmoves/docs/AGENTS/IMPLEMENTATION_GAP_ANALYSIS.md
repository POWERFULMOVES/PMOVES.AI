# AGENTS Documentation Implementation Gap Analysis

**Date:** 2026-02-02
**Branch:** PMOVES.AI-Edition-Hardened
**Purpose:** Identify gaps between AGENTS documentation and current hardened branch implementation

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
| **MCP Integration** | ✅ Partial | MCP adapters exist in `pmoves/integrations/archon/` |
| **NATS Message Bus** | ✅ Implemented | Core infrastructure for agent communication |
| **Gateway Agent** | ✅ Implemented | Located at `pmoves/services/gateway-agent/` |
| **BotZ Gateway** | ✅ Implemented | Located at `pmoves/services/botz-gateway/` |
| **Distributed Compute Services** | ✅ Implemented | Node Registry, vLLM Orchestrator, GPU Orchestrator |

---

## Critical Gaps Requiring Implementation

### 1. Agent2Agent (A2A) Protocol Integration

**Documented In:** `AI Agent Integration and Best Practices.md`

**Gap:** The documentation describes full A2A server and client implementation for Agent Zero and Archon. Currently:

- ❌ `/.well-known/agent.json` endpoint not implemented
- ❌ A2A task lifecycle (submitted → working → completed/failed) not implemented
- ❌ Server-Sent Events (SSE) streaming for task updates not implemented
- ❌ A2A client library integration in Archon not implemented

**Action Required:**
1. Add A2A server endpoint to Agent Zero: `python/features/a2a/server.py`
2. Implement Agent Card discovery endpoint
3. Add JSON-RPC 2.0 handler for task management
4. Implement SSE streaming for real-time updates
5. Integrate A2A client in Archon for agent discovery and task submission

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

**Gap:** Documentation calls for `security/patterns.yaml` with deterministic and probabilistic hooks.

**Required Implementation:**
```yaml
# security/patterns.yaml
global_protection:
  blocked_commands:
    - pattern: "rm -rf /"
      reason: "Catastrophic system destruction"
    - pattern: "git push --force"
      reason: "History rewriting forbidden"
    - pattern: "drop database"
      reason: "Database destruction requires human approval"

  protected_paths:
    - path: ".env"
      level: "zero_access"
    - path: ".git/"
      level: "read_only"
    - path: "src/core/"
      level: "no_delete"

hooks:
  pre_execution:
    - name: "Probabilistic Safety Check"
      type: "llm_eval"
      model: "utility"  # TensorZero role — routes to fast/cheap model
      trigger_on: "shell_command"
      action_on_risk: "ask_user"
```

**Action Required:**
1. Create `security/patterns.yaml`
2. Implement `security/hooks/pre_command.py` for deterministic hooks
3. Implement `security/hooks/prompt_scan.py` for probabilistic hooks
4. Integrate hooks into Agent Zero's tool execution flow
5. Add Haiku model integration for safety checks

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

**Gap:** Advanced geometry-based reasoning and CGP (Contextual Geometry Packets) not implemented.

**Required Components:**
1. **Geometry Normalizer** - Standardize inputs to coordinate system
2. **Shape Attributor** - Analyze topological features
3. **Composite Builder** - Merge shapes into constellations
4. **Visualizer** - Render as cymatic patterns

**Action Required:**
1. Implement CHIT Geometry Bus integration
2. Add shape-attribution agent capability
3. Create CGP serialization/deserialization
4. Implement MACA (Multi-Agent Consensus Alignment)
5. Add entropy-based consensus mechanism

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

### Phase 1: Foundation (Week 1-2)

1. ✅ Create `security/patterns.yaml`
2. ✅ Implement deterministic hooks (pre_command.py)
3. ✅ Create SKILL.md template
4. ✅ Convert one instrument to skill format as proof-of-concept

### Phase 2: Protocol Integration (Week 3-4)

1. Implement A2A server in Agent Zero
2. Add Agent Card endpoint
3. Integrate A2A client in Archon
4. Test basic agent discovery and task submission

### Phase 3: Architecture Refactoring (Week 5-6)

1. Refactor Agent Zero API to vertical slices
2. Implement dynamic context priming
3. Add expertise file system
4. Create thread pattern templates

### Phase 4: Advanced Features (Week 7+)

1. Implement P-Thread parallel execution
2. Add F-Thread fusion consensus
3. Implement L-Thread persistence
4. Begin CHIT geometry integration

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
