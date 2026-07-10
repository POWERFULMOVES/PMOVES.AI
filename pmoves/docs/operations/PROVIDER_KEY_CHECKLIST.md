# Provider Key Inventory + Status Checklist

**Generated:** 2026-07-09
**Scope:** Complete inventory of all LLM provider API keys for PMOVES.AI cloud-hybrid tier
**Audience:** DARKXSIDE (key custodian), DevOps, Agent Zero orchestrator
**Pipeline:** local.env / CHIT source -> `make -C pmoves secrets-funnel`
**Source of truth:** `pmoves/config/provider_catalog.yaml` + `pmoves/docs/operations/CANONICAL_NAMES.md`

---

## Key Inventory

### Critical Keys (8) — Required for LLM tier operation

> **Status legend (audited 2026-07-10 against GitHub Actions secrets):**
> `IN-GH-SECRETS` = a real value already exists in GitHub Secrets (repo scope
> or the `Prod` environment) and is delivered per node by the
> `sync-secrets-local.yml` workflow — no new key needed from the custodian,
> only a workflow dispatch to the target node's runner.
> `NEEDED` = not present in GitHub Secrets under any known name; requires
> the custodian to obtain/mint it (see `KEY_RECEIPT_FORM.md`).

| # | Key Name | Provider | Status | Models | TZ Functions | Sunset |
|---|----------|----------|--------|--------|-------------|--------|
| 1 | `Z_AI_API_KEY` | Zhipu AI (Z.AI) | IN-GH-SECRETS (repo) | glm-4-air, glm-4-flash, glm-4-plus, glm-4.7, glm-5-turbo, glm-5.1 | `pmoves_orchestrator_coding`, `pmoves_worker_glm` | - |
| 2 | `MOONSHOT_API_KEY` | Moonshot (KIMI) | NEEDED | kimi-k2 | `pmoves_worker_kimi` | - |
| 3 | `ALIBABA_PRO_CODING_PLAN` | Alibaba (Qwen) | IN-GH-SECRETS (Prod env) | qwen-coder-plus, qwen-max | `pmoves_worker_qwen` | - |
| 4 | `KILOCODE_API_KEY` | KiloCode | NEEDED | kilocode-default | `pmoves_worker_kilocode` | - |
| 5 | `OLLAMA_API_KEY` | Ollama Cloud | IN-GH-SECRETS (Prod env) | ollama-local, ollama-cloud | `pmoves_worker_ollama` | - |
| 6 | `HF_TOKEN` | HuggingFace | IN-GH-SECRETS (repo) | hf-mistral, hf-llama | `pmoves_worker_hf` | - |
| 7 | `MINIMAX_API_KEY` | MiniMax | IN-GH-SECRETS (Prod env) | minimax-m2.7, minimax-m2.1 | `pmoves_worker_minimax` | - |
| 8 | `OPENROUTER_API_KEY` | OpenRouter | IN-GH-SECRETS (repo) | openrouter-universal | `pmoves_worker_openrouter` | - |

### Extended Keys (3) — For expanded provider coverage

| # | Key Name | Provider | Status | Models | TZ Functions | Sunset |
|---|----------|----------|--------|--------|-------------|--------|
| 9 | `GROQ_API_KEY` | Groq | IN-GH-SECRETS (repo) | groq-llama3, groq-mixtral | `pmoves_worker_groq` | - |
| 10 | `NVIDIA_API_KEY` | NVIDIA | IN-GH-SECRETS (repo) | nemotron-4, nemotron-h100 | `pmoves_worker_nemotron` | - |
| 11 | `MCP_SERVER_TOKEN` | Local MCP | NEEDED (mint locally) | mcp-a2a-bridge | `pmoves_mcp_server` | - |

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
| **IN-GH-SECRETS** | 8 | `Z_AI_API_KEY`, `HF_TOKEN`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `NVIDIA_API_KEY` (repo scope) + `ALIBABA_PRO_CODING_PLAN`, `MINIMAX_API_KEY`, `OLLAMA_API_KEY` (Prod environment) |
| **NEEDED** | 3 | `MOONSHOT_API_KEY`, `KILOCODE_API_KEY` (custodian) + `MCP_SERVER_TOKEN` (mint locally) |
| **DEPRECATED** | 4 | Aliases with sunset dates |
| **VOICE-ACTIVATED** | 1 | CHIT_PASSPHRASE (never stored in files) |
| **FROM-TIER** | 1 | NATS_AUTH_TOKEN (from env.tier-nats) |

---

## Delivery Path (why keys can exist yet still read as placeholders on a node)

Keys in GitHub Secrets reach a node only through `sync-secrets-local.yml`
(manual `workflow_dispatch`), which runs on that node's **self-hosted runner**
(labels `self-hosted, ai-lab, <node>`) and writes `pmoves/secrets/local.env`
plus the CHIT bundle. From there `make -C pmoves secrets-funnel` hydrates
`env.shared` and regenerates the tier env files.

Per `SECRETS_DISTRIBUTION_PATTERNS.md`: SPARK has a registered runner; Z890
uses the artifact-upload / per-node pull path (Windows-native); **B850
(Knuckles) has no registered runner yet** — until one is enrolled
(`make -C pmoves gha-runner-up RUNNER_NODE=b850`) or a bundle is pulled from a
workflow artifact (`make -C pmoves secrets-funnel-sync-from-bundle`), keys that
exist in GitHub Secrets never arrive on that node. The three Prod-scoped
provider keys additionally required the workflow env-map entries added
2026-07-10 — a key absent from that map is silently never forwarded.

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

- [ ] DARKXSIDE: Fill `KEY_RECEIPT_FORM.md` for the **NEEDED** keys only
      (`MOONSHOT_API_KEY`, `KILOCODE_API_KEY`, `MCP_SERVER_TOKEN`) — the other
      8 already live in GitHub Secrets
- [ ] Node op: enroll the target node's runner if missing
      (`make -C pmoves gha-runner-up RUNNER_NODE=<node>`; B850 currently unregistered)
- [ ] Node op: dispatch `sync-secrets-local.yml` with `targets=<node>` to land
      GitHub-held keys in that node's `local.env` + CHIT bundle
- [ ] DevOps: `python pmoves/tools/secrets_funnel_populate.py --validate-only`
- [ ] DevOps: merge filled receipt template:
      `python pmoves/tools/secrets_funnel_populate.py --import-file <filled.env> --dry-run`, then without `--dry-run`
- [ ] DevOps: `make -C pmoves secrets-funnel` (hydrate + export + tier regen)
- [ ] DevOps: `python pmoves/tools/secrets_funnel_populate.py --verify`
- [ ] DARKXSIDE: Confirm all 8 critical keys resolve correctly
- [ ] DARKXSIDE: Shred the filled receipt template (local.env itself stays —
      it is the funnel's standing per-node overlay source, 0600)
- [ ] Schedule: Key rotation reminder for 2026-10-01 (sunset aliases)

---

**GRAPHITI_MARK: SECRETS::KEY-CHECKLIST::2026-07-09**
