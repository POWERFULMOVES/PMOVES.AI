# Operator-Facing Excerpts from `.claude/CLAUDE.md`

**Last synced:** 2026-04-15
**Source of truth:** `.claude/CLAUDE.md` sections:
- "Submodule working-tree wipe recovery" (currently lines 297–323)
- "CodeQL dataflow sanitizer pattern" (currently lines 487–542)

---

## Synchronization Note

These sections are **mirrored verbatim** from `.claude/CLAUDE.md` for operator
reference from `pmoves/docs/AGENTS/`. `.claude/CLAUDE.md` is the single source
of truth; any update must:

1. Edit the source section in `.claude/CLAUDE.md` first.
2. Update the corresponding section below (verbatim copy — no paraphrasing).
3. Update the **Last synced** date at the top of this file.

If the source file drifts without a matching update here, the mirror is stale.
A future enhancement (tracked informally — no ticket yet) is a
`scripts/validate-claude-md-mirrors.sh` CI check that fails when the two
diverge. Until that exists, freshness is a manual review discipline during PR
review of any change to the source sections.

**Why mirror at all?** Operators browsing `pmoves/docs/AGENTS/` expect to find
runbooks in that directory. `.claude/CLAUDE.md` is primarily an LLM context
file and isn't indexed in the agents README's tier TOC. The mirror surfaces
these two operator-critical runbooks through the normal operator documentation
path without making `.claude/CLAUDE.md` double-duty.

Grep for the section headers below to navigate directly:
- `## Submodule Working-Tree Wipe Recovery`
- `## CodeQL Dataflow Sanitizer Pattern`

---

## Submodule Working-Tree Wipe Recovery

When a submodule shows mass deletions (thousands of files gone but HEAD
intact), **do NOT** run `git submodule update --init --recursive`. That
resets to the superproject's tracked gitlink — may regress integration
commits that were ahead of the gitlink locally.

**Correct recovery:**

1. Confirm HEAD is intact and check gitlink skew:
   ```bash
   git -C <submodule> log --oneline -5
   git -C <submodule> rev-parse HEAD
   git ls-tree HEAD <submodule>                 # from superproject
   ```

2. If HEAD has commits you want to keep, restore working tree from HEAD
   without touching HEAD itself:
   ```bash
   git -C <submodule> restore .
   ```

3. If HEAD is also wrong, stash submodule commits before update:
   ```bash
   git -C <submodule> stash --include-untracked \
     -m "pre-update: $(git -C <submodule> rev-parse --short HEAD)"
   git submodule update --init --recursive <submodule>
   git -C <submodule> stash pop                 # if applicable
   ```

**Rule of thumb:** "read before write" on submodule state. Always check
`git log` and `git rev-parse HEAD` inside the submodule before running any
submodule reset command. `restore` rewrites the working tree from HEAD's
tree; `update` resets HEAD to the superproject pointer.

---

## CodeQL Dataflow Sanitizer Pattern

CodeQL's `py/full-ssrf` and `py/clear-text-logging-sensitive-data` queries
track taint through function calls and variable assignments. If your code
*is* safe but CodeQL can't prove it (e.g., validation is split across
multiple functions, or happens via `int()` conversion which CodeQL doesn't
model as a sanitizer), add an **explicit sanitizer boundary** call that
CodeQL's dataflow model recognizes.

**For SSRF (URL path / host taint):**

```python
from urllib.parse import quote

# BEFORE — path is validated upstream but CodeQL doesn't see the sanitizer
path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
response = pool.request("GET", path, headers={"Host": host})

# AFTER — explicit quote() call is CodeQL's recognized sanitizer
safe_path = quote(parsed.path or "/", safe="/%")
if parsed.query:
    safe_query = quote(parsed.query, safe="=&%")
    request_path = f"{safe_path}?{safe_query}"
else:
    request_path = safe_path
safe_host = quote(host, safe="")
response = pool.request("GET", request_path, headers={"Host": safe_host})
```

Runtime behavior is identical — `quote()` with these `safe` args passes
already-valid characters through unchanged. The purpose is *not* additional
security; it's making the sanitizer visible to the static analyzer.

**For sensitive-logging:**

```python
# BEFORE — CodeQL sees env-var string flowing into a log call
logger.warning("Invalid trusted proxy entry: %s", entry)

# AFTER — log only length; operators can inspect the env var directly
logger.warning("Invalid trusted proxy entry (length=%d)", len(entry))
```

Taint is broken at `len()` — the analyzer sees an int, not the string.

**When to use this pattern:**
- The real security fix lives elsewhere (upstream validation, allowlist, etc.)
- CodeQL is flagging a dataflow that is safe but not provable statically
- Adding a runtime-noop sanitizer is cheaper than restructuring validation

**When NOT to use this pattern:**
- If CodeQL is flagging a *real* dataflow bug, remediate the underlying issue
- If you can't articulate why the original code was safe, the answer
  isn't "add `quote()` until the warning goes away" — it's "read the
  code more carefully"

**Reference implementation:** PR #1227 commit `067c4e25` —
`pmoves/services/hi-rag-gateway-v2/security.py` (trusted-proxy length
logging + `quote()` SSRF sanitizer for outbound request construction).
