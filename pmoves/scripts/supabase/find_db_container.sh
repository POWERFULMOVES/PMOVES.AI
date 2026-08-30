#!/usr/bin/env bash
set -euo pipefail

mode="${1:-running}"

if [[ "$mode" == "running" ]]; then
  list_cmd=(docker ps --format '{{.Names}}')
else
  list_cmd=(docker ps -a --format '{{.Names}}')
fi

names="$("${list_cmd[@]}" 2>/dev/null || true)"

# Prefer the compose-managed PMOVES container over any legacy/sibling project container
result=$(printf '%s\n' "$names" | grep -E -m1 '^pmoves-supabase-db-1$' || true)
if [ -z "$result" ]; then
  result=$(printf '%s\n' "$names" | grep -E -m1 '^supabase_db(_.*)?$|^supabase-db$' || true)
fi
printf '%s\n' "$result"
