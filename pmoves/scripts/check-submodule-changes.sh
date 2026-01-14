#!/bin/bash
# Check for uncommitted changes in all PMOVES submodules

REPO_ROOT="/home/pmoves/PMOVES.AI"
cd "$REPO_ROOT"

echo "=== Checking for uncommitted changes in submodules ==="

SUBMODULES=(
  PMOVES-Archon
  PMOVES-Creator
  PMOVES-Deep-Serch
  PMOVES-HiRAG
  PMOVES-DoX
  PMOVES-Jellyfin
  Pmoves-Jellyfin-AI-Media-Stack
  PMOVES-Open-Notebook
  Pmoves-Health-wger
  PMOVES-Wealth
  PMOVES-Remote-View
  PMOVES-Tailscale
  PMOVES-crush
  PMOVES-n8n
  PMOVES-Pipecat
  PMOVES-Ultimate-TTS-Studio
  PMOVES-Pinokio-Ultimate-TTS-Studio
  PMOVES-tensorzero
  PMOVES.YT
  Pmoves-hyperdimensions
)

HAS_CHANGES=false

for dir in "${SUBMODULES[@]}"; do
  if [ -d "$dir/.git" ]; then
    changes=$(git -C "$dir" status --short 2>/dev/null | wc -l)
    if [ "$changes" -gt 0 ]; then
      echo "🔴 $dir: $changes uncommitted changes"
      git -C "$dir" status --short
      echo ""
      HAS_CHANGES=true
    fi
  fi
done

if [ "$HAS_CHANGES" = false ]; then
  echo "✅ All submodules are clean"
else
  echo "⚠️  Some submodules have uncommitted changes"
fi
