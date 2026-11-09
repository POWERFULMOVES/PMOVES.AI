#!/usr/bin/env bash
# test-launcher-root-resolution.sh
# ---------------------------------------------------------------------------
# Guards the bug class that produced #2538: a launcher deriving its repo root
# from `dirname "$BASH_SOURCE"` without resolving symlinks. Invoked through the
# ~/.local/bin/<name> symlink the installers create, ROOT became $HOME, so
# env.shared and the MCP roster both missed and every cred-dependent MCP started
# empty — behind a WARN, not an error.
#
# The original fix touched ONE of three launchers carrying that code. This test
# exists so the next person cannot repeat that: it asserts the symlink walk is
# byte-identical across all three, AND that each resolves correctly when invoked
# through a symlink.
#
# Run: bash deploy/provision/tests/test-launcher-root-resolution.sh
# ---------------------------------------------------------------------------
set -uo pipefail

SELF_DIR="$(CDPATH= cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(CDPATH= cd -P -- "$SELF_DIR/../../.." && pwd)"

LAUNCHERS=(
  "deploy/provision/claude-pmoves.sh"
  "deploy/provision/crush-pmoves.sh"
  "pmoves/scripts/claude-pmoves.sh"
)

pass=0; fail=0
ok()   { printf '  PASS  %s\n' "$1"; pass=$((pass+1)); }
bad()  { printf '  FAIL  %s\n' "$1"; fail=$((fail+1)); }

# --- 1. the walk must be byte-identical across all three -------------------
# Extract the canonical block: from the SELF= assignment through SELF_DIR=.
extract_walk() {
  awk '/^SELF="\$\{BASH_SOURCE\[0\]:-\$0\}"$/{f=1} f{print} /^SELF_DIR=/{if(f)exit}' "$1"
}

echo "== 1. symlink-walk identical across launchers =="
ref="$(extract_walk "$REPO/${LAUNCHERS[0]}")"
if [ -z "$ref" ]; then
  bad "${LAUNCHERS[0]}: no resolution block found (marker changed?)"
else
  for l in "${LAUNCHERS[@]}"; do
    got="$(extract_walk "$REPO/$l")"
    if [ -z "$got" ]; then
      bad "$l: no resolution block found"
    elif [ "$got" = "$ref" ]; then
      ok "$l"
    else
      bad "$l: walk DIFFERS from ${LAUNCHERS[0]} — fix all three together"
      diff <(printf '%s\n' "$ref") <(printf '%s\n' "$got") | sed 's/^/        /'
    fi
  done
fi

# --- 2. none may use the colliding variable name --------------------------
# PMOVES_REPO_ROOT is already consumed by pmoves/services/creator-operator/config.py.
echo "== 2. no PMOVES_REPO_ROOT collision =="
for l in "${LAUNCHERS[@]}"; do
  # Strip comments first — the files legitimately NAME the variable in a comment
  # explaining why it is avoided. Only real code references are a failure.
  if sed 's/#.*//' "$REPO/$l" 2>/dev/null | grep -q 'PMOVES_REPO_ROOT'; then
    bad "$l: uses PMOVES_REPO_ROOT (collides with creator-operator); use PMOVES_LAUNCHER_ROOT"
  else
    ok "$l"
  fi
done

# --- 3. resolve correctly when invoked through a symlink ------------------
# Fixture: a minimal repo (marker file only, no env.shared) plus a fake bin dir
# holding an absolute symlink and a relative symlink chain. A launcher that
# resolves correctly clears the marker gate; one that does not exits 1 with
# "no pmoves/Makefile".
echo "== 3. symlink invocation resolves to the fixture repo =="
FIX="$(mktemp -d)"
trap 'rm -rf "$FIX"' EXIT
mkdir -p "$FIX/repo/pmoves/scripts" "$FIX/repo/deploy/provision" "$FIX/bin"
: > "$FIX/repo/pmoves/Makefile"                     # the marker
printf '#!/bin/sh\nexit 0\n' > "$FIX/bin/claude"    # stubs so exec succeeds
printf '#!/bin/sh\nexit 0\n' > "$FIX/bin/crush"
chmod +x "$FIX/bin/claude" "$FIX/bin/crush"

for l in "${LAUNCHERS[@]}"; do
  name="$(basename "$l")"; sub="$(dirname "$l")"
  cp "$REPO/$l" "$FIX/repo/$sub/$name"
  chmod +x "$FIX/repo/$sub/$name"

  # absolute symlink, then a relative symlink pointing at that symlink (chain)
  ln -sf "$FIX/repo/$sub/$name" "$FIX/bin/abs-$name"
  ( cd "$FIX/bin" && ln -sf "abs-$name" "rel-$name" )

  for entry in "abs-$name" "rel-$name"; do
    err="$(PATH="$FIX/bin:$PATH" \
           HOME="$FIX/fakehome" \
           "$FIX/bin/$entry" --version 2>&1 >/dev/null)"
    if printf '%s' "$err" | grep -q 'no pmoves/Makefile'; then
      bad "$l via $entry — root misresolved: $(printf '%s' "$err" | head -1)"
    else
      ok "$l via $entry"
    fi
  done
done

echo
echo "  passed=$pass failed=$fail"
[ "$fail" -eq 0 ] || exit 1
