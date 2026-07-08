# Provider Key Inventory + Status Checklist

**Generated:** 2026-07-09
**Scope:** Complete inventory of all LLM provider API keys for PMOVES.AI cloud-hybrid tier
**Audience:** DARKXSIDE (key custodian), DevOps, Agent Zero orchestrator
**Pipeline:** local.env / CHIT source -> `make -C pmoves secrets-funnel`
**Source of truth:** `pmoves/config/provider_catalog.yaml` + `pmoves/docs/operations/CANONICAL_NAMES.md`

---

## Executive Summary

| Metric | Count |
|--------|-------|
| **Total keys inventoried** | 22 |
| **Keys MISSING (empty on node)** | 8 (critical) |
| **Keys SUNSET (deprecated aliases)** | 4 |
| **Keys ACTIVE (populated)** | 0 |
| **Born canonical (no aliases)** | 3 |
| **Naming inconsistencies found** | 5 |

---

## Critical Gap: AGNOTE4482 Keys (ALL EMPTY)

The following 8 keys are the priority fill from AGNOTE4482 (B850-CLAUDE, 2026-07-03).
The entire LLM tier is unset; the last CI chit-bundle has expired.

| # | Canonical Key | Status | Provider | Sunset |
|---|--------------|--------|----------|--------|
| 1 | `Z_AI_API_KEY` | **MISSING** | Zhipu AI (Z.AI) | Alias ZAI_API_KEY: 2026-10-01 |
| 2 | `MOONSHOT_API_KEY` | **MISSING** | Moonshot AI (Kimi) | Alias KIMI_API_KEY: 2026-10-01 |
| 3 | `ALIBABA_PRO_CODING_PLAN` | **MISSING** | Alibaba/DashScope | Aliases ALIBABA_API_KEY, DASHSCOPE_API_KEY: 2026-10-01 |
| 4 | `KILOCODE_API_KEY` | **MISSING** | Kilo Code | Born canonical 2026-07-02 |
| 5 | `OLLAMA_API_KEY` | **MISSING** | Ollama Pro (cloud) | Born canonical 2026-07-02 |
| 6 | `HF_TOKEN` | **MISSING** | HuggingFace Router | Alias HUGGINGFACE_TOKEN: 2026-10-01 |
| 7 | `MINIMAX_API_KEY` | **MISSING** | MiniMax Token Plan | No sunset |
| 8 | `OPENROUTER_API_KEY` | **MISSING** | OpenRouter | No sunset |

---

## Detailed Key Inventory

### 1. Z_AI_API_KEY (Zhipu AI / Z.AI / GLM Coding Plan)

| Attribute | Value |
|-----------|-------|
| **Canonical name** | `Z_AI_API_KEY` |
| **Deprecated aliases** | `ZAI_API_KEY` (sunset: 2026-10-01) |
| **Key pattern** | `.*` (per provider_catalog.yaml) |
| **API base** | `https://api.z.ai/api/coding/paas/v4` |
| **TensorZero type** | `openai` |
| **Provider slug** | `zai` |
| **Status** | **MISSING** |
| **Tier** | `llm` |
| **Coding stack** | `glm_coding_plan` |

**Model suits using this key:**
| Model Suit | Role | File |
|------------|------|------|
| `glm-4-plus` | Premium quality, complex reasoning | `pmoves/configs/model-suits/glm-4-plus.yaml` |
| `glm-4.7` | Balanced performance, coding-specialized | `pmoves/configs/model-suits/glm-4.7.yaml` |
| `glm-5.1` | Long-horizon autonomy, sustained engineering | `pmoves/configs/model-suits/glm-5.1.yaml` |
| `glm-4-air` | Efficient mid-tier | `pmoves/configs/model-suits/glm-4-air.yaml` |
| `glm-4-flash` | Fast, cost-effective | `pmoves/configs/model-suits/glm-4-flash.yaml` |
| `glm-5-turbo` | Tool-calling optimized | `pmoves/configs/model-suits/glm-5-turbo.yaml` |
| `kimi-k2` | TensorZero function reference | `pmoves/configs/model-suits/kimi-k2.yaml` |

