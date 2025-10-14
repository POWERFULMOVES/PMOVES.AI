# PMOVES Agent Ecosystem Enhancements

Inspired by state-of-the-art multi-agent architectures (specifically the YouTube video demonstrating Claude Code with OpenAI Realtime API orchestration), this document analyzes the current PMOVES infrastructure and recommends targeted enhancements based on what's already built versus what the video demonstrates.

## Current State Analysis

### ✅ Already Implemented

**Agent Infrastructure:**
- **Agent Zero**: MCP-compatible coordinator with `/mcp/execute` endpoint, NATS JetStream integration, and form-based temperaments (POWERFULMOVES, CREATOR, RESEARCHER)
- **Archon**: Specialized crawl/knowledge agent with MCP HTTP bridge (port 8051), task update events, and Supabase integration
- **Mesh Agent**: Network presence announcer broadcasting agent availability
- **NATS Event Bus**: JetStream-enabled message broker with structured topics (`ingest.*`, `archon.task.update.v1`, `content.published.v1`, etc.)

**Observability:**
- **Telemetry Endpoints**: Services expose `/metrics` (publisher, publisher-discord) with turnaround/latency/cost tracking
- **Supabase Rollup Tables**: `publisher_metrics_rollup`, `publisher_discord_metrics` for historical dashboard queries
- **Retrieval-Eval Dashboard**: Web UI at `:8090` for RAG quality metrics (MRR/NDCG)
- **Real-time Listener**: `pmoves/tools/realtime_listener.py` subscribes to NATS topics for live event monitoring (`python pmoves/tools/realtime_listener.py --topics content.published.v1 --max 1`)

**Orchestration:**
- **n8n Workflows**: Approval poller, echo publisher, content automation (JSON exports in `n8n/flows/`)
- **Gateway Orchestration**: `/workflow/demo_run` endpoint combining ingest → index → graph → CHIT decode
- **MCP Command Registry**: Agent Zero's `/mcp/commands` lists available tools (geometry, ingest, media, comfy, forms)

### 🚧 Gaps Identified (From Video Comparison)

**What the Video Has That We Don't:**

1. **Voice-Driven Orchestration**: OpenAI Realtime API providing voice → text → agent command flow
2. **Claude Code Hooks for Observability**: Real-time UI showing tool invocations, file edits, and agent validation steps with rich summaries
3. **Browser-Based Validation Agents**: Gemini 2.5 computer-use model taking screenshots and verifying UI changes
4. **Multi-Agent Collision Detection**: Explicit agent boundaries (Sony = backend, Blink = frontend) preventing work overlap

**What We Have That's Better:**

- **Event Contracts**: Versioned schema (`contracts/*.v1.schema.json`) with `topics.json` registry
- **MCP Standards**: HTTP/stdio MCP bridges (not proprietary hooks)
- **Supabase Persistence**: Approval workflows, studio board, geometry shapes persisted beyond ephemeral agent memory
- **Production Readiness**: Docker Compose profiles, health checks, Tailscale auth, GPU support

## Recommended Enhancements

### 1. Voice Orchestration Layer (Align with Video's "Ada" Agent)

**Status**: Not implemented; Agent Zero has HTTP API but no voice interface.

**Proposal**: Add OpenAI Realtime API wrapper as a new service (`services/voice-orchestrator/`) that:
- Accepts WebSocket connections for voice input
- Translates speech → text → Agent Zero `/mcp/execute` commands
- Streams TTS responses back to the client
- Publishes `voice.command.v1` events to NATS for audit trails

**Priority**: Medium (nice-to-have; CLI/HTTP workflows are sufficient for current use cases)

### 2. Enhanced Observability Dashboard (Expand retrieval-eval UI)

**Status**: Partial; telemetry exists but no unified "Live Pulse" view.

**Proposal**: Extend `services/retrieval-eval` web UI to include:
- **Real-time NATS feed**: Subscribe to `>` wildcard, display filtered event stream
- **Agent status cards**: Show agent-zero, archon, mesh-agent, publisher health (idle/working/error)
- **Task timeline**: Visualize `archon.task.update.v1` → `content.published.v1` workflows with Mermaid diagrams
- **Cost/engagement overlays**: Pull from Supabase rollups to show ROI metrics inline

