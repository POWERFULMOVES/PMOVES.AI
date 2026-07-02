# Cloud-Hybrid HERMES + Agent Zero Provider Standup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up node-aware HERMES Agent + Agent Zero on Knuckles routed through TensorZero, with cloud coding plans as the orchestrator tier and local sibling models as the worker tier, delivered as 3 stacked PRs.

**Architecture:** TensorZero (:3030 host / tensorzero-gateway:3000 in-network) is the single router. Cloud coding plans (z.ai, Moonshot/Kimi, Alibaba, Kilo Code, Ollama Pro) serve orchestrator functions; local sibling models (Ollama ROCm + llama.cpp-RDNA4 on :8090) serve worker functions. `pmoves/config/provider_catalog.yaml` is the provider source of truth; `pmoves/configs/model-suits/` is the per-model parameter canon. Agent Zero is already TZ-wired in compose (`A0_SET_chat_model_name=tensorzero::function_name::agent_zero`) — it needs bring-up plus a worker function, not rewiring.

**Tech Stack:** TensorZero TOML config, provider_catalog.yaml + `pmoves/tools/provider_cascade.py`, Hermes Agent v0.15.1 (`providers:` keyed config schema), docker compose (`agents` profile), Ollama ROCm, llama.cpp gfx1201 fork (`tlee933/llama.cpp-rdna4-gfx1201`), Pinokio launcher, pytest.

## Global Constraints

