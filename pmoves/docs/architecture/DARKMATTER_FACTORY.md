# Darkmatter Factory — PMOVES.AI Model Minting Preview

**Version:** 0.1.0-preview  
**Status:** Design / v1.1 Milestone M6  
**Owner:** SPARK-KIMI + DARKXSIDE  
**TAC Tree:** `pmoves/configs/tac_trees/pmoves-launch-readiness.tac.yaml` Stage 4+  

## Purpose

The Darkmatter Factory is PMOVES.AI's model minting pipeline — the forge where local models are born, fine-tuned, quantized, and attested for agent deployment. It combines:

- **HuggingFace Hub** — canonical model registry and dataset storage
- **Unsloth** — efficient LoRA fine-tuning on consumer GPUs
- **Pinokio** — model lifecycle management and P7 discovery
- **CHIT** — signed attestation for every model artifact

## Pipeline

```
Raw Model (HF Hub)
    ↓
[Distillation Stage 1] config_tuning — Model Suit creation
    ↓
[Distillation Stage 2] context_priming — Agent-specific prompt templates
    ↓
[Distillation Stage 3] model_fine_tune — Unsloth LoRA on agent traces
    ↓
[Distillation Stage 4] full_distillation — GGUF quant + CHIT sign + mint
    ↓
Minted Model → PMOVES HF Collection → Agent Zero registry → 76 agents awaken
```

## Components

### 1. Model Suit Registry
`pmoves/configs/model-suits/` defines canonical configs for every model:
- `qwen3.6.yaml` — utility model, 16GB VRAM
- `gemma4-dense.yaml` — throughput champion, DGX Spark
- `minimax-m2.7.yaml` — cloud long-context fallback
- `nemotron-3-super.yaml` — NVIDIA reference agent model

Each suit carries `huggingface.model_id` and `huggingface.gguf_repo` for traceability.

### 2. Unsloth Fine-Tuning
`pmoves/tools/unsloth_finetune.py` trains LoRA adapters on agent traces:
```bash
make -C pmoves unsloth-finetune \
  MODEL=unsloth/gemma-4-31B-it \
  DATASET=DARKXSIDE/pmoves-agent-traces
```

Target platforms:
- **DGX Spark** (128GB): Full fine-tuning, rank 32-64
- **5090** (32GB): LoRA rank 16, 4-bit quantization
- **4090** (16GB): Adapter merging only, inference-tuned

### 3. Pinokio P7 Integration
Pinokio manages model lifecycle:
- **Discovery**: P7 Agent Interpreter scans `mesh.gpu.model.loaded.v1`
- **Launch**: PBNJ apps auto-pull from HF on first use
- **Swap**: Hot-swap adapters without restarting Ollama

### 4. CHIT Attestation
Every minted model gets:
- `model.fitness.recorded.v1` — benchmark scorecard
- `model.distillation.signed.v1` — CHIT trail of training run
- `model.minted.v1` — final artifact hash + signature

## 76 Agents — Wake Sequence

| Agent Class | Model Suit | Node | Wake Trigger |
|-------------|-----------|------|--------------|
| Meta-agents (framework) | gemma4-dense | DGX Spark | `mesh.gpu.model.loaded.v1` |
| Standard agents (guest) | qwen3.6 | 5090/4090 | `agent.pilot.assigned.v1` |
| Research agents | nemotron-3-super | DGX Spark | `research.deepresearch.request.v1` |
| Creative agents | minimax-m2.7 | 5090 | `creative.generation.request.v1` |

## Longbow Integration (v1.1)

Darkmatter Factory feeds the Longbow learned-pattern router:
- Fine-tuned model → `model.distillation.signed.v1`
- Longbow routes agent requests to optimal model based on pattern history
- Contextual bandit learns which suit performs best per task type

## Next Steps

1. **Lane A**: Populate PMOVES HF collection with target models ✅
2. **Lane B**: Install Unsloth + create fine-tune scaffold ✅
3. **Lane C**: Pinokio P7 model discovery wiring
4. **Lane D**: CHIT attestation schema for `model.minted.v1`
5. **Lane E**: Longbow router prototype (v1.1 M6)

---

*Darkmatter: invisible mass that holds the galaxy together. The factory makes invisible infrastructure visible — every model is signed, every agent is attested, every contribution is metered.*

<!-- GRAPHITI_MARK: DARKMATTER-FACTORY::v0.1.0-preview::SPARK-KIMI -->