**Implementation Path**:
1. Add NATS WebSocket proxy endpoint to retrieval-eval (or gateway)
2. Build Vue/Svelte component consuming the feed
3. Wire agent health checks (`/healthz` polling or `agent.heartbeat.v1` events)

**Priority**: High (aligns with M2 automation loop validation needs documented in `NEXT_STEPS.md`)

### 3. Self-Validation Agents (Inspired by Video's Browser Agents)

**Status**: Smoke tests exist (`make smoke`) but no runtime validation loop.

**Proposal**: Create `services/validation-agent/` that:
- Subscribes to `*.task.update.v1` completion events
- Triggers schema validation, API health checks, or browser tests (Playwright)
- Publishes `validation.result.v1` with pass/fail + screenshot artifacts
- Integrates with approval workflows (block publish if validation fails)

**Example Workflow**:
```
archon.crawl.result.v1 → validation-agent checks JSON schema
                       → validation.result.v1 (success)
                       → approval-poller proceeds with publish
```

**Priority**: Medium-High (closes the automation loop; reduces manual QA)

### 4. Standardized Agent Command Structure

**Status**: Implemented via MCP `/mcp/execute` but no enforcement.

**Current Command Format** (Agent Zero):
```json
{
  "cmd": "geometry.jump",
  "arguments": { "point_id": "..." }
}
```

**Proposal**: Add validation middleware requiring:
- `correlation_id` for multi-step workflows
- `requester` field (agent name/ID)
- `timeout_sec` to prevent hung tasks

Update `contracts/schemas/` with `agent.command.v1.schema.json` and enforce via FastAPI dependencies.

**Priority**: Low (nice-to-have; current format is functional)

## Comparison: Video Demo vs. PMOVES

| Feature | Video (Claude Code + Realtime API) | PMOVES |
|---------|-----------------------------------|---------|
| **Voice Interface** | ✅ OpenAI Realtime API | ❌ HTTP/CLI only |
| **Agent Orchestration** | ✅ "Ada" voice agent | ✅ Agent Zero MCP + n8n workflows |
| **Observability UI** | ✅ Real-time tool call stream | 🚧 Telemetry endpoints; no unified UI |
| **Self-Validation** | ✅ Gemini browser agent | 🚧 Smoke tests only |
| **Event Bus** | ❌ Ephemeral (in-memory?) | ✅ NATS JetStream with persistence |
| **Multi-Agent Collab** | ✅ Sony/Blink with explicit roles | ✅ Agent Zero/Archon/Mesh via NATS topics |
| **Persistent State** | ❌ (relies on file system) | ✅ Supabase + Neo4j |

## Next Steps

### Immediate (Align with Video Concepts)

1. **Spike Voice Orchestrator** (1-2 days): Prototype OpenAI Realtime API wrapper; validate latency and cost vs. typing commands
2. **Extend Retrieval-Eval UI** (3-5 days): Add NATS feed + agent cards; document in `docs/OBSERVABILITY_DASHBOARD.md`
3. **Build Validation Agent** (2-3 days): Start with schema validation; add Playwright browser tests in Phase 2
4. **Document Agent Boundaries** (1 day): Update `AGENTS.md` with role definitions (prevent collision like Sony/Blink in video)

### Advanced (Leverage Existing PMOVES Innovations)

PMOVES already has unique capabilities beyond the video demo that should be highlighted:

**5. CHIT Geometry Bus Integration** (Already Built!)
- **Status**: `geometry.cgp.v1` events already flowing; ShapeStore cache operational
- **Enhancement**: Add geometry visualization to observability dashboard
- **Rationale**: CHIT (Cymatic-Holographic Information Transfer) provides geometric representations of knowledge that agents can share more efficiently than raw tokens
- **Implementation**: 
  - Integrate `/geometry/` UI into the observability dashboard
  - Show constellation harvest paths for agent reasoning traces
  - Display MHEP (Modified Hierarchical Entropy Product) scores for agent coherence monitoring

