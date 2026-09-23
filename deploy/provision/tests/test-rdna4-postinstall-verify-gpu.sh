#!/usr/bin/env bash
# Harness for verify_gpu() and health_checks() in rdna4-postinstall.sh.
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

# ---- health_checks: configured-not-started vs a failed start -------------
#   nomodel  : no default.gguf, exporter+socket up  -> rc 0, "CONFIGURED, NOT STARTED"
#   running  : model, service active, /v1/models ok -> rc 0
#   inactive : model, service NOT active            -> rc 1, "FAILED to start"
#   noanswer : model, active, /v1/models fails      -> rc 1
#   exporter : no model, exporter down              -> rc 1
HC_WORK="$(mktemp -d)"
hc() {
  local mode="$1" models="$HC_WORK/$1"
  mkdir -p "$models"
  [[ "$mode" == nomodel || "$mode" == exporter ]] || echo gguf > "$models/default.gguf"
  (
    log() { echo "$*"; }
    log_section() { :; }
    systemctl() {
      [[ "${1:-}" == "is-active" ]] || return 0
      local unit="${*: -1}"
      case "$unit" in
        llama-server.service) [[ "$mode" != inactive ]] ;;
        rocm-smi-exporter.service) [[ "$mode" != exporter ]] ;;
        *) return 0 ;;
      esac
    }
    curl() {
      local a url=""
      for a in "$@"; do [[ "$a" == http* ]] && url="$a"; done
      [[ "$url" == *"/v1/models" && "$mode" == noanswer ]] && return 22
      return 0
    }
    # shellcheck disable=SC2034  # read by the eval'd health_checks
    LLAMA_MODELS_DIR="$models"
    # shellcheck disable=SC2034
    LLAMA_SERVER_PORT=8080
    eval "$(awk '/^health_checks\(\) \{/,/^\}/' "$SCRIPT")"
    set -euo pipefail
    health_checks
  ) > "$HC_WORK/out" 2>&1
  echo "$?"
}
hc_check() {
  local mode="$1" want="$2" must="$3" got
  got="$(hc "$mode")"
  if [[ "$got" == "$want" ]] && { [[ -z "$must" ]] || grep -qF -- "$must" "$HC_WORK/out"; }; then
    echo "PASS  health_checks $mode -> rc $got"
  else
    echo "FAIL  health_checks $mode: want rc $want${must:+ + '$must'}, got $got"
    sed 's/^/        /' "$HC_WORK/out"
    fails=$((fails + 1))
  fi
}
hc_check nomodel  0 "CONFIGURED, NOT STARTED"
hc_check running  0 "running and answering"
hc_check inactive 1 "FAILED to start"
hc_check noanswer 1 "FAILED to start"
hc_check exporter 1 "rocm-smi-exporter is not running"
find "$HC_WORK" -mindepth 1 -delete 2>/dev/null
rmdir "$HC_WORK" 2>/dev/null || true

echo "---"
if [[ $fails -eq 0 ]]; then echo "ALL PASS"; exit 0; fi
echo "$fails FAILED"
exit 1