**TensorZero functions served:**
- `agent_zero` (variants: hosted_zai, hosted_glm_flash, hosted_zai_turbo, hosted_zai_vision_turbo)
- `coding_glm` (variants: cloud_zai_glm_flash, cloud_zai_glm51, cloud_zai_turbo, cloud_zai_vision_turbo)
- `orchestrator` (variant: primary_cloud_turbo)
- `agent_zero_subordinate` (variant: hosted_zai_turbo)
- `archon_work_orders` (variant: hosted_zai_turbo)
- `deepresearch` (variants: hosted_zai_turbo, hosted_zai_vision_turbo)
- `vl_sentinel` (variant: vision_glm5v_turbo)

**NATS subjects:**
- `mesh.gpu.model.loaded.v1` (local fallback publication)

**How to obtain:** https://z.ai/manage-apikey/apikey-list

---

### 2. MOONSHOT_API_KEY (Moonshot AI / Kimi)

| Attribute | Value |
|-----------|-------|
| **Canonical name** | `MOONSHOT_API_KEY` |
| **Deprecated aliases** | `KIMI_API_KEY` (sunset: 2026-10-01) |
| **Key pattern** | `.*` (per provider_catalog.yaml) |
| **API base** | `https://api.moonshot.ai/v1` |
| **TensorZero type** | `openai` |
| **Provider slug** | `moonshot` |
| **Status** | **MISSING** |
| **Tier** | `llm` |

**Model suits using this key:**
| Model Suit | Role | File |
|------------|------|------|
| `kimi-k2` | Long-context, Chinese-language specialist | `pmoves/configs/model-suits/kimi-k2.yaml` |

**TensorZero functions served:**
- `agent_zero` (variant: hosted_moonshot)
- `langextract` (variant: langextract_moonshot)

**NATS subjects:**
- `pmoves.worker.kimi.*`

**How to obtain:** https://platform.moonshot.ai/console/api-keys

---

### 3. ALIBABA_PRO_CODING_PLAN (Alibaba / DashScope / Qwen)

| Attribute | Value |
|-----------|-------|
| **Canonical name** | `ALIBABA_PRO_CODING_PLAN` |
| **Deprecated aliases** | `ALIBABA_API_KEY`, `DASHSCOPE_API_KEY` (sunset: 2026-10-01) |
| **Key pattern** | `^sk-[a-f0-9]{32}` (DashScope keys: sk- + 32 hex) |
| **API base** | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| **TensorZero type** | `openai` |
| **Provider slug** | `alibaba` |
| **Status** | **MISSING** |
| **Tier** | `llm` |
| **Coding stack** | `alibaba_coding_plan` |

**Model suits using this key:**
- No dedicated model suit file; used via `qwen3-coder-plus` model in provider_catalog.yaml

**TensorZero functions served:**
- `agent_zero` (variant: hosted_alibaba_qwen)
- `langextract` (variant: langextract_alibaba_qwen)
- `agent_zero_subordinate` (variant: hosted_alibaba_qwen)
- `pmoves_research_coordinator` (variant: hosted_alibaba_qwen)
- `archon_work_orders` (variant: hosted_alibaba_qwen)
- `archon_code_review` (variant: hosted_alibaba_qwen)
- `coding_claude_fallback` (variant: cloud_alibaba)
- `coding_alibaba` (variant: cloud_alibaba, **primary**)
- `coding` (variant: fallback_alibaba_qwen)
- `deepresearch` (variant: hosted_alibaba_qwen)

**How to obtain:** https://dashscope.console.aliyun.com/

---

### 4. KILOCODE_API_KEY (Kilo Code)

| Attribute | Value |
|-----------|-------|
| **Canonical name** | `KILOCODE_API_KEY` |
| **Deprecated aliases** | None (born canonical 2026-07-02) |
| **Key pattern** | `.*` (per provider_catalog.yaml) |
| **API base** | `https://api.kilocode.ai/api/openrouter` |
| **TensorZero type** | `openai` |
| **Provider slug** | `kilocode` |
| **Status** | **MISSING** |
| **Tier** | `llm` |
| **Coding stack** | `kilocode_plan` |

