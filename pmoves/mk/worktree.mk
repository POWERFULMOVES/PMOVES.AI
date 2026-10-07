# mk/worktree.mk — worktree sitrep
# ===========================================================================
#
# .claude/CLAUDE.md and .claude/PATTERNS.md have documented these two targets
# as the AUTHORITATIVE worktree check, telling readers to prefer them to
# per-worktree spot checks. Neither existed. Both sat in the command-anchor
# baseline as GHOST_TARGETs, so following the documented road produced:
#
#     make: *** No rule to make target 'worktree-sitrep-strict'.  Stop.
#
# and the reader hand-rolled `git status` across ~130 worktrees instead — the
# exact thing the doc was written to prevent.
#
#   worktree-sitrep         snapshot; always exits 0
#   worktree-sitrep-strict  gate; non-zero on any dirty or conflicted worktree
#   worktree-sitrep-json    machine-readable
#
# Husks (emptied directories) and clean-but-stale worktrees are reported but do
# NOT fail the gate — they are housekeeping, not uncommitted work, and a gate
# that fires on them gets muted.
#
# Uses $(PYTHON), not a bare `python`: pmoves/Makefile:57-75 resolves that to
# python3 on POSIX, python on Windows, and the .venv-pmoves interpreter when
# one exists. A bare `python` dies with 'command not found' on any Linux node
# without a python shim — recreating the exact GHOST_TARGET dead end this file
# was written to remove.

.PHONY: worktree-sitrep worktree-sitrep-strict worktree-sitrep-json

worktree-sitrep:
	@$(PYTHON) $(CURDIR)/tools/worktree_sitrep.py

worktree-sitrep-strict:
	@$(PYTHON) $(CURDIR)/tools/worktree_sitrep.py --strict

worktree-sitrep-json:
	@$(PYTHON) $(CURDIR)/tools/worktree_sitrep.py --json

# ---------------------------------------------------------------------------
# Orphan-branch ratchet (2026-10-07) — work stranded off main
# ---------------------------------------------------------------------------
# Measured 2026-10-07: 47 branches on origin held 92 commits whose change is
# not on main and that no open PR carries. Squash merges -- including a squash
# of a DIFFERENT branch -- are recognised by merged-PR-head matching and a
# no-op `git merge-tree` replay; commits that conflict are UNCERTAIN, not counted.
#
#   orphan-ratchet           remote heads vs main; PR facts from one `gh pr list`
#   orphan-ratchet-local     this node's local branches + detached worktrees
#   orphan-ratchet-json      remote mode, machine-readable
#   orphan-ratchet-baseline  re-record remote findings (keeps reasons; new
#                            entries get an EMPTY reason that fails until filled)
#
# Read-only: never pushes, deletes or moves a ref. Squash merges are handled
# (merged PR head + `git cherry`), so a squash-merged branch is not an orphan.
# Exit 0 clean / 1 findings / 3 COULD NOT MEASURE (gh or remote unavailable) —
# and `make` collapses 1 and 3 to 2, so call the tool directly when the
# distinction matters (CI does). Fetch first: `git fetch origin`.

.PHONY: orphan-ratchet orphan-ratchet-local orphan-ratchet-json orphan-ratchet-baseline

orphan-ratchet: ## Ratchet branches on origin holding commits not on main whose PRs merged/closed (0 clean / 1 findings / 3 could not measure)
	@$(PYTHON) $(CURDIR)/tools/orphan_branch_ratchet.py remote $(ARGS)

orphan-ratchet-local: ## Report this node's unpushed / upstream-gone branch commits not on main (read-only)
	@$(PYTHON) $(CURDIR)/tools/orphan_branch_ratchet.py local $(ARGS)

orphan-ratchet-json: ## Same as orphan-ratchet, JSON output
	@$(PYTHON) $(CURDIR)/tools/orphan_branch_ratchet.py remote --json $(ARGS)

orphan-ratchet-baseline: ## Re-record the remote orphan baseline (deliberate: every new entry needs a reason written in)
	@$(PYTHON) $(CURDIR)/tools/orphan_branch_ratchet.py remote --write-baseline $(ARGS)
