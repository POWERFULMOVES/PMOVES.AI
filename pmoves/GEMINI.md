# PMOVES.AI Service Development — Gemini CLI Integration

_v1.4.0 — Microservice Implementation & Registry Management_

This folder contains the core application code, service implementations, and the **Single Source of Truth** for the PMOVES.AI agent ecosystem.

## 1. Agent Registry & Taxonomy

All services in this directory must be defined in `pmoves/config/agent_registry.yaml`. This file is used to generate the **Agent Topology** and **TAC Tree**.

### Registry Management
- **Add Agent**: Add a new entry to `agent_registry.yaml` with class, type, tier, layers, NATS subjects, and CHIT toggles.
- **Regenerate Topology**: Run `python -m pmoves.tools.agent_taxonomy_helper mermaid --style topology` to update the visual diagrams in `pmoves/docs/AGENTS/PMOVES_AGENT_TOPOLOGY.md`.
- **Query Registry**: Use `python -m pmoves.tools.agent_taxonomy_helper show <agent_name>` to inspect a service's configuration.

## 2. Service Implementation (Tier 3-4)

Most services in this directory are **Workers (Tier 4)** or **LLM (Tier 3)** providers.

### Core Patterns
- **API**: Use FastAPI + uvicorn. All services MUST include the `pmoves_health` router for `/healthz` and `/metrics` endpoints.
- **LLM Routing**: All LLM calls must route through **TensorZero** at `localhost:3030`.
- **Event Bus**: Use **NATS JetStream** for inter-service coordination. Subjects follow the `domain.entity.action.v{n}` pattern (e.g., `ingest.file.added.v1`).
- **Data Persistence**: 
    - **Vector**: Qdrant (`:6333`)
    - **Graph**: Neo4j (`:7474`)
    - **Full-Text**: Meilisearch (`:7700`)
    - **Relational**: Supabase (`:3010`)
    - **Object**: MinIO (`:9000`)

## 3. Communication Planes (CHIT, MCP, Flute)

### CHIT (Compressed Hierarchical Information Transfer)
- **Geometry Bus**: Services produce and consume **CGP Packets** (Consciousness Geometry Protocol) to share state across the "Geometry Bus".
- **CHIT Toggles**: Declare your service's sensitivity to geometry signals (delta, kappa, Hz) in the registry.

### MCP (Model Context Protocol)
- **Agent-to-Agent (A2A)**: Agent Zero and Archon use MCP to call tools from specialized servers (e.g., `pmoves-e2b-mcp-server`).
- **Tool Registration**: Define MCP servers in `pmoves/env.shared` using the `A0_MCP_SERVERS` variable.

### Flute (Multimodal Integration)
- **Path**: `pmoves/services/flute/`
- **Function**: Normalizes multimodal inputs (image/audio) into structured POML prompts for Agent Zero.
- **Tools**: Integrates Qwen-3 Omni captioners and Mangle logic translators.

## 4. Skill Bundles

Implement services to support these canonical skill workflows:
- `bringup-audit`: Use `make smoke` and `/healthz` checks.
- `multimodal-verifier`: Publish verification evidence to NATS subjects.
- `persona-grounding`: Integrate with `pmoves_core.personas` in Supabase.

## 5. Development Workflow

### Build & Deploy
- `make -C pmoves up`: Start core data services and workers.
- `make -C pmoves down`: Stop all containers.
- `make -C pmoves smoke`: Run the core smoke tests.
- `make -C pmoves supa-start`: Start the local Supabase CLI stack.

### Diagnostics (Loki/Prometheus)
- **Prometheus**: `:9090` — Service health and custom metrics.
- **Grafana**: `:3000` — Monitoring dashboards.
- **Loki**: `:3100` — Centralized log aggregation.

## 5. Directory Structure
- `pmoves/services/`: Python microservices (FastAPI).
- `pmoves/contracts/`: Event schemas (`schemas/`) and topic mapping.
- `pmoves/config/`: Configuration (agent registry, NATS subjects).
- `pmoves/docs/`: Service-specific documentation, research, and audit logs.

---

_Reference `pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md` for the full type system._
