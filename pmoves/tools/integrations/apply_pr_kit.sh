#!/usr/bin/env bash
set -euo pipefail

KIT=""
REPO=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --kit) KIT="$2"; shift 2;;
    --repo) REPO="$2"; shift 2;;
    -h|--help)
      echo "Usage: $0 --kit {wger|firefly|open-notebook|jellyfin} --repo /path/to/repo"; exit 0;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

if [[ -z "$KIT" || -z "$REPO" ]]; then
  echo "Usage: $0 --kit {wger|firefly|open-notebook|jellyfin} --repo /path/to/repo"; exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
# Kits live under pmoves/integrations/pr-kits
KIT_DIR="$ROOT_DIR/pmoves/integrations/pr-kits/$KIT"

if [[ ! -d "$KIT_DIR" ]]; then
  echo "Kit not found: $KIT_DIR"; exit 1
fi
if [[ ! -d "$REPO" ]]; then
  echo "Repo path not found: $REPO"; exit 1
fi

echo "→ Applying PR kit '$KIT' to repo: $REPO"

# Copy files
shopt -s dotglob
cp -R "$KIT_DIR"/. "$REPO"/

# Ensure git repo
if ! git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repo: $REPO"; exit 1
fi

BRANCH="chore/pmoves-net+ghcr"
echo "→ Creating branch $BRANCH"
git -C "$REPO" checkout -B "$BRANCH"

echo "→ Staging files"
git -C "$REPO" add .github docker-compose.pmoves-net.yml README_PRSUMMARY.md 2>/dev/null || true

echo "→ Committing"
# Ensure author for local repo
git -C "$REPO" config user.email "ops@pmoves.ai"
git -C "$REPO" config user.name "PMOVES Bot"
git -C "$REPO" commit -m "chore: add pmoves-net compose and GHCR publish workflow"

echo "✔ PR kit applied. Next: push and open a PR"
echo "   cd \"$REPO\" && git push -u origin $BRANCH"
