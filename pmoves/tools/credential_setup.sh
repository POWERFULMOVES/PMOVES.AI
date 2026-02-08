#!/usr/bin/env bash
# =============================================================================
# PMOVES.AI Credential Setup Wrapper
# =============================================================================
# Convenience wrapper for the Python credential setup wizard.
#
# Usage:
#   ./pmoves/tools/credential_setup.sh
#   ./pmoves/tools/credential_setup.sh --tier llm
#   ./pmoves/tools/credential_setup.sh --all-tiers
# =============================================================================

set -euo pipefail

# Get to the repo root
SCRIPT_FILE="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_FILE")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    echo "Please install Python 3 and try again."
    exit 1
fi

# Run the Python module
cd "$REPO_ROOT"
python3 -m pmoves.tools.credential_setup "$@"
