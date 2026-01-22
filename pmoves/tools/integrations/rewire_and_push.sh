#!/usr/bin/env bash
set -euo pipefail

FORK_OWNER=${FORK_OWNER:-}
BASE_DIR=${1:-integrations-workspace}
BRANCH=${2:-chore/pmoves-net+ghcr}

if [[ -z "$FORK_OWNER" ]]; then
  echo "Set FORK_OWNER to your GitHub username (e.g., export FORK_OWNER=hunnibear)" >&2
  exit 1
fi

declare -a REPOS=(
  "Pmoves-Health-wger|POWERFULMOVES|Pmoves-Health-wger"
  "PMOVES-Firefly-iii|POWERFULMOVES|pmoves-firefly-iii"
  "Pmoves-open-notebook|POWERFULMOVES|Pmoves-open-notebook"
  "PMOVES-jellyfin|POWERFULMOVES|PMOVES-jellyfin"
)

for entry in "${REPOS[@]}"; do
  dir=${entry%%|*}; rest=${entry#*|}; parent_owner=${rest%%|*}; repo_name=${rest##*|}
  repo_path="$BASE_DIR/$dir"
  if [[ ! -d "$repo_path/.git" ]]; then
    echo "[WARN] Missing repo: $repo_path" >&2; continue
  fi
  echo "→ Rewiring remotes for $repo_path"
  (cd "$repo_path" && {
    # Rename current origin → upstream (parent), set origin to fork
    if git remote get-url origin >/dev/null 2>&1; then
      cur=$(git remote get-url origin)
      if [[ "$cur" == *"$parent_owner/$repo_name"* ]]; then
        git remote rename origin upstream || true
        git remote add origin "https://github.com/$FORK_OWNER/$repo_name.git" || true
      fi
    fi
    # Ensure upstream remote is parent
    if ! git remote get-url upstream >/dev/null 2>&1; then
      git remote add upstream "https://github.com/$parent_owner/$repo_name.git"
    fi
    echo "   origin:   $(git remote get-url origin)"
    echo "   upstream: $(git remote get-url upstream)"
    echo "→ Pushing $BRANCH to fork origin"
    git push -u origin "$BRANCH"
    echo "→ Open PR: https://github.com/$parent_owner/$repo_name/compare/$BRANCH...$FORK_OWNER:$BRANCH?expand=1"
  })
done

echo "✔ Done. Open the printed compare URLs to submit the PRs."

