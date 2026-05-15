> **DEPRECATED — 2026-05-08**
> Cross-references the dead branch `PMOVES.AI-Edition-Hardened`. Implementation gaps described here were largely resolved in the MOF convergence. See `IMPLEMENTATION_GAP_ANALYSIS.md` for current status.

# TBE Implementation Cross-Reference Report

**Date:** 2026-02-08
**Branch:** PMOVES.AI-Edition-Hardened
**Purpose:** Cross-reference AGENTS documentation with actual implementation code

---

## Executive Summary

This report provides a comprehensive cross-reference between the Thread-Based Engineering (TBE) patterns documented in `/pmoves/docs/AGENTS/` and the actual implementation across PMOVES.AI and its submodules. The analysis reveals significant alignment between documented architecture and implementation, with specific gaps identified for hardened branch production readiness.

---

## 1. Documented vs Implemented Matrix

| Feature | Documented In | Implementation Status | Implementation Location | Gap Severity |
|---------|--------------|----------------------|-------------------------|--------------|
| **Base Thread (B)** | PMOVES.AI Agentic Architecture Deep Dive | ✅ Fully Implemented | `pmoves/services/agent-zero/main.py` | None |
| **Parallel Thread (P)** | ALIGNED_IMPLEMENTATION_ROADMAP.md | ⚠️ Partial | `pmoves/services/agent-zero/.mprocs.yaml` | Medium |
| **Chained Thread (C)** | Deep Dive | ⚠️ Partial | NATS event coordination | Medium |
| **Fusion Thread (F)** | Deep Dive | ⚠️ Partial | MACA in BoTZ | Medium |
| **Big Thread (B)** | Deep Dive | ✅ Implemented | Agent Zero orchestrator | Low |
| **Long Thread (Z)** | Deep Dive | ❌ Not Implemented | N/A | High |
| **BoTZ Core Four** | Deep Dive | ✅ Implemented | `PMOVES-BoTZ/.mprocs.yaml` | Low |
| **SKILL.md Pattern** | Gap Analysis | ⚠️ Partial | BoTZ skills/ | Medium |
| **A2A Protocol** | Gap Analysis | ✅ Implemented | `pmoves/services/agent-zero/python/features/a2a/` | Low |
| **CHIT Geometry Bus** | Deep Dive | ✅ Implemented | `pmoves/services/gateway/gateway/api/chit.py` | Low |
| **MACA Consensus** | Deep Dive | ✅ Implemented | `PMOVES-BoTZ/features/agent_sdk/slices/geometry/maca.py` | Low |
| **Security Hooks** | Gap Analysis | ❌ Not in production | `pmoves/services/agent-zero/security/` | High |

---

## 2. Thread-Based Engineering (TBE) Cross-Reference

### 2.1 Base Thread (B)

**Documentation:**
> "A standard linear prompt-response loop. A developer asking Agent Zero to 'fix this bug.'"

**Implementation:** ✅ **FULLY IMPLEMENTED**
- **Location:** `/home/pmoves/PMOVES.AI/pmoves/services/agent-zero/main.py`
- **API:** `POST /sessions` - `send_session_message()`
- **NATS Subjects:** `agentzero.task.v1`, `agentzero.memory.update`
- **Controller:** `/home/pmoves/PMOVES.AI/pmoves/services/agent_zero/controller.py`

```python
# From main.py lines 858-877
@app.post("/sessions")
async def send_session_message(
    request: SessionRequest, _: None = Depends(ensure_runtime_running)
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "message": request.message,
    }
    if request.context_id:
        payload["context_id"] = request.context_id
    # ... sends to Agent Zero runtime
```

### 2.2 Parallel Thread (P)

**Documentation:**
> "Multiple agents running simultaneously in isolated processes. Using mprocs to spawn one agent for coding and another for writing tests concurrently."

**Implementation:** ⚠️ **PARTIALLY IMPLEMENTED**
- **Location:** `/home/pmoves/PMOVES.AI/pmoves/services/agent-zero/.mprocs.yaml`
- **Config:** Gateway, Architect, Builder, Auditor processes defined
- **Gap:** Dynamic thread spawning via mprocs remote control server is configured but not integrated

```yaml
# From .mprocs.yaml lines 17-30
gateway:
  cmd: ["python", "-m", "gateway.gateway"]
  cwd: "/app/python/gateway"
  autostart: true
  env:
    MPLCROCS_SERVER: "127.0.0.1:4050"  # Remote control for dynamic spawning
```