**6. Grounded Personas & Pack-Scoped Retrieval** (v5.12 Ready)
- **Status**: Schema in `db/v5_12_grounded_personas.sql`; personas/packs YAML manifests defined
- **Enhancement**: Wire personas as agent "forms" (POWERFULMOVES, CREATOR, RESEARCHER already exist)
- **Implementation**:
  - Agent Zero already has form switching via `/mcp/execute` + `form.switch` command
  - Map persona YAML to agent behavior policies (freshness, citation requirements, entity boosts)
  - Use pack-scoped search to ground agent responses in curated knowledge domains

**7. Latent Geometry as Agent Control Knob**
- **Research**: `docs/understand/Latent_Geometry_Is_a_Control_Knob/` demonstrates geometry manipulation improves OOD behavior
- **Application**: Use δ-hyperbolicity and Ollivier-Ricci curvature metrics to monitor agent reasoning quality
- **Implementation**:
  - Compute geometry metrics on agent embedding trajectories
  - Flag agents with high δ (low tree-likeness) for review/retraining
  - Experimental: Add geometry regularization to agent fine-tuning loops

**8. MindMap Graph Traversal** (Neo4j Integration)
- **Status**: `/mindmap/{constellation_id}` endpoint design in `pmoves_chit_graph_plus_mindmap/`
- **Enhancement**: Agent Zero can query Neo4j mind maps during reasoning
- **Implementation**:
  - Add `mindmap.query` to Agent Zero's MCP tool registry
  - Expose constellation-based knowledge graphs for causal reasoning
  - Enable agents to "jump" between knowledge domains via geometry

### Why These Matter More Than Voice

The video's voice interface is impressive, but **PMOVES already has deeper AI innovations**:

1. **Geometric Knowledge Transfer** (CHIT): Agents share compressed, structured representations instead of verbose tokens
2. **Grounded Reasoning** (Personas/Packs): Agents operate within curated knowledge domains with explicit policies
3. **Topological Quality Metrics** (Latent Geometry): Monitor agent reasoning coherence via mathematical invariants
4. **Graph-Native Memory** (Neo4j + MindMaps): Agents traverse knowledge graphs, not just vector similarity

These capabilities position PMOVES ahead of the video demo's "orchestration + voice" model. **Focus on showcasing these differentiators** in the observability UI before adding voice.

### Recommended Priority Order

1. ✅ **Enhanced Observability Dashboard** (High Priority) — Visualize CHIT geometry + agent status
2. ✅ **Self-Validation Agent** (Medium-High) — Close automation loop
3. ⚠️ **Voice Orchestrator** (Low Priority) — Nice-to-have, but not differentiating
4. ✅ **Geometry-Aware Agent Monitoring** (High Priority) — Unique to PMOVES
5. ✅ **Persona/Pack Integration** (Medium) — Already 80% built

Align with `docs/ROADMAP.md` M3 retrieval quality milestone and `docs/NEXT_STEPS.md` M2 automation loop completion checklist.

---

## Appendix: PMOVES Unique Capabilities Reference

### CHIT (Cymatic-Holographic Information Transfer)
- **Spec**: `chit.cgp.v0.1` JSON format with constellations, anchors, spectra
- **Backend**: CHR (Constellation Harvest Regularization) pipeline in `docs/understand/Constellation-Harvest-Regularization/`
- **Frontend**: D3 visualization with fractal drill-down and cymatic ripple patterns
- **Agent Integration**: `geometry.jump`, `geometry.decode_text` MCP commands

### Grounded Personas & Packs (v5.12)
- **Schema**: `pmoves_core.personas`, `pmoves_core.grounding_packs`, `pmoves_kb.chunks` with pack_id
- **Manifests**: YAML-based persona definitions with tool grants, boosts, filters, freshness policies
- **Retrieval**: Pack-scoped hybrid search (BM25 + vector + graph fusion) with reranker
- **Events**: `persona.published.v1`, `kb.pack.published.v1` for versioned knowledge updates

### Latent Geometry Research
- **Metrics**: δ-hyperbolicity, Ollivier-Ricci curvature, persistent homology (H₁), CKA similarity
- **Findings**: Geometry is observer-dependent, process-deformable, and directly optimizable for OOD robustness
- **Application**: Monitor agent reasoning via geometry metrics; use sidecar networks to "bend" geometry for improved generalization
