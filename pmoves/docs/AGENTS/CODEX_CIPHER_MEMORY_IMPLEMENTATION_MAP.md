# Codex + Cipher Memory Implementation Map
_Last updated: 2026-02-16_

This dossier maps where Codex integration and Cipher Memory integration exist in PMOVES.AI, and gives an operator-facing hygiene snapshot for active worktrees.

## Codex implementation locations

### Operator onboarding + parity docs
- `pmoves/docs/AGENTS/CODEX_OPERATOR_HOME.md`
- `pmoves/docs/AGENTS/CODEX_CLAUDE_PARITY_MAP.md`
- `pmoves/docs/AGENTS/CODEX_SUBMODULE_INTEGRATION_AUDIT.md`
- `pmoves/docs/AGENTS/CODEX_PERSONA_STYLE_PLAYBOOK.md`
- `.codex/README.md`
- `pmoves/docs/codex_full_config_bundle/README-Codex-MCP-Full.md`

### Codex command/bootstrap scripts
- `pmoves/scripts/codex_bootstrap.ps1`
- `pmoves/scripts/codex_bootstrap.sh`
- `pmoves/scripts/codex_apply_config.ps1`
- `pmoves/scripts/codex_submodule_audit.py`
- `pmoves/scripts/codex_health_quick.py`

### Codex Make targets
- `pmoves/mk/codex.mk`
  - `codex-config`
  - `codex-audit`
  - `codex-home`
  - `codex-health-quick`
  - `secrets-audit`
  - `tooling-audit`

### Layered audit + showtime extensions (Codex-led)
- `pmoves/mk/preflight.mk`
  - `submodule-layer-validate-one`
  - `submodule-layer-validate-all`
  - `audit-layers-static`
  - `audit-layers-runtime`
  - `showtime-links`
  - `showtime-links-strict`
- `pmoves/tools/submodule_layer_validate.py`
- `pmoves/tools/submodule_layer_runall.py`
- `pmoves/tools/showtime_verify_links.py`

## Cipher Memory implementation locations

### Cipher MCP bridge (repo-local)
- `pmoves-cipher-mcp/README.md`
- `pmoves-cipher-mcp/cipher_mcp/server.py`
- `pmoves-cipher-mcp/cipher_mcp/tools.py`
- `pmoves-cipher-mcp/cipher_mcp/client.py`
- `pmoves-cipher-mcp/main.py`

### Claude wiring for Cipher MCP
- `.claude/mcp.json`
- `.claude/CLAUDE.md` (Cipher section)
- `.claude/context/services-catalog.md` (Cipher service catalog)
- `.claude/skills/pmoves-cipher-memory/SKILL.md`
- `.claude/skills/pmoves-cipher-memory/skill.json`

### Runtime service wiring
- `pmoves/docker-compose.yml` (cipher-api service/profile)

## Worktree hygiene snapshot

### Clean/near-clean worktrees
- `PMOVES.AI-hardened-audit` (clean)
- `PMOVES.AI-hardened-ci` (clean)
- `PMOVES.AI-slice-ci-ghcr` (clean)
- `PMOVES.AI-submodule-audit` (clean after artifact cleanup)

### Dirty worktrees requiring triage
- `PMOVES.AI` (root branch): large mixed change-set (code, docs, workflows, submodules)
- `PMOVES.AI-main-audit`: many submodule pointer edits and integration updates pending commit policy
- `PMOVES.AI-slice-cipher`: includes unresolved merge conflicts (`UU`) in:
  - `.gitignore`
  - `pmoves/docker-compose.yml`

## Cleanup strategy (safe path)

1. Keep implementation work in clean worktrees (`PMOVES.AI-submodule-audit`, `PMOVES.AI-hardened-*`, `PMOVES.AI-slice-ci-ghcr`).
2. For dirty worktrees, create a triage commit-plan before touching files:
   - `git status --short`
   - `git diff --name-only`
   - split by lane (CI / Codex / Cipher / service runtime / docs).
3. Resolve conflict worktrees first (`PMOVES.AI-slice-cipher`) before any new feature commits there.
4. Avoid deleting generated artifacts manually; prefer `git clean -fd` in targeted clean-up worktrees.

