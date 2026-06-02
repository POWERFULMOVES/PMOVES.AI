---
name: model:pull
description: >
  Pull local inference models (Hermes V4, Gemma4 embed, NeMo Omni, Unsloth GGUF variants)
  via Ollama or HuggingFace CLI. Node-aware routing: ≥70B → SPARK only; 8B → any node with
  Ollama; embedding models → Z890/RDNA4/Spark; NeMo Omni → Spark only.
  Use /model:pull <model-id> or describe what you want to pull.
disable-model-invocation: true
---

# model:pull

Pull models from the Phase D catalog into local Ollama or HuggingFace cache.

## Models

| Flare ID | Ollama tag | HuggingFace ID | Node |
|----------|-----------|----------------|------|
| `pmoves/hermes-v4-8b` | `hermes3:8b` | `NousResearch/Hermes-3-Llama-3.1-8B` | dgx-spark, 5090, 4090, rdna4 |
| `pmoves/hermes-v4-70b` | `hermes3:70b` | `NousResearch/Hermes-3-Llama-3.1-70B` | dgx-spark only |
| `pmoves/gemma4-embed-text` | n/a | `google/gemma-embedding-exp-03-07` | z890, spark, rdna4 |
| `pmoves/nemo-omni-vl` | n/a | `nvidia/NVLM-D-72B` | dgx-spark only |

Unsloth variants (GGUF, optimized for local inference):
- `unsloth/Hermes-3-Llama-3.1-8B` — 4090/5090 friendly
- `unsloth/Hermes-3-Llama-3.1-70B` — Spark only

## Commands

**Ollama (8B on local node):**
```bash
ollama pull hermes3:8b
```

**Ollama (70B, Spark):**
```bash
ssh pmoves-spark "ollama pull hermes3:70b"
```

**HuggingFace — Gemma4 embedding (Z890 or Spark):**
```bash
huggingface-cli download google/gemma-embedding-exp-03-07 --local-dir ~/.cache/huggingface/gemma4-embed
```

**HuggingFace — Unsloth Hermes 8B GGUF:**
```bash
huggingface-cli download unsloth/Hermes-3-Llama-3.1-8B --local-dir ~/.cache/huggingface/hermes-v4-8b
```

**HuggingFace — NeMo Omni VL (Spark, requires NeMo >= 2.1):**
```bash
huggingface-cli download nvidia/NVLM-D-72B --local-dir ~/.cache/huggingface/nemo-omni-vl
```

## Node routing rules

- **dgx-spark** (`pmoves-spark`): All models, primary for 70B+ and NeMo Omni
- **5090 / 4090**: 8B models only via Ollama; Unsloth GGUF preferred
- **rdna4** (`pmoves-rdna4`): 8B via Ollama + ROCm; Gemma4 embed via HF sentence-transformers
- **z890**: Gemma4 embed only (no GPU large-model inference)

## Verification

After pulling Hermes V4 8B:
```bash
ollama run hermes3:8b "respond: ready" --nowordwrap
```

Check TensorZero variant weight (staging, 0.0 until soak passes):
```bash
curl http://localhost:3030/api/v1/variants | jq '.[] | select(.name | contains("hermes_v4"))'
```