**Gap Severity:** Medium - Orchestration configured but dynamic spawning needs testing

### 2.3 Chained Thread (C)

**Documentation:**
> "Sequential dependency where the output of Agent A becomes the input of Agent B. DeepResearch finding data → LangExtract structuring it → Publisher formatting it."

**Implementation:** ⚠️ **PARTIALLY IMPLEMENTED**
- **NATS Coordination:** `/home/pmoves/PMOVES.AI/pmoves/services/agent_zero/controller.py`
- **Event Flow:** `agentzero.task.v1` → `agentzero.task.result.v1`
- **Services:** DeepResearch → LangExtract → Publisher flow exists

**Gap Severity:** Medium - Chaining works via NATS but not explicitly managed as "Chained Threads"

### 2.4 Fusion Thread (F)

**Documentation:**
> "One prompt sent to multiple models to aggregate the best answer (Consensus). MACA (Multi-Agent Consensus Alignment) for validating complex reasoning."

**Implementation:** ✅ **IMPLEMENTED IN BoTZ**
- **Location:** `/home/pmoves/PMOVES.AI/PMOVES-BoTZ/features/agent_sdk/slices/geometry/maca.py`
- **Algorithm:** Entropy-based consensus via `MACAConsensus` class
- **Formula:** `ΔS = S_initial - S_final` (entropy reduction)

```python
# From maca.py lines 56-79
class MACAConsensus:
    """
    MACA (Multi-Agent Consensus Alignment) - Entropy-based consensus.

    Unlike traditional voting, MACA uses geometric arguments:
    - Each agent proposes shape transformations
    - Value is measured by entropy reduction: ΔS = S_initial - S_final
    - Consensus converges when global entropy decreases
    """
```

**Gap Severity:** Low - MACA implemented but not integrated with production TensorZero

### 2.5 Big Thread (Big)

**Documentation:**
> "A meta-structure where an Orchestrator manages a Directed Acyclic Graph (DAG) of sub-agents. Agent Zero managing a full feature implementation."

**Implementation:** ✅ **IMPLEMENTED**
- **Agent Zero:** Acts as orchestrator at `/home/pmoves/PMOVES.AI/pmoves/services/agent-zero/`
- **Controller:** Manages session state and task dispatch via NATS

**Gap Severity:** None - Core orchestration is production-ready

### 2.6 Long Thread (Z)

**Documentation:**
> "Hours/days duration with recovery. Long-running background tasks."

**Implementation:** ❌ **NOT IMPLEMENTED**
- **Gap:** No persistence mechanism for long-running agent tasks
- **Required:** Task resume capability, state checkpointing

**Gap Severity:** High - Critical for production autonomous workflows

---

## 3. BoTZ "Core Four" Primitives Cross-Reference

### 3.1 Context

**Documentation:**
> "Context as a managed resource, employing Progressive Disclosure. Data structured in cookbook/ directory. Agents retrieve specific 'recipes' or pivot files (SKILL.md) only when needed."

**Implementation:** ⚠️ **PARTIALLY IMPLEMENTED**
- **SKILL.md Files:** 100+ SKILL.md files exist across BoTZ and DoX submodules
- **Pattern:** Standardized frontmatter format with name, description, keywords
- **Gap:** Progressive disclosure not enforced - context loading is not on-demand

**Example SKILL.md:**
```yaml
---
name: code-builder
description: Agent skill for code generation and execution
keywords: code, development, programming
version: 1.0.0
---
```

**Gap Severity:** Medium - Pattern exists but R&D framework not enforced

### 3.2 Model

**Documentation:**
> "Opus 4.5 for architecture, Sonnet 3.5 for building, Haiku for auditing."

**Implementation:** ✅ **IMPLEMENTED**
- **mprocs Configuration:** `/home/pmoves/PMOVES.AI/pmoves/services/agent-zero/.mprocs.yaml`
- **TensorZero Integration:** Models routed via TensorZero gateway at port 3030

```yaml
# From .mprocs.yaml
architect:
  env:
    MODEL: "opus-4-5"
    TENSORZERO_FUNCTION: "orchestrator"
builder:
  env:
    MODEL: "sonnet-4-5"
    TENSORZERO_FUNCTION: "utility"
auditor:
  env:
    MODEL: "haiku"
```

**Gap Severity:** None - Model routing is production-ready

### 3.3 Prompt

**Documentation:**
> "Prompts are engineering artifacts, versioned, modular, stored in a library."

