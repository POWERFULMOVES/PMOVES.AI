#!/usr/bin/env bash
set -euo pipefail

# Basic environment sanity helper for PMOVES.
# - Verifies pmoves/env.shared exists
# - Uses the onboarding_helper to report CHIT/manifest coverage
# - Highlights keys present in env.shared.example but unset/empty in env.shared

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXAMPLE="$ROOT/pmoves/env.shared.example"
ENV_SHARED="$ROOT/pmoves/env.shared"

echo "→ Checking pmoves/env.shared"
if [[ ! -f "$ENV_SHARED" ]]; then
  echo "✖ pmoves/env.shared is missing. Copy pmoves/env.shared.example and populate secrets."
  exit 1
fi

if [[ ! -f "$EXAMPLE" ]]; then
  echo "↷ pmoves/env.shared.example not found; skipping example comparison."
else
  echo "→ Running onboarding_helper status (CHIT manifest coverage)"
  python3 -m pmoves.tools.onboarding_helper status || true

  echo
  echo "→ Scanning for unset keys in pmoves/env.shared (based on env.shared.example)"
  mapfile -t VARS < <(grep -E '^[A-Z0-9_]+=' "$EXAMPLE" | cut -d= -f1 | sort -u)
  MISSING=()
  for v in "${VARS[@]}"; do
    line="$(grep -E "^${v}=" "$ENV_SHARED" | head -n1 || true)"
    val="${line#*=}"
    if [[ -z "$line" || -z "$val" ]]; then
      MISSING+=("$v")
    fi
  done
  if [[ ${#MISSING[@]} -eq 0 ]]; then
    echo "  All keys from env.shared.example are present and non-empty in pmoves/env.shared."
  else
    echo "  Keys present in env.shared.example but unset/empty in pmoves/env.shared:"
    for v in "${MISSING[@]}"; do
      echo "    - $v"
    done
    echo "  Edit pmoves/env.shared and populate the missing values. Use docs/SECRETS.md and"
    echo "  pmoves/env.shared.example comments for provider rotation and dashboard links."
  fi
fi

echo
echo "✔ env-check completed"

