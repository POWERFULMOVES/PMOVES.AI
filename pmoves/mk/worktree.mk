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

.PHONY: worktree-sitrep worktree-sitrep-strict worktree-sitrep-json

worktree-sitrep:
	@python $(CURDIR)/tools/worktree_sitrep.py

worktree-sitrep-strict:
	@python $(CURDIR)/tools/worktree_sitrep.py --strict

worktree-sitrep-json:
	@python $(CURDIR)/tools/worktree_sitrep.py --json