**Model suits using this key:**
- No dedicated model suit; Kilo routes via `kilo-auto/balanced` plan

**TensorZero functions served:**
- `pmoves_orchestrator_coding` (variant: cloud_kilocode, **secondary**)

**How to obtain:** https://api.kilocode.ai (OpenRouter-compatible gateway)

---

### 5. OLLAMA_API_KEY (Ollama Pro Cloud)

| Attribute | Value |
|-----------|-------|
| **Canonical name** | `OLLAMA_API_KEY` |
| **Deprecated aliases** | None (born canonical 2026-07-02) |
| **Key pattern** | `.*` (per provider_catalog.yaml) |
| **API base** | `https://ollama.com/v1` |
| **TensorZero type** | `openai` |
| **Provider slug** | `ollama_cloud` |
| **Status** | **MISSING** |
| **Tier** | `llm` |
| **Distinction** | Cloud Ollama Pro (NOT `OLLAMA_BASE_URL` for local) |

**Model suits using this key:**
- Serves `glm-5.2` as cloud default model (verified 2026-07-02)

**TensorZero functions served:**
- `pmoves_orchestrator_chat` (variant: cloud_ollama_default, **primary**)
- `pmoves_orchestrator_coding` (variant: cloud_ollama_default, **fallback**)

**How to obtain:** https://ollama.com/settings/keys

---

### 6. HF_TOKEN (HuggingFace Inference Router)

| Attribute | Value |
|-----------|-------|
| **Canonical name** | `HF_TOKEN` |
| **Deprecated aliases** | `HUGGINGFACE_TOKEN` (sunset: 2026-10-01) |
| **Key pattern** | `^hf_` (per provider_catalog.yaml) |
| **API base** | `https://router.huggingface.co/v1` |
| **TensorZero type** | `openai` |
| **Provider slug** | `huggingface` |
| **Status** | **MISSING** |
| **Tier** | `llm` |

**Model suits using this key:**
- Serves `Qwen/Qwen3-Coder-30B-A3B-Instruct` via HF router

**TensorZero functions served:**
- `pmoves_orchestrator_coding` (variant: cloud_hf_router, **fallback**)

**Additional uses:**
- Model weight downloads (Unsloth, GGUF repos)
- Collection access: `DARKXSIDE/pmoves-68bcb20613cef7a0aa745e0e`

**How to obtain:** https://huggingface.co/settings/tokens

---

### 7. MINIMAX_API_KEY (MiniMax Token Plan)

| Attribute | Value |
|-----------|-------|
| **Canonical name** | `MINIMAX_API_KEY` |
| **Deprecated aliases** | `MINIMAX_TOKEN_PLAN_API_KEY` (used in model suits as primary) |
| **Key pattern** | `.*` (per provider_catalog.yaml) |
| **API base** | `https://api.minimaxi.chat/v1` |
| **TensorZero type** | `openai` |
| **Provider slug** | `minimax` |
| **Status** | **MISSING** |
| **Tier** | `llm` |
| **Coding stack** | `minimax_token_plan` |

**Model suits using this key:**
| Model Suit | Role | File |
|------------|------|------|
| `minimax-m2.7` | PRIMARY long-context model (1M tokens) | `pmoves/configs/model-suits/minimax-m2.7.yaml` |
| `minimax-m2.1` | Efficient overflow (100K tokens) | `pmoves/configs/model-suits/minimax-m2.1.yaml` |

**TensorZero functions served:**
- `coding_minimax` (variant: cloud_minimax, **primary**, weight 0.8)

**NATS subjects:**
- `mesh.minimax.status.v1`
- `mesh.minimax.quota.v1`

**How to obtain:** https://platform.minimax.io/docs/token-plan/intro

---

### 8. OPENROUTER_API_KEY (OpenRouter Multi-Model Aggregator)

