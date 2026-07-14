---
name: model-pull
description: >
  Pull local inference models (Hermes V4, Qwen3 embed, Gemma 4 multimodal, NeMo Omni,
  Unsloth GGUF variants) via Ollama or HuggingFace CLI. Node-aware routing: ≥70B → SPARK
  only; 8B → any node with Ollama; embedding models → Z890/RDNA4/Spark; multimodal (text/image/audio in, text out)
  → Spark/5090/4090; NeMo Omni → Spark only.
  Use /model-pull <model-id> or describe what you want to pull.
disable-model-invocation: true
---

# model-pull

Pull models from the Phase D catalog into local Ollama or HuggingFace cache.

## License policy (verified on HF, 2026-07)

Every model in this table is **license-verified on the Hugging Face Hub** and open for
commercial use (Apache-2.0 / MIT / permissive) per the open-source-only policy. Two rows
are flagged `⚠ verify` — their upstream licenses (Llama Community, NVIDIA) are **not** the
permissive class and must be license-checked against the policy before a production pull.

> **Legacy Gemma retired.** Gemma 2 / Gemma 3 / `embeddinggemma-300m` carry `license:gemma`
> (Google Gemma Terms of Use — gated, prohibited-use policy) and are **NOT** open-source-policy
> compliant. **Gemma 4** (E2B/E4B/31B/26B-A4B, released 2026, `license:apache-2.0`, ungated) is
> the compliant successor and the only Gemma family this skill pulls.

## Models

| Flare ID | Ollama tag | HuggingFace ID | HF license | Node |
|----------|-----------|----------------|-----------|------|
| `pmoves/qwen3-embed-0.6b` | n/a | `Qwen/Qwen3-Embedding-0.6B` | apache-2.0 | z890, rdna4, 4090 |
| `pmoves/qwen3-embed-4b` | n/a | `Qwen/Qwen3-Embedding-4B` | apache-2.0 | dgx-spark, 5090 |
| `pmoves/gemma4-e4b` | `gemma4:e4b` | `google/gemma-4-E4B-it` | apache-2.0 | dgx-spark, 5090, 4090 |
| `pmoves/gemma4-31b` | `gemma4:31b` | `google/gemma-4-31B-it` | apache-2.0 | dgx-spark only |
| `pmoves/qwen3-coder-30b` | n/a | `Qwen/Qwen3-Coder-30B-A3B-Instruct` | apache-2.0 | dgx-spark, 5090 |
| `pmoves/hermes-v4-8b` | `hermes3:8b` | `NousResearch/Hermes-3-Llama-3.1-8B` | ⚠ verify (Llama 3.1 Community) | dgx-spark, 5090, 4090, rdna4 |
| `pmoves/hermes-v4-70b` | `hermes3:70b` | `NousResearch/Hermes-3-Llama-3.1-70B` | ⚠ verify (Llama 3.1 Community) | dgx-spark only |
| `pmoves/nemo-omni-vl` | n/a | `nvidia/NVLM-D-72B` | ⚠ verify (NVIDIA — may be CC-BY-NC) | dgx-spark only |

Unsloth variants (GGUF, optimized for local inference):
- `unsloth/Hermes-3-Llama-3.1-8B` — 4090/5090 friendly (⚠ inherits Llama 3.1 Community license)
- `unsloth/Hermes-3-Llama-3.1-70B` — Spark only (⚠ inherits Llama 3.1 Community license)

## Commands

**HuggingFace — Qwen3 embedding, 0.6B (Z890 / RDNA4 / 4090):**
```bash
huggingface-cli download Qwen/Qwen3-Embedding-0.6B --local-dir ~/.cache/huggingface/qwen3-embed-0.6b
```

**HuggingFace — Qwen3 embedding, 4B (Spark / 5090):**
```bash
huggingface-cli download Qwen/Qwen3-Embedding-4B --local-dir ~/.cache/huggingface/qwen3-embed-4b
```

**Ollama — Gemma 4 E4B (text + image input; GGUF via Ollama):**
```bash
ollama pull gemma4:e4b
```
> The Ollama tag `gemma4:e4b` serves **text + image input, text output** only — its
> model card lists `Text, Image input`. For **audio-input** Gemma 4 usage, serve the
> full weights via HF/transformers or vLLM (`google/gemma-4-E4B-it`), not the Ollama tag.

**Ollama (8B on local node):**
```bash
ollama pull hermes3:8b
```

**Ollama (70B, Spark):**
```bash
ssh pmoves-spark "ollama pull hermes3:70b"
```

**HuggingFace — Unsloth Hermes 8B GGUF:**
```bash
huggingface-cli download unsloth/Hermes-3-Llama-3.1-8B --local-dir ~/.cache/huggingface/hermes-v4-8b
```

**HuggingFace — NeMo Omni VL (Spark, requires NeMo >= 2.1; ⚠ verify license first):**
```bash
huggingface-cli download nvidia/NVLM-D-72B --local-dir ~/.cache/huggingface/nemo-omni-vl
```

## Node routing rules

- **dgx-spark** (`pmoves-spark`): All models, primary for 70B+, Gemma 4 31B, and NeMo Omni
- **5090 / 4090**: 8B models via Ollama (Unsloth GGUF preferred); Gemma 4 E4B (text+image via Ollama); Qwen3-Embedding-4B on 5090
- **rdna4** (`pmoves-rdna4`): 8B via Ollama + ROCm; Qwen3-Embedding-0.6B via HF sentence-transformers
- **z890**: Qwen3-Embedding-0.6B only (no GPU large-model inference)

## Verification

After pulling Hermes V4 8B:
```bash
ollama run hermes3:8b "respond: ready" --nowordwrap
```

After pulling a Qwen3 embedding (sentence-transformers loads directly):
```bash
python -c "from sentence_transformers import SentenceTransformer; \
m=SentenceTransformer('Qwen/Qwen3-Embedding-0.6B'); print(m.encode(['ready']).shape)"
```

Check TensorZero variant weight (staging, 0.0 until soak passes):
```bash
curl http://localhost:3030/api/v1/variants | jq '.[] | select(.name | contains("hermes_v4"))'
```
