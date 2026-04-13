# Model Onboarding via HuggingFace MCP

Operational runbook for adding new LLM / multimodal models to the PMOVES.AI
registry using the HuggingFace MCP tools as the verification layer.

> Last updated: 2026-04-13

---

## Overview

PMOVES.AI routes all model calls through TensorZero, backed by a multi-file
registry (gpu-models, flare namespace, Supabase seed, TensorZero config,
provider catalog). Adding a new model touches 4-5 files in lockstep. This
runbook describes how to use the HF MCP (`claude_ai_Hugging_Face` plugin) to
verify model metadata BEFORE writing registry edits — avoiding the class of
error where a repo ID, license, or parameter count is wrong in the registry
because nobody checked upstream.

**When to use HF MCP:**
- Adding a new open-weights model (Gemma, Qwen, Llama, Mistral, Nemotron)
- Verifying license compatibility (Apache 2.0 / MIT / Gemma / BSD preferred)
- Confirming context length, parameter count, or VRAM budget claims
- Cross-referencing benchmark papers for quality tier placement

**When to skip HF MCP:**
- Adding a cloud-only provider (OpenAI, Anthropic, Alibaba DashScope) —
  metadata lives on the provider's API docs, not HF
- Bumping an existing model's weight or quantization (use git history)

---

## Pre-onboarding checklist

Before touching any registry file, capture these values and write them
into your PR description:

1. **License** — Apache 2.0 / MIT / Gemma / BSD-3 / non-commercial?
   PMOVES will not ship non-commercial licenses to production.
2. **Parameter count** — total and effective (for MoE, document active params)
3. **Context length** — training ctx vs deployment ctx
4. **Modalities** — text, vision, audio, video, any-to-any
5. **Quantization options** — Q4_K_M, Q8_0, FP16, BF16, AWQ
6. **VRAM budget estimation:**
   - Q4 Q_K_M rough rule: `params_billions × 0.6 GB`
   - FP16 rough rule: `params_billions × 2 GB`
   - Add ~2GB headroom for KV cache at 32K context
7. **Node affinity** — which PMOVES nodes can actually host this?
   (5090 / 4090 / z890 / jetson / dgx-spark / rdna4)
8. **Ollama tag** — `ollama pull <model>:<tag>` — confirm the tag exists

---

## HF MCP tool reference

The `claude_ai_Hugging_Face` plugin exposes these tools:

### `mcp__claude_ai_Hugging_Face__hub_repo_details`

Fetch metadata for one or more HF repo IDs. Repo IDs are CASE-SENSITIVE
(`google/gemma-4-E4B-it`, not `google/gemma-4-e4b-it`).

```
mcp__claude_ai_Hugging_Face__hub_repo_details(
  repo_ids=["google/gemma-4-31B-it", "google/gemma-4-E4B-it"],
  repo_type="model",
  include_readme=false
)
```

Returns: parameter count, architecture, last-updated date, license,
demo spaces, inference providers, tags. Failed lookups return
`Error: Model '<id>' not found` — useful for confirming a repo doesn't
exist under a guessed ID.

### `mcp__claude_ai_Hugging_Face__paper_search`

Semantic search on HF papers. Use for finding benchmark context
(LMArena scores, MMLU, AIME, SWE-Bench numbers).

```
mcp__claude_ai_Hugging_Face__paper_search(
  query="Gemma 4 31B benchmarks LMArena",
  results_limit=5,
  concise_only=true
)
```

### `mcp__claude_ai_Hugging_Face__hf_doc_search`

Search HF product docs. Useful for verifying the `inference_providers`
table of a model card (which endpoint supports it natively).

```
mcp__claude_ai_Hugging_Face__hf_doc_search(
  query="Transformers gemma4 example usage",
  product="transformers"
)
```

---

## Registry update checklist (5 files)

For each new model, update **all** of these files in a single atomic commit:

1. **`pmoves/config/gpu-models.yaml`** — GPU VRAM catalog
   Fields: `id`, `provider`, `vram_mb`, `description`, `priority_default`,
   `quantization`, `context_length`
2. **`pmoves/configs/flare-model-namespace.yaml`** — operator-facing flare aliases
   Fields: `flare_name`, `provider`, `model_id`, `lane`, `nodes`
3. **`pmoves/supabase/initdb/12_model_registry_seed.sql`** — Supabase seed for
   agent cascade / strength lookups. Insert inside the existing `DO $$`
   block matching the provider (e.g. `v_ollama_local_id` for Ollama models).
   Use `ON CONFLICT (provider_id, model_id) DO UPDATE SET` for idempotency.