- Canonical env var names come from `pmoves/config/provider_catalog.yaml`: `Z_AI_API_KEY`, `MOONSHOT_API_KEY`, `ALIBABA_PRO_CODING_PLAN`. New: `KILOCODE_API_KEY`, `OLLAMA_API_KEY`, `HF_TOKEN`. `KIMI_API_KEY`/`ALIBABA_API_KEY`/`ZAI_API_KEY`/`DASHSCOPE_API_KEY` are documentation aliases only.
- Every PR < 400 lines; commit format `<type>(<scope>): <subject>`; scopes per HERMES_ATOMIC_COMMITS (`hermes-profile`, `hermes-tac`, `hermes-docs`) plus `providers`, `tensorzero`, `pinokio`.
- All new TZ variants land with catalog-declared weights; brand-new cloud variants start `weight = 0.0` (safe-rollout convention already used in this file) and are activated via `provider_cascade.py activate`.
- NEVER commit or print secret values. `pmoves/env.tier-llm` is zero-access (damage-control hook). `~/.hermes/**` `.env`/`auth.json` never enter git. NATS credentials in docs/config committed to git must be `${NATS_URL}`-style, never literal.
- Tests: `cd pmoves && python -m pytest tests/ -q` must pass before each PR.
- Agent identity for AGNOTE entries: `B850-CLAUDE`. Claim before edits, release after merge (`pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`).
- Repo git identity already set locally (`POWERFULMOVES <142271328+POWERFULMOVES@users.noreply.github.com>`).
- Base branch for PRs: `main`. Live-host steps (hermes CLI, ollama, docker) run on the host from the main checkout regardless of worktree.
- TZ endpoint from host: `http://127.0.0.1:3030/openai/v1`. From compose network: `http://tensorzero-gateway:3000/openai/v1`. Model-name syntax through the OpenAI surface: `tensorzero::function_name::<fn>`.
- llama.cpp server on Knuckles binds **:8090** (8080 is Agent Zero's; the existing `llamacpp_rocm` blocks say 8080 but carry `weight = 0.0` everywhere, so moving them is safe and required).
- Spec deviations (documented): (1) no new `pmoves_embed` function — Agent Zero already consumes the existing `[embedding_models.gemma_embed_local]` (YAGNI); (2) Alibaba canonical env is `ALIBABA_PRO_CODING_PLAN` per `provider_catalog.yaml` (declared single source of truth), not the spec's `DASHSCOPE_API_KEY`, which becomes an alias.

---

## PR 1 — feat(providers): cloud-hybrid provider tier + worker siblings

Branch: `feat/provider-cloud-hybrid-tier`

### Task 1: Claim the lane and cut the branch

**Files:**
- Modify: `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (Active Claim Register section)

**Interfaces:**
- Produces: an active CLAIM row other agents can see; branch `feat/provider-cloud-hybrid-tier`.

- [ ] **Step 1: Read the claim register format**

Run: `grep -n "CLAIM" pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md | tail -5`
Expected: existing CLAIM/RELEASE lines showing the current format (agent, branch, scope, timestamp).

- [ ] **Step 2: Append a CLAIM entry matching the existing format exactly**

Content (adapt field order to the file's format):

```
CLAIM :: B850-CLAUDE :: feat/provider-cloud-hybrid-tier + feat/hermes-knuckles-standup + feat/pinokio-llamacpp-launcher :: HERMES/A0 cloud-hybrid provider standup (TAC phase_3_b850_knuckles) :: 2026-07-02
```

- [ ] **Step 3: Commit the claim on main and cut the branch**

```bash
git add pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md
git commit -m "docs(agnote): B850-CLAUDE claims cloud-hybrid provider standup lane"
git checkout -b feat/provider-cloud-hybrid-tier
```

### Task 2: Add kilocode, ollama_cloud, huggingface to provider_catalog.yaml

**Files:**
- Modify: `pmoves/config/provider_catalog.yaml` (append after the `ollama_spark:` provider block)

**Interfaces:**
- Consumes: existing catalog schema (header comment documents it).
- Produces: provider slugs `kilocode`, `ollama_cloud`, `huggingface` with `tz_model_key`s `chat_kilocode`, `chat_ollama_cloud_glm52`, `chat_hf_router` that Task 3 defines in TOML and Task 6's drift test asserts.

- [ ] **Step 1: Verify live model IDs before writing (no guessed model names)**

```bash
# Kilo Code is OpenRouter-compatible; list models (no key needed for the catalog list on most gateways — if 401, note it and keep the qwen coder id below):
curl -s https://kilocode.ai/api/openrouter/models | python3 -c "import json,sys; d=json.load(sys.stdin); print([m['id'] for m in d.get('data',[])][:20])" || echo "VERIFY-AT-ACTIVATION"
# HF router model list:
curl -s https://router.huggingface.co/v1/models | python3 -c "import json,sys; d=json.load(sys.stdin); print([m['id'] for m in d.get('data',[])][:20])" || echo "VERIFY-AT-ACTIVATION"
```

Expected: JSON id lists. Use a coding-capable id present in each list; defaults below are `qwen/qwen3-coder` (Kilo) and `Qwen/Qwen2.5-Coder-32B-Instruct` (HF). If the curl shows the id absent, substitute the closest Qwen-coder id from the live list and use it consistently in Task 3.

- [ ] **Step 2: Append the three provider entries**

```yaml
  # ---------------------------------------------------------------------------
  # Kilo Code — coding plan (OpenRouter-compatible gateway)
  # ---------------------------------------------------------------------------
  kilocode:
    env_var: KILOCODE_API_KEY
    key_pattern: ".*"
    api_base: "https://kilocode.ai/api/openrouter"
    tz_type: openai
    tier: llm
    coding_stack: kilocode_plan
    models:
      chat_kilocode:
        model_name: "qwen/qwen3-coder"
        tz_model_key: chat_kilocode
        serves:
          - function: pmoves_orchestrator_coding
            variant_name: cloud_kilocode
            role: secondary
            weight: 0.0
          - function: agent_zero
            variant_name: hosted_kilocode
            role: fallback
            weight: 0.0
        strength_ref: qwen3_coder
        vram_mb: 0

  # ---------------------------------------------------------------------------
  # Ollama Cloud — Ollama Pro plan (hosted models at ollama.com)
  # ---------------------------------------------------------------------------
  ollama_cloud:
    env_var: OLLAMA_API_KEY
    key_pattern: ".*"
    api_base: "https://ollama.com/v1"
    tz_type: openai
    tier: llm
    models:
      chat_ollama_cloud_glm52:
        model_name: "glm-5.2"
        tz_model_key: chat_ollama_cloud_glm52
        serves:
          - function: pmoves_orchestrator_chat
            variant_name: cloud_ollama_glm52
            role: primary
            weight: 0.0
          - function: pmoves_orchestrator_coding
            variant_name: cloud_ollama_glm52
            role: fallback
            weight: 0.0
        strength_ref: glm_5_2
        vram_mb: 0

  # ---------------------------------------------------------------------------
  # HuggingFace Inference Router — fallback + Unsloth weights source
  # ---------------------------------------------------------------------------
  huggingface:
    env_var: HF_TOKEN
    key_pattern: "^hf_"
    api_base: "https://router.huggingface.co/v1"
    tz_type: openai
    tier: llm
    models:
      chat_hf_router:
        model_name: "Qwen/Qwen2.5-Coder-32B-Instruct"
        tz_model_key: chat_hf_router
        serves:
          - function: pmoves_orchestrator_coding
            variant_name: cloud_hf_router
            role: fallback
            weight: 0.0
        strength_ref: qwen25_coder_32b
        vram_mb: 0
```

- [ ] **Step 3: Validate YAML parses**

Run: `python3 -c "import yaml; yaml.safe_load(open('pmoves/config/provider_catalog.yaml')); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pmoves/config/provider_catalog.yaml
git commit -m "feat(providers): add kilocode, ollama_cloud, huggingface to provider catalog"
```

### Task 3: TensorZero — new cloud models, worker sibling models, orchestrator + worker functions, :8090 port fix

**Files:**
- Modify: `pmoves/tensorzero/config/tensorzero.toml`

**Interfaces:**
- Consumes: `tz_model_key`s from Task 2; existing model keys `chat_zai_glm51`, `chat_moonshot`, `chat_alibaba_qwen`, `coding_qwen3_coder_30b_local`.
- Produces: functions `pmoves_orchestrator_coding`, `pmoves_orchestrator_chat`, `pmoves_worker_glm`, `pmoves_worker_qwen`, `pmoves_worker_hermes`, `pmoves_worker_kimi`; models `chat_kilocode`, `chat_ollama_cloud_glm52`, `chat_hf_router`, `glm4_9b_local`, `hermes3_8b_local`, `kimi_dev_72b_rocm`. Task 6's drift test and Task 9's Hermes profile reference these exact names.

- [ ] **Step 1: Move llamacpp_rocm blocks from :8080 to :8090**

Run: `grep -c "pmoves-9850x3d-r9700:8080" pmoves/tensorzero/config/tensorzero.toml`
Expected: 4 (or current count). Then:

```bash
sed -i 's|http://pmoves-9850x3d-r9700:8080/v1|http://pmoves-9850x3d-r9700:8090/v1|g' pmoves/tensorzero/config/tensorzero.toml
```

Add a comment above the first `llamacpp_rocm` block (near line ~470):

```toml
# Port 8090: 8080 is reserved for Agent Zero fleet-wide (HERMES_AGENT_INTEGRATION.md).
```

- [ ] **Step 2: Append new cloud model blocks (after the MiniMax/GLM blocks, ~line 320)**

```toml
# --- Kilo Code (coding plan, OpenRouter-compatible gateway) ---
[models.chat_kilocode]
routing = ["kilocode_primary"]

[models.chat_kilocode.providers.kilocode_primary]
type = "openai"
api_base = "https://kilocode.ai/api/openrouter"
model_name = "qwen/qwen3-coder"
api_key_location = "env::KILOCODE_API_KEY"

# --- Ollama Cloud (Ollama Pro plan — hosted glm-5.2) ---
[models.chat_ollama_cloud_glm52]
routing = ["ollama_cloud_primary"]

[models.chat_ollama_cloud_glm52.providers.ollama_cloud_primary]
type = "openai"
api_base = "https://ollama.com/v1"
model_name = "glm-5.2"
api_key_location = "env::OLLAMA_API_KEY"

# --- HuggingFace Inference Router (fallback) ---
[models.chat_hf_router]
routing = ["hf_router_primary"]

[models.chat_hf_router.providers.hf_router_primary]
type = "openai"
api_base = "https://router.huggingface.co/v1"
model_name = "Qwen/Qwen2.5-Coder-32B-Instruct"
api_key_location = "env::HF_TOKEN"
```

- [ ] **Step 3: Append worker sibling local models (next to `coding_qwen3_coder_30b_local`)**

```toml
# --- Worker siblings (cloud-hybrid: local autonomous versions of cloud parents) ---
# Sibling of z.ai GLM coding plan (chat_zai_glm51)
[models.glm4_9b_local]
routing = ["ollama_local"]

[models.glm4_9b_local.providers.ollama_local]
type = "openai"
api_base = "http://pmoves-ollama:11434/v1"
model_name = "glm4:9b"
api_key_location = "none"

# Sibling of Ollama Pro / OpenRouter hermes family
[models.hermes3_8b_local]
routing = ["ollama_local"]

[models.hermes3_8b_local.providers.ollama_local]
type = "openai"
api_base = "http://pmoves-ollama:11434/v1"
model_name = "hermes3:8b"
api_key_location = "none"

# Sibling of Moonshot Kimi coding plan — Kimi-Dev-72B Q4 row-split on dual R9700
# PENDING VALIDATION on gfx1201; weight stays 0.0 until llama-server soak passes.
[models.kimi_dev_72b_rocm]
routing = ["llamacpp_rocm"]

[models.kimi_dev_72b_rocm.providers.llamacpp_rocm]
type = "openai"
api_base = "http://pmoves-9850x3d-r9700:8090/v1"
model_name = "Kimi-Dev-72B-Q4_K_M.gguf"
api_key_location = "none"
```

- [ ] **Step 4: Append orchestrator + worker functions (end of `[functions]` region)**

Temperature/max_tokens values come from the model suits (coding = 0.2, chat = 0.7, 8192 out — Task 5 encodes the same numbers; Task 6 asserts they match).

```toml
# =====================================================================
# Cloud-hybrid tiers (2026-07-02): cloud coding plans orchestrate;
# local siblings work. Sibling escalation is same-family only.
# =====================================================================

[functions.pmoves_orchestrator_coding]
type = "chat"

[functions.pmoves_orchestrator_coding.variants.cloud_zai_glm51]
type = "chat_completion"
model = "chat_zai_glm51"
temperature = 0.2
max_tokens = 8192
weight = 1.0

[functions.pmoves_orchestrator_coding.variants.cloud_kimi]
type = "chat_completion"
model = "chat_moonshot"
temperature = 0.2
max_tokens = 8192
weight = 0.0

[functions.pmoves_orchestrator_coding.variants.cloud_alibaba]
type = "chat_completion"
model = "chat_alibaba_qwen"
temperature = 0.2
max_tokens = 8192
weight = 0.0

[functions.pmoves_orchestrator_coding.variants.cloud_kilocode]
type = "chat_completion"
model = "chat_kilocode"
temperature = 0.2
max_tokens = 8192
weight = 0.0

[functions.pmoves_orchestrator_coding.variants.cloud_ollama_glm52]
type = "chat_completion"
model = "chat_ollama_cloud_glm52"
temperature = 0.2
max_tokens = 8192
weight = 0.0

[functions.pmoves_orchestrator_coding.variants.cloud_hf_router]
type = "chat_completion"
model = "chat_hf_router"
temperature = 0.2
max_tokens = 8192
weight = 0.0

[functions.pmoves_orchestrator_chat]
type = "chat"

[functions.pmoves_orchestrator_chat.variants.cloud_ollama_glm52]
type = "chat_completion"
model = "chat_ollama_cloud_glm52"
temperature = 0.7
max_tokens = 8192
weight = 1.0

[functions.pmoves_orchestrator_chat.variants.cloud_zai_glm51]
type = "chat_completion"
model = "chat_zai_glm51"
temperature = 0.7
max_tokens = 8192
weight = 0.0

# --- Worker functions: local sibling primary, same-family cloud parent fallback ---

[functions.pmoves_worker_glm]
type = "chat"

[functions.pmoves_worker_glm.variants.local_glm4_9b]
type = "chat_completion"
model = "glm4_9b_local"
temperature = 0.2
max_tokens = 8192
weight = 1.0

[functions.pmoves_worker_glm.variants.parent_zai_glm51]
type = "chat_completion"
model = "chat_zai_glm51"
temperature = 0.2
max_tokens = 8192
weight = 0.0

[functions.pmoves_worker_qwen]
type = "chat"

[functions.pmoves_worker_qwen.variants.local_qwen3_coder_30b]
type = "chat_completion"
model = "coding_qwen3_coder_30b_local"
temperature = 0.2
max_tokens = 8192
weight = 1.0

[functions.pmoves_worker_qwen.variants.parent_alibaba_qwen]
type = "chat_completion"
model = "chat_alibaba_qwen"
temperature = 0.2
max_tokens = 8192
weight = 0.0

[functions.pmoves_worker_hermes]
type = "chat"

[functions.pmoves_worker_hermes.variants.local_hermes3_8b]
type = "chat_completion"
model = "hermes3_8b_local"
temperature = 0.7
max_tokens = 8192
weight = 1.0

[functions.pmoves_worker_kimi]
type = "chat"

# Local sibling pending gfx1201 validation — parent carries weight until then.
[functions.pmoves_worker_kimi.variants.local_kimi_dev_72b]
type = "chat_completion"
model = "kimi_dev_72b_rocm"
temperature = 0.2
max_tokens = 8192
weight = 0.0

[functions.pmoves_worker_kimi.variants.parent_moonshot]
type = "chat_completion"
model = "chat_moonshot"
temperature = 0.2
max_tokens = 8192
weight = 1.0
```

- [ ] **Step 5: Validate TOML parses**

Run: `python3 -c "import tomllib; tomllib.load(open('pmoves/tensorzero/config/tensorzero.toml','rb')); print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add pmoves/tensorzero/config/tensorzero.toml
git commit -m "feat(tensorzero): cloud-hybrid orchestrator/worker functions + kilocode/ollama-cloud/hf models; llamacpp_rocm to :8090"
```

### Task 4: Env plumbing — tier example, tier manifest, canonical aliases

**Files:**
- Modify: `pmoves/env.tier-llm.example`
- Modify: `pmoves/tools/fix_tier_manifest.py` (the `"env.tier-llm"` mapping dict starting ~line 25)
- Modify: `pmoves/bootstrap/registry.json` (`canonical_aliases` block)

**Interfaces:**
- Produces: env slots `KILOCODE_API_KEY`, `OLLAMA_API_KEY`, `HF_TOKEN`, `ALIBABA_PRO_CODING_PLAN` that the secrets funnel fills; aliases mapping legacy names → canonical.

- [ ] **Step 1: Add slots to `pmoves/env.tier-llm.example`** (in the "OPTIONAL: Additional Provider Keys" section, after `MOONSHOT_API_KEY=`)

```bash
# Kilo Code coding plan — https://kilocode.ai (OpenRouter-compatible)
KILOCODE_API_KEY=

# Ollama Pro (cloud) — https://ollama.com/settings/keys
OLLAMA_API_KEY=

# HuggingFace router / hub token — https://huggingface.co/settings/tokens
HF_TOKEN=

# Alibaba coding plan (DashScope key; canonical name per provider_catalog.yaml —
# DASHSCOPE_API_KEY above is the legacy alias)
ALIBABA_PRO_CODING_PLAN=
```

- [ ] **Step 2: Extend the tier manifest in `pmoves/tools/fix_tier_manifest.py`**

Open the dict that maps keys to `["env.tier-llm"]` (line ~25) and add, keeping alphabetical placement with the neighbors:

```python
    "ALIBABA_PRO_CODING_PLAN": ["env.tier-llm"],
    "DASHSCOPE_API_KEY": ["env.tier-llm"],
    "HF_TOKEN": ["env.tier-llm"],
    "KILOCODE_API_KEY": ["env.tier-llm"],
    "MOONSHOT_API_KEY": ["env.tier-llm"],
    "OLLAMA_API_KEY": ["env.tier-llm"],
    "Z_AI_API_KEY": ["env.tier-llm"],
```

(Only add entries not already present — check with `grep -n "MOONSHOT\|Z_AI" pmoves/tools/fix_tier_manifest.py` first.)

- [ ] **Step 3: Add canonical aliases to `pmoves/bootstrap/registry.json`**

Inspect the existing structure first: `python3 -c "import json; print(json.dumps(json.load(open('pmoves/bootstrap/registry.json'))['canonical_aliases'], indent=2)[:800])"`

Append entries **matching the existing element shape exactly** for:
- `KIMI_API_KEY` → `MOONSHOT_API_KEY`
- `ALIBABA_API_KEY` → `ALIBABA_PRO_CODING_PLAN`
- `DASHSCOPE_API_KEY` → `ALIBABA_PRO_CODING_PLAN`
- `ZAI_API_KEY` → `Z_AI_API_KEY`
- `HUGGINGFACE_TOKEN` → `HF_TOKEN`

- [ ] **Step 4: Validate + run the naming-drift gate**

```bash
python3 -c "import json; json.load(open('pmoves/bootstrap/registry.json')); print('OK')"
make -C pmoves naming-drift-check || true   # advisory; note any NEW findings caused by this change and fix
```

- [ ] **Step 5: Commit**

```bash
git add pmoves/env.tier-llm.example pmoves/tools/fix_tier_manifest.py pmoves/bootstrap/registry.json
git commit -m "feat(providers): env slots + tier manifest + canonical aliases for kilocode/ollama-cloud/hf/alibaba"
```

### Task 5: Worker model suits (the "glove")

**Files:**
- Create: `pmoves/configs/model-suits/glm-4-9b-worker.yaml`
- Create: `pmoves/configs/model-suits/qwen3-coder-30b-worker.yaml`
- Create: `pmoves/configs/model-suits/hermes3-8b-worker.yaml`
- Create: `pmoves/configs/model-suits/kimi-dev-72b-worker.yaml`

**Interfaces:**
- Consumes: suit schema from `pmoves/configs/model-suits/glm-5.1.yaml` (`suit:` + `model_config:` blocks).
- Produces: suits with `tier: worker`, `sibling_of: <parent suit id>`, `tz_model_key: <TZ model>` — Task 6's drift test reads exactly these three fields plus `model_config`.

- [ ] **Step 1: Write `glm-4-9b-worker.yaml`**

```yaml
# Model Suit: GLM-4 9B (local worker sibling of GLM-5.1 cloud parent)
# PMOVES.AI cloud-hybrid worker tier — Knuckles (dual R9700, ROCm)

suit:
  id: glm-4-9b-worker
  name: GLM-4 9B Worker (Ollama local)
  provider: ollama_local
  model_family: glm
  tier: worker
  sibling_of: glm-5.1
  tz_model_key: glm4_9b_local
  role: subagent-worker

model_config:
  context_window: 128000
  max_output_tokens: 8192
  supports_vision: false
  supports_extended_thinking: false
  supports_function_calling: true
  temperature_range: [0.0, 1.0]
  default_temperature: 0.2
  top_p_range: [0.0, 1.0]
  top_k: null
```

- [ ] **Step 2: Write `qwen3-coder-30b-worker.yaml`**

```yaml
# Model Suit: Qwen3-Coder 30B MoE (local worker sibling of Alibaba qwen3-coder-plus)
# PMOVES.AI cloud-hybrid worker tier — Knuckles (dual R9700, ROCm)

suit:
  id: qwen3-coder-30b-worker
  name: Qwen3-Coder 30B Worker (Ollama local)
  provider: ollama_local
  model_family: qwen
  tier: worker
  sibling_of: qwen3.6
  tz_model_key: coding_qwen3_coder_30b_local
  role: subagent-worker

model_config:
  context_window: 262144
  max_output_tokens: 8192
  supports_vision: false
  supports_extended_thinking: false
  supports_function_calling: true
  temperature_range: [0.0, 1.0]
  default_temperature: 0.2
  top_p_range: [0.0, 1.0]
  top_k: null
```

- [ ] **Step 3: Write `hermes3-8b-worker.yaml`**

```yaml
# Model Suit: Hermes-3 Llama-3.1 8B (local worker; NousResearch agent-native family)
# PMOVES.AI cloud-hybrid worker tier — Knuckles (dual R9700, ROCm)

suit:
  id: hermes3-8b-worker
  name: Hermes-3 8B Worker (Ollama local)
  provider: ollama_local
  model_family: hermes
  tier: worker
  sibling_of: null   # cloud parent via OpenRouter/Ollama Pro pool, no dedicated suit yet
  tz_model_key: hermes3_8b_local
  role: subagent-worker

model_config:
  context_window: 131072
  max_output_tokens: 8192
  supports_vision: false
  supports_extended_thinking: false
  supports_function_calling: true
  temperature_range: [0.0, 1.0]
  default_temperature: 0.7
  top_p_range: [0.0, 1.0]
  top_k: null
```

- [ ] **Step 4: Write `kimi-dev-72b-worker.yaml`**

```yaml
# Model Suit: Kimi-Dev-72B Q4 (local worker sibling of Moonshot Kimi coding plan)
# PENDING VALIDATION: gfx1201 row-split via llama.cpp fork; weight 0.0 in TZ until soak.

suit:
  id: kimi-dev-72b-worker
  name: Kimi-Dev 72B Worker (llama.cpp ROCm row-split)
  provider: llamacpp_rocm
  model_family: kimi
  tier: worker
  sibling_of: null   # parent = chat_moonshot (no dedicated moonshot suit file yet)
  tz_model_key: kimi_dev_72b_rocm
  role: subagent-worker
  status: pending-validation

model_config:
  context_window: 131072
  max_output_tokens: 8192
  supports_vision: false
  supports_extended_thinking: false
  supports_function_calling: true
  temperature_range: [0.0, 1.0]
  default_temperature: 0.2
  top_p_range: [0.0, 1.0]
  top_k: null
```

- [ ] **Step 5: Validate all four parse**

Run: `python3 -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('pmoves/configs/model-suits/*-worker.yaml')]; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add pmoves/configs/model-suits/*-worker.yaml
git commit -m "feat(providers): worker model suits with sibling linkage (glm/qwen/hermes/kimi)"
```

### Task 6: Suit↔TensorZero drift check (TDD)

**Files:**
- Create: `pmoves/tests/test_model_suit_tz_drift.py`

**Interfaces:**
- Consumes: suit fields `suit.tz_model_key`, `suit.sibling_of`, `model_config.default_temperature` from Task 5; TZ model/function names from Task 3.
- Produces: a pytest module run by the standard suite.

- [ ] **Step 1: Write the test**

```python
"""Drift gate: model suits and tensorzero.toml must agree.

Every suit that names a tz_model_key must find that model in tensorzero.toml.
Every worker suit's sibling_of must resolve to an existing suit id (or be null).
Worker-function variant temperatures must sit inside the suit's temperature_range.
"""
from __future__ import annotations

import glob
import tomllib
from pathlib import Path

import pytest
import yaml

PMOVES = Path(__file__).resolve().parents[1]
SUITS_DIR = PMOVES / "configs" / "model-suits"
TZ_TOML = PMOVES / "tensorzero" / "config" / "tensorzero.toml"


def _load_suits():
    suits = {}
    for path in glob.glob(str(SUITS_DIR / "*.yaml")):
        data = yaml.safe_load(open(path)) or {}
        suit = data.get("suit") or {}
        if suit.get("id"):
            suits[suit["id"]] = data
    return suits


def _load_tz():
    with open(TZ_TOML, "rb") as fh:
        return tomllib.load(fh)


def test_suit_tz_model_keys_exist():
    suits = _load_suits()
    tz = _load_tz()
    tz_models = set(tz.get("models", {})) | set(tz.get("embedding_models", {}))
    missing = {
        sid: s["suit"]["tz_model_key"]
        for sid, s in suits.items()
        if s["suit"].get("tz_model_key") and s["suit"]["tz_model_key"] not in tz_models
    }
    assert not missing, f"suits reference TZ models that do not exist: {missing}"


def test_worker_sibling_links_resolve():
    suits = _load_suits()
    bad = {
        sid: s["suit"]["sibling_of"]
        for sid, s in suits.items()
        if s["suit"].get("tier") == "worker"
        and s["suit"].get("sibling_of") not in (None, *suits.keys())
    }
    assert not bad, f"worker suits with dangling sibling_of: {bad}"


def test_worker_function_temperatures_within_suit_range():
    suits = _load_suits()
    tz = _load_tz()
    by_tz_key = {
        s["suit"]["tz_model_key"]: s
        for s in suits.values()
        if s["suit"].get("tz_model_key")
    }
    violations = []
    for fn_name, fn in tz.get("functions", {}).items():
        if not fn_name.startswith("pmoves_worker_"):
            continue
        for var_name, var in (fn.get("variants") or {}).items():
            suit = by_tz_key.get(var.get("model"))
            if suit is None:
                continue
            lo, hi = suit["model_config"]["temperature_range"]
            temp = var.get("temperature")
            if temp is not None and not (lo <= temp <= hi):
                violations.append((fn_name, var_name, temp, (lo, hi)))
    assert not violations, f"variant temperatures outside suit range: {violations}"
```

- [ ] **Step 2: Run the test — it must pass against Tasks 3+5 output (and fail if either is missing)**

Run: `cd pmoves && python -m pytest tests/test_model_suit_tz_drift.py -v`
Expected: 3 PASSED. To confirm the gate has teeth, temporarily rename `tz_model_key: glm4_9b_local` to `glm4_9b_localX` in the suit, re-run (expect FAIL on `test_suit_tz_model_keys_exist`), then revert.

- [ ] **Step 3: Run the full suite**

Run: `cd pmoves && python -m pytest tests/ -q`
Expected: all pass (pre-existing skips allowed).

- [ ] **Step 4: Commit**

```bash
git add pmoves/tests/test_model_suit_tz_drift.py
git commit -m "test(providers): suit-to-tensorzero drift gate (model keys, sibling links, temperature ranges)"
```

### Task 7: Open PR 1

- [ ] **Step 1: Push and open the PR**

```bash
git push -u origin feat/provider-cloud-hybrid-tier
gh pr create --title "feat(providers): cloud-hybrid provider tier — kilocode/ollama-cloud/hf + worker siblings + drift gate" --body "$(cat <<'EOF'
## Summary
- Cloud-hybrid inversion (spec: docs/superpowers/specs/2026-07-02-hermes-agent-zero-provider-standup-design.md): cloud coding plans orchestrate, local siblings work
- provider_catalog.yaml: +kilocode, +ollama_cloud, +huggingface (weight 0.0, cascade-activated)
- tensorzero.toml: pmoves_orchestrator_* + pmoves_worker_* functions; worker sibling models; llamacpp_rocm moved 8080→8090 (Agent Zero owns 8080)
- Worker model suits with sibling linkage; suit↔TZ drift gate test
- Env slots + tier manifest + canonical aliases (KIMI→MOONSHOT, ALIBABA/DASHSCOPE→ALIBABA_PRO_CODING_PLAN, ZAI→Z_AI)

## Test plan
- `cd pmoves && python -m pytest tests/test_model_suit_tz_drift.py -v` (3 pass)
- `python -m pytest tests/ -q` full suite
- TOML/YAML/JSON parse checks

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2: Verify CI green, report PR URL to operator**

---

## PR 2 — Knuckles live standup (HERMES profile + Agent Zero) — branch `feat/hermes-knuckles-standup` (stacked on PR 1)

### Task 8: Restart TensorZero with new config + secrets check

**Files:** none (live host operation)

**Interfaces:**
- Consumes: merged/checked-out PR 1 config.
- Produces: TZ gateway serving `pmoves_orchestrator_*`/`pmoves_worker_*`; a fill-list of empty provider keys for the operator.

- [ ] **Step 1: Regenerate tier env + restart TZ**

```bash
make -C pmoves secrets-funnel
docker compose -f pmoves/docker-compose.yml restart tensorzero-gateway
curl -sf http://127.0.0.1:3030/health
```

Expected: `{"gateway":"ok",...}`. If restart fails on `env::` lookups, the corresponding key is empty — record it, set a placeholder via the funnel path (never edit env.tier-llm directly), and continue.

- [ ] **Step 2: Build the operator fill-list WITHOUT reading secret values**

```bash
for k in Z_AI_API_KEY MOONSHOT_API_KEY ALIBABA_PRO_CODING_PLAN KILOCODE_API_KEY OLLAMA_API_KEY HF_TOKEN MINIMAX_API_KEY OPENROUTER_API_KEY; do
  docker compose -f pmoves/docker-compose.yml exec -T tensorzero-gateway sh -c "[ -n \"\$$k\" ] && echo \"$k: SET\" || echo \"$k: EMPTY\""
done
```

Expected: SET/EMPTY table. Report EMPTY rows to the operator (they update GH secrets / CHIT source, then `make -C pmoves secrets-funnel` again).

- [ ] **Step 3: Smoke each orchestrator function through TZ (skip EMPTY providers)**

```bash
curl -s http://127.0.0.1:3030/openai/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"tensorzero::function_name::pmoves_orchestrator_coding","messages":[{"role":"user","content":"Reply with the single word: ready"}],"max_tokens":10}' \
  | python3 -m json.tool | head -20
```

Expected: a completion (via whichever variant carries weight and has a key). Repeat with `pmoves_orchestrator_chat`.

### Task 9: Pull worker models + validate ROCm path

**Files:** none (live host operation)

**Interfaces:**
- Produces: `glm4:9b`, `hermes3:8b`, `qwen3-coder:30b` present in local Ollama; a recorded note whether Ollama uses GPU (gfx1201) or CPU on this node.

- [ ] **Step 1: Pull the siblings**

```bash
ollama pull glm4:9b && ollama pull hermes3:8b && ollama pull qwen3-coder:30b
```

Expected: three successful pulls (~2GB, ~5GB, ~19GB).

- [ ] **Step 2: Verify backend (the TZ comment warns Ollama's bundled ROCm may lack gfx1201)**

```bash
ollama run glm4:9b "Reply with: worker-online" --verbose 2>&1 | tail -5
ollama ps
rocm-smi --showuse | head -10
```

Expected: response text + tokens/sec. Record in the PR notes whether `ollama ps` shows GPU offload (`100% GPU`) or CPU. If CPU-only, workers still function (slowly); GPU-path GGUF serving arrives with the PR 3 llama.cpp launcher.

- [ ] **Step 3: Worker function smoke through TZ**

```bash
curl -s http://127.0.0.1:3030/openai/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"tensorzero::function_name::pmoves_worker_glm","messages":[{"role":"user","content":"Reply with the single word: working"}],"max_tokens":10}' \
  | python3 -m json.tool | head -20
```

Expected: completion from `glm4_9b_local`. Repeat for `pmoves_worker_qwen` and `pmoves_worker_hermes`. `pmoves_worker_kimi` routes to `chat_moonshot` (cloud parent) — smoke only if MOONSHOT_API_KEY is SET.

### Task 10: HERMES update + pmoves-hermes-knuckles profile

**Files:** live: `~/.hermes/profiles/pmoves-hermes-knuckles/config.yaml` (not committed)

**Interfaces:**
- Consumes: TZ functions from Task 8/9; Hermes `providers:` keyed schema (fields: `name`, `base_url`, `key_env`/`api_key`, `default_model`, `models`, `context_length`, `api_mode`).
- Produces: active Hermes profile `pmoves-hermes-knuckles` used by Tasks 11–12.

- [ ] **Step 1: Update Hermes (20 commits behind) and health-check**

```bash
hermes update && hermes --version && hermes doctor
```

Expected: version advances past v0.15.1; doctor reports no fatal issues (warnings about unset TTS keys acceptable).

- [ ] **Step 2: Create the profile**

```bash
hermes profile create pmoves-hermes-knuckles
hermes profile use pmoves-hermes-knuckles
```

- [ ] **Step 3: Write the profile config** — merge these keys into `~/.hermes/profiles/pmoves-hermes-knuckles/config.yaml` (keep tool-generated defaults for everything else). This mirrors repo `pmoves/config/profiles/hermes/b850.yaml` (updated in Task 13) so repo = documentation, live file = runtime:

```yaml
model:
  default: "tensorzero::function_name::pmoves_orchestrator_coding"
  provider: tensorzero
providers:
  tensorzero:
    name: tensorzero
    base_url: "http://127.0.0.1:3030/openai/v1"
    api_key: "none"
    api_mode: chat_completions
    default_model: "tensorzero::function_name::pmoves_orchestrator_coding"
    models:
      - "tensorzero::function_name::pmoves_orchestrator_coding"
      - "tensorzero::function_name::pmoves_orchestrator_chat"
      - "tensorzero::function_name::pmoves_worker_glm"
      - "tensorzero::function_name::pmoves_worker_qwen"
      - "tensorzero::function_name::pmoves_worker_hermes"
      - "tensorzero::function_name::pmoves_worker_kimi"
    context_length: 128000
fallback_providers:
  - provider: ollama
    model: "hermes3:8b"
delegation:
  model: "tensorzero::function_name::pmoves_worker_hermes"
  provider: tensorzero
  max_concurrent_children: 2
  max_iterations: 50
toolsets:
  enabled:
    - web
    - terminal
    - file
    - messaging
    - cronjob
    - code_execution
    - skills
    - memory
gateway:
  port: 7700
security:
  redact_secrets: true
```

- [ ] **Step 4: Validate**

```bash
hermes doctor
hermes chat -q "Reply with the single word: orchestrated"
```

Expected: doctor clean; chat answer arrives via TZ (confirm in TZ logs: `docker compose -f pmoves/docker-compose.yml logs --tail 5 tensorzero-gateway` shows the inference).

- [ ] **Step 5: Delegation smoke (worker sibling via trails path)**

```bash
hermes chat -q "Use delegate_task to have a subagent reply with the single word: sibling"
```

Expected: delegation runs on `pmoves_worker_hermes` (local hermes3:8b). Record latency.

### Task 11: Hermes secrets + NATS env via funnel

**Files:** live: `~/.hermes/profiles/pmoves-hermes-knuckles/.env` (never committed)

- [ ] **Step 1: Populate the profile .env from the funnel output paths** (copy only needed keys; do not cat the tier file into the terminal — use grep for key names then targeted copies via an editor, or the documented funnel helper if present):

Required keys: `NATS_URL` (authenticated form), plus any provider keys Hermes calls directly (none required when routing through TZ — TZ holds provider keys).

- [ ] **Step 2: Verify gitignore protection**

```bash
git -C ~/pinokio/api/PMOVES.AI check-ignore -v pmoves/env.tier-llm && echo TIER-IGNORED
grep -rn "hermes" .gitignore | head -3
```

Expected: tier file ignored; `.hermes` patterns present (if absent, add `**/.hermes/` to `.gitignore` in Task 13's commit).

### Task 12: Gateway launch + NATS observation + Agent Zero bring-up

**Files:** none (live host operation)

**Interfaces:**
- Produces: Hermes gateway healthy on :7700; Agent Zero healthy on :8080 answering via TZ.

- [ ] **Step 1: Start the Hermes gateway**

```bash
hermes --profile pmoves-hermes-knuckles gateway run &
sleep 8
curl -sf http://localhost:7700/api/health
```

Expected: health JSON. If port 7700 busy: `ss -ltnp | grep 7700` and stop the conflicting process.

- [ ] **Step 2: Observe NATS (authenticated URL from env, never hardcoded)**

```bash
docker run --rm --network pmoves_pmoves_bus natsio/nats-box:latest \
  sh -c 'nats --server "$NATS_URL" sub "hermes.>" --count 1 --timeout 30s' \
  2>&1 | head -5
