# Claude Handoff: Graphiti Protocol on UI 4482

_Created: 2026-03-04_
_Lane: `PHI-4482-T1`_
_Owner: `claude-opus`_
_Reviewer: `codex-gpt5`_

## Mission
Implement and validate Graphiti protocol visibility for the PMOVES UI on port `4482`, centered on Notebook Workbench/operator flow.

## Scope (Allowed Files)
- `pmoves/ui/app/**`
- `pmoves/ui/components/**`
- `pmoves/docs/infrastructure/UI_NOTEBOOK_WORKBENCH.md`
- `pmoves/docs/AGENTS/AI_GRAPHITI_PROTOCOL.md` (only if protocol wording must be clarified for UI behavior)
- `docs/AGENT_TRAIL.md` (Graphiti entry for this lane)

## Objectives
1. Expose Graphiti status in the UI lane served on `http://localhost:4482`.
2. Ensure the Graphiti artifact path/fallback behavior is explicit and non-failing when artifact is missing.
3. Document operator validation steps for Graphiti checks in the Notebook Workbench guide.

## Required Deliverables
1. A visible Graphiti status element in the 4482 UI path (Notebook Workbench or dashboard route that operators already use).
2. Graceful fallback state when Graphiti artifact is unavailable (no crash, clear warning).
3. Updated docs with exact smoke/verification commands and expected outputs.
4. A Graphiti trail entry and lane release note.

## Acceptance Criteria
1. `npm --prefix pmoves/ui run lint` passes for changed files (or changes are isolated behind existing known lint debt with rationale).
2. UI on `4482` renders Graphiti status without runtime errors.
3. Docs include at least one deterministic check command and one expected success signal.
4. `docs/AGENT_TRAIL.md` includes Claude Graphiti block with:
   - Done
   - Left Behind
   - For Next Agent

## Evidence Commands
```bash
# UI lint / static validation
npm --prefix pmoves/ui run lint

# Workbench smoke (uses current repo target)
make -C pmoves notebook-workbench-smoke

# Optional API probe if Graphiti status is API-backed
curl -s http://localhost:4482/api/audit/summary | jq '.summary.graphiti'
```

## Scope Guardrails
- Do not alter unrelated service runtime behavior.
- Do not reformat broad UI surfaces outside Graphiti/Workbench paths.
- Keep commits atomic:
  - `feat(ui): graphiti status on 4482 lane`
  - `docs(ui): graphiti workbench validation notes`

## Handoff Back to Codex
When complete, provide:
1. PR link(s)
2. commit SHAs
3. exact validation command output summary
4. unresolved risks, if any
