# Provider Key Inventory + Status Checklist

**Generated:** 2026-07-09
**Scope:** Complete inventory of all LLM provider API keys for PMOVES.AI cloud-hybrid tier
**Audience:** DARKXSIDE (key custodian), DevOps, Agent Zero orchestrator
**Pipeline:** local.env / CHIT source -> `make -C pmoves secrets-funnel`
**Source of truth:** `pmoves/config/provider_catalog.yaml` + `pmoves/docs/operations/CANONICAL_NAMES.md`

---

## Key Inventory

### Critical Keys (8) — Required for LLM tier operation

| # | Key Name | Provider | Status | Models | TZ Functions | Sunset |
|---|----------|----------|--------|--------|-------------|--------|
| 1 | `Z_AI_API_KEY` | Zhipu AI (Z.AI) | PENDING | glm-4-air, glm-4-flash, glm-4-plus, glm-4.7, glm-5-turbo, glm-5.1 | `pmoves_orchestrator_coding`, `pmoves_worker_glm` | - |
| 2 | `MOONSHOT_API_KEY` | Moonshot (KIMI) | PENDING | kimi-k2 | `pmoves_worker_kimi` | - |
| 3 | `ALIBABA_PRO_CODING_PLAN` | Alibaba (Qwen) | PENDING | qwen-coder-plus, qwen-max | `pmoves_worker_qwen` | - |
| 4 | `KILOCODE_API_KEY` | KiloCode | PENDING | kilocode-default | `pmoves_worker_kilocode` | - |
| 5 | `OLLAMA_API_KEY` | Ollama Cloud | PENDING | ollama-local, ollama-cloud | `pmoves_worker_ollama` | - |
| 6 | `HF_TOKEN` | HuggingFace | PENDING | hf-mistral, hf-llama | `pmoves_worker_hf` | - |
| 7 | `MINIMAX_API_KEY` | MiniMax | PENDING | minimax-m2.7, minimax-m2.1 | `pmoves_worker_minimax` | - |
| 8 | `OPENROUTER_API_KEY` | OpenRouter | PENDING | openrouter-universal | `pmoves_worker_openrouter` | - |

### Extended Keys (3) — For expanded provider coverage

| # | Key Name | Provider | Status | Models | TZ Functions | Sunset |
|---|----------|----------|--------|--------|-------------|--------|
| 9 | `GROQ_API_KEY` | Groq | PENDING | groq-llama3, groq-mixtral | `pmoves_worker_groq` | - |
| 10 | `NVIDIA_API_KEY` | NVIDIA | PENDING | nemotron-4, nemotron-h100 | `pmoves_worker_nemotron` | - |
| 11 | `MCP_SERVER_TOKEN` | Local MCP | PENDING | mcp-a2a-bridge | `pmoves_mcp_server` | - |

### Deprecated Aliases (4) — Migrate to canonical names

| # | Deprecated | Canonical | Sunset Date | Action |
|---|-----------|-----------|-------------|--------|
| 12 | `KIMI_API_KEY` | `MOONSHOT_API_KEY` | 2026-10-01 | Migrate value |
| 13 | `ZAI_API_KEY` | `Z_AI_API_KEY` | 2026-10-01 | Migrate value |
| 14 | `ALIBABA_API_KEY` | `ALIBABA_PRO_CODING_PLAN` | 2026-10-01 | Migrate value |
| 15 | `HUGGINGFACE_TOKEN` | `HF_TOKEN` | 2026-10-01 | Migrate value |

### Variant Key Names (5) — Alternate names for same provider

| # | Variant | Primary | Notes |
|---|---------|---------|-------|
| 16 | `ZHIPU_API_KEY` | `Z_AI_API_KEY` | Legacy name |
| 17 | `MINIMAX_TOKEN_PLAN_API_KEY` | `MINIMAX_API_KEY` | Token plan variant |
| 18 | `DASHSCOPE_API_KEY` | `ALIBABA_PRO_CODING_PLAN` | DashScope direct |
| 19 | `OPENAI_API_KEY` | - | Not used (OpenRouter preferred) |
| 20 | `ANTHROPIC_API_KEY` | - | Not used (Claude via TensorZero) |

### Infrastructure Keys (2)

| # | Key Name | Purpose | Status |
|---|----------|---------|--------|
| 21 | `CHIT_PASSPHRASE` | CHIT encryption passphrase | Voice-activated |
| 22 | `NATS_AUTH_TOKEN` | NATS JetStream authentication | From env.tier-nats |

---

## Status Summary

| Status | Count | Keys |
|--------|-------|------|
| **PENDING** | 11 | All critical + extended keys need population |
| **DEPRECATED** | 4 | Aliases with sunset dates |
| **VOICE-ACTIVATED** | 1 | CHIT_PASSPHRASE (never stored in files) |
| **FROM-TIER** | 1 | NATS_AUTH_TOKEN (from env.tier-nats) |

---

## Format Validation Patterns

| Key | Pattern | Example (redacted) |
|-----|---------|-------------------|
| `Z_AI_API_KEY` | 20+ chars alphanumeric | `abc12...xyz89` |
| `MOONSHOT_API_KEY` | `sk-` + 32+ alphanum | `sk-abc...xyz` |
| `ALIBABA_PRO_CODING_PLAN` | `sk-` + 32+ alphanum | `sk-abc...xyz` |
| `HF_TOKEN` | `hf_` + 30-40 alphanum | `hf_abc...xyz` |
| `OPENROUTER_API_KEY` | `sk-or-` + 32+ alphanum | `sk-or-abc...xyz` |
| `GROQ_API_KEY` | `gsk_` + 28-36 alphanum | `gsk_abc...xyz` |
| `NVIDIA_API_KEY` | `nvapi-` + 32+ alphanum | `nvapi-abc...xyz` |

---

## Action Items

- [ ] DARKXSIDE: Fill `KEY_RECEIPT_FORM.md` with actual key values
- [ ] DevOps: Run `python pmoves/tools/secrets_funnel_populate.py --validate-only`
- [ ] DevOps: Run `python pmoves/tools/secrets_funnel_populate.py --dry-run`
- [ ] DevOps: Run `python pmoves/tools/secrets_funnel_populate.py`
- [ ] DevOps: Run `python pmoves/tools/secrets_funnel_populate.py --verify`
- [ ] DARKXSIDE: Confirm all 8 critical keys resolve correctly
- [ ] DARKXSIDE: Delete `local.env` after successful injection
- [ ] Schedule: Key rotation reminder for 2026-10-01 (sunset aliases)

---

**GRAPHITI_MARK: SECRETS::KEY-CHECKLIST::2026-07-09**
