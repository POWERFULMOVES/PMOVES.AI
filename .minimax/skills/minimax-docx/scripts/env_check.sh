#!/usr/bin/env bash
# minimax-docx strict environment check
# This script is authoritative for whether the skill may run.
# Supports --level read|render|full (default: full).
set -euo pipefail

# --- Parse --level argument ---
LEVEL="full"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --level)
      shift
      LEVEL="${1:-}"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

case "$LEVEL" in
  read|render|full) ;;
  *)
    echo "Invalid --level value: '$LEVEL'. Must be one of: read, render, full" >&2
    exit 2
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DOTNET_DIR="$SCRIPT_DIR/dotnet"
DOTNET_REQUIRED_MAJOR=9

export DOTNET_CLI_UI_LANGUAGE=en

resolve_soffice_path() {
  local candidates=(
    "$(command -v soffice 2>/dev/null || true)"
    "$HOME/.local/bin/soffice"
    "$HOME/Applications/LibreOffice.app/Contents/MacOS/soffice"
    "/Applications/LibreOffice.app/Contents/MacOS/soffice"
  )
  local p
  for p in "${candidates[@]}"; do
    [ -n "$p" ] || continue
    [ -x "$p" ] || continue
    printf '%s\n' "$p"
    return 0
  done
  return 1
}

OS="unknown"
case "$(uname -s)" in
  Darwin) OS="macos" ;;
  Linux) OS="linux"; grep -qi microsoft /proc/version 2>/dev/null && OS="wsl" ;;
  MINGW*|MSYS*|CYGWIN*) OS="windows-shell" ;;
esac

echo "=== minimax-docx Environment Check (level: $LEVEL) ==="
echo ""

STATUS="READY"

check_ok() {
  printf "[OK]      %-14s %s\n" "$1" "$2"
}

check_fail() {
  printf "[FAIL]    %-14s %s\n" "$1" "$2"
  STATUS="NOT READY"
}

# --- read-level checks (always run) ---

if ! command -v python3 >/dev/null 2>&1; then
  check_fail "python3" "not found"
else
  check_ok "python3" "$(python3 --version 2>/dev/null | awk '{print $2}')"
fi

if ! command -v unzip >/dev/null 2>&1; then
  check_fail "unzip" "not found"
else
  check_ok "unzip" "available"
fi

# Locale check: macOS non-interactive shells often have empty LANG but default to UTF-8.
# Fall back to `locale charmap` when LANG is empty or does not contain utf-8.
current_lang="${LANG:-}"
if [ -n "$current_lang" ] && echo "$current_lang" | grep -qi 'utf-8\|utf8'; then
  check_ok "locale" "$current_lang"
else
  charmap="$(locale charmap 2>/dev/null || echo "unknown")"
  if echo "$charmap" | grep -qi 'utf-8\|utf8'; then
    check_ok "locale" "charmap=$charmap (LANG empty/non-UTF-8, but system charmap is UTF-8)"
  else
    check_fail "locale" "LANG='$current_lang', charmap='$charmap' — neither is UTF-8"
  fi
fi

perm_issues=0
for s in "$SCRIPT_DIR"/*.sh; do
  if [ -f "$s" ] && [ ! -x "$s" ]; then
    perm_issues=$((perm_issues + 1))
  fi
done
if [ "$perm_issues" -eq 0 ]; then
  check_ok "permissions" "all scripts executable"
else
  check_fail "permissions" "$perm_issues script(s) not executable"
fi

# --- render-level checks (render + full) ---

if [[ "$LEVEL" == "render" || "$LEVEL" == "full" ]]; then
  SOFFICE_PATH="$(resolve_soffice_path 2>/dev/null || true)"
  if [ -z "$SOFFICE_PATH" ]; then
    check_fail "soffice" "not found"
  else
    check_ok "soffice" "$SOFFICE_PATH"
  fi

  if ! command -v pdftoppm >/dev/null 2>&1; then
    check_fail "pdftoppm" "not found"
  else
    check_ok "pdftoppm" "available"
  fi
fi

# --- full-level checks (full only) ---

if [[ "$LEVEL" == "full" ]]; then
  if ! command -v dotnet >/dev/null 2>&1; then
    check_fail "dotnet" "not found"
  else
    ver="$(dotnet --version 2>/dev/null || echo 0.0.0)"
    major="${ver%%.*}"
    if [ "$major" -ge "$DOTNET_REQUIRED_MAJOR" ] 2>/dev/null; then
      check_ok "dotnet" "$ver (>= $DOTNET_REQUIRED_MAJOR.0)"
    else
      check_fail "dotnet" "$ver (requires >= $DOTNET_REQUIRED_MAJOR.0)"
    fi
  fi

  if ! command -v pandoc >/dev/null 2>&1; then
    check_fail "pandoc" "not found"
  else
    check_ok "pandoc" "$(pandoc --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' || echo '?')"
  fi

  if ! command -v zip >/dev/null 2>&1; then
    check_fail "zip" "not found"
  else
    check_ok "zip" "available"
  fi

  if [ ! -d "$DOTNET_DIR" ]; then
    check_fail "project" "directory not found: $DOTNET_DIR"
  else
    if [ -f "$DOTNET_DIR/MiniMaxAIDocx.Cli/bin/Debug/net10.0/MiniMaxAIDocx.Cli.dll" ] || \
       [ -f "$DOTNET_DIR/MiniMaxAIDocx.Cli/bin/Debug/net9.0/MiniMaxAIDocx.Cli.dll" ] || \
       [ -f "$DOTNET_DIR/MiniMaxAIDocx.Cli/bin/Debug/net8.0/MiniMaxAIDocx.Cli.dll" ]; then
      check_ok "project" "built"
    else
      if dotnet restore "$DOTNET_DIR" --verbosity quiet >/dev/null 2>&1 && \
         dotnet build "$DOTNET_DIR" --verbosity quiet --no-restore >/dev/null 2>&1; then
        check_ok "project" "restore+build succeeded"
      else
        check_fail "project" "restore/build failed"
      fi
    fi
  fi
fi

echo ""
if [ "$STATUS" = "READY" ]; then
  echo "Status: READY"
else
  echo "Status: NOT READY"
  echo ""
  if [ "$OS" = "macos" ]; then
    if [[ "$LEVEL" == "read" ]]; then
      echo "The read-level gate requires: python3, unzip, UTF-8 locale, executable scripts."
      echo "Install the missing items above, then re-run:"
      echo "  bash $0 --level read"
    elif [[ "$LEVEL" == "render" ]]; then
      echo "The render-level gate requires all read-level items plus: soffice, pdftoppm."
      echo "Run: bash scripts/setup.sh"
    else
      echo "Run: bash scripts/setup.sh"
      echo "This script must succeed before any minimax-docx skill run on macOS."
    fi
  fi
  exit 1
fi
