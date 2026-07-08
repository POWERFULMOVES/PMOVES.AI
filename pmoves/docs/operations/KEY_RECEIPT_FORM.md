# Provider Key Receipt Form

**Classification:** INTERNAL - CREDENTIAL MATERIAL
**Audience:** DARKXSIDE (key custodian) ONLY
**Purpose:** Secure template for collecting provider API key values
**WARNING:** This document, when filled, contains live credentials. Handle per PMOVES Secret Handling Policy.

---

## Security Warnings (READ BEFORE FILLING)

> [!CAUTION]
> **NEVER** commit this file with real values to git.
> **NEVER** paste keys into chat, email, or any non-encrypted channel.
> **NEVER** store filled copies in cloud-synced folders (Dropbox, Drive, etc.).
> **ALWAYS** transfer via `make -C pmoves secrets-funnel` or encrypted CHIT pipeline.
> **ALWAYS** shred (secure-delete) filled forms after successful injection.
> **ALWAYS** verify key destination via `make -C pmoves secrets-verify` after funnel.

### Secure Transfer Procedure

1. Fill this form on an airgapped or trusted machine
2. Save as `local.env` in the PMOVES repo root (gitignored)
3. Run `make -C pmoves secrets-funnel` to inject into CHIT storage
4. Verify: `make -C pmoves secrets-verify`
5. Secure-delete this file: `shred -u local.env` (Linux) or `srm local.env` (macOS)

---

## Key Value Entry Section

### Priority 1: AGNOTE4482 Critical Keys (ALL EMPTY ON NODE)

These 8 keys are required for the cloud-hybrid LLM tier to function.
The entire orchestrator pipeline depends on these being populated.

---

#### 1. Z_AI_API_KEY (Zhipu AI / Z.AI / GLM Coding Plan)

```
Obtained from: https://z.ai/manage-apikey/apikey-list
Account:      (fill your Z.AI account email)
Date:         YYYY-MM-DD
Key format:   (any string, typically alphanumeric)
```

```
Z_AI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Verification:**
```bash
curl -s -H "Authorization: Bearer $Z_AI_API_KEY" \
  https://api.z.ai/v1/models | head -c 200
echo "--- If you see JSON model list, key is valid ---"
```

---

#### 2. MOONSHOT_API_KEY (Moonshot AI / Kimi)

```
Obtained from: https://platform.moonshot.ai/console/api-keys
Account:      (fill your Moonshot account email)
Date:         YYYY-MM-DD
Key format:   sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Sunset note:  Alias KIMI_API_KEY is deprecated (sunset: 2026-10-01)
```

```
MOONSHOT_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Verification:**
```bash
curl -s -H "Authorization: Bearer $MOONSHOT_API_KEY" \
  https://api.moonshot.ai/v1/models | head -c 200
echo "--- If you see JSON model list, key is valid ---"
```

---

#### 3. ALIBABA_PRO_CODING_PLAN (Alibaba / DashScope / Qwen)

```
Obtained from: https://dashscope.console.aliyun.com/
Account:      (fill your Alibaba Cloud account)
Date:         YYYY-MM-DD
Key format:   sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (32 hex chars after sk-)
Sunset note:  Aliases ALIBABA_API_KEY, DASHSCOPE_API_KEY deprecated (sunset: 2026-10-01)
```

```
ALIBABA_PRO_CODING_PLAN=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Verification:**
```bash
curl -s -H "Authorization: Bearer $ALIBABA_PRO_CODING_PLAN" \
  https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models | head -c 200
echo "--- If you see JSON model list, key is valid ---"
```

---

#### 4. KILOCODE_API_KEY (Kilo Code)

```
Obtained from: https://api.kilocode.ai (OpenRouter-compatible gateway)
Account:      (fill your Kilo Code account email)
Date:         YYYY-MM-DD
Key format:   (any string)
Note:         Born canonical 2026-07-02; no deprecated aliases
```

```
KILOCODE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Verification:**
```bash
curl -s -H "Authorization: Bearer $KILOCODE_API_KEY" \
  https://api.kilocode.ai/api/openrouter/models | head -c 200
echo "--- If you see JSON model list, key is valid ---"
```

---