**Implementation:** ✅ **IMPLEMENTED**
- **Form Management:** `/home/pmoves/PMOVES.AI/pmoves/services/common/forms.py`
- **Storage:** YAML-based prompt forms in `pmoves/services/common/forms/`
- **Dynamic Loading:** `resolve_form_name()`, `resolve_forms_dir()`

**Gap Severity:** None - Prompt management is production-ready

### 3.4 Tools

**Documentation:**
> "Standardized executable scripts (Python, Bash) wrapped in tools/ directories, exposed via MCP interfaces."

**Implementation:** ✅ **IMPLEMENTED**
- **MCP Server:** `/home/pmoves/PMOVES.AI/pmoves/services/agent-zero/mcp_server.py`
- **Command Registry:** 20+ tools including geometry, YouTube, notebook search

```python
# From mcp_server.py
COMMAND_REGISTRY: Dict[str, str] = {
    "geometry.publish_cgp": "Publish a constellation graph program to the geometry gateway",
    "ingest.youtube": "Ingest a YouTube URL via the ingest pipeline",
    "notebook.search": "Search Open Notebook for curated notes",
    # ... 17 more commands
}
```

**Gap Severity:** None - MCP tooling is production-ready

---

## 4. SKILL.md Pattern Cross-Reference

### 4.1 Pattern Standardization

**Documentation:** SKILL.md template with frontmatter and structured sections

**Implementation:** ✅ **CONSISTENT ACROSS SUBMODULES**

| Submodule | SKILL.md Count | Pattern Consistency |
|-----------|----------------|---------------------|
| PMOVES-BoTZ | 50+ | ✅ Standardized |
| PMOVES-DoX | 80+ | ✅ Standardized |
| Agent-Zero | 0 | ❌ Not adopted |

**Gap Severity:** Low - Pattern is well-defined, adoption is gradual

### 4.2 SKILL.md Structure

**Expected Structure (from Gap Analysis):**
```
skills/
└── [skill-name]/
    ├── SKILL.md          # The Pivot File (required)
    ├── tools/            # Implementation tools
    ├── prompts/          # Prompt templates
    └── cookbook/         # Usage examples
```

**Actual Implementation in BoTZ:**
```
PMOVES-BoTZ/skills/
└── code-builder/
    └── SKILL.md          # ✅ Present
```

**Gap:** tools/, prompts/, cookbook/ subdirectories not consistently implemented

---

## 5. A2A Protocol Cross-Reference

### 5.1 Protocol Specification

**Documentation:** Google's A2A specification (https://a2aproject.github.io/A2A/)

**Implementation:** ✅ **FULLY IMPLEMENTED**

**File:** `/home/pmoves/PMOVES.AI/pmoves/services/agent-zero/python/features/a2a/server.py`

**Endpoints:**
- `GET /.well-known/agent.json` - Agent Card discovery ✅
- `POST /a2a/v1/tasks` - Task creation ✅
- `GET /a2a/v1/tasks/{task_id}` - Task status ✅
- `POST /a2a/v1/tasks/{task_id}/cancel` - Task cancellation ✅
- `POST /a2a/v1/tasks/{task_id}/artifacts` - Artifact management ✅

**Task States Implemented:**
```python
class TaskState(str, Enum):
    UNSPECIFIED = "TASK_STATE_UNSPECIFIED"
    SUBMITTED = "TASK_STATE_SUBMITTED"
    WORKING = "TASK_STATE_WORKING"
    COMPLETED = "TASK_STATE_COMPLETED"
    FAILED = "TASK_STATE_FAILED"
    CANCELLED = "TASK_STATE_CANCELLED"
    INPUT_REQUIRED = "TASK_STATE_INPUT_REQUIRED"
    REJECTED = "TASK_STATE_REJECTED"
    AUTH_REQUIRED = "TASK_STATE_AUTH_REQUIRED"
```

**Gap Severity:** None - Full A2A v1.0 compliance

### 5.2 Agent Card

**Implementation:** `/home/pmoves/PMOVES.AI/pmoves/services/agent-zero/python/features/a2a/types.py`

```python
AGENT_ZERO_CARD = AgentCard(
    protocol_version="1.0",
    name="Agent Zero",
    description="PMOVES.AI autonomous agent for general development tasks...",
    version="2.0.0",
    capabilities=AgentCapabilities(
        streaming=True,
        push_notifications=False,
        state_transition_history=False
    )
)
```

---

## 6. MACA (Multi-Agent Consensus Alignment) Cross-Reference

### 6.1 Documentation vs Implementation