```

Expected: one `hermes.gateway.*` message if the NATS bridge is active in this Hermes build. If Hermes v0.15+ has no native NATS publisher, record GAP: "NATS bridge = Phase 4 TAC item, publish via MCP relay pending" — do not fake it.

- [ ] **Step 3: Bring up Agent Zero**

```bash
make -C pmoves up-agents
docker ps --format '{{.Names}}\t{{.Status}}' | grep -i agent
curl -sf http://127.0.0.1:8080/healthz
```

Expected: agent-zero container healthy; `/healthz` 200. A0 already points at `tensorzero::function_name::agent_zero` (compose lines ~2631-2641) — no config change needed.

- [ ] **Step 4: A0 end-to-end smoke via MCP**

Use the `agents:status` skill (or `curl -sf http://127.0.0.1:8080/mcp/status` if exposed) and one `agents:execute` round-trip: task "Reply with the single word: zero-online".
Expected: completion routed through TZ (verify in TZ logs).

### Task 13: Repo profile updates, TAC flips, AGNOTE entry — commit PR 2

**Files:**
- Modify: `pmoves/config/profiles/hermes/b850.yaml` (full replace of `model:`/`delegation:` blocks + add `providers:` block mirroring Task 10 Step 3; keep NATS/toolsets/rocm sections)
- Modify: `pmoves/config/profiles/hermes/spark.yaml` (same TZ-first pattern; local tier = hermes3:70b primary per existing content; delegation → `pmoves_worker_hermes`)
- Modify: `pmoves/configs/tac_trees/node-hermes-agent.tac.yaml` (`hermes.integration.profile.node_b850` → `status: done`; `phase_3_b850_knuckles` → `status: DONE`; add `phase_2_spark` note "config ready, node offline 2026-07-02")
- Modify: `pmoves/docs/AGENTS/HERMES_AGENT_INTEGRATION.md` (Provider Credential Mapping table: replace Elder-Melchor Tier-1-local framing with cloud-hybrid orchestrator/worker tiers + canonical env names)
- Modify: `pmoves/docs/AGENTS/AGNOTE4482.md` (append audit record: "Cloud-Hybrid Provider Standup — Knuckles (2026-07-02)" with work performed, files, findings incl. Ollama GPU/CPU note + key fill-list, ACK `B850-CLAUDE`)

