#!/usr/bin/env bash
#
# Pulls specified Docker images and saves them as .tar files.
#
# This script is useful for pre-loading container images for offline deployment
# on Jetson devices. The image names are sanitized to create valid filenames.
#
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
