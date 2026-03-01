# Submodule Codex Homes

This directory tracks Codex operator overlays for submodules that do not yet
ship native `.codex` assets.

Purpose:
- keep PMOVES release lanes deterministic without forcing submodule pointer churn
- provide minimum Codex command parity for focus modules
- give `pmoves/scripts/codex_submodule_audit.py` a stable artifact path to score

Naming:
- primary key: `<submodule-path-with-slashes-replaced-by-__>.md`
- fallback key: `<submodule-basename>.md`

The audit script records these as:
- `overlay:pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/<name>.md`

Maintenance:
- Regenerate and verify coverage with `make -C pmoves codex-audit`.
- If a new submodule is added to `.gitmodules`, add a matching overlay file in this folder in the same PR.
- Keep overlays docs-only and deterministic; do not change submodule pointers in this lane.