- [ ] **Step 1: Apply the five file edits** (b850.yaml model block shown; spark.yaml mirrors with its own local models)

```yaml
model:
  default: "tensorzero::function_name::pmoves_orchestrator_coding"
  provider: tensorzero
  base_url: "http://127.0.0.1:3030/openai/v1"
  fallback:
    provider: "ollama"
    model: "hermes3:8b"

delegation:
  model: "tensorzero::function_name::pmoves_worker_hermes"
  provider: tensorzero
  max_concurrent_children: 2
  max_iterations: 50
```

- [ ] **Step 2: Full test suite + drift gate**

Run: `cd pmoves && python -m pytest tests/ -q`
Expected: pass.

- [ ] **Step 3: Commit (atomic per scope) and open PR 2**

```bash
git checkout -b feat/hermes-knuckles-standup
git add pmoves/config/profiles/hermes/b850.yaml pmoves/config/profiles/hermes/spark.yaml
git commit -m "feat(hermes-profile): b850+spark v2 — TensorZero-first cloud-hybrid routing"
git add pmoves/configs/tac_trees/node-hermes-agent.tac.yaml
git commit -m "feat(hermes-tac): phase_3_b850_knuckles done; spark config-ready"
git add pmoves/docs/AGENTS/HERMES_AGENT_INTEGRATION.md pmoves/docs/AGENTS/AGNOTE4482.md
git commit -m "docs(hermes-docs): cloud-hybrid provider tiers + Knuckles standup audit record"
git push -u origin feat/hermes-knuckles-standup
gh pr create --base main --title "feat(hermes): Knuckles live standup — TZ-first profiles, TAC flips, audit record" --body "Stacked on feat/provider-cloud-hybrid-tier. Live verification evidence in AGNOTE4482.md audit record. 🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## PR 3 — Pinokio llama.cpp-ROCm launcher + SPARK runbook — branch `feat/pinokio-llamacpp-launcher`

### Task 14: Pinokio launcher for Unsloth GGUF serving

**Files:**
- Create: `pmoves/integrations/pinokio/pmoves-llamacpp-rocm/pinokio.json`
- Create: `pmoves/integrations/pinokio/pmoves-llamacpp-rocm/pinokio.js`
- Create: `pmoves/integrations/pinokio/pmoves-llamacpp-rocm/install.js`
- Create: `pmoves/integrations/pinokio/pmoves-llamacpp-rocm/start.js`
- Create: `pmoves/integrations/pinokio/pmoves-llamacpp-rocm/download-model.js`
- Create: `pmoves/integrations/pinokio/pmoves-llamacpp-rocm/reset.js`
- Create: `pmoves/integrations/pinokio/pmoves-llamacpp-rocm/update.js`
- Create: `pmoves/integrations/pinokio/pmoves-llamacpp-rocm/README.md`
- Live: symlink `~/pinokio/api/pmoves-llamacpp-rocm` → the repo folder

**MANDATORY pre-work (CLAUDE.md Pinokio execution workflow):**
1. Load `.claude/PINOKIO_LAUNCHER_GUIDE.md` and re-read `/home/pmoves-knuckles/pinokio/CLAUDE.md` §Critical Pattern Lock.
2. Destination resolution: `PINOKIO_HOME=/home/pmoves-knuckles/pinokio` (verified via `~/.pinokio/config.json` → `home`). App launchers live at `PINOKIO_HOME/api/<name>`; we author in-repo and symlink (precedent: PMOVES.AI itself lives under `api/`).
3. Example lock-in: keep `/home/pmoves-knuckles/pinokio/prototype/system/examples/mochi/start.js` open; the `start.js` URL-capture block below mirrors it — verify against the example at execution and fix any divergence in favor of the example.

**Interfaces:**
- Produces: `llama-server` on `127.0.0.1:8090` serving the selected GGUF, matching TZ `llamacpp_rocm` provider (`http://pmoves-9850x3d-r9700:8090/v1`).

