# Damage-Control Hook Recovery Runbook

Recovery procedure for the "stuck hook" failure mode where `patterns.yaml`
has unresolved merge conflict markers and the `bash-tool-damage-control.py`
hook fails closed, blocking ALL Bash commands.

> Last updated: 2026-04-13
> Origin: observed during Phase 5.5 Part 2 (2026-04-12), when a rebase
> conflict on `patterns.yaml` left conflict markers in place and the next
> `git status` invocation was blocked by its own safety system.

---

## Symptom recognition

Error message (appears on EVERY Bash invocation):

```
SECURITY: Failed to parse C:\...\patterns.yaml: while scanning a simple key
  in "C:\...\patterns.yaml", line 893, column 1
could not find expected ':'
  in "C:\...\patterns.yaml", line 894, column 3 — blocking all commands (fail-closed)
```

Or variants:
- `could not find expected ':'` — YAML key syntax error
- `mapping values are not allowed here` — value where a key is expected
- `did not find expected key` — malformed dict
- `found undefined alias` — corrupted anchor reference

**Diagnostic detail:** if the error mentions `patterns.yaml` line numbers
that correspond to merge conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`),
you've hit the stuck-hook deadlock.

---

## Root cause

`.claude/hooks/damage-control/bash-tool-damage-control.py` loads
`.claude/hooks/damage-control/patterns.yaml` at the start of every Bash
tool invocation. The hook uses this file to decide which commands to block
(e.g. `rm -rf`, raw `docker compose up`, `git push --force` on main). If
the YAML parser raises an exception, the hook cannot determine the policy,
so it fails closed (blocks all).

This is a SAFETY FEATURE. Fail-closed is correct when the policy file is
corrupt — we don't want to accidentally execute a blocked command because
the hook couldn't validate it. But it creates a deadlock during conflict
resolution: you can't run `git status` to diagnose, let alone `git add` +
`git rebase --continue` to resolve, because the very tool you need is
gated on the file that's broken.

---

## Recovery procedure

The escape hatch is the **Edit tool**, which routes through
`edit-tool-damage-control.py` (a SEPARATE hook). Edit's hook only blocks
paths in `readOnlyPaths` and `zeroAccessPaths`. `patterns.yaml` is
intentionally NOT in either list — it must be self-editable for recovery.

### Step 1 — Confirm the parse error

Use the **Read tool** on `patterns.yaml`:

```
Read(file_path="C:/Users/russe/Documents/GitHub/PMOVES.AI/.claude/hooks/damage-control/patterns.yaml")
```

Read does NOT route through the Bash hook. Look for:
- `<<<<<<< HEAD` / `=======` / `>>>>>>> <branch-sha>` markers
- Unclosed string literals or dangling colons
- Missing indentation after a new section was added

### Step 2 — Resolve the conflict using the Edit tool

Invoke Edit with `old_string` containing the full conflict region
(including all 3 marker lines) and `new_string` containing the merged
result:

```
Edit(
  file_path="C:/Users/russe/Documents/GitHub/PMOVES.AI/.claude/hooks/damage-control/patterns.yaml",
  old_string="""  - '\\bdeploy-vps-cluster\\b'
<<<<<<< HEAD
  # git cleanup patterns from branch A
  - 'rm\\s+.*\\.git[/\\\\]MERGE_HEAD'
=======
  # chit decode patterns from branch B
  - 'chit.*decode'
>>>>>>> 8138b0ffd8 (fix(hooks): add CHIT bypass)""",
  new_string="""  - '\\bdeploy-vps-cluster\\b'
  # git cleanup patterns from branch A
  - 'rm\\s+.*\\.git[/\\\\]MERGE_HEAD'
  # chit decode patterns from branch B
  - 'chit.*decode'"""
)
```

Choose which side of the conflict to keep based on the semantics:
usually both sides are additive and can be merged by concatenating them
(as shown above). The conflict occurred because both branches added
patterns to the same list without a common ancestor entry between them.

### Step 3 — Verify YAML parses

Re-read the file with the Read tool and eyeball it. Optionally scan for
any leftover `<<<`, `===`, `>>>` markers:

```
Grep(
  pattern="<<<<<<|======|>>>>>>",
  path="C:/Users/russe/Documents/GitHub/PMOVES.AI/.claude/hooks/damage-control/patterns.yaml"
)
```

If Grep returns matches, repeat Step 2 on the remaining conflicts.

### Step 4 — Bash tool should now work again

Try a simple status check:

```
Bash(command="git -C 'C:/Users/russe/Documents/GitHub/PMOVES.AI' status --short")
```

No restart needed — the hook re-reads `patterns.yaml` on every Bash
invocation. If the file parses cleanly now, Bash is immediately unblocked.

### Step 5 — Continue the git workflow

Stage the resolved file and continue the rebase:

```
Bash(command="git -C 'C:/Users/russe/Documents/GitHub/PMOVES.AI' add .claude/hooks/damage-control/patterns.yaml && git -C 'C:/Users/russe/Documents/GitHub/PMOVES.AI' rebase --continue")
```

Or `git merge --continue` / `git cherry-pick --continue` depending on
which operation was interrupted.

---

## Prevention

1. **Avoid rebases that touch `patterns.yaml`.** When possible, keep
   damage-control changes in dedicated branches that land quickly without
   parallel edits elsewhere.
2. **Resolve conflicts immediately.** If a rebase touches `patterns.yaml`,
   resolve the conflict BEFORE running any other commands — don't let
   the file sit broken and accidentally trigger a Bash call.
3. **Use `--ours` or `--theirs` for clearer merges.** If the conflict is
   purely additive and both sides should be kept, `git checkout --theirs`
   followed by manual insertion of the "ours" additions is often cleaner
   than leaving the marker block for manual editing.
4. **Test the file after editing.** Even without a rebase, a manual edit
   to `patterns.yaml` that introduces YAML syntax errors will trigger the
   same deadlock on the next Bash call. Always validate after writing:
   ```
   Read(file_path=".../patterns.yaml")  # eyeball the change
   ```
   And run a trivial Bash probe (`git status`) BEFORE doing anything
   expensive.

---

## Adjacent failure modes

### Edit tool also blocked

If the Edit tool refuses to touch `patterns.yaml` (e.g. because a future
patch added it to `zeroAccessPaths`), the fallback is the **Write tool**
— same separate hook, same graceful-degrade behavior on missing config.
If Write is also blocked:

- Ask the user to resolve the conflict manually via their editor
- Or have the user temporarily run `git rebase --abort` and retry the
  rebase with different conflict resolution strategy

### `patterns.yaml` missing entirely

If the file is deleted (not just broken), `bash-tool-damage-control.py`
falls back to empty config at `load_config()` (check line ~107 of the
hook source). Empty config means NO patterns are enforced — this is a
DIFFERENT failure mode (fail-open) and indicates the file was lost, not
corrupted. Recovery: restore from `git checkout HEAD -- .claude/hooks/damage-control/patterns.yaml`.

### Hook source itself is broken

If `bash-tool-damage-control.py` has a syntax error, every Bash invocation
will fail with a Python traceback (not a YAML parse error). Recovery:
Edit the hook source directly — it's not in readOnlyPaths by default.

---

## Related

- `.claude/hooks/damage-control/bash-tool-damage-control.py` — hook source
- `.claude/hooks/damage-control/edit-tool-damage-control.py` — Edit hook source
- `.claude/hooks/damage-control/patterns.yaml` — policy file (NOT self-protected)
- `pmoves/docs/operations/MODEL_ONBOARDING.md` — related ops runbook
- Historical context: Phase 5.5 Part 2 stuck-hook recovery (2026-04-12)

**`patterns.yaml` intentionally has no `readOnlyPaths` entry for itself.**
This is by design — the recovery path depends on Edit/Write being able
to modify the file when the Bash tool is broken. Don't add `patterns.yaml`
to either `readOnlyPaths` or `zeroAccessPaths` without providing an
alternative escape hatch.
