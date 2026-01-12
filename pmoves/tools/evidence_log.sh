#!/usr/bin/env bash
set -euo pipefail

# Append an evidence entry to a CSV log.
# Usage:
#   ./pmoves/tools/evidence_log.sh "Step label" "pmoves/docs/evidence/20250930_...png" "optional note"

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <label> <path> [note]" >&2
  exit 1
fi

LABEL="$1"
PATH_IN="$2"
NOTE="${3:-}"

DIR="pmoves/docs/evidence"
FILE="$DIR/log.csv"
mkdir -p "$DIR"

STAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

if [[ ! -f "$FILE" ]]; then
  echo "timestamp,label,path,note" > "$FILE"
fi

# CSV escape: replace quotes with doubled quotes, wrap fields in quotes
esc() { echo "$1" | sed 's/"/""/g'; }
printf '"%s","%s","%s","%s"\n' "$(esc "$STAMP")" "$(esc "$LABEL")" "$(esc "$PATH_IN")" "$(esc "$NOTE")" >> "$FILE"
echo "$FILE"

