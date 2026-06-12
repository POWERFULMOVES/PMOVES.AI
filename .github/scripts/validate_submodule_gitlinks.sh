#!/usr/bin/env bash
# Submodule branch-strategy gate (API-based — no submodule clone, no deep history).
#
# Enforces, at PR time, that every submodule gitlink CHANGED in the PR obeys the
# .gitmodules branch strategy:
#   1. DANGLING — the new gitlink must be ON its declared tracked branch. A
#      pointer to a commit that isn't on the tracked branch (a feature branch, a
#      fork-default, an un-merged sha) is "dangling / not pointed correctly".
#   2. LEFT / ROLLBACK — the new gitlink must be a forward advance from the base
#      gitlink. A backward or sideways move ("left/right") is a rollback.
#
# Ancestry is resolved server-side via the GitHub compare API (gh api
# repos/<fork>/compare/A...B -> .status), so this needs NO local submodule clone
# and NO deep superproject history — only `git ls-tree` of the base + head
# commits (which the workflow fetches shallow). That keeps it disk-free, which
# matters: the self-hosted runners ran out of disk doing full-history checkouts.
#
# compare A...B .status semantics (B relative to A):
#   identical  B == A
#   behind     B is an ancestor of A   (B is "behind" A)
#   ahead      B has commits A doesn't  (B is "ahead" of A)
#   diverged   both sides have unique commits
#
# Requires: gh (authenticated via GH_TOKEN). Tracked branches + fork slugs are
# derived from .gitmodules, so ALL submodules are covered (no hardcoded list).
#
# Usage: validate_submodule_gitlinks.sh <base-ref> [--all]
set -uo pipefail

BASE_REF="${1:?usage: validate_submodule_gitlinks.sh <base-ref> [--all]}"
MODE="${2:-changed}"
fail=0

names=$(git config -f .gitmodules --get-regexp '^submodule\..*\.path$' \
          | sed -E 's/^submodule\.(.*)\.path .*/\1/')

while IFS= read -r name; do
  [ -z "$name" ] && continue
  path=$(git config -f .gitmodules --get "submodule.$name.path")
  branch=$(git config -f .gitmodules --get "submodule.$name.branch" 2>/dev/null || true)
  url=$(git config -f .gitmodules --get "submodule.$name.url" 2>/dev/null || true)

  if [ -z "${branch:-}" ]; then
    echo "warn  $name: no .gitmodules branch pin — branch strategy undefined, skipped"
    continue
  fi
  # Derive OWNER/REPO from the submodule URL (https or ssh form).
  slug=$(printf '%s' "$url" | sed -E 's#(git@github\.com:|https?://github\.com/)##; s#\.git$##')

  head_link=$(git ls-tree HEAD -- "$path" 2>/dev/null | awk '$2=="commit"{print $3}')
  base_link=$(git ls-tree "$BASE_REF" -- "$path" 2>/dev/null | awk '$2=="commit"{print $3}')

  [ -z "$head_link" ] && continue                                  # not a gitlink / removed
  if [ "$MODE" != "--all" ] && [ "$head_link" = "$base_link" ]; then
    continue                                                       # unchanged in this PR
  fi
  if [ -z "$slug" ]; then
    echo "FAIL  $name: no resolvable github.com URL in .gitmodules"
    fail=1; continue
  fi

  ok=1
  # 1. DANGLING — compare tracked-branch...head; on-branch iff head is behind/== branch.
  st=$(gh api "repos/$slug/compare/$branch...$head_link" --jq '.status' 2>/dev/null || echo "error")
  case "$st" in
    behind|identical) : ;;                                          # head is on the branch
    ahead)    echo "FAIL  $name: gitlink ${head_link:0:9} is AHEAD of '$branch' — commits not merged to the tracked branch (off-strategy)"; fail=1; ok=0 ;;
    diverged) echo "FAIL  $name: gitlink ${head_link:0:9} has DIVERGED from '$branch' (dangling — not on the tracked branch)"; fail=1; ok=0 ;;
    *)        echo "FAIL  $name: cannot compare ${head_link:0:9} against '$branch' on $slug (status='$st' — bad branch pin or unreachable sha?)"; fail=1; ok=0 ;;
  esac

  # 2. LEFT / ROLLBACK — compare base...head; forward iff head is ahead/== base.
  if [ -n "$base_link" ] && [ "$base_link" != "$head_link" ]; then
    st2=$(gh api "repos/$slug/compare/$base_link...$head_link" --jq '.status' 2>/dev/null || echo "error")
    case "$st2" in
      ahead|identical) : ;;                                         # forward advance
      behind)   echo "FAIL  $name: gitlink ${base_link:0:9} -> ${head_link:0:9} ROLLBACK (head is behind the base gitlink)"; fail=1; ok=0 ;;
      diverged) echo "FAIL  $name: gitlink ${base_link:0:9} -> ${head_link:0:9} SIDEWAYS (diverged — not a forward advance)"; fail=1; ok=0 ;;
      *)        echo "warn  $name: cannot compare base..head on $slug (status='$st2') — rollback check skipped" ;;
    esac
  fi

  [ "$ok" -eq 1 ] && echo "ok    $name ($branch): ${head_link:0:9}"
done <<< "$names"

echo ""
if [ "$fail" -ne 0 ]; then
  echo "❌ Submodule branch-strategy gate FAILED — see FAIL lines above."
  echo "   Every changed gitlink must be ON its .gitmodules tracked branch and a forward advance."
  echo "   Fix: check out a commit that is on origin/<tracked-branch> in the submodule"
  echo "        (sync the fork, or 'git submodule update --remote <path>'), then re-commit the gitlink."
  exit 1
fi
echo "✅ Submodule branch-strategy gate PASSED."
