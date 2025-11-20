#!/usr/bin/env bash
set -euo pipefail

# Extract a path from this monorepo into a standalone repository and re-add as a submodule.
# Usage:
#   ./pmoves/tools/submodules/extract_to_submodule.sh services/pmoves-yt POWERFULMOVES/PMOVES.YT pmoves/integrations/pmoves-yt

if [ $# -lt 3 ]; then
  echo "Usage: $0 <monorepo-path> <github-org/repo> <submodule-path> [branch-name]" >&2
  exit 2
fi

SRC_PATH="$1"         # e.g., services/pmoves-yt
REMOTE_REPO="$2"      # e.g., POWERFULMOVES/PMOVES.YT
SUBMODULE_PATH="$3"   # e.g., pmoves/integrations/pmoves-yt
BRANCH_NAME="${4:-pmoves/edition}"  # default branch for our overlays

if [ ! -d "$SRC_PATH" ]; then
  echo "Path not found: $SRC_PATH" >&2
  exit 1
fi

echo "→ Creating subtree split for $SRC_PATH …"
SHA=$(git subtree split --prefix "$SRC_PATH" HEAD)
echo "Subtree SHA: $SHA"

echo "→ Creating remote (if not present): git@github.com:$REMOTE_REPO.git"
git ls-remote --exit-code "git@github.com:$REMOTE_REPO.git" >/dev/null 2>&1 || {
  echo "Remote repo must exist beforehand: https://github.com/$REMOTE_REPO" >&2
  exit 1
}

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

echo "→ Initializing new repo in $TMP_DIR from subtree SHA"
git init "$TMP_DIR" >/dev/null
git -C "$TMP_DIR" pull "$(git rev-parse --show-toplevel)" "$SHA" --no-rebase
git -C "$TMP_DIR" branch -m "$BRANCH_NAME"
git -C "$TMP_DIR" remote add origin "git@github.com:$REMOTE_REPO.git"
git -C "$TMP_DIR" push -u origin "$BRANCH_NAME"

echo "→ Adding submodule at $SUBMODULE_PATH"
git submodule add "git@github.com:$REMOTE_REPO.git" "$SUBMODULE_PATH"
git submodule update --init --recursive "$SUBMODULE_PATH"

echo "✔ Submodule added. Next: update compose to use published image or dev-local build, and wire CI."

