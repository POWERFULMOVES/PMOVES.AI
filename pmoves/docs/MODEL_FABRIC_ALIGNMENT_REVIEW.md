# Model Fabric Alignment Review — PMOVES.AI

_Generated: 2026-04-16 | Source: 10 documentation files_

---

## Document Purpose

Structured extraction from PMOVES.AI documentation for model fabric alignment review. Each doc summarized against 7 focus areas: model routing, embeddings, local models, HuggingFace integration, Z.AI GLM provider, agent spawning, and TensorZero configuration.

---

## DOC 1: PMOVES_AGENT_TOPOLOGY.md

| Field | Value |
|-------|-------|
| **What it defines** | Master visual topology of the 60-agent PMOVES.AI ecosystem. Mermaid diagrams for: master topology, TAC tree (Taxonomy-Agent-Connection), agent evolution path, data flow, NATS nervous system. Derived from single source of truth `agent_registry.yaml`. |
| **Model Routing** | TensorZero listed as infrastructure backbone component (port 3030). Archon routes through TensorZero for LLM calls. All LLM interactions flow: Agent Zero -> Archon -> TensorZero -> Models. |
| **Embeddings** | Hi-RAG v2 writes to Qdrant (vector DB) via data flow. Extract Worker writes to Qdrant + Meilisearch. No explicit embedding model wiring in this doc. |
| **Local Models** | Llama Throughput Lab listed as domain application for LLM benchmarking. No specific local model configs. |
| **HuggingFace** | Not referenced. |
| **Z.AI GLM** | Not referenced. |
| **Agent Spawning** | Agent evolution pipeline defined: CLI Base -> Stage 1 (NATS connected) -> Stage 2 (CHIT-enabled) -> Mega Evolution. Team formation when context limits reached. 76 agents organized into 12 subsystems. NATS subjects define inter-agent communication. |
| **TensorZero** | Classified as Standard type, API/LLM tier 2, Stage 1 evolution. Positioned in infrastructure backbone. Archon connects to it. |
| **Gaps/TODOs** | No explicit gaps. Doc is descriptive ("what is" not "what should be"). Evolution stages are aspirational for most agents. |

---

## DOC 2: PMOVES_AGENT_CLASS_TAXONOMY.md

| Field | Value |
|-------|-------|
| **What it defines** | Formal type system for 60 PMOVES agents. 4 classes (Legendary/Standard/Specialized/Utility), 7 types (Data/API/LLM/Worker/Media/Agent/UI), layer coverage (L0-L5), evolution stages (Base/Stage1/Stage2/Mega), CHIT toggle integration, canonical planes mapping, resilience attributes, invocation discipline. |
| **Model Routing** | TensorZero typed as Standard, API/LLM, Tier 2. LLM type interactions: Agent -> LLM = reasoning request via TensorZero ("Super effective"). LLM -> Data = embedding generation ("Super effective"). Evolution trigger: "Add LLM calls" = L4 (Modal) = Route through TensorZero Gateway. |
| **Embeddings** | LLM -> Data type interaction = embedding generation. No specific embedding models mentioned. |
| **Local Models** | Not directly. Llama Throughput Lab classified as Specialized LLM/Worker tier 3. |
| **HuggingFace** | Not referenced. |
| **Z.AI GLM** | Not referenced. |
| **Agent Spawning** | Invocation discipline: agents are explicitly invoked, never implicitly triggered ("no teleportation" rule). No transitive calls allowed. NATS subject ownership per agent. `invocation_policy` schema in registry. Resilience strategies: `cipher_resumable`, `idempotent_replay`, `manual_handoff`. Context budgets: small (25K), medium (50K), large (100K+). |
| **TensorZero** | Listed in type chart as Standard, API/LLM, Tier 2, Stage 1. CHIT toggles: delta=yes, kappa=no, Hz=no. Evolution trigger for LLM: route through TensorZero. Connection topology shows TensorZero between Archon and downstream research agents. |
| **Gaps/TODOs** | No explicit TODOs. Resilience patterns referenced as separate doc. CHIT toggle matrix shows many agents have minimal toggle coverage. |

---

## DOC 3: BOTZ_GATEWAY_AGENT_INTEGRATION.md

