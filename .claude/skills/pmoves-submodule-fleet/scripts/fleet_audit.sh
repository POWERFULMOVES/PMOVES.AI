#!/usr/bin/env bash
# pmoves-submodule-fleet — single-screen submodule audit.
# Always exits 0 (informational).
#
# Updated 2026-08-05: non-recursive, uses .gitmodules tracked branch,
# skips sync=false forks, NO per-submodule fetch (that hangs on nested
# repos with 60+ submodules). The fork-sync.yml workflow handles upstream
# drift; this script is a fast local gitlink-vs-tracked-branch comparison.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "${REPO_ROOT}" || exit 0

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "ERROR: not a git repo at ${REPO_ROOT}" >&2
  exit 0
fi

# Build the sync=false set from fork_registry.json (if Python available)
SYNC_FALSE=""
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  PY=""
fi

if [[ -n "$PY" && -f "${REPO_ROOT}/pmoves/config/fork_registry.json" ]]; then
  SYNC_FALSE="$($PY -c "
import json
try:
    data = json.load(open('${REPO_ROOT}/pmoves/config/fork_registry.json', encoding='utf-8'))
    forks = data.get('forks', {})
    print(' '.join(name for name, info in forks.items() if not info.get('sync', True)))
except Exception:
    pass
" 2>/dev/null)"
fi

# Top-level submodule status ONLY (NOT --recursive — that hangs)
status_out="$(git submodule status 2>/dev/null || true)"

if [[ -z "${status_out}" ]]; then
  echo "(no submodules registered)"
  exit 0
fi

printf "%-45s | %-12s | %-9s | %-6s | %-25s\n" "path" "HEAD" "behind" "dirty" "tracked-branch"
printf -- "---------------------------------------------+--------------+-----------+--------+-------------------------\n"

while IFS= read -r line; do
  [[ -z "${line}" ]] && continue
  prefix="${line:0:1}"
  rest="${line:1}"
  sha="$(echo "${rest}" | awk '{print $1}')"
  sm_path="$(echo "${rest}" | awk '{print $2}')"

  if [[ -z "${sm_path}" || ! -d "${REPO_ROOT}/${sm_path}" ]]; then
    continue
  fi

  # Skip sync=false forks
  if [[ -n "$SYNC_FALSE" ]]; then
    sm_name="$(basename "$sm_path")"
    if [[ " $SYNC_FALSE " == *" ${sm_name} "* || " $SYNC_FALSE " == *" ${sm_path} "* ]]; then
      printf "%-45.45s | %-12s | %-9s | %-6s | %-25s\n" "${sm_path}" "${sha:0:7}" "skip" "-" "sync=false"
      continue
    fi
  fi

  # Get tracked branch from .gitmodules
  tracked_branch="$(git config --file "${REPO_ROOT}/.gitmodules" "submodule.${sm_path}.branch" 2>/dev/null || echo "main")"

  short_sha="${sha:0:7}"
  if [[ "${prefix}" == "-" ]]; then
    short_sha="uninit"
  fi

  # Compute commits behind using the TRACKED branch (NOT origin/main blindly)
  # No fetch — uses whatever refs are already local. For fresh upstream data,
  # run: gh workflow run fork-sync.yml --ref main -f dry_run=true -f max_forks=40
  behind="?"
  for ref in "origin/${tracked_branch}" "origin/PMOVES.AI-Edition-Hardened" "origin/main" "origin/master"; do
    if git -C "${REPO_ROOT}/${sm_path}" rev-parse --verify "${ref}" >/dev/null 2>&1; then
      behind="$(git -C "${REPO_ROOT}/${sm_path}" rev-list --count "HEAD..${ref}" 2>/dev/null || echo '?')"
      break
    fi
  done

  # Dirty check
  if [[ -n "$(git -C "${REPO_ROOT}/${sm_path}" status --short 2>/dev/null)" ]]; then
    dirty="y"
  else
    dirty="n"
  fi

  printf "%-45.45s | %-12s | %-9s | %-6s | %-25s\n" "${sm_path}" "${short_sha}" "${behind}" "${dirty}" "${tracked_branch}"
done <<< "${status_out}"

echo ""
echo "Notes:"
echo "  - Top-level only (NOT recursive). Use fork-sync.yml for upstream audit."
echo "  - 'skip' = fork_registry.json marks this fork sync=false"
echo "  - 'behind' uses local refs only (no network fetch). Run fork-sync for fresh data."
echo "  - For full sync: gh workflow run fork-sync.yml --ref main -f dry_run=true -f max_forks=40"
echo ""
echo "(informational — exits 0 regardless of drift)"
exit 0
