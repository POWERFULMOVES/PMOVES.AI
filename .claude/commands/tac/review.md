# TAC Tree Review

Run a TAC (Task-Action-Context) tree audit for an integration submodule.

## Usage
Accepts a submodule name or tree path as argument:
- `/tac:review health-wger` — Review health integration
- `/tac:review firefly-iii` — Review wealth integration
- `/tac:review n8n` — Review n8n workflows
- `/tac:review pmoves/configs/tac_trees/custom.tac.yaml` — Custom tree

## Instructions

1. Resolve the argument to a TAC tree path:
   - If arg matches a known name (`health-wger`, `firefly-iii`, `n8n`), map to `pmoves/configs/tac_trees/<name>.tac.yaml`
   - If arg is a file path, use directly
   - If no arg provided, list available trees in `pmoves/configs/tac_trees/`

2. Run the TAC runner in text mode:
   ```bash
   python pmoves/tools/tac_runner.py --format text <tree-path>
   ```

3. Also run in JSON mode for structured analysis:
   ```bash
   python pmoves/tools/tac_runner.py <tree-path>
   ```

4. Present results to the user with:
   - Overall pass/fail summary
   - Each failing node with its `agent_hint` (who should fix it)
   - Suggested next actions for each failure
   - If all pass, confirm the integration is audit-clean

5. For failing nodes, offer to fix them:
   - `file_exists` failures → offer to create the missing file
   - `grep` failures → offer to add the missing content
   - `manual` items → flag for user review

## Agent Assignment Hints
Each TAC node includes an `agent_hint` field suggesting which agent should handle the fix:
- `codex` — Claude Code CLI (documentation, config, scripts)
- `archon` — Archon agent (Supabase, prompts)
- `tokenism` — CHIT encoding
- `n8n` — n8n workflow creation

$ARGUMENTS