| Field | Value |
|-------|-------|
| **What it defines** | Integration architecture between BoTZ Gateway (work item distribution, port 8054) and Gateway Agent (MCP tool orchestration, port 8100). Conclusion: services are complementary, not duplicates. |
| **Model Routing** | Both services route through TensorZero at `http://tensorzero-gateway:3030`. Work items routed via NATS subjects. |
| **Embeddings** | Not directly referenced. |
| **Local Models** | Cipher Memory container uses `VENICE_API_KEY` suggesting local/cloud hybrid inference. |
| **HuggingFace** | Not referenced. |
| **Z.AI GLM** | Not referenced. |
| **Agent Spawning** | High relevance. Gateway Agent can spawn BoTZ CLI instances via mprocs API (port 4050). Skill level tiers: basic -> tac_enabled -> mcp_augmented -> agentic. BoTZ Gateway manages CLI instance registration (pull model). |
| **TensorZero** | Central LLM gateway for both services. `TENSORZERO_URL` env var configured. |
| **Gaps/TODOs** | Credential sharing to BoTZ CLI instances not implemented. mprocs integration medium priority. Health check consolidation not done. NATS subjects `botz.gateway.tool.executed.v1` proposed but not implemented. A2A protocol low priority. |

---

## DOC 4: CODEX_CIPHER_MEMORY_IMPLEMENTATION_MAP.md

| Field | Value |
|-------|-------|
| **What it defines** | Map of Codex and Cipher Memory integration points. Documents onboarding, bootstrap scripts, Make targets, layered audit extensions, and Cipher Memory resilience categories. Operator hygiene snapshot for worktrees. |
| **Model Routing** | Not referenced. |
| **Embeddings** | Not referenced. |
| **Local Models** | Not directly. Cipher Memory is L2 recovery backbone. |
| **HuggingFace** | Not referenced. |
| **Z.AI GLM** | Not referenced. |
| **Agent Spawning** | Indirect. Cipher Memory resilience categories: `agent_plan` (7-day TTL), `agent_checkpoint` (3-day TTL), `agent_completion` (30-day TTL). Per-agent declarations in `agent_registry.yaml`. |
| **TensorZero** | Not referenced. |
| **Gaps/TODOs** | Cipher MCP `pyproject.toml` build issue fixed (commit `17cc8706`). Dirty worktrees need triage. Conflict worktrees need resolution before new features. |

---

## DOC 5: MODEL_SOURCE_OF_TRUTH.md (THE KEY DOC)

| Field | Value |
|-------|-------|
| **What it defines** | **Canonical model routing policy document.** PMOVES.AI is model-agnostic by design. TensorZero is the single routing point. Defines 9 TensorZero role names. Model Spotlight strength profiling (6 dimensions). CHIT-Distilled model pipeline. Hardware-tier-specific model recommendations. |
| **Model Routing** | **Definitive.** Flow: Agent Code -> POST `/v1/chat/completions` with model=`role_name` -> TensorZero Gateway -> routing table lookup -> concrete model based on hardware + load + capability. Strength-aware selection. |
| **Embeddings** | **High.** Role `embed` (Qwen3-Embedding-4B/8B, BGE-Large). Role `hirag_rerank` (Qwen3-Reranker-4B, Jina-Reranker-v2). First-class TensorZero role names. |
| **Local Models** | **High.** Examples: Qwen2.5-14B/32B/72B, Mixtral-8x22B, Phi-3-Mini, Gemma-2-2B, DeepSeek-Coder-6.7B, Qwen2-VL-7B. Hardware tiers: CPU, consumer GPU, workstation, multi-GPU in `models_by_tier.yaml`. |
| **HuggingFace** | **High.** CHIT-Distilled pipeline publishes to DARKXSIDE org: `pmoves-chit-text`, `pmoves-chit-multimodal`, `pmoves-agent-traces`. 3 PMOVES-built model templates: `pmoves-chit-text-7b`, `pmoves-chit-multi-7b`, `pmoves-agent-dpo-7b`. Dataset catalog in `datasets.yaml`. |
| **Z.AI GLM** | Not explicitly named in this doc. Models lean toward Qwen/DeepSeek/Mixtral. |
| **Agent Spawning** | Not directly. |
| **TensorZero** | **Central and definitive.** Single routing point. Observability: TensorZero -> OTLP -> ClickHouse -> Supabase -> Grafana. Every inference logged to ClickHouse. |
| **Gaps/TODOs** | Automated training loop (EvoSwarm->CHIT->AgentGym->HF->Spotlight) future. Image/audio CHIT lanes not done. MACA consensus future. Model seasons future. OTLP export currently disabled. Automated hourly ClickHouse aggregation not running. NATS model milestone events future. Hyperdimensions strength viz future. User preference learning future. |

---

## DOC 6: provider_catalog.yaml (lines 1-100)

