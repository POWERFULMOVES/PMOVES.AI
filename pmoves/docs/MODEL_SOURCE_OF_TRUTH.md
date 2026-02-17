# Model Source of Truth

> Referenced by: `PMOVES_UNIFIED_AGENT_TAXONOMY.md`, `PMOVES_AGENT_CLASS_TAXONOMY.md`

## Principle

PMOVES.AI is **model-agnostic by design**. TensorZero is the single routing point for all LLM calls. Documentation, architecture descriptions, and runtime code must use **role names**, not concrete model IDs.

## TensorZero Role Names

| Role | Purpose | Example Concrete Models (for sizing only) |
|------|---------|------------------------------------------|
| `orchestrator` | Complex reasoning, task planning, architecture | Qwen2.5-14B/32B/72B, Mixtral-8x22B |
| `utility` | Fast simple tasks, safety checks, auditing | Phi-3-Mini, Qwen2.5-3B, Gemma-2-2B |
| `coding` | Code generation and analysis | Qwen2.5-Coder-7B, DeepSeek-Coder-6.7B |
| `reasoning` | Deep multi-hop logical tasks | DeepSeek-V3.1 distilled, Qwen2.5-72B |
| `embed` | Text embedding generation | Qwen3-Embedding-4B/8B, BGE-Large |
| `vl_sentinel` | Vision-language processing | Qwen2-VL-7B, Qwen3-VL-8B |
| `hirag_rerank` | Cross-encoder reranking for RAG | Qwen3-Reranker-4B, Jina-Reranker-v2 |
| `research` | Deep research, coordinator tasks | Qwen2.5-32B/72B |

## Where Concrete Model Names Are Acceptable

| Context | Acceptable? | Reason |
|---------|------------|--------|
| Hardware sizing docs (`HARDWARE_TTS_REQUIREMENTS.md`) | Yes | VRAM calculations need exact parameters |
| Model setup guides (`LOCAL_MODEL_SETUP.md`) | Yes | `ollama pull` commands need exact IDs |
| Config files (`pmoves/config/models.yaml`) | Yes | Canonical model catalog |
| Historical footnotes / Works Cited | Yes | Academic attribution |
| Architecture descriptions | **No** | Use role names |
| Taxonomy definitions | **No** | Use role names |
| API examples in docs | **No** | Use `"model": "orchestrator"` |
| Runtime code | **No** | Use TensorZero role routing |

## Canonical Config Files

- **`pmoves/config/models.yaml`** — Master catalog of local models with HuggingFace mappings, hardware requirements, and role assignments
- **`pmoves/config/models_by_tier.yaml`** — Hardware-tier-specific model recommendations (CPU, consumer GPU, workstation, multi-GPU)

## How Runtime Routing Works

```
Agent Code                    TensorZero Gateway              Model Backend
─────────────                 ──────────────────              ─────────────
POST /v1/chat/completions     Receives role name              Routes to concrete
  model: "orchestrator"   →   Looks up routing table      →   model based on
                              (hardware profile +              current config
                               load balancing)
```

Agents never specify concrete model names at runtime. TensorZero resolves the role to the best available model based on:
1. Hardware profile (CPU, consumer GPU, workstation, multi-GPU)
2. Current load and availability
3. Model capability requirements (context length, multimodal, etc.)

## Cross-References

- Agent registry: `pmoves/config/agent_registry.yaml`
- Agent taxonomy: `pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md`
- Unified taxonomy: `pmoves/docs/AGENTS/PMOVES_UNIFIED_AGENT_TAXONOMY.md`
- Hardware sizing: `pmoves/docs/AGENTS/HARDWARE_TTS_REQUIREMENTS.md`
- Local setup: `pmoves/docs/PMOVESCHIT/LOCAL_MODEL_SETUP.md`
