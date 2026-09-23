#!/usr/bin/env bash
# Harness for install_uv() in b850-bootstrap.sh and dgx-spark-bootstrap.sh.
#
# Extracts ONLY the install_uv function from each bootstrap and runs it
# unprivileged against the REAL uv release assets, installing into a temp dir
# (UV_INSTALL_DIR). Nothing is written outside that temp dir; the bootstraps
# themselves are never executed. Cases per script:
#   ok        real asset + real .sha256          -> installs uv (and uvx)
#   tampered  .sha256 rewritten to a wrong hash  -> refuses, nothing installed
#   missing   .sha256 download fails (HTTP 404)  -> refuses, nothing installed
#   malformed .sha256 is not a 64-hex digest     -> refuses, nothing installed
#
# Needs network access to github.com. Exit codes: 0 all pass, 1 a case
# failed, 3 could not measure (no network / missing tool).
set -uo pipefail

SELF_DIR="$(CDPATH='' cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# PROV_DIR lets the harness run against another copy (e.g. a pre-fix
# revision extracted with git show) as a positive control.
PROV="${PROV_DIR:-$(CDPATH='' cd -P -- "$SELF_DIR/.." && pwd)}"
UV_VERSION_UNDER_TEST="${UV_VERSION_UNDER_TEST:-0.6.0}"

for t in curl tar sha256sum awk install mktemp; do
  command -v "$t" >/dev/null 2>&1 || { echo "COULD-NOT-MEASURE: $t missing"; exit 3; }
done
if ! curl -fsS -o /dev/null -I "https://github.com/astral-sh/uv/releases/download/${UV_VERSION_UNDER_TEST}/uv-x86_64-unknown-linux-gnu.tar.gz.sha256"; then
  echo "COULD-NOT-MEASURE: github.com release assets unreachable"
  exit 3
fi

WORK="$(mktemp -d)"
CACHE="$WORK/cache"
mkdir -p "$CACHE"
fails=0

# run_case <script> <case> -> prints "installed" / "refused"
run_case() {
  local script="$1" mode="$2" dest
  dest="$WORK/$(basename "$1" .sh)-$2"
  mkdir -p "$dest"
  (
    set -euo pipefail
    log() { :; }
    log_section() { :; }
    # Force the "uv not present" branch regardless of the host.
    command() { if [[ "${1:-}" == "-v" && "${2:-}" == "uv" ]]; then return 1; fi; builtin command "$@"; }
    # curl shim: cache real downloads; inject checksum faults for the case.
    curl() {
      local url="" out="" a prev=""
      for a in "$@"; do
        [[ "$prev" == "-o" ]] && out="$a"
        [[ "$a" == https://* ]] && url="$a"
        prev="$a"
      done
      if [[ "$url" == *.sha256 && "$mode" == "missing" ]]; then return 22; fi
      local c
      c="$CACHE/$(basename "$url")"
      [[ -f "$c" ]] || builtin command curl -fLsS "$url" -o "$c" || return $?
      cp "$c" "$out"
      if [[ "$url" == *.sha256 && "$mode" == "tampered" ]]; then
        printf '%064d  %s\n' 0 "$(basename "${url%.sha256}")" > "$out"
      elif [[ "$url" == *.sha256 && "$mode" == "malformed" ]]; then
        printf 'not-a-digest\n' > "$out"
      fi
    }
    # shellcheck disable=SC2034  # read by the eval'd install_uv
    UV_VERSION="$UV_VERSION_UNDER_TEST"
    # shellcheck disable=SC2034
    UV_INSTALL_DIR="$dest"
    eval "$(awk '/^install_uv\(\) \{/,/^\}/' "$script")"
    install_uv
  ) >/dev/null 2>&1
  if [[ -x "$dest/uv" ]]; then echo installed; else echo refused; fi
}

check() {
  local label="$1" want="$2" got="$3"
  if [[ "$want" == "$got" ]]; then
    echo "PASS  $label: $got"
  else
    echo "FAIL  $label: want $want, got $got"
    fails=$((fails + 1))
  fi
}

for s in b850-bootstrap.sh dgx-spark-bootstrap.sh; do
  script="$PROV/$s"
  check "$s ok"        installed "$(run_case "$script" ok)"
  check "$s tampered"  refused   "$(run_case "$script" tampered)"
  check "$s missing"   refused   "$(run_case "$script" missing)"
  check "$s malformed" refused   "$(run_case "$script" malformed)"
done

# The ok case must have produced BOTH binaries from uv-<triple>/.
for d in "$WORK"/b850-bootstrap-ok "$WORK"/dgx-spark-bootstrap-ok; do
  if [[ -x "$d/uvx" ]]; then echo "PASS  $(basename "$d"): uvx installed"; else echo "FAIL  $(basename "$d"): uvx missing"; fails=$((fails + 1)); fi
done

find "$WORK" -mindepth 1 -delete 2>/dev/null
rmdir "$WORK" 2>/dev/null || true
echo "---"
if [[ $fails -eq 0 ]]; then echo "ALL PASS"; exit 0; fi
echo "$fails FAILED"
exit 1
