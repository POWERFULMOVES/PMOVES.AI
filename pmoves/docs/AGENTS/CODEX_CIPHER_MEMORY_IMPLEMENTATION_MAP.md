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

## Cipher Memory Resilience Categories

Cipher Memory serves as the Layer 2 recovery backbone for all PMOVES agents. The following categories are defined in [AGENT_RESILIENCE_PATTERNS.md](./AGENT_RESILIENCE_PATTERNS.md#layer-2-cipher-memory-integration):

| Category | Purpose | TTL |
|----------|---------|-----|
| `agent_plan` | Pre-flight plan for resumable work | 7 days |
| `agent_checkpoint` | Mid-work progress snapshot (after each commit+push) | 3 days |
| `agent_completion` | Final summary of all changes (after PR creation) | 30 days |

These categories are declared per-agent in `pmoves/config/agent_registry.yaml` under the `resilience.cipher_categories` field.

## Cipher Memory implementation locations

### Cipher MCP bridge (repo-local)
- `pmoves-cipher-mcp/README.md`
- `pmoves-cipher-mcp/cipher_mcp/server.py`
- `pmoves-cipher-mcp/cipher_mcp/tools.py`
- `pmoves-cipher-mcp/cipher_mcp/client.py`
- `pmoves-cipher-mcp/main.py`
- `pmoves-cipher-mcp/pyproject.toml` — **Fixed** (commit `17cc8706`): added hatchling `[tool.hatch.build.targets.wheel]` package discovery so `pip install -e .` finds `cipher_mcp/` correctly

### Claude wiring for Cipher MCP
- `.claude/mcp.json`
- `.claude/CLAUDE.md` (Cipher section)
- `.claude/context/services-catalog.md` (Cipher service catalog)
- `.claude/skills/pmoves-cipher-memory/SKILL.md`
- `.claude/skills/pmoves-cipher-memory/skill.json`

### Runtime service wiring
- `pmoves/docker-compose.yml` (cipher-api service/profile)

## Worktree hygiene checks (runtime-verified)

### Verify before acting
- Run `git worktree list` to enumerate active worktrees.
- For each worktree, run:
  - `git -C <worktree-path> status --short`
  - `git -C <worktree-path> branch --show-current`
- If merge/cherry-pick state is suspected, inspect:
  - `git -C <worktree-path> status`
  - `git -C <worktree-path> rev-parse -q --verify MERGE_HEAD`

### Operator note
- Do not treat historical clean/dirty examples as current truth.
- Use `make -C pmoves worktree-sitrep` and `make -C pmoves worktree-sitrep-strict` as the authoritative snapshot/gate for current state.

## Cleanup strategy (safe path)

1. Keep implementation work in clean worktrees (`PMOVES.AI-submodule-audit`, `PMOVES.AI-hardened-*`, `PMOVES.AI-slice-ci-ghcr`).
2. For dirty worktrees, create a triage commit-plan before touching files:
   - `git status --short`
   - `git diff --name-only`
   - split by lane (CI / Codex / Cipher / service runtime / docs).
3. Resolve conflict worktrees first (`PMOVES.AI-slice-cipher`) before any new feature commits there.
4. Avoid deleting generated artifacts manually; prefer `git clean -fd` in targeted clean-up worktrees.
