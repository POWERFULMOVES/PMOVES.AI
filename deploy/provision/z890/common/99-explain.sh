#!/usr/bin/env bash
# Z890 Playlist Explain — Phase 1 STUB
#
# Phase 1 (current): Prints a pointer to the manual reference list in
# distro-manifest.yaml. No Hi-RAG dependency — works offline during reimaging.
#
# Phase 2 (after 5090-claude's YT-pipeline fix PR merges):
#   Replace this stub with a live Hi-RAG v2 query:
#     curl -X POST http://localhost:8086/hirag/query \
#       -d '{"query":"z890 step <N> <topic>","top_k":3,"rerank":true}' |
#     jq -r '.results[] | "\(.source_url) @ \(.timestamp): \(.excerpt)"'
#
#   Playlist to ingest first:
#     https://www.youtube.com/playlist?list=PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8
#   via:
#     /yt:add-playlist <url>
#
# Usage:
#   99-explain.sh --step 3 --topic "nvidia driver"
#   99-explain.sh --step partition-layout

set -euo pipefail

STEP=""
TOPIC=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --step)   STEP="$2"; shift 2 ;;
    --topic)  TOPIC="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown: $1" >&2; exit 2 ;;
  esac
done

PROVISION_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="${PROVISION_ROOT}/pxe/distro-manifest.yaml"

cat <<EOF
─────────────────────────────────────────────────────────
  PMOVES Z890 Bootstrap — Playlist Explain (Phase 1 stub)
─────────────────────────────────────────────────────────
  Step:  ${STEP:-<unspecified>}
  Topic: ${TOPIC:-<unspecified>}

  Hi-RAG playlist ingestion is pending Phase 2 (depends on
  5090-claude's YT-pipeline fix PR merging).

  For manual references during Phase 1, see:
    ${MANIFEST}
  — which lists ISO sources, checksums, and kernel args.

  When Phase 2 lands, this command will query Hi-RAG v2
  (http://localhost:8086/hirag/query) and return specific
  video / timestamp citations for the step you asked about.

  To advance to Phase 2 once the YT PR merges:
    /yt:add-playlist https://www.youtube.com/playlist?list=PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8
    # wait for transcript ingestion to Hi-RAG, then this script
    # will be updated to query the index.
─────────────────────────────────────────────────────────
EOF