| Attribute | Value |
|-----------|-------|
| **Canonical name** | `OPENROUTER_API_KEY` |
| **Deprecated aliases** | None |
| **Key pattern** | `^sk-or-` (per provider_catalog.yaml) |
| **API base** | `https://openrouter.ai/api/v1` |
| **TensorZero type** | `openai` |
| **Provider slug** | `openrouter` |
| **Status** | **MISSING** |
| **Tier** | `llm` |

**Model suits using this key:**
- Global fallback provider (all model families)

**TensorZero functions served:**
- `agent_zero` (variant: hosted_openrouter)
- `langextract` (variant: langextract_openrouter)
- `agent_zero_subordinate` (variant: hosted_openrouter)
- `pmoves_research_coordinator` (variant: hosted_openrouter)
- `archon_work_orders` (variant: hosted_openrouter)
- `archon_code_review` (variant: hosted_openrouter)
- `coding_codex` (variant: cloud_openrouter, **fallback**)
- `coding_alibaba` (variant: cloud_openrouter, **fallback**)

**How to obtain:** https://openrouter.ai/keys

---

## Additional Provider Keys (Status: Empty but Configured)

These keys have slots in `env.shared` / `env.tier-llm` but are also empty.

| # | Canonical Key | Provider | Key Pattern | TensorZero Functions | Status |
|---|--------------|----------|-------------|---------------------|--------|
| 9 | `OPENAI_API_KEY` | OpenAI | `^sk-` | orchestrator, coding_codex, agent_zero, langextract | EMPTY |
| 10 | `ANTHROPIC_API_KEY` | Anthropic | `^sk-ant-` | agent_zero, coding_claude_fallback | EMPTY |
| 11 | `GEMINI_API_KEY` | Google/Gemini | `.*` | agent_zero | EMPTY |
| 12 | `GROQ_API_KEY` | Groq | `^gsk_` | agent_zero | EMPTY |
| 13 | `MISTRAL_API_KEY` | Mistral | `.*` | (not in provider_catalog) | EMPTY |
| 14 | `DEEPSEEK_API_KEY` | DeepSeek | `.*` | (not in provider_catalog) | EMPTY |
| 15 | `XAI_API_KEY` | xAI | `.*` | (not in provider_catalog) | EMPTY |
| 16 | `ELEVENLABS_API_KEY` | ElevenLabs | `.*` | TTS/voice | EMPTY |
| 17 | `COHERE_API_KEY` | Cohere | `.*` | reranking/embeddings | EMPTY |
| 18 | `FIREWORKS_AI_API_KEY` | Fireworks AI | `.*` | (not in provider_catalog) | EMPTY |
| 19 | `PERPLEXITYAI_API_KEY` | Perplexity | `.*` | (not in provider_catalog) | EMPTY |
| 20 | `TOGETHER_AI_API_KEY` | Together AI | `.*` | agent_zero, pmoves_research_coordinator, archon_work_orders, coding_minimax fallback | EMPTY |
| 21 | `VENICE_API_KEY` | Venice AI | `.*` | agent_zero, langextract | EMPTY |
| 22 | `CLOUDFLARE_API_TOKEN` | Cloudflare | `.*` | agent_zero, langextract, coding | EMPTY |

---

## Non-Provider Keys Requiring Attention

### MCP_SERVER_TOKEN

| Attribute | Value |
|-----------|-------|
| **Canonical mapping** | `MCP_SERVER_TOKEN = ${MCP_CLIENT_SECRET}` (compose interpolation) |
| **Status** | **NOT_PINNED** |
| **Issue** | Compose hard-requires this when a2a is enabled. Ephemeral token was used this session. Must be pinned durably per CANONICAL_NAMES.md §5. |
| **Location** | `env.tier-agent` should provide `A0_SET_mcp_server_token` |
| **Action** | Generate durable token and set in `env.tier-agent`; remove from compose empty-default |

---

## Naming Inconsistencies Found

### INCONSISTENCY-1: `local-disabled` sentinel

