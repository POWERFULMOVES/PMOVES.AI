# Agent Zero v1.3 Sync Plan

Last updated: 2026-03-29
Author: KiloCode GLM ▲ | DARKXSIDE ✦ witness

## Current State

| Item | Value |
|------|-------|
| PMOVES pinned commit | `2e000aa304e` (March 7, 2026) |
| Upstream version | v1.3 (March 27, 2026) |
| Gap | ~502 upstream commits |
| PMOVES-specific patches | 24 commits to preserve |
| Risk to existing PRs | None (zero coupling) |

## Sync Strategy

### Phase 1: Assessment (Pre-Sync)
- [ ] Create a fresh clone of PMOVES-Agent-Zero at upstream v1.3
- [ ] Diff PMOVES hardened branch against upstream v1.3
- [ ] Catalog all PMOVES-specific files and patches
- [ ] Identify upstream changes that conflict with PMOVES patches
- [ ] Create conflict resolution plan

### Phase 2: PMOVES Patch Inventory

The following PMOVES-specific patches MUST be preserved during sync:

#### Security Hardening
- Path containment and non-root container configuration
- NATS auth/credentials integration
- Sandbox fail-closed policies
- Telegram/webhook security patches

#### Operator Documentation
- CLAUDE.md — PMOVES service map and development patterns
- Codex operator home and ecosystem traversal docs
- PMOVES.AI_INTEGRATION.md — integration guide

#### Runtime Configuration
- docker-compose.pmoves.yml — PMOVES service topology
- env.shared — PMOVES environment variables
- Credential bootstrap scripts
- conf/model_providers.yaml — PMOVES TensorZero/PMOVES provider entries

#### Feature Wiring
- Persona-based agent creation (Supabase pmoves_core.personas)
- TensorZero provider integration
- Prometheus metrics endpoints
- PMOVES-branded MCP server defaults (make a0-mcp-seed)

#### Governance
- CODEOWNERS file
- Dependabot configuration
- CI audit gates
- Hardened Dockerfile

### Phase 3: Execution

1. **Branch from upstream v1.3:**
   ```bash
   cd PMOVES-Agent-Zero
   git fetch upstream
   git checkout -b pmoves-hardened-v1.3 upstream/main
   ```

2. **Cherry-pick or re-apply PMOVES patches:**
   - Start with security hardening (most critical)
   - Then runtime configuration
   - Then feature wiring
   - Then documentation
   - Resolve any conflicts with upstream v1.3 changes

3. **Validate:**
   ```bash
   # Personas
   docker exec -it supabase_db psql -c "select name,version from pmoves_core.personas;"
   # MCP defaults
   make -C pmoves a0-mcp-seed && cat pmoves/data/agent-zero/runtime/mcp/servers.env
   # Health
   curl -s http://localhost:8080/healthz
   # Prometheus
   curl -s http://localhost:8080/metrics | head -5
   ```

4. **Update gitlink:**
   ```bash
   cd ..
   git add PMOVES-Agent-Zero
   git commit -m "feat(submodule): sync PMOVES-Agent-Zero to v1.3 with hardened patches"
   ```

### Phase 4: Post-Sync Validation

- [ ] Full smoke: `make -C pmoves smoke`
- [ ] Agent smoke: `make -C pmoves agents-headless-smoke`
- [ ] MCP smoke: `make -C pmoves archon-mcp-smoke`
- [ ] GPU smoke: `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu`
- [ ] Codex parity: verify CLAUDE.md and Codex docs reflect v1.3 changes
- [ ] AGNOTE4482 signoff: complete AGNOTE4482_SIGNOFF_CHECKLIST.md

### Phase 5: Cadence

Per AGNOTE4482 recommendations:
- Check upstream tags each sprint (weekly)
- Update gap report if drift exceeds 100 commits
- Maintain weekly release-note/CVE intake funnel

## Conflict Risk Areas

| Area | Risk | Mitigation |
|------|------|-----------|
| MCP server (python/helpers/mcp_server.py) | Medium — upstream may have refactored | Test MCP endpoint after sync, re-apply PMOVES changes if needed |
| Docker configuration | Low — PMOVES uses separate compose file | Keep docker-compose.pmoves.yml as overlay |
| Model providers | Low — PMOVES adds TensorZero, upstream has LiteLLM | Merge provider lists, keep TensorZero as primary |
| Knowledge tools | Medium — upstream may have changed tool interface | Test knowledge import/query after sync |

## References

- Gap report: pmoves/docs/AGENTS/AGNOTE4482_AGENT_ZERO_V1_3_GAP_REPORT.md
- Signoff checklist: pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md
- CLAWZ coding plan alignment: pmoves/docs/AGENTS/AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md
- Claw taxonomy: pmoves/docs/CLAW_TAXONOMY.md
- KRISS KROSS parity: pmoves/docs/AGENTS/KRISS_KROSS_ACK.md
