# PMOVES Model Fabric Contract
_Last updated: 2026-03-06_

## Purpose
Define one abstraction contract for model/provider selection across PMOVES.AI so integrations can evolve independently while runtime behavior stays consistent.

This is the execution policy for:
- Agent Zero / Archon orchestration
- Open Notebook provider bootstrap
- TensorZero routing
- GPU model lifecycle
- Creator pipeline (vision/audio/TTS/image)
- AgentGym-RL training and HuggingFace dataset/model publication

## Architecture Principles
1. Model-agnostic runtime: services route by alias/role, not hardcoded model IDs.
2. Upstream-first overlays: PMOVES additions remain additive modules and ImportError-guarded.
3. Local-first cloud-hybrid: always prefer local providers, then low-cost cloud fallbacks only.
4. Idempotent bootstrap: provider/model seed flows must be safe to rerun.
5. Single control plane: Supabase model registry + persona mappings are authoritative.
6. Measurable rollout: every model change requires readiness checks and smoke evidence.
7. Topology-safe rails: worker and agent changes must respect Graphiti protocol and CHIT wiring gates.

## Planes
### 1) Control Plane (authoritative state)
- Supabase tables/views in `pmoves_core` for providers, models, mappings, personas, deployments.
- Canonical docs: `MODEL_REGISTRY.md`, `MODEL_SOURCE_OF_TRUTH.md`, `TAC/TAC_MODEL_INFRA_PERSONA_PROD_READINESS.md`.
- All service routing decisions resolve through this plane.

### 2) Routing Plane (execution)
- TensorZero is the default routing gateway for OpenAI-compatible execution.
- Runtime model calls from agents/workers route through TensorZero unless a lane has explicit exemption.
- TensorZero runs must be visible in observability (ClickHouse + Prometheus/Grafana + model-readiness evidence).
- Open Notebook in PMOVES uses provider mode overlay (`tensorzero`, `hybrid`, `native`).
- Agent Zero and Archon consume aliases and endpoint contracts, not provider-specific schemas.

### 3) Runtime Plane (inference providers)
- Local providers (default): Ollama local, vLLM, LM Studio/OpenAI-compatible, HuggingFace local endpoints, TTS engines.
- Cloud fallback order (explicit):
  1. Ollama Cloud
  2. Cloudflare Workers AI free-tier lanes (through TensorZero/OpenAI-compatible bridge)
  3. Coding-plan lanes (`GLM coding plan`, `Claude Code`, `Codex CLI`) for coding workflows
- Direct high-cost API fallback providers are disabled by default in production lanes and require explicit opt-in with cost/risk justification.
- GPU Orchestrator manages load/unload/eviction and publishes lifecycle events.

### 4) Training Plane (feedback + model production)
- AgentGym-RL emits trajectory/reward signals and training artifacts.
- Dataset/model publication to HuggingFace follows PMOVES dataset contracts.
- Newly trained models enter registry as managed candidates, then promotion gates apply.

## Canonical Entities
- `provider`: endpoint + auth mode + capabilities + locality (`local|cloud`).
- `model`: provider model ID + type (`chat|embed|rerank|vl|stt|tts|image|video`) + constraints.
- `alias` (or role): stable name used by services and personas.
- `mapping`: service/function -> alias/model selection policy.
- `deployment`: where a model is currently loaded and usable.
- `persona binding`: persona/model preference + fallback chain.

## Integration Contract (all repos/submodules)
1. Must resolve models via alias/registry mapping.
2. Must not hardcode concrete model IDs in runtime request paths.
3. Must expose health/readiness including model provider connectivity where relevant.
4. Must publish/consume model lifecycle events when loading/unloading on GPU nodes.
5. Must implement fallback priority: local -> Ollama Cloud -> Cloudflare free tier -> coding-plan lanes.
6. Must keep secrets in approved channels (`*_FILE`, GH secrets, vault), never static defaults.
7. Must preserve Graphiti + CHIT rail compliance for agent/worker PRs (`chit-flow-pr-monitor-strict` in merge lane).

## Open Notebook Overlay Policy
- Keep upstream credential system and provider UX intact.
- PMOVES-specific behavior lives in additive `pmoves_provider/` modules.
- Bootstrap mode selects runtime behavior:
  - `tensorzero`: seed TensorZero-compatible provider and models.
  - `hybrid`: seed TensorZero + selected local providers from registry + approved cloud fallbacks.
  - `native`: upstream behavior only.
- Overlay failures must be non-fatal to upstream startup unless explicit strict mode is enabled.

## Worker Rails (Graphiti + CHIT)
- Worker lanes that publish/consume agent outcomes must:
  - emit/consume traceable subjects aligned with Graphiti protocol where applicable.
  - keep CHIT contract checks green before merge (`make -C pmoves chit-flow-pr-monitor-strict`).
  - avoid topology drift (service DNS aliases, network namespaces, and port policies must remain deterministic).

## Model Change Lifecycle
1. Discover candidate model/provider (local first; cloud only by fallback policy).
2. Register in Supabase model registry + mappings + persona relevance.
3. Sync routing artifacts (TensorZero/Open Notebook/GPU registry).
4. Run readiness and domain smokes (agents, creator, voice, retrieval).
5. Verify observability visibility for routed calls/runs.
6. Promote by branch policy (Integrations -> Hardened -> Main) with evidence.

## Required Validation for Promotions
- `make -C pmoves model-readiness`
- `make -C pmoves smoke`
- `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu` (when GPU lane applies)
- Service-specific smokes for changed lanes:
  - agents (`agents-headless-smoke`)
  - notebook (`notebook-workbench-smoke`)
  - creator/media/voice smokes as applicable
- PR monitor + CHIT/Graphiti gate:
  - `make -C pmoves pr-monitor-strict`
  - `make -C pmoves chit-flow-pr-monitor-strict`

## PR Review Lens (Topology + Agents)
Every PR touching networking, agents, or model routing should be reviewed for:
1. Local-first fallback ordering is preserved.
2. TensorZero remains primary route and call telemetry is observable.
3. Graphiti/CHIT rails remain intact for worker handoffs.
4. Compose/network namespace/port changes do not break deterministic topology.
5. Evidence includes model-readiness + relevant smokes.

## Operator and Coding-Agent Roles
- Agent Zero / Archon: runtime orchestration + policy execution.
- Codex / Claude Code: implementation and ops automation against this contract.
- Coding agents should modify adapters/mappings/docs before touching core runtime behavior.

## Near-Term Standardization Backlog
1. Complete registry-driven `hybrid` bootstrap in Open Notebook overlay for local + approved cloud fallback lanes.
2. Normalize model type taxonomy across registry, GPU orchestrator, and creator services.
3. Add one compatibility matrix doc per integration lane (agents, creator, voice, notebook, RL).
4. Gate PRs that alter model routing with mandatory readiness + observability evidence attachments.
