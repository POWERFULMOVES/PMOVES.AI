#!/usr/bin/env bash
# Harness for verify_installation() in hostinger-kvm-setup.sh.
#
# Extracts ONLY verify_installation and runs it for every node type with the
# host commands stubbed (docker, tailscale, systemctl) and PMOVES_WORKDIR
# pointed at a temp dir. The provisioner itself is never executed and nothing
# outside the temp dir is touched.
#
# Expected outcomes:
#   docker-hosting types (kvm4-1 kvm4-2 kvm2 gpu-5090 rdna4-workstation dgx-spark)
#     docker+compose present   -> rc 0
#     docker absent            -> rc 1 ("Docker NOT found")
#   pve-member, pve-member-fresh (install_docker/install_runner skip by design)
#     docker absent            -> rc 0, Docker AND runner report "skipped (by design)"
#   any type, workdir not a checkout -> rc 1
#
# Exit codes: 0 all pass, 1 a case failed.
set -uo pipefail

SELF_DIR="$(CDPATH='' cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# PROV_DIR lets the harness run against another copy (e.g. a pre-fix revision
# extracted with git show) as a positive control.
PROV="${PROV_DIR:-$(CDPATH='' cd -P -- "$SELF_DIR/.." && pwd)}"
SCRIPT="$PROV/hostinger-kvm-setup.sh"

WORK="$(mktemp -d)"
mkdir -p "$WORK/checkout/.git" "$WORK/not-a-checkout"
printf 'MODEL_NAMESPACE=pmoves\n' > "$WORK/checkout/.env.local"
fails=0

# run_verify <node_type> <docker:yes|no> <workdir> -> "<rc>" then the log
run_verify() {
  local node="$1" have_docker="$2" wd="$3"
  (
    set -euo pipefail
    log_info()    { echo "INFO $1"; }
    log_warn()    { echo "WARN $1"; }
    log_error()   { echo "ERROR $1"; }
    log_section() { echo "SECTION $1"; }
    command() {
      if [[ "${1:-}" == "-v" && "${2:-}" == "docker" && "$have_docker" != "yes" ]]; then return 1; fi
      if [[ "${1:-}" == "-v" && ( "${2:-}" == "docker" || "${2:-}" == "tailscale" ) ]]; then echo "/stub/$2"; return 0; fi
      builtin command "$@"
    }
    docker() {
      [[ "$have_docker" == "yes" ]] || return 127
      case "${1:-}" in
        --version) echo "Docker version stub" ;;
        compose)   echo "Docker Compose version stub" ;;
      esac
    }
    tailscale() { return 0; }
    systemctl() { return 0; }
    # shellcheck disable=SC2034  # read by the eval'd verify_installation
    NODE_TYPE="$node"
    # shellcheck disable=SC2034
    PMOVES_WORKDIR="$wd"
    eval "$(awk '/^verify_installation\(\) \{/,/^\}/' "$SCRIPT")"
    verify_installation
  ) > "$WORK/out" 2>&1
  echo "$?"
}

expect() {
  local label="$1" want_rc="$2" got_rc="$3" must="$4" mustnot="$5" ok=1
  [[ "$got_rc" == "$want_rc" ]] || ok=0
  if [[ -n "$must" ]] && ! grep -qF -- "$must" "$WORK/out"; then ok=0; fi
  if [[ -n "$mustnot" ]] && grep -qF -- "$mustnot" "$WORK/out"; then ok=0; fi
  if [[ $ok -eq 1 ]]; then
    echo "PASS  $label (rc=$got_rc)"
  else
    echo "FAIL  $label: want rc=$want_rc${must:+, contains '$must'}${mustnot:+, lacks '$mustnot'}; got rc=$got_rc"
    sed 's/^/        /' "$WORK/out"
    fails=$((fails + 1))
  fi
}

for n in kvm4-1 kvm4-2 kvm2 gpu-5090 rdna4-workstation dgx-spark; do
  rc="$(run_verify "$n" yes "$WORK/checkout")"
  expect "$n docker present"  0 "$rc" "✓ Docker installed" "skipped (by design)"
  rc="$(run_verify "$n" no "$WORK/checkout")"
  expect "$n docker absent"   1 "$rc" "Docker NOT found" ""
done

for n in pve-member pve-member-fresh; do
  rc="$(run_verify "$n" no "$WORK/checkout")"
  expect "$n docker absent (by design)" 0 "$rc" "Docker + Compose: skipped (by design" "Docker NOT found"
  expect "$n runner skipped"            0 "$rc" "Actions runner: skipped (by design" ""
done

rc="$(run_verify kvm2 yes "$WORK/not-a-checkout")"
expect "kvm2 workdir not a checkout" 1 "$rc" "checkout NOT found" ""
rc="$(run_verify pve-member no "$WORK/not-a-checkout")"
expect "pve-member workdir not a checkout" 1 "$rc" "checkout NOT found" ""

find "$WORK" -mindepth 1 -delete 2>/dev/null
rmdir "$WORK" 2>/dev/null || true
echo "---"
if [[ $fails -eq 0 ]]; then echo "ALL PASS"; exit 0; fi
echo "$fails FAILED"
exit 1
