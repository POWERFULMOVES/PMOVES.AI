#!/usr/bin/env bash
set -euo pipefail

# Usage: REGISTRY=docker.io/yourorg VERSION=v1.0.0 ./scripts/buildx-agent-zero.sh
# Pushes multi-arch images: ${REGISTRY}/agent-zero:${VERSION} and :latest

REGISTRY=${REGISTRY:-}
VERSION=${VERSION:-}
IMAGE=agent-zero
DOCKERFILE=services/agent-zero/Dockerfile.multiarch
CONTEXT=services/agent-zero

if [[ -z "$REGISTRY" ]]; then
  echo "Set REGISTRY (e.g., docker.io/yourorg or ghcr.io/yourorg)" >&2
  exit 2
fi
if [[ -z "$VERSION" ]]; then
  echo "Set VERSION (e.g., v1.0.0). Using latest only." >&2
fi

if ! docker buildx inspect pmoves-builder >/dev/null 2>&1; then
  docker buildx create --name pmoves-builder --use
fi

TAGS=(-t "$REGISTRY/$IMAGE:latest")
if [[ -n "$VERSION" ]]; then
  TAGS+=( -t "$REGISTRY/$IMAGE:$VERSION" )
fi

docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f "$DOCKERFILE" \
  "${TAGS[@]}" \
  --push \
  "$CONTEXT"

echo "Pushed: ${REGISTRY}/${IMAGE}:${VERSION:-latest} (multi-arch)"

