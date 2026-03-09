# Submodule Codex Homes

_Last updated: 2026-03-01_

This directory tracks Codex operator overlays for submodules that do not yet
ship native `.codex` assets. Currently **41 files** (40 submodule overlays + this README).

## Purpose

- Keep PMOVES release lanes deterministic without forcing submodule pointer churn
- Provide minimum Codex command parity for focus modules
- Give `pmoves/scripts/codex_submodule_audit.py` a stable artifact path to score

## Naming Convention

Two naming keys are supported by the audit script:

| Key | Format | Example | When Used |
|-----|--------|---------|-----------|
| **Primary** | `<submodule-path-with-slashes-replaced-by-__>.md` | `pmoves__integrations__archon.md` | Nested submodules (path contains `/`) |
| **Fallback** | `<submodule-basename>.md` | `PMOVES-Agent-Zero.md` | Top-level submodules (most common) |

The casing in fallback names **matches the submodule name** from `.gitmodules`:
- Standard class (`PMOVES-` prefix): `PMOVES-Agent-Zero.md`, `PMOVES-BoTZ.md`
- Specialized class (`Pmoves-` prefix): `Pmoves-cipher.md`, `Pmoves-Health-wger.md`
- Utility class (`pmoves-` prefix): `pmoves-e2b-mcp-server.md`
- Dot-separated: `PMOVES.YT.md`

The audit script records these as:
- `overlay:pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/<name>.md`

## Known Orphans

| File | Status | Notes |
|------|--------|-------|
| `pmoves-e2b-mcp-server.md` | Orphaned | Gitlink removed from index (no `.gitmodules` entry); kept for reference |

## Maintenance

- Regenerate and verify coverage with `make -C pmoves codex-audit`.
- If a new submodule is added to `.gitmodules`, add a matching overlay file in this folder in the same PR.
- Keep overlays docs-only and deterministic; do not change submodule pointers in this lane.
- Do **not** rename files to "standardize" casing — the names match submodule names by design.
