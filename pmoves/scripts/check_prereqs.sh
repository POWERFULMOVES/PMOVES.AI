#!/usr/bin/env bash
# check_prereqs.sh — verify system binaries required for PMOVES bringup.
#
# Python deps land in pmoves/.venv-pmoves/ via create_venv.sh. This script
# checks the NON-Python prerequisites that can't be pip-installed: jq, make,
# curl, git, python3. Reports per-binary status and prints install hints for
# any missing entries.
#
# Exit codes:
#   0  all prereqs present
#   1  one or more missing (CI gate / Make target failure)
#
# Usage:
#   bash pmoves/scripts/check_prereqs.sh         # human-readable report
#   bash pmoves/scripts/check_prereqs.sh --quiet # suppress per-binary OK lines, only show fails

set -uo pipefail

QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

# Binary name → one-line install hint per platform (apt | brew | pacman | choco).
declare -A HINTS=(
  [jq]="apt: sudo apt install jq | brew: brew install jq | pacman: sudo pacman -S jq | choco: choco install jq"
  [make]="apt: sudo apt install build-essential | brew: xcode-select --install | pacman: sudo pacman -S base-devel | choco: choco install make"
  [curl]="apt: sudo apt install curl | brew: brew install curl | pacman: sudo pacman -S curl | choco: choco install curl"
  [git]="apt: sudo apt install git | brew: brew install git | pacman: sudo pacman -S git | choco: choco install git"
  [python3]="apt: sudo apt install python3 python3-venv | brew: brew install python | pacman: sudo pacman -S python | choco: choco install python"
)

REQUIRED=(jq make curl git python3)

missing=0
report=""
for bin in "${REQUIRED[@]}"; do
  if command -v "$bin" >/dev/null 2>&1; then
    if [[ "$QUIET" -eq 0 ]]; then
      version=$("$bin" --version 2>&1 | head -1 || echo "<version-unknown>")
      printf "  ✅ %-10s %s\n" "$bin" "$version"
    fi
  else
    missing=$((missing+1))
    printf "  ❌ %-10s MISSING — %s\n" "$bin" "${HINTS[$bin]}"
  fi
done

echo
if [[ "$missing" -eq 0 ]]; then
  echo "✅ All ${#REQUIRED[@]} prereqs present."
  exit 0
else
  echo "❌ $missing prereq(s) missing. Install with the per-platform hint above and re-run."
  echo "   Then: make -C pmoves venv-bringup"
  exit 1
fi