| Field | Value |
|-------|-------|
| **What it defines** | **Single source of truth for provider activation.** Schema: provider slug -> env var -> key validation -> API base -> TensorZero provider type -> tier -> coding_stack -> models with deterministic function assignments (function, variant_name, role primary/secondary/fallback, weight 0.0-1.0) -> embedding_models. |
| **Model Routing** | **Core routing config.** Deterministic `serves` declarations map models to TensorZero functions with explicit variant names, roles, and weights. Provider cascade: deterministic for known models, fit-score for unknowns. |
| **Embeddings** | `embedding_models` section per provider with `model_name` and `tz_model_key`. OpenAI has `text-embedding-3-small` configured. |
| **Local Models** | Not in first 100 lines (local providers appear later). |
| **HuggingFace** | Not in first 100 lines. |
| **Z.AI GLM** | Not in first 100 lines (appears at line 290+). |
| **Agent Spawning** | Not referenced. |
| **TensorZero** | **Core integration.** `tz_type` maps to TensorZero provider types. `tz_model_key` maps to `[models.<key>]` in tensorzero.toml. Weights control TZ routing. |
| **Gaps/TODOs** | Claude Sonnet 4 `strength_ref: null` needs seed entry. Some model weights at 0.0 (available but not active). |

---

## DOC 7: model_nexus.yaml (lines 1-150)

| Field | Value |
|-------|-------|
| **What it defines** | **Provider Parity Registry** — additive contract layer over TensorZero-first model fabric. Canonical request shapes (`nexus.chat.v1`, `nexus.embed.v1`), execution order (tensorzero -> native_sdk -> openai_compatible), exemption rules, adapter contracts. |
| **Model Routing** | **Architecture-level routing.** Default: TensorZero. Execution: tensorzero -> native_sdk -> openai_compatible. Native SDK lanes require explicit owner and validation. Provider strategies: `native_sdk_first` (OpenAI/Anthropic/Gemini), `tensorzero_or_direct` (NVIDIA NIM), `tensorzero_first` (Ollama). |
| **Embeddings** | Canonical embedding shape `nexus.embed.v1` defined. |
| **Local Models** | **High.** Three local providers: NVIDIA NIM (llama-3_1-nemotron-nano-8b, nemotron-3-nano-30b, llama-3_3-nemotron-super-49b), Ollama (local-first, offline dev, tensorzero_first), vLLM (openai_compatible, local_http). |
| **HuggingFace** | Not referenced. |
| **Z.AI GLM** | Not in lines 1-150. |
| **Agent Spawning** | Not referenced. |
| **TensorZero** | **Central.** Default gateway role. Centralized routing, unified telemetry, experiment hooks, shared secrets. `observability_mode` for all providers references TensorZero. `fallback_lane: tensorzero` for most. |
| **Gaps/TODOs** | Contract version 1 — may evolve. Exemption rules suggest ongoing parity validation work. |

---

## DOC 8: PMOVES-BoTZ.md (Submodule Codex Home)

| Field | Value |
|-------|-------|
| **What it defines** | Codex Home Overlay for PMOVES-BoTZ submodule. Scope: BoTZ agent lifecycle, MCP gateway parity, role orchestration. Use-when conditions for MCP servers, tool catalogs, skills marketplace. |
| **Model Routing** | Not directly. |
| **Embeddings** | Not referenced. |
| **Local Models** | Not referenced. |
| **HuggingFace** | Not referenced. |
| **Z.AI GLM** | Not referenced. |
| **Agent Spawning** | Indirect. BoTZ agent lifecycle management. References `skill-pairings.yaml` and `submodule_skill_registry.json` for skill/tool assignment. |
| **TensorZero** | Not directly. |
| **Gaps/TODOs** | None. Short navigation document. |

---

## DOC 9: Pmoves-cipher.md (Submodule Codex Home)

| Field | Value |
|-------|-------|
| **What it defines** | Codex Home Overlay for Pmoves-cipher submodule. Scope: Cipher memory service parity for store/search/reasoning traces. Use-when: durable memory across sessions, PR waves, agent handoffs. |
| **Model Routing** | Not referenced. |
| **Embeddings** | Not referenced. |
| **Local Models** | Not referenced. |
| **HuggingFace** | Not referenced. |
| **Z.AI GLM** | Not referenced. |
| **Agent Spawning** | Indirect — memory-backed tool traces support agent handoffs and checkpoint/resume. |
| **TensorZero** | Not referenced. |
| **Gaps/TODOs** | None. Short navigation document. |

---

## DOC 10: tensorzero/ directory

