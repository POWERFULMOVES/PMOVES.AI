#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PATCH_FILE="${SCRIPT_DIR}/patches/glancer.diff"
PMOVES_DIR="${REPO_ROOT}/pmoves"
GLANCER_DIR="${PMOVES_DIR}/services/glancer"
GLANCER_IMAGE="${GLANCER_IMAGE:-pmoves-glancer:local}"
GLANCER_REPO_URL="${GLANCER_REPO_URL:-https://github.com/POWERFULMOVES/Glancer.git}"
GLANCER_REF="${GLANCER_REF:-main}"

if [ ! -d "$PMOVES_DIR" ]; then
  echo "pmoves directory not found at $PMOVES_DIR" >&2
  exit 1
fi

if [ -f "$PATCH_FILE" ]; then
  if git -C "$REPO_ROOT" apply --check "$PATCH_FILE" >/dev/null 2>&1; then
    git -C "$REPO_ROOT" apply "$PATCH_FILE"
    echo "Applied Glancer compose/env patch."
  else
    echo "Glancer patch already applied or conflicts detected; skipping git apply." >&2
  fi
else
  echo "Missing patch file at $PATCH_FILE" >&2
  exit 1
fi

if [ ! -d "$GLANCER_DIR" ]; then
  echo "Cloning Glancer into $GLANCER_DIR (ref: $GLANCER_REF)…"
  git clone --depth 1 --branch "$GLANCER_REF" "$GLANCER_REPO_URL" "$GLANCER_DIR"
else
  echo "Refreshing existing Glancer checkout at $GLANCER_DIR…"
  (cd "$GLANCER_DIR" && git fetch --depth 1 origin "$GLANCER_REF" && git checkout "$GLANCER_REF" && git pull --ff-only || true)
fi

if command -v docker >/dev/null 2>&1; then
  echo "Building Glancer image: $GLANCER_IMAGE"
  if docker build -t "$GLANCER_IMAGE" "$GLANCER_DIR"; then
    echo "Glancer image built as $GLANCER_IMAGE"
  else
    echo "Docker build failed. Check that $GLANCER_DIR contains a valid Dockerfile." >&2
  fi
else
  echo "Docker not available; skipping Glancer build." >&2
fi
