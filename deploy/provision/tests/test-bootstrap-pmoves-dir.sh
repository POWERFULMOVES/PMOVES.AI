#!/usr/bin/env bash
# Harness for preflight_pmoves_dir() in b850-bootstrap.sh and
# dgx-spark-bootstrap.sh.
#
# Extracts ONLY the pre-flight functions (and the legacy-entry list) and runs
# them against temp directories. Asserts the outcome for each /opt/pmoves
# shape AND that the pre-flight never moves, deletes or changes anything.
#
#   absent / empty / git checkout        -> rc 0 (setup may proceed)
#   legacy layout (bin data etc lib logs profile.yaml, no .git)
#                                        -> rc 1, "LEGACY" + migration command
#   legacy subset (e.g. bin + profile.yaml) -> rc 1, "LEGACY"
#   legacy + an unknown entry            -> rc 1, generic (not LEGACY)
#   other non-empty, non-git             -> rc 1, generic message
#
# Exit codes: 0 all pass, 1 a case failed.
set -uo pipefail

SELF_DIR="$(CDPATH='' cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROV="${PROV_DIR:-$(CDPATH='' cd -P -- "$SELF_DIR/.." && pwd)}"
WORK="$(mktemp -d)"
fails=0

mk() { # <name> <entries...>  (a trailing / makes a directory)
  local d="$WORK/$1" e
  shift
  mkdir -p "$d"
  for e in "$@"; do
    if [[ "$e" == */ ]]; then mkdir -p "$d/$e"; else echo "x" > "$d/$e"; fi
  done
  echo "$d"
}

snapshot() { (cd "$1" 2>/dev/null && find . -printf '%y %p %s\n' | sort) | sha256sum | cut -c1-16; }

run() { # <script> <dir>
  (
    # shellcheck disable=SC2034  # read by the eval'd functions
    OPERATOR_USER=operator
    # shellcheck disable=SC2034
    OPERATOR_GROUP=operator
    # shellcheck disable=SC2034
    PMOVES_DIR="$2"
    eval "$(awk '/^PMOVES_LEGACY_ENTRIES=/' "$1")"
    eval "$(awk '/^pmoves_dir_is_legacy\(\) \{/,/^\}/' "$1")"
    eval "$(awk '/^preflight_pmoves_dir\(\) \{/,/^\}/' "$1")"
    preflight_pmoves_dir
  ) > "$WORK/out" 2>&1
  echo "$?"
}

check() { # <script> <label> <dir> <want_rc> <must-contain> <must-not-contain>
  local script="$1" label="$2" dir="$3" want="$4" must="$5" mustnot="$6" before after rc ok=1
  before="$(snapshot "$dir")"
  rc="$(run "$script" "$dir")"
  after="$(snapshot "$dir")"
  [[ "$rc" == "$want" ]] || ok=0
  [[ "$before" == "$after" ]] || ok=0
  if [[ -n "$must" ]] && ! grep -qF -- "$must" "$WORK/out"; then ok=0; fi
  if [[ -n "$mustnot" ]] && grep -qF -- "$mustnot" "$WORK/out"; then ok=0; fi
  if [[ $ok -eq 1 ]]; then
    echo "PASS  $(basename "$script") $label (rc=$rc, unchanged)"
  else
    echo "FAIL  $(basename "$script") $label: want rc=$want unchanged; got rc=$rc changed=$([[ "$before" == "$after" ]] && echo no || echo YES)"
    sed 's/^/        /' "$WORK/out"
    fails=$((fails + 1))
  fi
}

for s in b850-bootstrap.sh dgx-spark-bootstrap.sh; do
  S="$PROV/$s"
  t="${s%.sh}"
  check "$S" "absent"         "$WORK/$t-absent"                                   0 "" ""
  check "$S" "empty"          "$(mk "$t-empty")"                                   0 "" ""
  check "$S" "git checkout"   "$(mk "$t-git" .git/ README.md pmoves/)"             0 "" ""
  check "$S" "legacy layout"  "$(mk "$t-legacy" bin/ data/ etc/ lib/ logs/ profile.yaml)" 1 "LEGACY" ""
  check "$S" "legacy migrate cmd" "$WORK/$t-legacy"                                1 ".legacy-" ""
  check "$S" "legacy subset"  "$(mk "$t-legacy-sub" bin/ profile.yaml)"            1 "LEGACY" ""
  check "$S" "legacy+unknown" "$(mk "$t-legacy-plus" bin/ data/ profile.yaml notes.txt)" 1 "not the known legacy layout" "LEGACY pre-checkout"
  check "$S" "other non-git"  "$(mk "$t-other" random.txt stuff/)"                 1 "not a git checkout" "LEGACY pre-checkout"
  check "$S" "hidden-only"    "$(mk "$t-hidden" .cache/)"                          1 "not the known legacy layout" "LEGACY pre-checkout"
done

find "$WORK" -mindepth 1 -delete 2>/dev/null
rmdir "$WORK" 2>/dev/null || true
echo "---"
if [[ $fails -eq 0 ]]; then echo "ALL PASS"; exit 0; fi
echo "$fails FAILED"
exit 1
