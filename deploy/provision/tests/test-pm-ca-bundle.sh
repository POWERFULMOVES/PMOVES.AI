#!/usr/bin/env bash
# test-pm-ca-bundle.sh
# ---------------------------------------------------------------------------
# Guards pmoves/scripts/pm-ca-bundle.sh — the launcher fragment that repairs
# host TLS after env.shared exports SSL_CERT_FILE= / SSL_CERT_DIR= ... EMPTY
# (a container leak guard). Set-but-empty made python ssl and the HF Xet
# backend fail with CERTIFICATE_VERIFY_FAILED on Knuckles, 2026-09-28.
#
# All bundle paths are stubbed via PM_CA_BUNDLE_CANDIDATES; the certifi probe
# is disabled with PM_CA_BUNDLE_NO_CERTIFI=1. No network, no system paths.
#
# Run: bash deploy/provision/tests/test-pm-ca-bundle.sh
# ---------------------------------------------------------------------------
set -uo pipefail

# shellcheck disable=SC1007  # CDPATH= (empty) is intentional, as in sibling tests
SELF_DIR="$(CDPATH= cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1007
REPO="$(CDPATH= cd -P -- "$SELF_DIR/../../.." && pwd)"
FRAGMENT="$REPO/pmoves/scripts/pm-ca-bundle.sh"

pass=0; fail=0
ok()  { printf '  PASS  %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  FAIL  %s\n' "$1"; fail=$((fail+1)); }

if [ ! -f "$FRAGMENT" ]; then
  printf '  FAIL  fragment missing: %s\n' "$FRAGMENT"
  exit 1
fi

FIXTURE="$(mktemp -d)"
trap 'rm -rf "$FIXTURE"' EXIT
BUNDLE="$FIXTURE/ca-certificates.crt"
printf -- '-----BEGIN CERTIFICATE-----\nstub\n-----END CERTIFICATE-----\n' > "$BUNDLE"
OTHER="$FIXTURE/other.pem"
printf 'x\n' > "$OTHER"
EMPTYFILE="$FIXTURE/empty.crt"
: > "$EMPTYFILE"

# Run the fragment in a clean subshell under the SAME strict mode launchers
# use. Args are `VAR=value` (export) or `VAR=` (export empty) or `-VAR`
# (ensure unset). Prints the resulting env as KEY=<value>|<UNSET>.
run_norm() {
  (
    set -euo pipefail
    unset SSL_CERT_FILE SSL_CERT_DIR REQUESTS_CA_BUNDLE CURL_CA_BUNDLE NODE_EXTRA_CA_CERTS
    export PM_CA_BUNDLE_NO_CERTIFI=1
    local a
    for a in "$@"; do
      # shellcheck disable=SC2163  # exporting the NAME=value held in $a is the point
      case "$a" in
        -*) unset "${a#-}" ;;
        *=*) export "$a" ;;
      esac
    done
    # shellcheck source=/dev/null
    . "$FRAGMENT"
    pm_ca_bundle_normalize
    printf 'rc=%s\n' "$?"
    local v
    for v in SSL_CERT_FILE SSL_CERT_DIR REQUESTS_CA_BUNDLE CURL_CA_BUNDLE NODE_EXTRA_CA_CERTS; do
      if [ -n "${!v+x}" ]; then printf '%s=%s\n' "$v" "${!v}"; else printf '%s=<UNSET>\n' "$v"; fi
    done
    printf 'LINE=%s\n' "${PM_CA_BUNDLE_LINE:-}"
  ) 2>"$FIXTURE/stderr"
}
get() { printf '%s\n' "$1" | sed -n "s/^$2=//p" | head -1; }

echo "== pm-ca-bundle =="

