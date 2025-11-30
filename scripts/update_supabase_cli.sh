#!/usr/bin/env bash
set -euo pipefail

if ! command -v supabase >/dev/null 2>&1; then
  echo "Supabase CLI not found in PATH." >&2
  exit 1
fi

echo "Stopping local Supabase stack (if running) ..."
supabase stop >/dev/null 2>&1 || true

run_cmd=""
if command -v scoop >/dev/null 2>&1; then
  run_cmd="scoop update supabase"
elif command -v winget >/dev/null 2>&1; then
  run_cmd="winget upgrade --id Supabase.Supabase --accept-source-agreements --accept-package-agreements"
elif command -v brew >/dev/null 2>&1; then
  run_cmd="brew update && brew upgrade supabase/tap/supabase"
elif command -v apt-get >/dev/null 2>&1 && dpkg -s supabase >/dev/null 2>&1; then
  run_cmd="sudo apt-get update && sudo apt-get install --only-upgrade supabase"
elif command -v dnf >/dev/null 2>&1 && rpm -q supabase >/dev/null 2>&1; then
  run_cmd="sudo dnf upgrade -y supabase"
elif command -v paru >/dev/null 2>&1; then
  run_cmd="paru -Syu --noconfirm supabase-cli"
elif command -v yay >/dev/null 2>&1; then
  run_cmd="yay -Syu --noconfirm supabase-cli"
elif command -v npm >/dev/null 2>&1; then
  run_cmd="npm install -g supabase"
fi

if [ -z "$run_cmd" ]; then
  echo "No supported package manager found. See docs/LOCAL_TOOLING_REFERENCE.md for manual update instructions." >&2
  exit 1
fi

echo "Executing: $run_cmd"
if ! bash -c "$run_cmd"; then
  echo "Supabase CLI update command failed." >&2
  exit 1
fi

supabase --version