4. **`pmoves/tensorzero/config/tensorzero.toml`** — TensorZero routing:
   - `[models.<key>]` block with `routing = [...]` and provider sub-block
   - `[functions.<fn>.variants.<key>]` blocks — ALWAYS at `weight = 0.0`
     for safe rollout (operators flip weights manually after validation)
5. **`pmoves/config/provider_catalog.yaml`** — ONLY when adding a new
   PROVIDER (not per-model). Local Ollama-routed models do not need
   catalog entries — they're reachable via the existing `ollama_local`
   TensorZero provider.

---

## Safe rollout pattern

New TensorZero function variants MUST be introduced at `weight = 0.0`.
This makes the variant discoverable via `GET /v1/models` without routing
any traffic to it. Operators increase the weight manually after:

1. Model pulled onto the target node (`ollama pull <tag>` or GGUF download)
2. Health check succeeds via `make -C pmoves <node>-health`
3. Smoke test passes via `curl http://localhost:3030/v1/chat/completions`
4. No regression in existing function behavior

Existing variant weights MUST NOT be touched when adding a new variant.
The incumbent stays at whatever weight it had; the new variant joins at 0.

---

## Worked example — adding Gemma 3n E4B (historical)

Gemma 3n E4B was onboarded in PRs #1211 / #1212 via the HF MCP workflow.
The process was:

### Step 1 — Verify via HF MCP

```
mcp__claude_ai_Hugging_Face__hub_repo_details(
  repo_ids=["google/gemma-3n-E4B-it"],
  repo_type="model"
)
```

Returned: 8B params, Apache 2.0, `gemma3n` architecture, any-to-any
multimodal, updated 2025-07-14. Confirmed `gemma3n:e4b` exists on Ollama.

### Step 2 — Calculate VRAM budget

`8B × 0.6 = 4.8 GB` (Q4_K_M). PMOVES registered at **3500 MB** based on
Google's published "Effective 4B" footprint — E4B architecture uses
Per-Layer Embeddings to reduce active RAM vs total params. Always trust
the model card's "effective" footprint over the naive parameter math.

### Step 3 — Write the 4 registry files

See `pmoves/config/gpu-models.yaml` lines 240-247 for the final entry.
TensorZero variant lives in `[functions.multimodal_edge.variants.gemma_3n_e4b]`
at `weight = 1.0` (promoted to primary after validation).

### Step 4 — Verification

```
curl http://localhost:3030/v1/models | grep gemma_3n_e4b_local
make -C pmoves verify-all
```

### Forward reference — Gemma 4

PR #1226 (2026-04-13) onboards the Gemma 4 family (E2B / E4B / 26B-A4B / 31B)
using the same HF MCP workflow. Repo IDs:

- `google/gemma-4-E2B-it` — Effective 2B, 128K ctx
- `google/gemma-4-E4B-it` — Effective 4B, 128K ctx, any-to-any
- `google/gemma-4-26B-A4B-it` — 26B total / 3.8B active MoE, 256K ctx
- `google/gemma-4-31B-it` — 32.7B dense, 256K ctx, LMArena 1452

All Apache 2.0. PR #1226 introduces a new `multimodal_large` TensorZero
function to house 26B-A4B and 31B variants separately from `multimodal_edge`.

---

## Post-onboarding verification

Before pushing the branch:

1. **YAML parse** — `python3 -c "import yaml; yaml.safe_load(open('pmoves/config/gpu-models.yaml'))"`
   (repeat for flare-model-namespace.yaml, any other YAML touched)
2. **TOML parse** — `python3 -c "import tomllib; tomllib.load(open('pmoves/tensorzero/config/tensorzero.toml','rb'))"`
3. **SQL syntax check** — `psql -c "BEGIN; \i pmoves/supabase/initdb/12_model_registry_seed.sql; ROLLBACK;"`
   (explicit transaction rollback; never use `--dry-run`, psql has no such flag)
4. **`git diff --stat`** — should show only the files you intended

After merging:

1. **TensorZero catalog** — `curl -sf http://localhost:3030/v1/models | jq '.data[].id' | grep <new-model-key>`
2. **`make -C pmoves verify-all`** — full smoke test suite
3. **Pull the model on target nodes** — `make -C pmoves <node>-model-pull`
   or `ollama pull <tag>` via SSH

---

## Reference links

- [HuggingFace MCP plugin](https://github.com/huggingface/mcp-hub-tools) — tool source
- [Gemma 4 blog](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/)
- [Welcome Gemma 4 (HF)](https://huggingface.co/blog/gemma4)
- `pmoves/config/provider_catalog.yaml` — canonical provider schema
- `pmoves/docs/operations/TOPOLOGY.md` — node affinity reference
- `.claude/CLAUDE.md` — section "Credential & Secrets Management" for
  env var conventions when a new provider requires an API key