# --- 1. THE BUG: env.shared's empty guards, bundle present --------------------
out="$(run_norm "PM_CA_BUNDLE_CANDIDATES=$BUNDLE" SSL_CERT_FILE= SSL_CERT_DIR= REQUESTS_CA_BUNDLE= CURL_CA_BUNDLE= NODE_EXTRA_CA_CERTS=)"
[ "$(get "$out" rc)" = "0" ] && ok "returns 0 (bundle present)" || bad "rc=$(get "$out" rc)"
[ "$(get "$out" SSL_CERT_FILE)" = "$BUNDLE" ] && ok "empty SSL_CERT_FILE -> system bundle" || bad "SSL_CERT_FILE=$(get "$out" SSL_CERT_FILE)"
[ "$(get "$out" REQUESTS_CA_BUNDLE)" = "$BUNDLE" ] && ok "empty REQUESTS_CA_BUNDLE -> system bundle" || bad "REQUESTS_CA_BUNDLE=$(get "$out" REQUESTS_CA_BUNDLE)"
[ "$(get "$out" SSL_CERT_DIR)" = "<UNSET>" ] && ok "empty SSL_CERT_DIR is UNSET (not left empty)" || bad "SSL_CERT_DIR=$(get "$out" SSL_CERT_DIR)"
[ "$(get "$out" CURL_CA_BUNDLE)" = "<UNSET>" ] && ok "empty CURL_CA_BUNDLE is UNSET" || bad "CURL_CA_BUNDLE=$(get "$out" CURL_CA_BUNDLE)"
[ "$(get "$out" NODE_EXTRA_CA_CERTS)" = "<UNSET>" ] && ok "empty NODE_EXTRA_CA_CERTS is UNSET" || bad "NODE_EXTRA_CA_CERTS=$(get "$out" NODE_EXTRA_CA_CERTS)"
get "$out" LINE | grep -q "SSL_CERT_FILE=$BUNDLE" && ok "PM_CA_BUNDLE_LINE names the bundle" || bad "LINE=$(get "$out" LINE)"
get "$out" LINE | grep -q "cleared empty" && ok "PM_CA_BUNDLE_LINE reports the cleared empties" || bad "LINE lacks cleared list"
! grep -q WARN "$FIXTURE/stderr" && ok "no WARN when a bundle is found" || bad "unexpected WARN: $(cat "$FIXTURE/stderr")"

# --- 2. vars genuinely unset (not the empty form) -> still resolved -----------
out="$(run_norm "PM_CA_BUNDLE_CANDIDATES=$BUNDLE")"
[ "$(get "$out" SSL_CERT_FILE)" = "$BUNDLE" ] && ok "unset SSL_CERT_FILE -> system bundle" || bad "SSL_CERT_FILE=$(get "$out" SSL_CERT_FILE)"

# --- 3. candidate ORDER: first readable non-empty file wins -------------------
out="$(run_norm "PM_CA_BUNDLE_CANDIDATES=$FIXTURE/nope.crt
$EMPTYFILE
$BUNDLE
$OTHER" SSL_CERT_FILE=)"
[ "$(get "$out" SSL_CERT_FILE)" = "$BUNDLE" ] && ok "skips missing + zero-byte candidates, takes first real one" || bad "SSL_CERT_FILE=$(get "$out" SSL_CERT_FILE)"

# --- 4. OPERATOR OVERRIDE is never touched ------------------------------------
out="$(run_norm "PM_CA_BUNDLE_CANDIDATES=$BUNDLE" "SSL_CERT_FILE=$OTHER" "REQUESTS_CA_BUNDLE=$OTHER" SSL_CERT_DIR=)"
[ "$(get "$out" SSL_CERT_FILE)" = "$OTHER" ] && ok "operator SSL_CERT_FILE kept" || bad "operator SSL_CERT_FILE overridden: $(get "$out" SSL_CERT_FILE)"
[ "$(get "$out" REQUESTS_CA_BUNDLE)" = "$OTHER" ] && ok "operator REQUESTS_CA_BUNDLE kept" || bad "operator REQUESTS_CA_BUNDLE overridden"
[ "$(get "$out" SSL_CERT_DIR)" = "<UNSET>" ] && ok "empty SSL_CERT_DIR still cleared beside an operator SSL_CERT_FILE" || bad "SSL_CERT_DIR=$(get "$out" SSL_CERT_DIR)"

# --- 5. operator REQUESTS_CA_BUNDLE kept when only SSL_CERT_FILE is resolved --
out="$(run_norm "PM_CA_BUNDLE_CANDIDATES=$BUNDLE" SSL_CERT_FILE= "REQUESTS_CA_BUNDLE=$OTHER")"
[ "$(get "$out" SSL_CERT_FILE)" = "$BUNDLE" ] && ok "SSL_CERT_FILE resolved" || bad "SSL_CERT_FILE=$(get "$out" SSL_CERT_FILE)"
[ "$(get "$out" REQUESTS_CA_BUNDLE)" = "$OTHER" ] && ok "REQUESTS_CA_BUNDLE only set when unset" || bad "REQUESTS_CA_BUNDLE overridden: $(get "$out" REQUESTS_CA_BUNDLE)"

