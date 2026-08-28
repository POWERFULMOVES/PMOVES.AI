# followups-v1 LEARNINGS

The followups-v1 slice closed the 4 "not done" items from the mcpcli
docs: AGENTS.md open format adoption, HiRAG mcp.json registration,
v2 HiRAG promotion, submodule freshness check. 11 commits on
`feat/followups-v1`; 50/50 tests pass; PR open path is `rebase +
review` against `origin/main` (local main was 30+ commits behind at
slice start).

## Lesson 1: pair-review taxonomy applied to docs work

The mavis pair-review skill's 4-bucket observation taxonomy
(reasoning gap / semantic-naming drift / contract-correctness /
defense-in-depth) applies to docs work too, not just code. The
PMOVES-EXT marker convention in commit 3 is the defense-in-depth
half: the format reference is a doc convention, the test pins it
as a contract. A future PR that adds a PMOVES section without the
marker fails at PR time (test_agents_md_no_unmarked_pmovesspecific_sections),
not at "someone reads the file in 6 months and notices".

## Lesson 2: marker convention is grep-discoverable AND machine-checkable

The `<!-- PMOVES-EXT: name -->` marker is load-bearing on both
properties:
- **Grep-discoverable**: `grep -rn 'PMOVES-EXT:' AGENTS.md` returns
  every PMOVES-specific section, so a code review can spot
  unmarked sections in seconds.
- **Machine-checkable**: the 8 tests in
  `test_agents_md_format.py` (especially the inverse check,
  `test_agents_md_no_unmarked_pmovesspecific_sections`) fail at
  PR time if a future section is added without a marker.

Both properties are needed. A convention that's only machine-
checkable (no grep surface) is opaque; one that's only grep-
discoverable (no test) is unenforceable.

## Lesson 3: open format's 3 canonical section names are not a "rename all"

The agents.md open format names 3 canonical sections: "Dev
environment tips", "Testing instructions", "PR instructions".
PMOVES.AI's existing AGENTS.md had 2 of 3 with different names
(`## Build & Development Commands` and `## Testing`). The fix is
NOT to rename all 3 to the canonical names — it's to:
- Rename what the canonical name captures
  (`## Build & Development Commands` → `## Dev environment tips`)
- Adopt the canonical name for what the open format expected
  (`## Testing` → `## Testing instructions`)
- Keep PMOVES-specific content under `## PR instructions` +
  a sub-heading `### Commit & PR Guidelines (PMOVES extension)`
  so the PMOVES-specific content has a clear home

The PMOVES-specific commit guidelines are not lost — they live
under a sub-heading that makes their PMOVES-extended nature
explicit. A cold-start agent that knows the open format finds
the section by its canonical name; a PMOVES-aware agent finds
the sub-heading.

## Lesson 4: 5-surface wire-up pattern — SSE MCP servers touch 3-4 surfaces

The `pmoves_minimax_mcp` slice (#2612) established the 5-surface
pattern; HiRAG is the simpler case (SSE, not stdio), so it
touches 3 surfaces:
- `pmoves/config/agent_registry.yaml` (the source of truth)
- `.claude/mcp.json` (the runtime registration)
- `.claude/BOOTSTRAP.md` (the cold-start table)

(The other 2 surfaces — CGP example `mcps` and skill-pairings —
are for stdio MCP servers that need package install + skill
pairing. SSE-only MCP servers don't need them.)

## Lesson 5: drift-detector tests catch wire-up asymmetry

`test_hirag_wireup.py` doesn't test that HiRAG works at runtime
(the SSE connection + the underlying service). It tests that
**all 4 wire-up surfaces are consistent** — registry status
matches mcp.json transport matches BOOTSTRAP.md table. A future
PR that flips the registry status to `planned` (forgetting to
flip the BOOTSTRAP row), or that changes the transport to
`stdio` (forgetting to update the JSON), fails at PR time.

This is the "test the wire-up, not the runtime" pattern from
the mcpcli slice. Runtime tests are flaky and slow; wire-up
tests are deterministic and fast.

## Lesson 6: REMOTE-side vs LOCAL-side submodule checks are different tools

`pmoves/tools/submodule_integrity.py` checks the LOCAL checkout
— it requires the submodules to be initialized and reports
drifts (the local SHA != the parent gitlink). It does NOT
catch the case where the parent gitlink is fine but the
submodule's tracked branch has new commits on the remote that
haven't been consumed yet.

`pmoves/tools/submodule_freshness_check.py` is the REMOTE-side
complement. It walks every submodule, asks the remote
(`git ls-remote <url> refs/heads/<branch>`) for the tracked
branch's HEAD, and compares to the parent gitlink. Status
`remote_ahead` means "the submodule's tracked branch has
commits the parent hasn't picked up" — the operator can
`git submodule update --remote` to consume.

The two tools are complementary, not redundant. Both are
needed in CI; freshness is a weekly cron (drift accumulates
slowly), integrity is a pre-merge gate (drift must be zero
at PR time).

## Lesson 7: workflow-glue tests pin the patterns that bind workflow to tool

The 6 tests in `test_submodule_freshness_workflow.py` are
NOT testing the tool — those tests are in
`test_submodule_freshness_check.py`. The workflow-glue
tests are testing the YAML+bash that BIND the workflow to
the tool: `python` not `py`, `set -e -o pipefail`, the
canonical entry point, minimal permissions, weekly schedule,
artifact upload.

This is Lesson 12 from the Mavis harness v0 follow-ups
slice, restated: workflow glue needs code review, not just
unit tests. The `python`/`py` distinction was the bug
on #2623; the missing `pipefail` was the bug on #2568.
A test that asserts on the workflow text catches both at
PR time.

## What I'd do differently next slice

- **Rebase onto current main FIRST** (before the docs commits).
  Local main was 30+ commits behind origin/main; doing the
  AGENTS.md renames on a stale main risks landing commits
  that need to be re-done after a rebase. Better: rebase
  the worktree to current origin/main before any work, so
  the slice builds on the right base.

- **The v2 HiRAG promotion should be its own slice** when the
  operator decides. The `pmoves-hirag-mcp` submodule is in
  place; the registry has the `pmoves_hirag_mcp` entry
  (status=active); bumping v1 → v2 in the entry is one line.
  Doing it in a separate slice gives the operator a clean
  PR to review and approve.
