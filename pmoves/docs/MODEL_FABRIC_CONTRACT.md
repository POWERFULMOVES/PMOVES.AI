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
3. Local-first, cloud-capable: prefer local providers; allow cloud fallback by policy.
4. Idempotent bootstrap: provider/model seed flows must be safe to rerun.
5. Single control plane: Supabase model registry + persona mappings are authoritative.
6. Measurable rollout: every model change requires readiness checks and smoke evidence.

## Planes
### 1) Control Plane (authoritative state)
- Supabase tables/views in `pmoves_core` for providers, models, mappings, personas, deployments.
- Canonical docs: `MODEL_REGISTRY.md`, `MODEL_SOURCE_OF_TRUTH.md`, `TAC/TAC_MODEL_INFRA_PERSONA_PROD_READINESS.md`.
- Target state: all service routing decisions should resolve through this plane.
- Current migration evidence (still being normalized): literal `model_name` entries in `tensorzero/config/tensorzero.toml`, static entries in `services/gpu-orchestrator/models/model_registry.py`, and hardcoded `llm` fields in `models/agent-zero.yaml`.
- Migration path: replace direct bindings with alias-to-model resolution in `pmoves_core` and promote via `MODEL_REGISTRY.md` / `MODEL_SOURCE_OF_TRUTH.md` governance.

### 2) Routing Plane (execution)
- TensorZero is the default routing gateway for OpenAI-compatible APIs.
- Open Notebook in PMOVES uses provider mode overlay (`tensorzero`, future `hybrid`, `native`).
- Agent Zero and Archon consume aliases and endpoint contracts, not provider-specific schemas.

### 3) Runtime Plane (inference providers)
- Local providers: Ollama, vLLM, LM Studio/OpenAI-compatible, HuggingFace local endpoints, TTS engines.
- Cloud providers: OpenRouter and other OpenAI-compatible endpoints.
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
5. Must support OpenAI-compatible fallback path for cross-provider portability.
6. Must keep secrets in approved channels (`*_FILE`, GH secrets, vault), never static defaults.

## Open Notebook Overlay Policy
- Keep upstream credential system and provider UX intact.
- PMOVES-specific behavior lives in additive `pmoves_provider/` modules.
- Bootstrap mode selects runtime behavior:
  - `tensorzero`: seed TensorZero-compatible provider and models.
  - `hybrid` (target): seed TensorZero + selected local providers from registry.
  - `native`: upstream behavior only.
- Overlay failures must be non-fatal to upstream startup unless explicit strict mode is enabled.

## Model Change Lifecycle
1. Discover candidate model/provider (local or cloud).
2. Register in Supabase model registry + mappings + persona relevance.
3. Sync routing artifacts (TensorZero/Open Notebook/GPU registry).
4. Run readiness and domain smokes (agents, creator, voice, retrieval).
5. Promote by branch policy (Integrations -> Hardened -> Main) with evidence.

## Required Validation for Promotions
- `make -C pmoves model-readiness`
- `make -C pmoves smoke`
- `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu` (when GPU lane applies)
- Service-specific smokes for changed lanes:
  - agents (`agents-headless-smoke`)
  - notebook (`notebook-workbench-smoke`)
  - creator/media/voice smokes as applicable

## Operator and Coding-Agent Roles
- Agent Zero / Archon: runtime orchestration + policy execution.
- Codex / Claude Code: implementation and ops automation against this contract.
- Coding agents should modify adapters/mappings/docs before touching core runtime behavior.

## Near-Term Standardization Backlog
1. Add `hybrid` provider mode and registry-driven bootstrap in Open Notebook overlay. (Tracking: `MF-ONB-HYBRID` -> `NEXT_STEPS.md` current focus lane)
2. Normalize model type taxonomy across registry, GPU orchestrator, and creator services. (Tracking: `MF-TAXONOMY-ALIGN` -> `PMOVES.AI PLANS/ROADMAP.md` model standardization lane)
3. Add one compatibility matrix doc per integration lane (agents, creator, voice, notebook, RL). (Tracking: `MF-COMPAT-MATRIX` -> `PMOVES.AI PLANS/README_DOCS_INDEX.md` canonical docs map)
4. Gate PRs that alter model routing with mandatory readiness evidence attachments. (Tracking: `MF-EVIDENCE-GATE` -> `NEXT_STEPS.md` / `ROADMAP.md` release evidence policy)