**Location:** `docker-compose.yml`, `docker-compose.core.yml`
**Pattern:** `${VAR:-local-disabled}` for all provider keys
**Issue:** Per AGNOTE4482: "Reads backwards in cloud-hybrid era — rename sweep to `unset-pending-key`"
**Current:**
```yaml
- Z_AI_API_KEY=${Z_AI_API_KEY:-local-disabled}
- KILOCODE_API_KEY=${KILOCODE_API_KEY:-local-disabled}
```
**Recommended:**
```yaml
- Z_AI_API_KEY=${Z_AI_API_KEY:-unset-pending-key}
- KILOCODE_API_KEY=${KILOCODE_API_KEY:-unset-pending-key}
```

### INCONSISTENCY-2: MiniMax key dual naming

**Location:** `pmoves/configs/model-suits/minimax-m2.7.yaml`, `minimax-m2.1.yaml`
**Issue:** Model suits reference `MINIMAX_TOKEN_PLAN_API_KEY` as primary and `MINIMAX_API_KEY` as fallback, but:
- `provider_catalog.yaml` only knows `MINIMAX_API_KEY`
- `registry.json` only knows `MINIMAX_API_KEY`
- `env.shared` only has `MINIMAX_API_KEY`
**Resolution:** Model suits should use canonical `MINIMAX_API_KEY`; update model suit files.

### INCONSISTENCY-3: Ollama cloud vs local key confusion

**Location:** `pmoves/scripts/fetch_credentials.sh`
**Issue:** Script references `OLLAMA_CLOUD_API_KEY` but canonical name is `OLLAMA_API_KEY`
**Resolution:** Update fetch_credentials.sh to use canonical `OLLAMA_API_KEY`

### INCONSISTENCY-4: GH_APP_SEC vs GH_APP_PRIVATE_KEY

**Location:** `pmoves/env.shared`, workflows
**Issue:** `GH_APP_SEC` is used as the OAuth client secret AND as PEM private key in 5 workflows
**CANONICAL_NAMES §3:** `GH_APP_PRIVATE_KEY` is canonical; `GH_APP_SEC` should remain as OAuth client secret only
**Resolution:** Upload PEM as `GH_APP_PRIVATE_KEY` secret; migrate 5 workflows

### INCONSISTENCY-5: MCP_SERVER_TOKEN compose override

**Location:** `docker-compose.yml`, `env.tier-agent`
**Issue:** Empty default `${MCP_SERVER_TOKEN:-}` silently overrides `env_file` value
**CANONICAL_NAMES §5:** Do not set in compose env list at all; let `env_file: env.tier-agent` provide it
**Resolution:** Remove `MCP_SERVER_TOKEN` from compose env list; add `# host-leak-guard` comment

---

## Model Suit -> Key Mapping Matrix

| Model Suit | Provider | Canonical Key | File |
|------------|----------|---------------|------|
| `kimi-k2` | moonshot_ai | `MOONSHOT_API_KEY` | `pmoves/configs/model-suits/kimi-k2.yaml` |
| `minimax-m2.7` | minimax | `MINIMAX_API_KEY` | `pmoves/configs/model-suits/minimax-m2.7.yaml` |
| `minimax-m2.1` | minimax | `MINIMAX_API_KEY` | `pmoves/configs/model-suits/minimax-m2.1.yaml` |
| `qwen3.6` | ollama_local | None (local) | `pmoves/configs/model-suits/qwen3.6.yaml` |
| `nemotron-3-super` | ollama_spark | None (local) | `pmoves/configs/model-suits/nemotron-3-super.yaml` |
| `gemma4-dense` | ollama_spark | None (local) | `pmoves/configs/model-suits/gemma4-dense.yaml` |
| `claude-opus-4` | anthropic | `ANTHROPIC_API_KEY` | `pmoves/configs/model-suits/claude-opus-4.yaml` |
| `claude-sonnet-4` | anthropic | `ANTHROPIC_API_KEY` | `pmoves/configs/model-suits/claude-sonnet-4.yaml` |
| `claude-haiku-4` | anthropic | `ANTHROPIC_API_KEY` | `pmoves/configs/model-suits/claude-haiku-4.yaml` |
| `glm-4-plus` | zai | `Z_AI_API_KEY` | `pmoves/configs/model-suits/glm-4-plus.yaml` |
| `glm-4.7` | zai | `Z_AI_API_KEY` | `pmoves/configs/model-suits/glm-4.7.yaml` |
| `glm-5.1` | zai | `Z_AI_API_KEY` | `pmoves/configs/model-suits/glm-5.1.yaml` |
| `glm-4-air` | zai | `Z_AI_API_KEY` | `pmoves/configs/model-suits/glm-4-air.yaml` |
| `glm-4-flash` | zai | `Z_AI_API_KEY` | `pmoves/configs/model-suits/glm-4-flash.yaml` |
| `glm-5-turbo` | zai | `Z_AI_API_KEY` | `pmoves/configs/model-suits/glm-5-turbo.yaml` |