# --- 6. operator value pointing nowhere: kept, but WARNed ---------------------
out="$(run_norm "PM_CA_BUNDLE_CANDIDATES=$BUNDLE" "SSL_CERT_FILE=$FIXTURE/missing.pem")"
[ "$(get "$out" SSL_CERT_FILE)" = "$FIXTURE/missing.pem" ] && ok "unreadable operator value kept (not silently replaced)" || bad "replaced: $(get "$out" SSL_CERT_FILE)"
grep -q 'WARN: SSL_CERT_FILE=.*not a readable file' "$FIXTURE/stderr" && ok "unreadable operator value WARNs" || bad "no WARN for unreadable operator value"

# --- 7. NO bundle anywhere: fail OPEN, loudly ---------------------------------
out="$(run_norm "PM_CA_BUNDLE_CANDIDATES=$FIXTURE/a.crt
$FIXTURE/b.crt" SSL_CERT_FILE= SSL_CERT_DIR=)"
[ "$(get "$out" rc)" = "0" ] && ok "returns 0 when no bundle found (fail open)" || bad "rc=$(get "$out" rc) — must not abort a launcher"
[ "$(get "$out" SSL_CERT_FILE)" = "<UNSET>" ] && ok "SSL_CERT_FILE left UNSET, not empty, when no bundle" || bad "SSL_CERT_FILE=$(get "$out" SSL_CERT_FILE)"
grep -q "WARN: no CA bundle found (tried: $FIXTURE/a.crt, $FIXTURE/b.crt)" "$FIXTURE/stderr" && ok "WARN names every path tried" || bad "WARN missing/incomplete: $(cat "$FIXTURE/stderr")"
get "$out" LINE | grep -q "NOT FOUND" && ok "PM_CA_BUNDLE_LINE says NOT FOUND" || bad "LINE=$(get "$out" LINE)"

# --- 8. already-sound env: silent no-op ---------------------------------------
out="$(run_norm "PM_CA_BUNDLE_CANDIDATES=$BUNDLE" "SSL_CERT_FILE=$OTHER")"
[ -z "$(get "$out" LINE)" ] && ok "no line when nothing changed" || bad "LINE=$(get "$out" LINE)"
[ ! -s "$FIXTURE/stderr" ] && ok "no stderr when nothing changed" || bad "stderr: $(cat "$FIXTURE/stderr")"

# --- 9. every env.shared launcher + with-env.sh wires the fragment ------------
# A fragment that exists but is never sourced is the failure this fleet
# repeats; assert the call site, not just the file.
for f in deploy/provision/claude-pmoves.sh deploy/provision/codex-pmoves.sh \
         deploy/provision/crush-pmoves.sh deploy/provision/hermes-pmoves.sh \
         deploy/provision/kilo-pmoves.sh deploy/provision/kimi-pmoves.sh \
         deploy/provision/pmoves-mini.sh pmoves/scripts/with-env.sh; do
  if grep -q 'pm-ca-bundle.sh' "$REPO/$f" && grep -q 'pm_ca_bundle_normalize' "$REPO/$f"; then
    ok "wired: $f"
  else
    bad "NOT wired: $f"
  fi
done

# --- 10. with-env.sh end-to-end: empty guard in an env file -> bundle ---------
mkdir -p "$FIXTURE/pm/scripts"
cp "$REPO/pmoves/scripts/with-env.sh" "$REPO/pmoves/scripts/pm-ca-bundle.sh" "$FIXTURE/pm/scripts/"
printf 'SSL_CERT_FILE=\nSSL_CERT_DIR=\nREQUESTS_CA_BUNDLE=\nPM_PROBE=1\n' > "$FIXTURE/pm/env.shared"
res="$(env -i PATH="$PATH" HOME="$FIXTURE" PM_CA_BUNDLE_NO_CERTIFI=1 "PM_CA_BUNDLE_CANDIDATES=$BUNDLE" \
  bash "$FIXTURE/pm/scripts/with-env.sh" bash -c 'printf "%s|%s|%s|%s" "${PM_PROBE:-}" "${SSL_CERT_FILE-<UNSET>}" "${SSL_CERT_DIR-<UNSET>}" "${REQUESTS_CA_BUNDLE-<UNSET>}"' 2>"$FIXTURE/stderr")"
[ "$res" = "1|$BUNDLE|<UNSET>|$BUNDLE" ] && ok "with-env.sh: env file loaded AND CA vars normalized" || bad "with-env.sh got '$res' (stderr: $(head -c 300 "$FIXTURE/stderr"))"

echo
echo "pm-ca-bundle: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
