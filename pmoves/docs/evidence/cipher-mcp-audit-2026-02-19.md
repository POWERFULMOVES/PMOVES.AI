# Cipher-MCP Wiring Audit Report
_Generated: 2026-02-19_

## Architecture
```
Claude Code CLI ──stdio──► pmoves-cipher-mcp (Python) ──HTTP──► cipher-api (Node.js/Neo4j) @ :8096
```

## Audit Checklist

| # | Check | Status | Details |
|---|-------|--------|---------|
| 1 | MCP config correct | PASS | `.claude/mcp.json` → `pmoves-cipher` server, stdio transport via `uv`, `CIPHER_URL=http://localhost:8096` |
| 2 | Server code valid | PASS | `cipher_mcp/server.py` registers 4 tools via `TOOL_HANDLERS` mapping, asyncio entry point |
| 3 | Client connects | PASS | `cipher_mcp/client.py` uses `httpx.AsyncClient`, resolves URL via `pmoves_registry.get_cipher_url()` |
| 4 | All 4 tools registered | PASS | `pmoves_cipher_store`, `pmoves_cipher_search`, `pmoves_cipher_store_reasoning`, `pmoves_cipher_reasoning_patterns` |
| 5 | Service registry correct | PASS | `pmoves_registry/__init__.py` checks `CIPHER_URL` → `CIPHER_MEMORY_URL` → default `http://localhost:8096` |
| 6 | cipher-api in compose | PASS | Service `cipher-api` defined at compose line 1608, builds from `../Pmoves-cipher`, port 8096 mapped from 3000 |
| 7 | NATS URL has creds | PASS | `get_nats_url()` defaults to `nats://nats:pmoves@nats:4222` |

## Findings

### P1: `pmoves-botz-cipher` is a dangling reference
**File:** `pmoves/docker-compose.yml:2224`
**Issue:** `gateway-agent` env `CIPHER_URL=${CIPHER_URL:-http://pmoves-botz-cipher:8000}` references a service `pmoves-botz-cipher` that is **not defined** in docker-compose.
**Impact:** gateway-agent cannot reach cipher memory if `CIPHER_URL` is unset.
**Fix:** Change default to `http://cipher-api:8096` (the actual cipher service).

### P2: `pmoves-cipher-mcp/` is NOT a submodule
**Current:** Tracked as a regular directory (tree object in git index).
**Expected:** Should be a submodule at `POWERFULMOVES/PMOVES-cipher-mcp` repo.
**Impact:** Cannot be independently versioned, branched, or CI-tested.
**Action:** Create `PMOVES-cipher-mcp` GitHub repo, convert to submodule (deferred — requires user action for repo creation).

### P3: Missing `.gitignore` in `pmoves-cipher-mcp/`
**Issue:** `.venv/` and `__pycache__/` directories present and potentially tracked.
**Fix:** Add `.gitignore` with standard Python exclusions.

### INFO: Two separate cipher services
- `cipher-api` (:8096) — Cipher Memory Node.js service (Neo4j backend, used by pmoves-cipher-mcp)
- `pmoves-botz-cipher` (:8000) — BoTZ cipher service (referenced but undefined in compose)
- These are architecturally distinct; `cipher-api` is the canonical PMOVES cipher memory.

## BoTZ Integration Review

### BoTZ Open PRs (3 dependency bumps)
| PR | Title | Blocking? |
|----|-------|-----------|
| #60 | chore(deps): bump lucide-react 0.563.0 → 0.574.0 | No |
| #61 | chore(deps): bump fastapi 0.128.7 → 0.129.0 | No |
| #62 | chore(deps): bump uvicorn 0.40.0 → 0.41.0 | No |

None of these block cipher functionality. They are routine dependency updates.

### BoTZ cipher at `archive/Features_folder/cipher/`
BoTZ has its own cipher integration (separate from pmoves-cipher-mcp):
- `app_cipher_memory.py`, `Dockerfile.cipher`, config templates
- MCP mode at `core/mcp/modes/cipher_memory_mode.json`
- NATS events: `botz.cipher.memory.stored.v1`, `botz.cipher.memory.recalled.v1`
- This appears to be a BoTZ-specific cipher client that may target a separate `pmoves-botz-cipher` service.

## Operational Testing

Requires cipher-api container running (Docker profile `agents`):
```bash
# Start cipher-api
docker compose --profile agents up -d cipher-api

# Verify health
curl http://localhost:8096/health

# Test MCP server locally
uv --directory ./pmoves-cipher-mcp run python -m cipher_mcp.server

# Verify Claude Code sees tools
# Check /mcp listing in Claude Code CLI
```

## Recommended Immediate Actions

1. **Fix dangling CIPHER_URL** in gateway-agent (change `pmoves-botz-cipher:8000` → `cipher-api:8096`)
2. **Add .gitignore** to `pmoves-cipher-mcp/`
3. **Defer submodule conversion** until PMOVES-cipher-mcp repo is created on GitHub