#### 5. OLLAMA_API_KEY (Ollama Pro Cloud)

```
Obtained from: https://ollama.com/settings/keys
Account:      (fill your Ollama account email)
Date:         YYYY-MM-DD
Key format:   (any string)
Note:         This is OLLAMA PRO CLOUD (not OLLAMA_BASE_URL for local)
              Distinct from local Ollama which needs no key
```

```
OLLAMA_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Verification:**
```bash
curl -s -H "Authorization: Bearer $OLLAMA_API_KEY" \
  https://ollama.com/v1/models | head -c 200
echo "--- If you see JSON model list, key is valid ---"
```

---

#### 6. HF_TOKEN (HuggingFace Inference Router)

```
Obtained from: https://huggingface.co/settings/tokens
Account:      (fill your HuggingFace account)
Date:         YYYY-MM-DD
Key format:   hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Sunset note:  Alias HUGGINGFACE_TOKEN deprecated (sunset: 2026-10-01)
Scopes:       Read access to models (for router + weight downloads)
```

```
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Verification:**
```bash
curl -s -H "Authorization: Bearer $HF_TOKEN" \
  https://router.huggingface.co/v1/models | head -c 200
echo "--- If you see JSON model list, key is valid ---"
```

---

#### 7. MINIMAX_API_KEY (MiniMax Token Plan)

```
Obtained from: https://platform.minimax.io/docs/token-plan/intro
Account:      (fill your MiniMax account email)
Date:         YYYY-MM-DD
Key format:   (any string)
Note:         Model suits also reference MINIMAX_TOKEN_PLAN_API_KEY
              but canonical per registry is MINIMAX_API_KEY
Plan tier:    (starter/plus/max/plus_highspeed/max_highspeed/ultra_highspeed)
```

```
MINIMAX_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Verification:**
```bash
curl -s -H "Authorization: Bearer $MINIMAX_API_KEY" \
  https://api.minimaxi.chat/v1/models | head -c 200
echo "--- If you see JSON model list, key is valid ---"
```

---

#### 8. OPENROUTER_API_KEY (OpenRouter Multi-Model Aggregator)

```
Obtained from: https://openrouter.ai/keys
Account:      (fill your OpenRouter account email)
Date:         YYYY-MM-DD
Key format:   sk-or-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Note:         Global fallback provider; key starts with sk-or-
```

```
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Verification:**
```bash
curl -s -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  https://openrouter.ai/api/v1/models | head -c 200
echo "--- If you see JSON model list, key is valid ---"
```

---

### Priority 2: Additional Provider Keys (Optional but Recommended)

These keys expand provider diversity and fallback resilience.

---

#### 9. OPENAI_API_KEY (OpenAI / GPT family)

```
Obtained from: https://platform.openai.com/api-keys
Account:      (fill your OpenAI account email)
Date:         YYYY-MM-DD
Key format:   sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx or sk-proj-...
```

```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

#### 10. ANTHROPIC_API_KEY (Anthropic / Claude family)

```
Obtained from: https://console.anthropic.com/settings/keys
Account:      (fill your Anthropic account email)
Date:         YYYY-MM-DD
Key format:   sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

```
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

#### 11. GEMINI_API_KEY (Google / Gemini)

```
Obtained from: https://aistudio.google.com/app/apikey
Account:      (fill your Google account)
Date:         YYYY-MM-DD
Key format:   (any string)
Note:         Also set GOOGLE_API_KEY as alias if needed
```

```
GEMINI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

#### 12. GROQ_API_KEY (Groq / Ultra-fast inference)

```
Obtained from: https://console.groq.com/keys
Account:      (fill your Groq account email)
Date:         YYYY-MM-DD
Key format:   gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

#### 13. CLOUDFLARE_API_TOKEN (Cloudflare Workers AI)

```
Obtained from: https://dash.cloudflare.com/profile/api-tokens
Account:      (fill your Cloudflare account email)
Date:         YYYY-MM-DD
Key format:   (any string)
Requires:     CLOUDFLARE_ACCOUNT_ID (also set below)
```

```
CLOUDFLARE_API_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CLOUDFLARE_ACCOUNT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

### Priority 3: Infrastructure Keys

---