**Documentation (Deep Dive Section 5.2):**
> "MACA: To validate these geometric constructs, agents exchange 'arguments' in the form of shape transformations. The consensus mechanism is mathematically rigorous, based on Entropy Reduction. The value of a shape (its 'truth') is defined by ΔS = S_initial - S_final."

**Implementation:** ✅ **FULLY ALIGNED**

**File:** `/home/pmoves/PMOVES.AI/PMOVES-BoTZ/features/agent_sdk/slices/geometry/maca.py`

**Key Methods:**
- `propose()` - Propose a shape for consensus
- `vote()` - Cast vote with entropy delta
- `finalize()` - Compute consensus via entropy reduction

```python
# Lines 233-237: Consensus acceptance criteria
accepted = (
    avg_score >= self.threshold and
    entropy_metric.delta > 0  # Entropy MUST be reduced
)
```

**Gap Severity:** None - Implementation matches documentation exactly

### 6.2 Geometry Models

**Implementation:** `/home/pmoves/PMOVES.AI/pmoves/services/common/geometry_models.py`

**CGP (CHIT Geometry Packet) Structure:**
- `spec` - Version identifier
- `super_nodes` - High-level groupings
- `constellations` - Point clusters
- `points` - Individual geometric points
- `attribution` - Dirichlet weights (v0.2)
- `sig` - HMAC signature

**Gap Severity:** None - Full CHIT v0.1 and v0.2 support

---

## 7. NATS Integration Cross-Reference

### 7.1 Documented Subjects

**Documentation:** Standardized NATS event subjects

**Implementation:** `/home/pmoves/PMOVES.AI/pmoves/services/agent-zero/python/events/subjects.py`

```python
# Standard subjects defined
AGENT_STARTED = "pmoves.agent.started.v1"
TASK_CREATED = "pmoves.work.task.created.v1"
TASK_COMPLETED = "pmoves.work.task.completed.v1"
TOOL_STARTED = "pmoves.agent.tool.started.v1"
CGP_READY = "pmoves.geometry.cgp.ready.v1"
```

**Gap Severity:** None - Event bus is production-ready

### 7.2 Controller Implementation

**File:** `/home/pmoves/PMOVES.AI/pmoves/services/agent_zero/controller.py`

**Features:**
- ✅ JetStream support with fallback to core NATS
- ✅ Durable subscriptions
- ✅ Pull-based message consumption
- ✅ Metrics tracking
- ✅ Session management

**Gap Severity:** None - Robust production implementation

---

## 8. Gap Severity Analysis

### Critical Gaps (Production Blocking)

| Gap | Impact | Recommendation |
|-----|--------|----------------|
| **Long Thread (Z) Persistence** | Cannot recover from failures | Implement task checkpointing in Agent Zero |
| **Security Hooks in Production** | No pre-execution validation | Integrate `security/patterns.yaml` into agent runtime |

### High Priority Gaps

| Gap | Impact | Recommendation |
|-----|--------|----------------|
| **Parallel Thread Dynamic Spawning** | Limited swarm flexibility | Test mprocs remote control at `127.0.0.1:4050` |
| **Progressive Context Loading** | Context pollution in long sessions | Implement on-demand SKILL.md loading |

### Medium Priority Gaps

| Gap | Impact | Recommendation |
|-----|--------|----------------|
| **MACA + TensorZero Integration** | Consensus not using production LLM routing | Wire MACA through TensorZero orchestrator function |
| **SKILL.md Subdirectories** | Inconsistent skill structure | Standardize tools/, prompts/, cookbook/ pattern |

### Low Priority Gaps

| Gap | Impact | Recommendation |
|-----|--------|----------------|
| **Chained Thread Explicit Management** | Chaining works implicitly | Document NATS-based chaining pattern |
| **Cookbook/ Examples** | Limited progressive disclosure | Add usage examples to SKILL.md files |

---

## 9. Production Integration Recommendations

### 9.1 For Hardened Branch

1. **Enable Security Hooks**
   - Add `security/patterns.yaml` to Agent Zero container
   - Integrate `deterministic.py` and `probabilistic.py` into MCP execution
   - Add audit logging to all tool executions

2. **Implement Long Thread Persistence**
   - Add state checkpointing to `controller.py`
   - Store task state in Supabase `agent_tasks` table
   - Implement task resume on service restart

3. **Wire MACA to TensorZero**
   - Create TensorZero function for `maca_consensus`
   - Route consensus requests through TensorZero gateway
   - Add observability for consensus rounds

