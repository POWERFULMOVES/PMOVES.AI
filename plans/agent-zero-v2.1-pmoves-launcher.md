# Implementation Plan: Agent Zero v2.1 Update + PMOVES Fork Launcher

## Overview
Update the running Agent Zero instance from v1.20 to v2.1, audit the custom plugins installed under `usr/plugins/`, and customize the new v2.1 launcher so it can launch the PMOVES.AI fork (`PMOVES.AI` submodule/project) instead of vanilla Agent Zero.

## Architecture Decisions
- Use a git worktree in `/tmp/` for all v2.1 inspection and launcher customization; never branch-switch in `/a0` or `/a0/usr/projects/project_2`.
- Preserve user-space plugins at `/a0/usr/plugins/` across the framework update (they survive updates by design).
- Launcher customization will be packaged as a user plugin under `/a0/usr/plugins/pmoves_launcher/` so it survives future framework updates.
- The PMOVES fork is already a git submodule/project at `/a0/usr/projects/project_2`; the launcher only needs to know how to bootstrap/start it.

## Task List

### Phase 1: Discovery & Risk Assessment
- [ ] Task 1: Check out Agent Zero v2.1 in a temporary worktree (`/tmp/a0-v2.1-worktree`).
- [ ] Task 2: Inventory v2.1 launcher files (`run_ui.py`, `helpers/server_startup.py`, `helpers/runtime.py`, `docker/run/`, `docs/guides/launcher.md`).
- [ ] Task 3: Compare v1.20→v2.1 breaking changes that affect plugins, startup, or environment.
- [ ] Task 4: Inventory custom plugins in `/a0/usr/plugins/` and identify any that may conflict with v2.1.

### Phase 2: Plugin Review
- [ ] Task 5: Validate each custom plugin's `plugin.yaml` against v2.1 manifest expectations.
- [ ] Task 6: Check extension point paths (old flattened vs new `_functions/.../start|end/` layout).
- [ ] Task 7: Test-load critical custom plugins (`a0_agent_skills`, `a0_swarm`, `channels_provider`, etc.) in the worktree and capture errors.
- [ ] Task 8: Produce plugin audit report with recommended fixes/removals.

### Phase 3: Launcher Customization
- [ ] Task 9: Read the v2.1 launcher documentation and entry-point code.
- [ ] Task 10: Identify the minimal change to make the launcher start the PMOVES.AI fork (env var, CLI flag, or wrapper).
- [ ] Task 11: Create `/a0/usr/plugins/pmoves_launcher/` plugin with any required tools, extensions, prompts, or API endpoints.
- [ ] Task 12: Add a `pmoves-launch` helper/wrapper that invokes `python3 -m pmoves.tools.mini_cli` or the appropriate PMOVES bootstrap command.

### Phase 4: Update & Verification
- [ ] Task 13: Apply the framework update to `/a0` (git fetch + checkout v2.1) while preserving `usr/`.
- [ ] Task 14: Reinstall/refresh Python dependencies (`requirements.txt` / `pyproject.toml` changes).
- [ ] Task 15: Restart Agent Zero and verify it boots without plugin errors.
- [ ] Task 16: Verify the PMOVES launcher works end-to-end (starts PMOVES services or opens the right project).

### Checkpoint: After Tasks 1-4
- [ ] Worktree exists at `/tmp/a0-v2.1-worktree`.
- [ ] Launcher file list documented.
- [ ] Custom plugin inventory documented.

### Checkpoint: After Tasks 5-8
- [ ] Plugin audit report saved.
- [ ] No blocking plugin conflicts identified, or fixes applied.

### Checkpoint: After Tasks 9-16
- [ ] Launcher plugin created and enabled.
- [ ] Agent Zero v2.1 running.
- [ ] PMOVES launcher smoke test passes.

## Risks and Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Updating in place breaks running /a0 instance | High | Stage in worktree; snapshot `/a0/usr/` first; rollback plan via git reflog |
| v2.1 plugin manifest changes break custom plugins | Medium | Audit `plugin.yaml` and extension layout before update |
| Launcher customization needs deep framework changes | Medium | Keep changes in `usr/plugins/` plugin; avoid patching core files |
| PMOVES submodule pointer drift | Low | Verify `project_2` is on intended commit before launcher test |

## Open Questions
- Does PMOVES need the launcher to start the whole compose stack, or just open the PMOVES project in Agent Zero?
- Which Agent Zero entry point is currently used in this sidecar (run_ui.py, Docker, or something else)?
