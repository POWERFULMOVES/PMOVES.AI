#!/usr/bin/env bash
# Harness for verify_gpu() in rdna4-postinstall.sh.
#
# Extracts ONLY ensure_jq + verify_gpu and runs them with rocm-smi (and, for
# one case, jq) stubbed. Nothing on the host is touched. Asserts the exit-code
# split: 0 pass, 1 finding (ROCm absent / measured zero GPUs), 3 could not
# measure (rocm-smi failed, output unparseable, jq unavailable).
#
# NOTE: the stubbed JSON follows the documented `rocm-smi --showid --json`
# shape ({"card0": {...}, ...}); confirming it against real ROCm output needs
# RDNA4 hardware and is COULD-NOT-MEASURE here.
set -uo pipefail

SELF_DIR="$(CDPATH='' cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROV="${PROV_DIR:-$(CDPATH='' cd -P -- "$SELF_DIR/.." && pwd)}"
SCRIPT="$PROV/rdna4-postinstall.sh"
command -v jq >/dev/null 2>&1 || { echo "COULD-NOT-MEASURE: jq missing on the test host"; exit 3; }
fails=0

# run <case> -> exit code of verify_gpu
run() {
  local mode="$1"
  (
    log() { :; }
    log_section() { :; }
    apt-get() { return 1; }                 # never install anything
    command() {
      if [[ "${1:-}" == "-v" && "${2:-}" == "rocm-smi" ]]; then [[ "$mode" != "absent" ]]; return; fi
      if [[ "${1:-}" == "-v" && "${2:-}" == "jq" && "$mode" == "nojq" ]]; then return 1; fi
      builtin command "$@"
    }
    rocm-smi() {
      [[ "${1:-}" == "--showid" ]] || return 0      # the human table
      case "$mode" in
        two)       echo '{"card0": {"Device ID": "0x7551"}, "card1": {"Device ID": "0x7551"}}' ;;
        preamble)  printf 'WARNING: AMD GPU device(s) is/are in a low-power state\n{"card0": {"Device ID": "0x7551"}}\n' ;;
        system)    echo '{"card0": {"Device ID": "0x7551"}, "system": {"Driver version": "x"}}' ;;
        zero)      echo '{}' ;;
        fail)      return 2 ;;
        garbage)   echo 'ERROR: not json at all' ;;
        array)     echo '[1,2]' ;;
        *)         echo '{"card0": {}}' ;;
      esac
    }
    eval "$(awk '/^ensure_jq\(\) \{/,/^\}/' "$SCRIPT")"
    eval "$(awk '/^verify_gpu\(\) \{/,/^\}/' "$SCRIPT")"
    set -euo pipefail
    verify_gpu
  ) >/dev/null 2>&1
  echo "$?"
}

check() {
  local mode="$1" want="$2" got
  got="$(run "$mode")"
  if [[ "$got" == "$want" ]]; then echo "PASS  $mode -> rc $got"; else echo "FAIL  $mode: want rc $want, got $got"; fails=$((fails + 1)); fi
}

check two      0
check preamble 0
check system   0   # a non-card key is not counted as a GPU
check zero     1
check absent   1
check fail     3
check garbage  3
check array    3
check nojq     3

echo "---"
if [[ $fails -eq 0 ]]; then echo "ALL PASS"; exit 0; fi
echo "$fails FAILED"
exit 1
