# Build Fixes - December 6, 2025

## DeepResearch Dockerfile Build Context Fix

**Issue**: Build failed with "services: not found" and "contracts: not found" errors.

**Root Cause**: Build context mismatch between docker-compose.yml and Dockerfile.
- docker-compose.yml set `context: ./services`
- Dockerfile tried to `COPY services/deepresearch/...` (looking for services inside services)

**Fix Applied**: Updated `services/deepresearch/Dockerfile` to use relative paths:
```diff
- COPY services/deepresearch/requirements.txt /tmp/deepresearch-requirements.txt
+ COPY deepresearch/requirements.txt /tmp/deepresearch-requirements.txt

- COPY services /app/services
- COPY contracts /app/contracts
+ COPY deepresearch /app/services/deepresearch
```

**Why contracts removed**: DeepResearch doesn't import contracts module, so COPY was unnecessary.

**Committed**: 3147c52

## .env.local JSON Syntax Fix

**Issue**: Shell error `.env.local: line 11: 0.3,: command not found`

**Root Cause**: Unquoted JSON value in environment variable.
```bash
AGENT_ZERO_DECODING={"temperature": 0.3, "top_p": 0.8}
```
Shell interpreted `{"temperature":` as a command.

**Fix Applied**: Quote JSON values in .env.local:
```bash
AGENT_ZERO_DECODING='{"temperature": 0.3, "top_p": 0.8}'
```

**Note**: .env.local is gitignored - users must apply this fix locally.

## Other Services Verified

**No changes needed for**:
- `pdf-ingest`: Uses `context: .` - COPY paths are correct
- `agent-zero`: Uses `context: .` - COPY paths are correct

Only DeepResearch had the context mismatch due to `context: ./services`.

## Next Steps

1. Rebuild DeepResearch image (will pick up fixes automatically)
2. Complete service bring-up verification
3. Test all slash commands with live services
