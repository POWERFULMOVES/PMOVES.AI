#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/build_integration_image.sh --integration <name> [options]

Required:
  --integration NAME   Integration identifier (see list below)

Options:
  --ref BRANCH_OR_TAG  Git ref to build (default: main)
  --registry REGISTRY  Registry hostname (default: ghcr.io)
  --namespace NS       Registry namespace/owner (default: powerfulmoves)
  --tag TAG            Image tag to apply (default: pmoves-local)
  --push               Push the image after build (requires auth)
  --context PATH       Override Docker build context (rare)
  --dockerfile PATH    Override Dockerfile path (rare)
  --help               Show this help message

Available integrations:
  agent-zero, archon, archon-ui, open-notebook, wger, firefly-iii,
  jellyfin, pmoves-yt, deepresearch, supaserch
EOF
}

if [ "$#" -eq 0 ]; then
  usage
  exit 1
fi

INTEGRATION=""
REF="main"
REGISTRY="ghcr.io"
NAMESPACE="powerfulmoves"
TAG="pmoves-local"
PUSH="false"
CUSTOM_CONTEXT=""
CUSTOM_DOCKERFILE=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --integration)
      INTEGRATION="$2"
      shift 2
      ;;
    --ref)
      REF="$2"
      shift 2
      ;;
    --registry)
      REGISTRY="$2"
      shift 2
      ;;
    --namespace)
      NAMESPACE="$2"
      shift 2
      ;;
    --tag)
      TAG="$2"
      shift 2
      ;;
    --push)
      PUSH="true"
      shift 1
      ;;
    --context)
      CUSTOM_CONTEXT="$2"
      shift 2
      ;;
    --dockerfile)
      CUSTOM_DOCKERFILE="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [ -z "$INTEGRATION" ]; then
  echo "Missing required --integration option" >&2
  usage
  exit 1
fi

case "$INTEGRATION" in
  agent-zero)
    GIT_URL="https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git"
    CONTEXT="."
    DOCKERFILE="Dockerfile"
    IMAGE_NAME="pmoves-agent-zero"
    ;;
  archon)
    GIT_URL="https://github.com/POWERFULMOVES/PMOVES.AI.git"
    CONTEXT="pmoves"
    DOCKERFILE="pmoves/services/archon/Dockerfile"
    IMAGE_NAME="pmoves-archon"
    ;;
  archon-ui)
    GIT_URL="https://github.com/POWERFULMOVES/PMOVES-Archon.git"
    CONTEXT="archon-ui-main"
    DOCKERFILE="Dockerfile"
    IMAGE_NAME="pmoves-archon-ui"
    ;;
  open-notebook)
    GIT_URL="https://github.com/lfnovo/open-notebook.git"
    CONTEXT="."
    DOCKERFILE="Dockerfile"
    IMAGE_NAME="pmoves-open-notebook"
    ;;
  wger)
    GIT_URL="https://github.com/hunnibear/pmoves-health-wger.git"
    CONTEXT="."
    DOCKERFILE="Dockerfile"
    IMAGE_NAME="pmoves-health-wger"
    ;;
  firefly-iii)
    GIT_URL="https://github.com/cataclysm-studios-inc/pmoves-firefly-iii.git"
    CONTEXT="."
    DOCKERFILE="Dockerfile"
    IMAGE_NAME="pmoves-firefly-iii"
    ;;
  jellyfin)
    GIT_URL="https://github.com/cataclysm-studios-inc/pmoves-jellyfin.git"
    CONTEXT="."
    DOCKERFILE="Dockerfile"
    IMAGE_NAME="pmoves-jellyfin"
    ;;
  pmoves-yt)
    GIT_URL="https://github.com/POWERFULMOVES/PMOVES.YT.git"
    CONTEXT="."
    DOCKERFILE="Dockerfile"
    IMAGE_NAME="pmoves-yt"
    ;;
  deepresearch)
    GIT_URL="https://github.com/POWERFULMOVES/PMOVES.AI.git"
    CONTEXT="pmoves"
    DOCKERFILE="pmoves/services/deepresearch/Dockerfile"
    IMAGE_NAME="pmoves-deepresearch"
    ;;
  supaserch)
    GIT_URL="https://github.com/POWERFULMOVES/PMOVES.AI.git"
    CONTEXT="pmoves"
    DOCKERFILE="pmoves/services/supaserch/Dockerfile"
    IMAGE_NAME="pmoves-supaserch"
    ;;
  *)
    echo "Unsupported integration: $INTEGRATION" >&2
    usage
    exit 1
    ;;
 esac

if [ -n "$CUSTOM_CONTEXT" ]; then
  CONTEXT="$CUSTOM_CONTEXT"
fi

if [ -n "$CUSTOM_DOCKERFILE" ]; then
  DOCKERFILE="$CUSTOM_DOCKERFILE"
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "Cloning $GIT_URL@$REF"
git clone --depth=1 --branch "$REF" "$GIT_URL" "$WORKDIR/src" >/dev/null 2>&1

BUILD_CONTEXT="$WORKDIR/src/$CONTEXT"
BUILD_FILE="$WORKDIR/src/$DOCKERFILE"
if [ ! -d "$BUILD_CONTEXT" ]; then
  echo "Resolved context $BUILD_CONTEXT does not exist" >&2
  exit 1
fi
if [ ! -f "$BUILD_FILE" ]; then
  echo "Resolved Dockerfile $BUILD_FILE does not exist" >&2
  exit 1
fi

FULL_IMAGE="$REGISTRY/$NAMESPACE/$IMAGE_NAME:$TAG"

echo "Building $FULL_IMAGE"
docker build -t "$FULL_IMAGE" -f "$BUILD_FILE" "$BUILD_CONTEXT"

echo "Image built locally: $FULL_IMAGE"

if [ "$PUSH" = "true" ]; then
  echo "Pushing $FULL_IMAGE"
  docker push "$FULL_IMAGE"
  echo "Push complete"
fi