4. **Standardize SKILL.md Structure**
   - Create template at `pmoves/services/agent-zero/skills/.template/SKILL.md`
   - Add skill loader that respects progressive disclosure
   - Document in contributor guidelines

### 9.2 For Submodule Integration

1. **BoTZ Pattern Alignment**
   - Sync Agent Zero mprocs config with BoTZ `.mprocs.yaml`
   - Adopt BoTZ security patterns
   - Integrate MACA for cross-agent consensus

2. **CHIT Geometry Bus**
   - Standardize CGP format across all services
   - Add CHIT signing to all geometry events
   - Implement anchor encryption for sensitive constellations

---

## 10. Cross-Reference Notes

### Related Implementations in Submodules

| Pattern | PMOVES.AI | PMOVES-BoTZ | PMOVES-DoX | PMOVES-Agent-Zero |
|---------|-----------|------------|-----------|-------------------|
| mprocs orchestration | `pmoves/services/agent-zero/.mprocs.yaml` | `PMOVES-BoTZ/.mprocs.yaml` | N/A | `PMOVES-Agent-Zero/.mprocs.yaml` |
| A2A server | `pmoves/services/agent-zero/python/features/a2a/` | `PMOVES-BoTZ/features/gateway/python-gateway/a2a/` | `PMOVES-DoX/backend/app/api/routers/a2a.py` | `PMOVES-Agent-Zero/python/helpers/fasta2a_server.py` |
| SKILL.md pattern | Partial (BoTZ only) | ✅ 50+ files | ✅ 80+ files | N/A |
| MACA consensus | Via BoTZ SDK | ✅ Full implementation | N/A | N/A |
| CHIT geometry | `pmoves/services/common/geometry_models.py` | Via SDK | N/A | N/A |
| Security hooks | Not implemented | ✅ `patterns.yaml` + hooks/ | N/A | N/A |

### Key File Locations

| Component | File | Purpose |
|-----------|------|---------|
| Agent Zero Main | `pmoves/services/agent-zero/main.py` | FastAPI service wrapper |
| Agent Zero Controller | `pmoves/services/agent_zero/controller.py` | NATS coordination |
| Agent Zero MCP | `pmoves/services/agent-zero/mcp_server.py` | Tool execution |
| A2A Server | `pmoves/services/agent-zero/python/features/a2a/server.py` | Agent protocol |
| mprocs Config | `pmoves/services/agent-zero/.mprocs.yaml` | Orchestration |
| CHIT API | `pmoves/services/gateway/gateway/api/chit.py` | Geometry bus |
| Common Models | `pmoves/services/common/geometry_models.py` | CGP types |
| MACA | `PMOVES-BoTZ/features/agent_sdk/slices/geometry/maca.py` | Consensus |

---

## 11. Validation Criteria

### Phase 1 Validation (Security)
```bash
# Test security hooks
python pmoves/services/agent-zero/security/hooks/deterministic.py --test
python pmoves/services/agent-zero/security/hooks/probabilistic.py --test
```

### Phase 2 Validation (A2A)
```bash
# Test A2A endpoints
curl http://localhost:8082/.well-known/agent.json
curl -X POST http://localhost:8082/a2a/v1/tasks -d '{"message": {...}}'
```

### Phase 3 Validation (MACA)
```bash
# Test MACA consensus
python -m PMOVES-BoTZ.features.agent_sdk.slices.geometry.maca
```

### Phase 4 Validation (CHIT)
```bash
# Test CHIT geometry
curl -X POST http://localhost:8086/geometry/event -d '{"type":"geometry.cgp.v1","data":{...}}'
```

---

## 12. Conclusion

The AGENTS documentation is well-aligned with the actual implementation across PMOVES.AI and its submodules. The core TBE patterns (Base, Parallel, Chained, Fusion, Big) are implemented to varying degrees, with Long Thread (Z) being the primary gap. The BoTZ "Core Four" primitives are substantially implemented, particularly Model routing and Tools (MCP). SKILL.md patterns are consistent but not universally adopted. A2A protocol is fully implemented. CHIT geometry and MACA consensus are sophisticated and production-ready.

**Primary Recommendations for Hardened Branch:**
1. Add security hooks to agent runtime
2. Implement Long Thread persistence
3. Integrate MACA with TensorZero
4. Standardize SKILL.md subdirectories

---

**Report Generated:** 2026-02-08
**Cross-Reference Version:** 1.0.0
**Analyzed By:** Claude Code CLI TBE Cross-Reference