---

## Secrets Pipeline Flow

```
+------------------+     +------------------+     +------------------+
|  Provider        |     |  local.env       |     |  CHIT-encrypted  |
|  Dashboards      | --> |  (key values)    | --> |  Storage         |
|  (DARKXSIDE)     |     |  (gitignored)    |     |  (env.cgp.json)  |
+------------------+     +------------------+     +------------------+
                                                          |
                                                          v
+------------------+     +------------------+     +------------------+
|  TensorZero      | <-- |  make secrets-   | <-- |  CHIT passphrase |
|  Gateway         |     |    funnel        |     |  (GitHub Secret) |
|  (runtime)       |     |                  |     |                  |
+------------------+     +------------------+     +------------------+
```

### Pipeline Steps
1. DARKXSIDE obtains keys from provider dashboards (see KEY_RECEIPT_FORM.md)
2. Keys are written to `local.env` ( NEVER committed; gitignored )
3. `make -C pmoves secrets-funnel` reads `local.env`, validates formats
4. CHIT encrypts and stores in `pmoves/data/chit/env.cgp.json`
5. Runtime hydration decrypts and injects into container env

---

## Canonical Aliases (from registry.json)

```json
{
  "MOONSHOT_API_KEY": {
    "aliases": ["KIMI_API_KEY"],
    "sunset": "2026-10-01",
    "severity": "P2"
  },
  "ALIBABA_PRO_CODING_PLAN": {
    "aliases": ["ALIBABA_API_KEY", "DASHSCOPE_API_KEY"],
    "sunset": "2026-10-01",
    "severity": "P2"
  },
  "Z_AI_API_KEY": {
    "aliases": ["ZAI_API_KEY"],
    "sunset": "2026-10-01",
    "severity": "P2"
  },
  "HF_TOKEN": {
    "aliases": ["HUGGINGFACE_TOKEN"],
    "sunset": "2026-10-01",
    "severity": "P2"
  },
  "KILOCODE_API_KEY": {
    "aliases": [],
    "sunset": null,
    "severity": null
  },
  "OLLAMA_API_KEY": {
    "aliases": [],
    "sunset": null,
    "severity": null
  }
}
```

---

## Action Items

| # | Action | Owner | Priority |
|---|--------|-------|----------|
| 1 | Fill all 8 AGNOTE4482 keys via KEY_RECEIPT_FORM.md | DARKXSIDE | P0 |
| 2 | Run `make -C pmoves secrets-funnel` after key fill | DevOps | P0 |
| 3 | Pin `MCP_SERVER_TOKEN` durably in `env.tier-agent` | DevOps | P1 |
| 4 | Rename `local-disabled` -> `unset-pending-key` in compose | Engineer | P2 |
| 5 | Update model suits to use `MINIMAX_API_KEY` canonical | Engineer | P2 |
| 6 | Update `fetch_credentials.sh` to use `OLLAMA_API_KEY` | Engineer | P2 |
| 7 | Upload `GH_APP_PRIVATE_KEY` PEM; migrate 5 workflows | DARKXSIDE | P1 |
| 8 | Remove `MCP_SERVER_TOKEN` from compose env list | Engineer | P2 |
| 9 | Run `make -C pmoves naming-drift-check` after all changes | DevOps | P2 |

---

*Generated by Workstream 1: Provider Key Inventory + Secrets Funnel Pipeline*
*Commit: feat(secrets): provider key inventory, secure receipt form, secrets funnel pipeline*
