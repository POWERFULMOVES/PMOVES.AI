#!/usr/bin/env bash
# Example: pre-pull key containers and save tarballs to this USB for offline loads
set -euo pipefail
IMAGES=(
  "nvcr.io/nvidia/l4t-ml:r36.3.0-py3"
)
mkdir -p ./images
for img in "${IMAGES[@]}"; do
  docker pull "$img"
  safe=$(echo "$img" | tr '/:' '__')
  docker save "$img" -o "./images/${safe}.tar"
done
echo "Saved images under ./images/"
