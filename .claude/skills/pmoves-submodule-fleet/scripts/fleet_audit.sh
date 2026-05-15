#!/usr/bin/env bash
# pmoves-submodule-fleet — single-screen submodule audit.
# Always exits 0 (informational).
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "${REPO_ROOT}" || exit 0

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "ERROR: not a git repo at ${REPO_ROOT}" >&2
  exit 0
fi

# git submodule status --recursive lines look like:
#  <sha> <path> (<describe>)
# Leading char: ' ' clean, '-' uninitialized, '+' commit differs, 'U' merge conflict.
status_out="$(git submodule status --recursive 2>/dev/null || true)"

if [[ -z "${status_out}" ]]; then
  echo "(no submodules registered)"
  exit 0
fi

printf "%-50s | %-12s | %-9s | %-7s\n" "path" "HEAD" "behind" "dirty"
printf -- "---------------------------------------------------+--------------+-----------+--------\n"

# Process each submodule line.
while IFS= read -r line; do
  [[ -z "${line}" ]] && continue
  prefix="${line:0:1}"
  rest="${line:1}"
  # rest = "<sha> <path> (...)"
  sha="$(echo "${rest}" | awk '{print $1}')"
  path="$(echo "${rest}" | awk '{print $2}')"

  if [[ -z "${path}" || ! -d "${REPO_ROOT}/${path}" ]]; then
    continue
  fi

  short_sha="${sha:0:7}"
  if [[ "${prefix}" == "-" ]]; then
    short_sha="uninit"
  fi

  # Best-effort fetch — silent failure is fine (no network, no auth, etc.).
  git -C "${REPO_ROOT}/${path}" fetch --quiet origin 2>/dev/null || true

  # Compute commits behind. Try main, then master.
  behind="?"
  for ref in origin/main origin/master; do
    if git -C "${REPO_ROOT}/${path}" rev-parse --verify "${ref}" >/dev/null 2>&1; then
      behind="$(git -C "${REPO_ROOT}/${path}" rev-list --count "HEAD..${ref}" 2>/dev/null || echo '?')"
      break
    fi
  done

  # Dirty check.
  if [[ -n "$(git -C "${REPO_ROOT}/${path}" status --short 2>/dev/null)" ]]; then
    dirty="y"
  else
    dirty="n"
  fi

  printf "%-50.50s | %-12s | %-9s | %-7s\n" "${path}" "${short_sha}" "${behind}" "${dirty}"
done <<< "${status_out}"

echo ""
echo "(informational — exits 0 regardless of drift)"
exit 0
