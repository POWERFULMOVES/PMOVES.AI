# TensorZero PR #336 Review Learnings

**Date:** 2025-12-21
**PR:** https://github.com/POWERFULMOVES/PMOVES.AI/pull/336

## Key Insights

### 1. Docker Networking: Host vs Container Ports
**Issue:** Services used host-mapped port (3030) instead of container port (3000) for inter-container communication.

**Learning:** When containers communicate within Docker networks, use the **internal container port**, not the host-mapped port.

```yaml
# WRONG - host port
TENSORZERO_BASE_URL=http://tensorzero-gateway:3030

# CORRECT - container port
TENSORZERO_BASE_URL=http://tensorzero-gateway:3000
```

**Port mapping reminder:** `3030:3000` means host:container

### 2. Architecture Principle: Local-First, Cloud-Hybrid
**Correction:** PR originally described "Cloud-First" but actual architecture is **Local-First, Cloud-Hybrid**.

**Routing Priority:**
1. Local (Ollama) - qwen3:8b, qwen2.5 series
2. Anthropic - claude-sonnet-4-5 for complex reasoning
3. Gemini Flash - gemini-2.0-flash-exp as backup

**Key Principle:** TensorZero is the SINGLE source of truth for all models. No hardcoded models in compose files or services.

### 3. Environment Variable Deduplication
**Issue:** `.env.example` had duplicate `OPENAI_MODEL` keys which causes last-wins override behavior.

**Learning:** Always check for duplicate keys in `.env` files. Use comments to document alternatives:
```bash
OPENAI_MODEL=gpt-4o-mini
# OPENAI_MODEL=tensorzero::function_name::orchestrator  # Use when routing through TensorZero
```

### 4. Dockerfile numpy/_core Preservation
**Issue:** Removing `numpy/_core` directory breaks numpy 1.26+ at runtime.

**Learning:** Never delete `numpy/_core` - it contains essential C-extensions and compatibility infrastructure. The `_core` module is NOT a leftover artifact.

### 5. Documentation Hygiene
**Common issues found:**
- Duplicate sections (DeepResearch documented twice)
- Wrong timestamps (future date instead of current)
- Missing language specifiers on code blocks
- Duplicate comment headers

**Best Practice:** Always validate documentation in PRs for:
- Duplicate content (`grep -n "^#### " docs/*.md | sort | uniq -d`)
- Correct timestamps
- Proper markdown formatting

### 6. TensorZero Tool Definitions
**Requirement:** All tool definitions in `tensorzero.toml` must have corresponding JSON schema files.

```toml
[tools.web_search]
description = "Search the internet"
parameters = "tools/web_search.json"  # Must exist!
```

### 7. Cloudflare Variable Substitution
**Issue:** TOML doesn't support shell-style `${VAR}` substitution.

**Learning:** TensorZero uses `env::VARIABLE_NAME` syntax for credentials, not `${...}`:
```toml
# WRONG
api_base = "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai"

# CORRECT - use hardcoded or env:: syntax for credentials only
api_key_location = "env::CLOUDFLARE_API_TOKEN"
```

## Review Automation

### CodeRabbit Categories
| Severity | Icon | Action Required |
|----------|------|-----------------|
| Critical | 🔴 | Must fix before merge |
| Major | 🟠 | Should fix |
| Minor | 🟡 | Nitpick, optional |

### Files Requiring Most Attention
1. `docker-compose.yml` - Port configurations, networking
2. `.env.example` - Duplicate keys, ordering
3. `Dockerfile` - Build layer issues, package management
4. `*.toml` - Configuration validity, file references
5. Documentation - Duplicates, timestamps, formatting

## Action Items Applied

- [x] Fixed TensorZero port from 3030 to 3000 (2 locations)
- [x] Commented duplicate OPENAI_MODEL with explanation
- [x] Removed numpy/_core deletion from Dockerfile
- [x] Removed duplicate DeepResearch section
- [x] Fixed timestamp to 2025-12-21
- [x] Removed duplicate BoTZ Models comment
- [x] Added `text` language specifier to code block
- [x] Verified web_search.json exists