- [ ] **Step 1: `pinokio.json`**

```json
{
  "title": "PMOVES llama.cpp ROCm (Unsloth GGUF)",
  "description": "Dual-R9700 row-split GGUF serving for the PMOVES worker tier. OpenAI-compatible on :8090, routed by TensorZero.",
  "icon": "icon.png"
}
```

- [ ] **Step 2: `install.js`** — clone + build the gfx1201 fork (Linux/ROCm only; declared in pinokio.json at exit-checklist if guide requires `platform` field)

```javascript
module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        message: [
          "git clone https://github.com/tlee933/llama.cpp-rdna4-gfx1201 app"
        ]
      }
    },
    {
      method: "shell.run",
      params: {
        path: "app",
        message: [
          "cmake -B build -DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201 -DCMAKE_BUILD_TYPE=Release",
          "cmake --build build --config Release -j"
        ]
      }
    }
  ]
}
```

- [ ] **Step 3: `download-model.js`** — Unsloth GGUF fetch via hf.download

```javascript
module.exports = {
  run: [
    {
      method: "input",
      params: {
        title: "Unsloth GGUF repo",
        form: [
          { key: "repo", title: "HF repo", default: "unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF" },
          { key: "file", title: "GGUF file", default: "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf" }
        ]
      }
    },
    {
      method: "hf.download",
      params: {
        path: "models",
        "_": ["{{input.repo}}"],
        "include": ["{{input.file}}"]
      }
    }
  ]
}
```