| Field | Value |
|-------|-------|
| **What it defines** | **TensorZero gateway runtime configuration.** Contains: `clickhouse/` (observability SQL/XML configs), `config/functions/orchestrator/` (system prompt template + structured output schema), `config/tensorzero.toml` (1208-line main gateway config with models, providers, routing, functions, variants, embedding models), `config/tools/web_search.json`. |
| **Model Routing** | **Definitive runtime config.** Explicit routing chains per model. Provider entries define type, api_base, model_name, api_key_location. Updated 2026-03-15 with Qwen 3.5 + LFM2 family. |
| **Embeddings** | Embedding models configured (referenced by provider_catalog entries). |
| **Local Models** | **Primary focus.** 15+ local models via Ollama at `http://pmoves-ollama:11434/v1`. Edge models at `http://jetson-ollama:11434/v1`. Models: qwen35_9b, qwen35_4b, qwen35_27b, qwen35_0.8b, lfm2_24b_a2b, qwen2_5_32b, qwen2_5_14b, qwen2_vl_7b, qwen3_reranker_4b, nemotron_mini, qwen3_8b, and more. |
| **HuggingFace** | Models are HF-sourced (Qwen, LFM2, Nemotron) served through Ollama. |
| **Z.AI GLM** | **Not present in tensorzero.toml** (cloud section covers OpenAI, Groq, Moonshot, OpenRouter). Needs verification that GLM variants from provider_catalog are wired into TOML functions. |
| **Agent Spawning** | Not referenced. |
| **TensorZero** | **This IS the TensorZero configuration.** |
| **Gaps/TODOs** | OTLP export disabled. Z.AI GLM models in provider_catalog but need verification in tensorzero.toml. OpenRouter provider availability varies by account. |

---

## CROSS-CUTTING ALIGNMENT MATRIX

| Focus Area | Status | Key Documents | Primary Gap |
|---|---|---|---|
| **Model Routing** | Well-defined, TensorZero-first | MODEL_SOURCE_OF_TRUTH, provider_catalog.yaml, model_nexus.yaml, tensorzero.toml | Provider cascade for unknown models needs approval workflow; fit-score not fully automated |
| **Embeddings** | Defined as first-class roles | MODEL_SOURCE_OF_TRUTH, provider_catalog.yaml, tensorzero.toml | Embedding model wiring in tensorzero.toml functions not fully audited against provider_catalog |
| **Local Models** | Comprehensive, 15+ models | tensorzero.toml, model_nexus.yaml, MODEL_SOURCE_OF_TRUTH | Image/audio CHIT lanes not implemented; edge/Jetson models need production hardening |
| **HuggingFace** | Pipeline defined, partially built | MODEL_SOURCE_OF_TRUTH | Automated training loop not built; MACA consensus pending; model templates seeded but not trained |
| **Z.AI GLM** | Defined in provider_catalog but gap in tensorzero.toml | provider_catalog.yaml (line 290+), memories (coding plan config) | **Critical gap: GLM variants in provider_catalog may not be wired into tensorzero.toml functions/variants** |
| **Agent Spawning** | Architecture defined, partially implemented | BOTZ_GATEWAY_AGENT_INTEGRATION, PMOVES_AGENT_CLASS_TAXONOMY | mprocs dynamic scaling not implemented; A2A protocol low priority; no automated context-limit-triggered spawning |
| **TensorZero** | Central hub, well-integrated | All config docs | OTLP export disabled; automated ClickHouse aggregation not running; hourly refresh cycle manual |

---

## RECOMMENDED PROJECT PLAN ACTIONS

### Critical (P0)
1. **Audit Z.AI GLM wiring** — Verify all GLM models from provider_catalog.yaml are present as providers+variants in tensorzero.toml
2. **Enable OTLP export** — Requires OTel collector running; unlocks full observability pipeline
3. **Seed Claude Sonnet 4 strength_ref** — Null entry in provider_catalog needs model_strengths_seed.yaml entry

### High (P1)
4. **Embedding model audit** — Cross-reference provider_catalog embedding_models with tensorzero.toml embedding configs
5. **mprocs integration** — Wire Gateway Agent to mprocs API for dynamic BoTZ CLI scaling
6. **Automated ClickHouse refresh** — n8n or cron hourly refresh_model_strengths() pipeline

### Medium (P2)
7. **CHIT image/audio lanes** — Implement Pillow/torchvision and torchaudio CHIT encoding
8. **Model milestone NATS events** — `model.milestone.reached.v1` when models hit request/token thresholds
9. **User preference learning** — Feedback loop into routing weights
10. **Hyperdimensions strength viz** — Visualize model strength profiles in control plane

### Low (P3)
11. **MACA consensus** — CHIT reconstruction quality validation
12. **Model seasons** — Periodic retraining with EvoSwarm parameters
13. **Soulbound tokens** — Shape attribution + geometry proofs for published models
14. **A2A protocol** — Agent-to-agent communication standard