#### 14. MCP_SERVER_TOKEN (Agent Zero A2A / MCP Auth)

```
Generated via: openssl rand -base64 48 | tr -d '\n=' | cut -c1-64
Purpose:       MCP server authentication for A2A enablement
Status:        NOT_PINNED (was ephemeral this session)
Note:          This maps to MCP_CLIENT_SECRET in compose
               Must be pinned durably per CANONICAL_NAMES.md §5
```

```
MCP_SERVER_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## Quick-Check: Generate local.env from this form

After filling in the keys above, run this to generate the `local.env` file:

```bash
#!/bin/bash
# generate_local_env.sh - Run this after filling the form
# This script extracts key lines from a filled KEY_RECEIPT_FORM.md

cat <<'EOF' > local.env
# =============================================================================
# PMOVES.AI Provider Keys - Generated from KEY_RECEIPT_FORM.md
# DO NOT COMMIT THIS FILE - it is in .gitignore
# Generated: $(date -Iseconds)
# =============================================================================

# --- Priority 1: AGNOTE4482 Critical Keys ---
Z_AI_API_KEY=
MOONSHOT_API_KEY=
ALIBABA_PRO_CODING_PLAN=
KILOCODE_API_KEY=
OLLAMA_API_KEY=
HF_TOKEN=
MINIMAX_API_KEY=
OPENROUTER_API_KEY=

# --- Priority 2: Additional Cloud Providers ---
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
GROQ_API_KEY=
MISTRAL_API_KEY=
DEEPSEEK_API_KEY=
XAI_API_KEY=
COHERE_API_KEY=
FIREWORKS_AI_API_KEY=
PERPLEXITYAI_API_KEY=
TOGETHER_AI_API_KEY=
VENICE_API_KEY=
CLOUDFLARE_API_TOKEN=
CLOUDFLARE_ACCOUNT_ID=

# --- Priority 3: Infrastructure ---
MCP_SERVER_TOKEN=
MCP_CLIENT_SECRET=

EOF

echo "local.env generated. Now fill in the key values and run:"
echo "  make -C pmoves secrets-funnel"
```

---

## Post-Fill Checklist

- [ ] All Priority 1 keys filled with verified values
- [ ] Each key verified with the curl command (200 response, JSON model list)
- [ ] `local.env` saved in repo root (NOT committed)
- [ ] `make -C pmoves secrets-funnel` executed successfully
- [ ] `make -C pmoves secrets-verify` confirms all keys present
- [ ] This form securely deleted (`shred -u` or equivalent)
- [ ] CHIT passphrase updated if this is a new CI bundle
- [ ] `MCP_SERVER_TOKEN` pinned in `env.tier-agent` if A2A enabled

---

## Key Format Validation Reference

| Key | Expected Prefix | Length | Example Pattern |
|-----|----------------|--------|-----------------|
| `Z_AI_API_KEY` | (varies) | 32+ | alphanumeric |
| `MOONSHOT_API_KEY` | `sk-` | 32+ | `sk-[a-z0-9]{32}` |
| `ALIBABA_PRO_CODING_PLAN` | `sk-` | 35 | `sk-[a-f0-9]{32}` |
| `KILOCODE_API_KEY` | (varies) | 32+ | alphanumeric |
| `OLLAMA_API_KEY` | (varies) | 32+ | alphanumeric |
| `HF_TOKEN` | `hf_` | 37 | `hf_[a-zA-Z0-9]{34}` |
| `MINIMAX_API_KEY` | (varies) | 32+ | alphanumeric |
| `OPENROUTER_API_KEY` | `sk-or-` | 36 | `sk-or-[a-z0-9-]{28}` |
| `OPENAI_API_KEY` | `sk-` or `sk-proj-` | 32+ | `sk-[a-z0-9]{32}` |
| `ANTHROPIC_API_KEY` | `sk-ant-` | 36+ | `sk-ant-api03-[a-z0-9-]{20}` |
| `GROQ_API_KEY` | `gsk_` | 35 | `gsk_[a-zA-Z0-9]{31}` |

---

*This form is generated automatically. Do not edit the structure manually.*
*For key rotation, use the same form and note the rotation date in the "Date" field.*
*Version: 2026-07-09 | Workstream 1*
