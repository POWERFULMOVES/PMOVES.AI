#!/usr/bin/env bash
set -euo pipefail
REPO_DIR=${1:-.}
cd "$REPO_DIR"

PATCH="/mnt/data/pmoves_hirag_reranker_upgrade.patch"
BRANCH="feat/hirag-reranker-v2"
TITLE="feat(hirag): v2 gateway with optional reranker + eval sweeps"
BODY="/mnt/data/pmoves-hirag-rerank-pr/PR_BODY_HIRAG_RERANK_V2.md"

git checkout -b "$BRANCH" || git checkout "$BRANCH"
git apply "$PATCH"
git add .
git commit -m "$TITLE"
git push -u origin "$BRANCH"

if command -v gh >/dev/null 2>&1; then
  gh pr create --title "$TITLE" --body-file "$BODY" --base main --head "$BRANCH" || true
else
  echo "gh CLI not installed; PR not auto-opened."
fi
