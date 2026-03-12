# Codex Home Overlay: PMOVES-Open-Notebook

Scope:
- PMOVES-Open-Notebook is the drafting, evidence, memory, and operator review lane for creator
  operations.
- Use this home when the task needs structured notes, campaign drafts, creator research, approval
  artifacts, reusable prompts, or cross-session memory for a creator workflow.

Traversal role:
- Stage drafts, notes, and supporting evidence before public-facing actions are executed.
- Use the notebook lane to preserve rationale, source evidence, and follow-up tasks so creator
  operations are traceable instead of ephemeral.

Read alongside:
- `pmoves/docs/PMOVES.AI PLANS/CREATOR_NETWORK_CONTROL_PLANE.md`
- `pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/PMOVES-Creator.md`
- `pmoves/docs/AGENTS/PMOVES_YT_CONTROL_WORKTREE_REVIEW.md`
- `pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/PMOVES.YT.md`
- `pmoves/docs/PMOVESCHIT/CATACLYSM_STUDIOS_INC.md`

Core checks:
- `git submodule status -- PMOVES-Open-Notebook`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-Open-Notebook`
- `make -C pmoves submodule-branch-policy-check`

Operator prompts:
- What notes or evidence should be captured before action is approved?
- What draft, comment template, playlist rationale, or creator brief should live in notebook form?
- What context should persist for later agent or human review?
- Which artifacts belong in notebook memory versus runtime audit rows in Supabase?

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`

