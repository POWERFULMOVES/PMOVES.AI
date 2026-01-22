#!/usr/bin/env bash
set -euo pipefail

# Create an evidence path stamped with UTC time and a label.
# Usage:
#   ./pmoves/tools/evidence_stamp.sh [label] [ext]
# Prints the full suggested path, e.g., pmoves/docs/evidence/20250930_142233_discord-ping.png

LABEL=${1:-evidence}
EXT=${2:-png}

# slugify label (lowercase, replace non-alnum with dash)
SLUG=$(echo "$LABEL" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g')
STAMP=$(date -u +%Y%m%d_%H%M%S)
DIR="pmoves/docs/evidence"
mkdir -p "$DIR"
PATH_OUT="$DIR/${STAMP}_${SLUG}.${EXT}"
echo "$PATH_OUT"

