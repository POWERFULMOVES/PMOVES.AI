# Provider Key Receipt Form

**Classification:** INTERNAL - CREDENTIAL MATERIAL
**Audience:** DARKXSIDE (key custodian) ONLY
**Purpose:** Secure template for collecting provider API key values
**WARNING:** This document, when filled, contains live credentials. Handle per PMOVES Secret Handling Policy.

---

## Security Warnings (READ BEFORE FILLING)

1. **Never commit filled values to git.** This template is the ONLY file that should be committed. Fill a COPY and delete it after injection.
2. **Use secure channels only.** Transfer filled forms via encrypted channels (Signal, encrypted email).
3. **Delete after use.** Shred or secure-delete the filled form after keys are injected.
4. **Rotate regularly.** All keys should be rotated every 90 days per PMOVES security policy.
5. **No screenshots.** Never screenshot key values. Type them directly into the injection tool.

---

## How to Obtain Each Key

### Z_AI_API_KEY (Zhipu AI / GLM)
- **Dashboard:** https://open.bigmodel.cn/usercenter/apikeys
- **Steps:** Login → User Center → API Keys → Create New Key
- **Format:** Long alphanumeric string (no prefix)
- **Models:** glm-4-air, glm-4-flash, glm-4-plus, glm-4.7, glm-5-turbo, glm-5.1

### MOONSHOT_API_KEY (KIMI)
- **Dashboard:** https://platform.moonshot.cn/console/api-keys
- **Steps:** Login → Console → API Keys → Create
- **Format:** `sk-` followed by 32+ alphanumeric characters
- **Note:** Replaces deprecated `KIMI_API_KEY` (sunset 2026-10-01)
- **Models:** kimi-k2

### ALIBABA_PRO_CODING_PLAN (Qwen)
- **Dashboard:** https://dashscope.console.aliyun.com/apiKey
- **Steps:** Login → DashScope → API Key Management → Create
- **Format:** `sk-` followed by 32+ alphanumeric characters
- **Note:** Replaces deprecated `ALIBABA_API_KEY`
- **Models:** qwen-coder-plus, qwen-max

### KILOCODE_API_KEY
- **Dashboard:** https://kilocode.ai/settings/api
- **Steps:** Login → Settings → API Keys → Generate
- **Format:** Variable length alphanumeric

### OLLAMA_API_KEY
- **Dashboard:** https://ollama.com/settings/keys
- **Steps:** Login → Settings → API Keys
- **Format:** Variable length
- **Note:** For Ollama Cloud, not local Ollama

### HF_TOKEN (HuggingFace)
- **Dashboard:** https://huggingface.co/settings/tokens
- **Steps:** Login → Settings → Access Tokens → New Token
- **Format:** `hf_` followed by 30-40 alphanumeric characters
- **Note:** Replaces deprecated `HUGGINGFACE_TOKEN`

### MINIMAX_API_KEY
- **Dashboard:** https://platform.minimaxi.com/user-center/basic-information/interface-key
- **Steps:** Login → User Center → Basic Information → Interface Key
- **Format:** Variable length

### OPENROUTER_API_KEY
- **Dashboard:** https://openrouter.ai/keys
- **Steps:** Login → Keys → Create Key
- **Format:** `sk-or-` followed by 32+ alphanumeric characters

### GROQ_API_KEY
- **Dashboard:** https://console.groq.com/keys
- **Steps:** Login → API Keys → Create API Key
- **Format:** `gsk_` followed by 28-36 alphanumeric characters

### NVIDIA_API_KEY
- **Dashboard:** https://build.nvidia.com/explore/discover
- **Steps:** Login → Build → API Keys → Generate
- **Format:** `nvapi-` followed by 32+ alphanumeric characters

### MCP_SERVER_TOKEN
- **Source:** Generated locally via `pmoves/tools/generate_mcp_token.py`
- **Steps:** Run `./pmoves/tools/generate_mcp_token.py --pin` and copy output
- **Format:** JWT-style token
- **Note:** This is NOT a third-party API key. It's a local auth token for MCP/A2A.

---

## Key Value Template (COPY THIS SECTION, FILL, THEN DELETE)

> **As of 2026-07-11 every inventory key is held in GitHub Secrets** (see
> `PROVIDER_KEY_CHECKLIST.md` § Status Summary) — there is currently nothing
> to fill here. Keys are delivered per node by dispatching
> `sync-secrets-local.yml` with `targets=<node>`. Use this form only when a
> FUTURE provider key is added to the inventory before it reaches GitHub
> Secrets, listing that key in the template below.

```
=== COPY BELOW THIS LINE === DO NOT COMMIT FILLED VALUES ===

NEW_PROVIDER_KEY_NAME=

=== COPY ABOVE THIS LINE === DO NOT COMMIT FILLED VALUES ===
```

---

## Injection Procedure

After filling the template above, save it OUTSIDE the repository (e.g.
`~/filled-keys.env`) and deliver it through the sanctioned funnel:

1. Validate the template:
   `python pmoves/tools/secrets_funnel_populate.py --import-file ~/filled-keys.env --dry-run`
2. Review the validation report (values are never printed)
3. Merge into `local.env` (project-local `pmoves/secrets/local.env`, else the
   host config dir — the same file the funnel hydrates from):
   `python pmoves/tools/secrets_funnel_populate.py --import-file ~/filled-keys.env`
4. Run the funnel to hydrate `env.shared`, export the CHIT bundle, and
   regenerate tier env files: `make -C pmoves secrets-funnel`
5. Verify the exported bundle: `python pmoves/tools/secrets_funnel_populate.py --verify`
6. **Shred the filled template** (`shred -u ~/filled-keys.env`); `local.env`
   itself stays — it is the funnel's standing per-node overlay source (0600)
7. If a key also needs to reach other nodes, add it to GitHub Secrets and the
   `sync-secrets-local.yml` env map instead of copying files between machines

---

**GRAPHITI_MARK: SECRETS::KEY-RECEIPT-FORM::2026-07-09**