- [ ] **Step 4: `start.js`** — row-split serve + MANDATED URL-capture pattern

```javascript
module.exports = {
  daemon: true,
  run: [
    {
      method: "input",
      params: {
        title: "Model to serve",
        form: [
          { key: "gguf", title: "GGUF path (under models/)", default: "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf" }
        ]
      }
    },
    {
      method: "shell.run",
      params: {
        path: "app",
        env: { HIP_VISIBLE_DEVICES: "0,1" },
        message: [
          "./build/bin/llama-server -m ../models/{{input.gguf}} --host 127.0.0.1 --port 8090 --tensor-split 0.5,0.5 -ngl 999"
        ],
        on: [{
          event: "/(http:\\/\\/[0-9.:]+)/",
          done: true
        }]
      }
    },
    {
      method: "local.set",
      params: {
        url: "{{input.event[1]}}"
      }
    }
  ]
}
```

- [ ] **Step 5: `pinokio.js`, `reset.js`, `update.js`, `README.md`** — mirror the guide's dynamic-menu pattern (`info.exists('app')` gates install vs start; running state surfaces the captured `url` local as "Open API"; reset deletes `app/`; update `git pull` in `app/`). README documents: what it serves, TZ registration (`llamacpp_rocm` :8090), curl/Python/JS API examples against `http://127.0.0.1:8090/v1/chat/completions`.

