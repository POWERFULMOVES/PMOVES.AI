# Codex Operator Home (PMOVES)
_Last updated: 2026-03-02_

This is the Codex-first operations guide for PMOVES.AI. It mirrors the mature
Claude setup, but keeps Codex workflows command-first and Makefile-native.

For the full PMOVES traversal map, including skills, memory, personas, voice,
service selection, and submodule routing, see:
- `pmoves/docs/AGENTS/CODEX_ECOSYSTEM_TRAVERSAL.md`

## Runtime signaling

- Use `mode=focus` for implementation/validation windows.
- Use `mode=open-chat+scout` for context gathering while staying conversational.
- See protocol details in `pmoves/docs/AGENTS/CODEX_RUNTIME_PROTOCOL.md`.

## KRISS KROSS lane roles

- `Codex` lead mode: implementation owner, command author, parity authority.
- `Claude` in Codex-led windows: scout/reviewer lane for risk and alternative diffs.
- Use overlay handoff rules from `pmoves/docs/AGENTS/KRISS_KROSS_ACCORD.md` when scopes intersect.

## Bootstrap

1. Install pinned Codex config:
   - `make -C pmoves codex-config`
2. Start Codex with repo profile:
   - `codex --profile pmoves`
3. Open this runbook plus parity map:
   - `pmoves/docs/AGENTS/CODEX_CLAUDE_PARITY_MAP.md`

## Ecosystem traversal

Codex should not act like a standalone code assistant in PMOVES.AI. It should
traverse the existing PMOVES surfaces in this order:

1. Operator lane: this runbook + `CODEX_RUNTIME_PROTOCOL.md`
2. Service map: `.claude/CLAUDE.md`
3. Submodule map: `.claude/context/submodules.md`
4. Skill map: `PmovesSKillZ.md` + `pmoves/configs/skill-pairings.yaml`
5. Memory path: `CODEX_CIPHER_MEMORY_IMPLEMENTATION_MAP.md`
6. Persona + voice path: `PERSONAS.md` + `CODEX_PERSONA_STYLE_PLAYBOOK.md`

Use `CODEX_ECOSYSTEM_TRAVERSAL.md` as the canonical quick route across these
surfaces.

## Codex Config Parity (Mar 2026)

- Keep web search configured at top-level:
  - `web_search = "live"` (or `"cached"` / `"disabled"`).
- Keep Windows sandbox under current keys:
  - `[features].experimental_windows_sandbox = true`
  - `[windows.sandbox]` for runtime sandbox controls.
- For Docker MCP startup stability, set:
  - `[mcp_servers.MCP_DOCKER] startup_timeout_sec = 60` (or higher for slower hosts).
- Validate discovered Docker MCP servers before agent sessions:
  - `docker mcp server ls`
  - `docker mcp gateway run --dry-run --servers filesystem --servers github`

## Core Codex commands

- `make -C pmoves codex-health-quick`
- `make -C pmoves smoke`
- `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu`
- `make -C pmoves verify-all`
- `make -C pmoves codex-audit`
- `make -C pmoves codex-parity-check`
- `make -C pmoves a0-plugins-check`
- `make -C pmoves a0-plugins-check-remote`

## CHIT Geometry Bus

- Service health:
  - `curl -fsS http://localhost:8086/healthz`
  - `curl -fsS http://localhost:8086/hirag/admin/stats | jq .`
- Geometry validation:
  - `curl -fsS http://localhost:8086/geometry/calibration/report | jq .`
- Event subjects to watch:
  - `geometry.cgp.v1`
  - `geometry.swarm.meta.v1`
  - `pmoves.geometry.cgp.ready.v1`

## EvoSwarm

- Controller health:
  - `curl -fsS http://localhost:8113/healthz`
- Controller config:
  - `curl -fsS http://localhost:8113/config | jq .`
- Ensure downstream services persist and publish `pack_id` metadata in CGP flow.

## Flute + Voice stack

- Flute health:
  - `curl -fsS http://localhost:8055/healthz | jq .`
- Flute session status:
  - `curl -fsS http://localhost:8055/v1/sessions -H "Authorization: Bearer $FLUTE_API_KEY" | jq .`
- TTS backend:
  - `curl -fsS http://localhost:7861/gradio_api/info | jq .`

