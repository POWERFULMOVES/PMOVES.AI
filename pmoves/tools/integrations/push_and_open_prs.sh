#!/usr/bin/env bash
set -euo pipefail

BASE_DIR=${1:-integrations-workspace}
BRANCH=${2:-chore/pmoves-net+ghcr}
FORK_OWNER=${FORK_OWNER:-}

declare -a REPOS=(
  "Pmoves-Health-wger|https://github.com/POWERFULMOVES/Pmoves-Health-wger"
  "PMOVES-Firefly-iii|https://github.com/POWERFULMOVES/pmoves-firefly-iii"
  "Pmoves-open-notebook|https://github.com/POWERFULMOVES/Pmoves-open-notebook"
  "PMOVES-jellyfin|https://github.com/POWERFULMOVES/PMOVES-jellyfin"
)

has_gh() { command -v gh >/dev/null 2>&1; }

for entry in "${REPOS[@]}"; do
  dir="${entry%%|*}"; url="${entry##*|}"
  repo_path="$BASE_DIR/$dir"
  if [[ ! -d "$repo_path/.git" ]]; then
    echo "[WARN] Skipping missing repo: $repo_path" >&2
    continue
  fi
  echo "→ Pushing $BRANCH in $repo_path"
  (cd "$repo_path" && git push -u origin "$BRANCH") || {
    echo "[WARN] Push failed for $repo_path; check credentials or remote config" >&2
    continue
  }
  if has_gh; then
    echo "→ Opening PR via gh for $dir"
    if [[ -n "$FORK_OWNER" ]]; then
      # Open PR against parent repo explicitly, using fork_owner:branch as head
      parent_repo=$(basename "$url")
      parent_owner=$(basename $(dirname "$url"))
      (cd "$repo_path" && gh pr create \
        --repo "$parent_owner/$parent_repo" \
        --title "chore: PMOVES integration — pmoves-net compose + GHCR publish" \
        --body-file README_PRSUMMARY.md \
        --base main \
        --head "$FORK_OWNER:$BRANCH") || {
          echo "[WARN] gh pr create failed for $repo_path" >&2
          echo "Open manually: $url/compare/$BRANCH?expand=1"
        }
    else
      (cd "$repo_path" && gh pr create --title "chore: PMOVES integration — pmoves-net compose + GHCR publish" --body-file README_PRSUMMARY.md --base main --head "$BRANCH") || {
        echo "[WARN] gh pr create failed for $repo_path" >&2
        echo "Open manually: $url/compare/$BRANCH?expand=1"
      }
    fi
  else
    echo "Open PR manually: $url/compare/$BRANCH?expand=1"
  fi
done

echo "✔ Done. Review PRs in the browser and merge when ready."
