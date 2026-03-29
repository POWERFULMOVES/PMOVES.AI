#!/usr/bin/env bash
# PMOVES Knowledge Ingestion — Push pmoves/knowledge/ into Agent Zero
#
# Usage:
#   bash pmoves/tools/knowledge_ingest.sh [--dry-run]
#
# Sources:
#   pmoves/knowledge/zai-glm-coding-plan.md
#   pmoves/knowledge/claw-taxonomy-reference.md
#   pmoves/docs/CLAW_TAXONOMY.md
#   pmoves/docs/MODEL_FABRIC_CONTRACT.md
#
# Target:
#   Agent Zero knowledge/ directory (via filesystem copy)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
KNOWLEDGE_DIR="$ROOT_DIR/pmoves/knowledge"
A0_KNOWLEDGE_DIR="$ROOT_DIR/PMOVES-Agent-Zero/knowledge/main/pmoves"

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
  echo "=== DRY RUN — no files will be copied ==="
fi

REFERENCE_DOCS=(
  "$ROOT_DIR/pmoves/docs/CLAW_TAXONOMY.md"
  "$ROOT_DIR/pmoves/docs/MODEL_FABRIC_CONTRACT.md"
)

KNOWLEDGE_FILES=(
  "$KNOWLEDGE_DIR/zai-glm-coding-plan.md"
  "$KNOWLEDGE_DIR/claw-taxonomy-reference.md"
)

echo "PMOVES Knowledge Ingestion"
echo "==========================="
echo "Source: $KNOWLEDGE_DIR"
echo "Target: $A0_KNOWLEDGE_DIR"
echo ""

if [[ "$DRY_RUN" == "false" ]]; then
  mkdir -p "$A0_KNOWLEDGE_DIR"
fi

COPIED=0

for src in "${KNOWLEDGE_FILES[@]}"; do
  if [[ -f "$src" ]]; then
    dest="$A0_KNOWLEDGE_DIR/$(basename "$src")"
    echo "  COPY $(basename "$src")"
    if [[ "$DRY_RUN" == "false" ]]; then
      cp "$src" "$dest"
    fi
    ((COPIED++))
  else
    echo "  SKIP $(basename "$src") — not found"
  fi
done

for src in "${REFERENCE_DOCS[@]}"; do
  if [[ -f "$src" ]]; then
    dest="$A0_KNOWLEDGE_DIR/$(basename "$src")"
    echo "  COPY $(basename "$src") (reference)"
    if [[ "$DRY_RUN" == "false" ]]; then
      cp "$src" "$dest"
    fi
    ((COPIED++))
  else
    echo "  SKIP $(basename "$src") — not found"
  fi
done

echo ""
echo "Ingested: $COPIED files"

if [[ "$DRY_RUN" == "false" ]]; then
  echo ""
  echo "To reindex Agent Zero knowledge (requires A0 running):"
  echo "  curl -s -X POST http://localhost:8080/api/knowledge/reindex"
  echo ""
  echo "To verify via Agent Zero API (requires A0 running):"
  echo "  curl -s http://localhost:8080/api/knowledge | python3 -m json.tool"
fi