- [ ] **Step 6: Exit checklist (mandatory)** — confirm against `.claude/PINOKIO_LAUNCHER_GUIDE.md`: destination recorded, example path cited in comments, URL captured via `local.set` from `input.event[1]`, relative paths only in `shell.run`, port not hardcoded where `{{port}}` fits better (8090 is intentional — TZ config pins it; note this exception explicitly in README).

- [ ] **Step 7: Live link + smoke**

```bash
ln -sfn ~/pinokio/api/PMOVES.AI/pmoves/integrations/pinokio/pmoves-llamacpp-rocm ~/pinokio/api/pmoves-llamacpp-rocm
# Launch install → download-model → start via Pinokio UI (or pterm start), then:
curl -s http://127.0.0.1:8090/v1/models | python3 -m json.tool
curl -s http://127.0.0.1:3030/openai/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"tensorzero::model_name::llamacpp_rdna4_gemma4_31b_q4km","messages":[{"role":"user","content":"Reply: gguf-online"}],"max_tokens":10}' | head -5
```

Expected: model list from llama-server; TZ round-trip succeeds (or records the exact failure for the soak notes).

- [ ] **Step 8: Commit**

```bash
git checkout -b feat/pinokio-llamacpp-launcher
git add pmoves/integrations/pinokio/pmoves-llamacpp-rocm/
git commit -m "feat(pinokio): llama.cpp-ROCm Unsloth GGUF launcher (dual-R9700 row-split, :8090 worker tier)"
```

