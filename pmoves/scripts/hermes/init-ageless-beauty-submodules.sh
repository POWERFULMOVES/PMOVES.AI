#!/usr/bin/env bash
# ============================================================
# PMOVES.AI Submodule Initialization Script
# Ageless Beauty Practice Workstation (Elder-Melchor)
# ============================================================
# Usage: ./init-ageless-beauty-submodules.sh
# 
# This script initializes ONLY the submodules needed for the
# Ageless Beauty nurse practitioner practice.
# 
# Full fleet: 50+ submodules (see .gitmodules)
# Practice subset: 10 priority submodules
# ============================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../.."
cd "$REPO_ROOT"

echo "========================================"
echo "Ageless Beauty Submodule Initialization" 
echo "========================================"
echo "" 

# Priority 1: Health + Wealth (core practice)
echo "[1/4] Initializing Health + Wealth submodules..."
git submodule update --init Pmoves-Health-wger
git submodule update --init PMOVES-Wealth
echo "✓ Health + Wealth initialized" 
echo "" 

# Priority 2: Workflow + UI + Data
echo "[2/4] Initializing Workflow + UI + Data submodules..."
git submodule update --init PMOVES-n8n
git submodule update --init PMOVES-MAI-UI
git submodule update --init PMOVES-supabase
echo "✓ Workflow + UI + Data initialized" 
echo "" 

# Priority 3: Media + Voice + Geometry
echo "[3/4] Initializing Media + Voice + Geometry submodules..."
git submodule update --init Pmoves-Jellyfin-AI-Media-Stack
git submodule update --init PMOVES-Pinokio-Ultimate-TTS-Studio
git submodule update --init Pmoves-hyperdimensions
git submodule update --init PMOVES-ToKenism-Multi
echo "✓ Media + Voice + Geometry initialized" 
echo "" 

# Priority 4: Security
echo "[4/4] Initializing Security submodules..."
git submodule update --init Pmoves-cipher
git submodule update --init pmoves-cipher-mcp
echo "✓ Security initialized" 
echo "" 

echo "========================================" 
echo "Ageless Beauty submodules ready!" 
echo "========================================" 
echo "" 
echo "Next steps:" 
echo "  1. Configure Pmoves-Health-wger for HIPAA mode" 
echo "  2. Set up PMOVES-Wealth for medical billing (CPT codes)" 
echo "  3. Import PMOVES-n8n workflows for practice BPM³" 
echo "  4. Deploy PMOVES-MAI-UI to Hostinger VPS" 
echo "  5. Configure PMOVES-supabase for patient data" 
echo "" 
echo "To initialize ALL 50+ submodules:" 
echo "  git submodule update --init --recursive" 
