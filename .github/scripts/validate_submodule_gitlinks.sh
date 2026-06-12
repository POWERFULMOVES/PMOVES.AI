#!/usr/bin/env bash
# Submodule branch-strategy gate.
#
# Enforces, at PR time, that every submodule gitlink CHANGED in the PR obeys the
# .gitmodules branch strategy:
#   1. DANGLING check  — the new gitlink commit must be ON its declared tracked
#      branch (reachable from origin/<branch>). A pointer to a commit that isn't
#      on the tracked branch (a feature branch, a fork-default, a random sha) is
#      "dangling / not pointed correctly".
#   2. LEFT / ROLLBACK — the new gitlink must be a forward advance from the base
#      gitlink (base is an ancestor of head). A backward or sideways move ("left/
#      right") is a rollback and fails.
#
# Tracked branches are derived from .gitmodules, so ALL submodules are covered
# (no hardcoded list to drift). Exit non-zero on any violation — this is a gate.
#
# Usage: validate_submodule_gitlinks.sh <base-ref> [--all]
#   <base-ref>  commit to diff gitlinks against (e.g. the PR base sha)
#   --all       validate EVERY submodule's current gitlink, not just changed ones
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

  if [ -z "${branch:-}" ]; then
    echo "warn  $name: no .gitmodules branch pin — branch strategy undefined, skipped"
    continue
  fi

  head_link=$(git ls-tree HEAD -- "$path" 2>/dev/null | awk '$2=="commit"{print $3}')
  base_link=$(git ls-tree "$BASE_REF" -- "$path" 2>/dev/null | awk '$2=="commit"{print $3}')

  [ -z "$head_link" ] && continue                                  # not a gitlink / removed
  if [ "$MODE" != "--all" ] && [ "$head_link" = "$base_link" ]; then
    continue                                                       # unchanged in this PR
  fi

  [ -e "$path/.git" ] || git submodule update --init -- "$path" >/dev/null 2>&1 || true
  if ! git -C "$path" fetch -q origin "$branch" 2>/dev/null; then
    echo "FAIL  $name: tracked branch 'origin/$branch' not fetchable (does it exist on the fork?)"
    fail=1; continue
  fi
  # A dangling gitlink is NOT on origin/<branch>, so fetching the branch alone
  # won't bring it. Fetch the gitlink SHAs explicitly so they're resolvable as
  # objects — GitHub serves any commit reachable from a ref (allowReachableSHA1InWant).
  git -C "$path" fetch -q origin "$head_link" 2>/dev/null || true
  [ -n "$base_link" ] && git -C "$path" fetch -q origin "$base_link" 2>/dev/null || true

  if ! git -C "$path" cat-file -e "${head_link}^{commit}" 2>/dev/null; then
    echo "FAIL  $name: gitlink ${head_link:0:9} is not a reachable commit on the fork (orphan/garbage pointer)"
    fail=1; continue
  fi

  ok=1
  # 1. DANGLING — head gitlink must be reachable from the tracked branch HEAD.
  if ! git -C "$path" merge-base --is-ancestor "$head_link" "origin/$branch" 2>/dev/null; then
    echo "FAIL  $name: gitlink ${head_link:0:9} is NOT on tracked branch '$branch' (dangling/divergent — off-strategy)"
    fail=1; ok=0
  fi
  # 2. LEFT / ROLLBACK — base gitlink (if resolvable) must be an ancestor of head.
  if [ -n "$base_link" ] && [ "$base_link" != "$head_link" ]; then
    if git -C "$path" cat-file -e "${base_link}^{commit}" 2>/dev/null; then
      if ! git -C "$path" merge-base --is-ancestor "$base_link" "$head_link" 2>/dev/null; then
        echo "FAIL  $name: gitlink ${base_link:0:9} -> ${head_link:0:9} moved backward/sideways (rollback, not a forward advance)"
        fail=1; ok=0
      fi
    else
      echo "warn  $name: base gitlink ${base_link:0:9} unresolvable — rollback check skipped"
    fi
  fi
  [ "$ok" -eq 1 ] && echo "ok    $name ($branch): ${head_link:0:9}"
done <<< "$names"

echo ""
if [ "$fail" -ne 0 ]; then
  echo "❌ Submodule branch-strategy gate FAILED — see FAIL lines above."
  echo "   Every changed gitlink must be ON its .gitmodules tracked branch and a forward advance."
  echo "   Fix: in the submodule, check out a commit on origin/<tracked-branch>"
  echo "        (sync the fork, or 'git submodule update --remote <path>'), then re-commit the gitlink."
  exit 1
fi
echo "✅ Submodule branch-strategy gate PASSED."