### Task 15: SPARK apply runbook + retry live

**Files:**
- Create: `pmoves/docs/runbooks/SPARK_HERMES_APPLY.md`

**Interfaces:**
- Consumes: `spark.yaml` v2 from Task 13.
- Produces: operator-executable runbook.

- [ ] **Step 1: Probe SPARK once more**

```bash
tailscale status | grep -w pmoves-spark
ssh -o ConnectTimeout=5 pmoves-spark 'echo up && ollama --version' || echo "SPARK-OFFLINE"
```

If **up**: execute the runbook steps below live on SPARK (hermes install → profile `pmoves-hermes-spark` from `spark.yaml` → `ollama pull hermes3:70b hermes3:8b` → gateway health) and record evidence in the runbook's "Applied" section.
If **offline**: runbook ships with "Pending apply" status.

- [ ] **Step 2: Write the runbook** — numbered steps: (1) `curl -fsSL <hermes install.sh> | bash` + `hermes update`; (2) `hermes profile create pmoves-hermes-spark` + copy `pmoves/config/profiles/hermes/spark.yaml` → `~/.hermes/profiles/pmoves-hermes-spark/config.yaml`; (3) secrets via `make -C pmoves secrets-funnel` on SPARK checkout; (4) `ollama pull hermes3:70b && ollama pull hermes3:8b`; (5) gateway run + `curl -sf localhost:7700/api/health`; (6) TZ reachability from SPARK (`curl http://<knuckles-tailscale>:3030/health`) and note that `ollama_spark` TZ provider (`http://pmoves-gb10-spark:11434/v1`) activates automatically once SPARK's Ollama is serving; (7) verification checklist mirroring Tasks 8–12.

- [ ] **Step 3: Commit, RELEASE the claim, open PR 3**

```bash
git add pmoves/docs/runbooks/SPARK_HERMES_APPLY.md
git commit -m "docs(hermes-docs): SPARK apply runbook (pending node online)"
# RELEASE entry in pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md matching the CLAIM from Task 1:
git add pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md
git commit -m "docs(agnote): B850-CLAUDE releases cloud-hybrid standup lane"
git push -u origin feat/pinokio-llamacpp-launcher
gh pr create --base main --title "feat(pinokio)+docs(spark): Unsloth llama.cpp launcher + SPARK apply runbook" --body "Stacked on feat/hermes-knuckles-standup. 🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

### Task 16: Signoff + operator handoff

- [ ] **Step 1: Tick verified items in `pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md` HERMES section** (add the section if absent, per TAC `hermes.integration.docs.signoff`): room manifest untouched (pre-existing ✓), NATS subjects catalogued (pre-existing ✓), gateway health (this session's evidence), CHIT secrets flow documented, profile configs reviewed for b850+spark. Only tick what was actually verified; the NATS-bridge GAP (if found in Task 12) stays unticked with a note.

- [ ] **Step 2: Final report to operator** — PR links, key fill-list (EMPTY providers), Ollama GPU/CPU finding, Kimi-Dev-72B validation status, SPARK applied-or-pending, and the exact next commands for them (GH secret names + `make -C pmoves secrets-funnel`).