## Gateway + Agent Zero MCP

- Agent Zero health:
  - `curl -fsS http://localhost:8080/healthz | jq .`
- Agent Zero MCP health:
  - `curl -fsS http://localhost:8080/mcp/health | jq .`
- Hi-RAG query (preferred knowledge path):
  - `curl -X POST http://localhost:8086/hirag/query -H "Content-Type: application/json" -d '{"query":"agent orchestration", "top_k":10, "rerank":true}' | jq .`

## Cipher MCP bridge

- Cipher API health:
  - `curl -fsS http://localhost:8096/health | jq .`
- Local MCP bridge server:
  - `uv run --directory ./pmoves-cipher-mcp python -m cipher_mcp.server`
- Compose service check:
  - `docker compose -f pmoves/docker-compose.yml --profile agents ps cipher-api`

## BotZ alignment

- BotZ has its own Codex mapping under `PMOVES-BoTZ/config/codex/mcp_gateway.json`.
- Keep BotZ Codex mappings consistent with PMOVES root profile and MCP strategy.
- For parity checks across all submodules, regenerate:
  - `make -C pmoves codex-audit`

## Known Gaps

For a comprehensive view of what's implemented vs. what's still planned, see:
- [IMPLEMENTATION_GAP_ANALYSIS.md](./IMPLEMENTATION_GAP_ANALYSIS.md) — Full gap analysis with Phase 1 completion status
- Key gaps: A2A server (`/.well-known/agent.json`) not exposed, probabilistic safety hooks not implemented, CGP pipeline incomplete

## Session Notes (2026-03-02)

### CI gates unblocked (PR #759)
- `SQL Policy Lint` — no longer fails on `TO anon` grants (role-alias resolution via `format()`)
- `Python Tests` — no longer hits `CollectorRegistry` collision (service-local registry in `yt.py`)
- **Codex implication:** `--admin` bypass no longer needed for these two checks
- Verify: `make -C pmoves codex-parity-check` should still show 100% coverage

### Production baseline
- `make -C pmoves verify-all` → 25/25 parallel readiness, 19/24 retro
- 5 retro ERR are container-only checks (Jellyfin, Firefly, Wger, Open Notebook, Presign)
- Prometheus targets timeout is pre-existing, non-blocking

### Supabase runtime
- Reconciled to `SUPABASE_RUNTIME=compose` via `make -C pmoves supa-runtime-reconcile`
- 11 CLI containers stopped; compose-managed containers start with next `make -C pmoves up`

### Housekeeping
- Worktrees: 1 (main only) — all merged/stale worktrees cleaned
- Stashes: 13 on Hardened/older branches
- Queue guard log: `pmoves/docs/logs/queue_guard_20260302_074034.json`

## Priority links

- Codex submodule audit:
  - `pmoves/docs/AGENTS/CODEX_SUBMODULE_INTEGRATION_AUDIT.md`
- Codex ecosystem traversal:
  - `pmoves/docs/AGENTS/CODEX_ECOSYSTEM_TRAVERSAL.md`
- Hyperdimensions control plane taxonomy:
  - `pmoves/docs/AGENTS/PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md`
- Claude parity map:
  - `pmoves/docs/AGENTS/CODEX_CLAUDE_PARITY_MAP.md`
- Persona style playbook:
  - `pmoves/docs/AGENTS/CODEX_PERSONA_STYLE_PLAYBOOK.md`
- Runtime protocol (focus + scout):
  - `pmoves/docs/AGENTS/CODEX_RUNTIME_PROTOCOL.md`
- Operation Dock.Tier Git.Flare parity runbook:
  - `pmoves/docs/AGENTS/OPERATION_DOCK_TIER_GIT_FLARE_PARITY.md`
- Unified taxonomy:
  - `pmoves/docs/AGENTS/PMOVES_UNIFIED_AGENT_TAXONOMY.md`
- Codex + Cipher implementation map:
  - `pmoves/docs/AGENTS/CODEX_CIPHER_MEMORY_IMPLEMENTATION_MAP.md`
- PMOVES skill bundles:
  - `pmoves/docs/AGENTS/PmovesSKillZ.md`
- Existing Claude context stack:
  - `.claude/CLAUDE.md`
  - `.claude/context/`
