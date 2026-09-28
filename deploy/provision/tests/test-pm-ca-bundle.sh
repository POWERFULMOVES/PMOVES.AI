#!/usr/bin/env bash
# test-pm-ca-bundle.sh
# ---------------------------------------------------------------------------
# Guards pmoves/scripts/pm-ca-bundle.sh — the launcher fragment that repairs
# host TLS after env.shared exports SSL_CERT_FILE= / SSL_CERT_DIR= ... EMPTY
# (a container leak guard). Set-but-empty made python ssl and the HF Xet
# backend fail with CERTIFICATE_VERIFY_FAILED on a fleet node, 2026-09-28.
#
# All bundle paths are stubbed via PM_CA_BUNDLE__TEST_CANDIDATES; the certifi
# probe is disabled with PM_CA_BUNDLE__TEST_NO_CERTIFI=1. No network.
# The httpx/requests effective-CA probes need a python with both installed
# (PM_CA_BUNDLE_TEST_PY, else python3); they SKIP, loudly, if none has them.
#
# Run: bash deploy/provision/tests/test-pm-ca-bundle.sh
# ---------------------------------------------------------------------------
set -uo pipefail

# shellcheck disable=SC1007  # CDPATH= (empty) is intentional, as in sibling tests
SELF_DIR="$(CDPATH= cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1007
REPO="$(CDPATH= cd -P -- "$SELF_DIR/../../.." && pwd)"
FRAGMENT="$REPO/pmoves/scripts/pm-ca-bundle.sh"

pass=0; fail=0; skip=0
ok()   { printf '  PASS  %s\n' "$1"; pass=$((pass+1)); }
bad()  { printf '  FAIL  %s\n' "$1"; fail=$((fail+1)); }
skp()  { printf '  SKIP  %s\n' "$1"; skip=$((skip+1)); }

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
CADIR="$FIXTURE/corp-ca.d"
mkdir -p "$CADIR"

# Set up a clean subshell under the SAME strict mode launchers use, apply the
# args, source the fragment and make a BARE call (no `|| true`) — so a
# non-zero return or an aborting builtin kills the subshell and is visible.
# Args: `VAR=value` exports (`VAR=` exports empty); `RO:VAR=value` exports
# then marks readonly. run_norm prints the env; run_probe execs a python
# probe in the normalized env.
_norm_setup='
    set -euo pipefail
    unset SSL_CERT_FILE SSL_CERT_DIR REQUESTS_CA_BUNDLE CURL_CA_BUNDLE NODE_EXTRA_CA_CERTS
    export PM_CA_BUNDLE__TEST_NO_CERTIFI=1
    for a in "$@"; do
      case "$a" in
        RO:*) a="${a#RO:}"; export "${a?}"; readonly "${a%%=*}" ;;
        *=*)  export "${a?}" ;;
      esac
    done
    . "$FRAGMENT"
    pm_ca_bundle_normalize
    printf "rc=%s\n" "$?"
'
run_norm() {
  FRAGMENT="$FRAGMENT" bash -c "$_norm_setup"'
    for v in SSL_CERT_FILE SSL_CERT_DIR REQUESTS_CA_BUNDLE CURL_CA_BUNDLE NODE_EXTRA_CA_CERTS; do
      if [ -n "${!v+x}" ]; then printf "%s=%s\n" "$v" "${!v}"; else printf "%s=<UNSET>\n" "$v"; fi
    done
    printf "LINE=%s\n" "${PM_CA_BUNDLE_LINE:-}"
    printf "ALIVE=1\n"
  ' _ "$@" 2>"$FIXTURE/stderr"
}
get() { printf '%s\n' "$1" | sed -n "s/^$2=//p" | head -1; }

echo "== pm-ca-bundle =="

# --- 1. THE BUG: env.shared's empty guards, bundle present --------------------
out="$(run_norm "PM_CA_BUNDLE__TEST_CANDIDATES=$BUNDLE" SSL_CERT_FILE= SSL_CERT_DIR= REQUESTS_CA_BUNDLE= CURL_CA_BUNDLE= NODE_EXTRA_CA_CERTS=)"
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
out="$(run_norm "PM_CA_BUNDLE__TEST_CANDIDATES=$BUNDLE")"
[ "$(get "$out" SSL_CERT_FILE)" = "$BUNDLE" ] && ok "unset SSL_CERT_FILE -> system bundle" || bad "SSL_CERT_FILE=$(get "$out" SSL_CERT_FILE)"

# --- 3. candidate ORDER: first readable non-empty file wins -------------------
out="$(run_norm "PM_CA_BUNDLE__TEST_CANDIDATES=$FIXTURE/nope.crt
$EMPTYFILE
$BUNDLE
$OTHER" SSL_CERT_FILE=)"
[ "$(get "$out" SSL_CERT_FILE)" = "$BUNDLE" ] && ok "skips missing + zero-byte candidates, takes first real one" || bad "SSL_CERT_FILE=$(get "$out" SSL_CERT_FILE)"

# --- 4. configured SSL_CERT_FILE (later env file) is never touched ------------
out="$(run_norm "PM_CA_BUNDLE__TEST_CANDIDATES=$BUNDLE" "SSL_CERT_FILE=$OTHER" "REQUESTS_CA_BUNDLE=$OTHER" SSL_CERT_DIR=)"
[ "$(get "$out" SSL_CERT_FILE)" = "$OTHER" ] && ok "configured SSL_CERT_FILE kept" || bad "SSL_CERT_FILE overridden: $(get "$out" SSL_CERT_FILE)"
[ "$(get "$out" REQUESTS_CA_BUNDLE)" = "$OTHER" ] && ok "configured REQUESTS_CA_BUNDLE kept" || bad "REQUESTS_CA_BUNDLE overridden"
[ "$(get "$out" SSL_CERT_DIR)" = "<UNSET>" ] && ok "empty SSL_CERT_DIR still cleared beside a configured SSL_CERT_FILE" || bad "SSL_CERT_DIR=$(get "$out" SSL_CERT_DIR)"

# --- 5. P2: configured REQUESTS_CA_BUNDLE alone -> NOTHING filled in ----------
out="$(run_norm "PM_CA_BUNDLE__TEST_CANDIDATES=$BUNDLE" SSL_CERT_FILE= "REQUESTS_CA_BUNDLE=$OTHER")"
[ "$(get "$out" SSL_CERT_FILE)" = "<UNSET>" ] && ok "REQUESTS_CA_BUNDLE configured -> SSL_CERT_FILE not filled (cleared to UNSET)" || bad "SSL_CERT_FILE=$(get "$out" SSL_CERT_FILE)"
[ "$(get "$out" REQUESTS_CA_BUNDLE)" = "$OTHER" ] && ok "configured REQUESTS_CA_BUNDLE kept" || bad "REQUESTS_CA_BUNDLE overridden: $(get "$out" REQUESTS_CA_BUNDLE)"

# --- 6. P2: configured SSL_CERT_DIR alone -> SSL_CERT_FILE stays UNSET --------
out="$(run_norm "PM_CA_BUNDLE__TEST_CANDIDATES=$BUNDLE" SSL_CERT_FILE= "SSL_CERT_DIR=$CADIR" REQUESTS_CA_BUNDLE= CURL_CA_BUNDLE=)"
[ "$(get "$out" SSL_CERT_FILE)" = "<UNSET>" ] && ok "SSL_CERT_DIR configured -> SSL_CERT_FILE left UNSET (would shadow the DIR)" || bad "SSL_CERT_FILE=$(get "$out" SSL_CERT_FILE)"
[ "$(get "$out" REQUESTS_CA_BUNDLE)" = "<UNSET>" ] && ok "SSL_CERT_DIR configured -> REQUESTS_CA_BUNDLE not filled" || bad "REQUESTS_CA_BUNDLE=$(get "$out" REQUESTS_CA_BUNDLE)"
[ "$(get "$out" SSL_CERT_DIR)" = "$CADIR" ] && ok "configured SSL_CERT_DIR kept" || bad "SSL_CERT_DIR=$(get "$out" SSL_CERT_DIR)"

# --- 7. P2: configured CURL_CA_BUNDLE alone -> REQUESTS_CA_BUNDLE not set -----
out="$(run_norm "PM_CA_BUNDLE__TEST_CANDIDATES=$BUNDLE" SSL_CERT_FILE= SSL_CERT_DIR= REQUESTS_CA_BUNDLE= "CURL_CA_BUNDLE=$OTHER")"
[ "$(get "$out" REQUESTS_CA_BUNDLE)" = "<UNSET>" ] && ok "CURL_CA_BUNDLE configured -> REQUESTS_CA_BUNDLE left UNSET (would shadow it)" || bad "REQUESTS_CA_BUNDLE=$(get "$out" REQUESTS_CA_BUNDLE)"
[ "$(get "$out" SSL_CERT_FILE)" = "<UNSET>" ] && ok "CURL_CA_BUNDLE configured -> SSL_CERT_FILE not filled" || bad "SSL_CERT_FILE=$(get "$out" SSL_CERT_FILE)"
[ "$(get "$out" CURL_CA_BUNDLE)" = "$OTHER" ] && ok "configured CURL_CA_BUNDLE kept" || bad "CURL_CA_BUNDLE=$(get "$out" CURL_CA_BUNDLE)"

# --- 8. P2 effective-value probes: what httpx and requests ACTUALLY use -------
# Records ssl.SSLContext.load_verify_locations (never actually loads, so stub
# paths are fine) and asks requests for its merged verify setting.
PROBE='
import ssl
calls = []
def rec(self, cafile=None, capath=None, cadata=None):
    calls.append((cafile, capath))
ssl.SSLContext.load_verify_locations = rec
import httpx, requests
httpx.Client(trust_env=True).close()
print("HTTPX_CAFILE=%s" % (calls[-1][0] if calls else None))
print("HTTPX_CAPATH=%s" % (calls[-1][1] if calls else None))
v = requests.Session().merge_environment_settings("https://example.invalid/", {}, None, None, None)["verify"]
print("REQUESTS_VERIFY=%s" % v)
'
PY="${PM_CA_BUNDLE_TEST_PY:-python3}"
if "$PY" -c 'import httpx, requests' >/dev/null 2>&1; then
  pv="$("$PY" -c 'import httpx,requests;print(httpx.__version__, requests.__version__)')"
  run_probe() { FRAGMENT="$FRAGMENT" PY="$PY" PROBE="$PROBE" bash -c "$_norm_setup"'exec "$PY" -c "$PROBE"' _ "$@" 2>"$FIXTURE/stderr"; }
  out="$(run_probe "PM_CA_BUNDLE__TEST_CANDIDATES=$BUNDLE" SSL_CERT_FILE= "SSL_CERT_DIR=$CADIR" REQUESTS_CA_BUNDLE= CURL_CA_BUNDLE=)"
  [ "$(get "$out" HTTPX_CAPATH)" = "$CADIR" ] && [ "$(get "$out" HTTPX_CAFILE)" = "None" ] \
    && ok "httpx (httpx/requests $pv) effective CA = configured SSL_CERT_DIR" || bad "httpx used cafile=$(get "$out" HTTPX_CAFILE) capath=$(get "$out" HTTPX_CAPATH)"
  out="$(run_probe "PM_CA_BUNDLE__TEST_CANDIDATES=$BUNDLE" SSL_CERT_FILE= SSL_CERT_DIR= REQUESTS_CA_BUNDLE= "CURL_CA_BUNDLE=$OTHER")"
  [ "$(get "$out" REQUESTS_VERIFY)" = "$OTHER" ] \
    && ok "requests (httpx/requests $pv) effective CA = configured CURL_CA_BUNDLE" || bad "requests verify=$(get "$out" REQUESTS_VERIFY)"
  out="$(run_probe "PM_CA_BUNDLE__TEST_CANDIDATES=$BUNDLE" SSL_CERT_FILE= SSL_CERT_DIR= REQUESTS_CA_BUNDLE= CURL_CA_BUNDLE=)"
  [ "$(get "$out" HTTPX_CAFILE)" = "$BUNDLE" ] && [ "$(get "$out" REQUESTS_VERIFY)" = "$BUNDLE" ] \
    && ok "no CA configured: httpx + requests both use the resolved bundle" || bad "httpx cafile=$(get "$out" HTTPX_CAFILE) requests=$(get "$out" REQUESTS_VERIFY)"
else
  skp "httpx/requests effective-CA probes: '$PY' lacks httpx+requests (set PM_CA_BUNDLE_TEST_PY)"
fi

# --- 9. configured value pointing nowhere: kept, but WARNed -------------------
out="$(run_norm "PM_CA_BUNDLE__TEST_CANDIDATES=$BUNDLE" "SSL_CERT_FILE=$FIXTURE/missing.pem")"
[ "$(get "$out" SSL_CERT_FILE)" = "$FIXTURE/missing.pem" ] && ok "unreadable configured value kept (not silently replaced)" || bad "replaced: $(get "$out" SSL_CERT_FILE)"
grep -q 'WARN: SSL_CERT_FILE=.*not a readable file' "$FIXTURE/stderr" && ok "unreadable configured value WARNs" || bad "no WARN for unreadable configured value"

# --- 10. NO bundle anywhere: fail OPEN, loudly --------------------------------
out="$(run_norm "PM_CA_BUNDLE__TEST_CANDIDATES=$FIXTURE/a.crt
$FIXTURE/b.crt" SSL_CERT_FILE= SSL_CERT_DIR=)"
[ "$(get "$out" rc)" = "0" ] && ok "returns 0 when no bundle found (fail open)" || bad "rc=$(get "$out" rc) — must not abort a launcher"
[ "$(get "$out" SSL_CERT_FILE)" = "<UNSET>" ] && ok "SSL_CERT_FILE left UNSET, not empty, when no bundle" || bad "SSL_CERT_FILE=$(get "$out" SSL_CERT_FILE)"
grep -q "WARN: no CA bundle found (tried: $FIXTURE/a.crt, $FIXTURE/b.crt)" "$FIXTURE/stderr" && ok "WARN names every path tried" || bad "WARN missing/incomplete: $(cat "$FIXTURE/stderr")"
get "$out" LINE | grep -q "NOT FOUND" && ok "PM_CA_BUNDLE_LINE says NOT FOUND" || bad "LINE=$(get "$out" LINE)"

# --- 11. already-sound env: silent no-op --------------------------------------
out="$(run_norm "PM_CA_BUNDLE__TEST_CANDIDATES=$BUNDLE" "SSL_CERT_FILE=$OTHER")"
[ -z "$(get "$out" LINE)" ] && ok "no line when nothing changed" || bad "LINE=$(get "$out" LINE)"
[ ! -s "$FIXTURE/stderr" ] && ok "no stderr when nothing changed" || bad "stderr: $(cat "$FIXTURE/stderr")"

# --- 12. READONLY empties: skipped, not reported cleared, bare call survives --
out="$(run_norm "PM_CA_BUNDLE__TEST_CANDIDATES=$BUNDLE" RO:SSL_CERT_FILE= SSL_CERT_DIR=)"
[ "$(get "$out" ALIVE)" = "1" ] && [ "$(get "$out" rc)" = "0" ] && ok "readonly empty SSL_CERT_FILE: bare call under set -euo pipefail returns 0 and caller survives" || bad "caller aborted (out: $(printf '%s' "$out" | tr '\n' ' ') stderr: $(cat "$FIXTURE/stderr"))"
[ "$(get "$out" SSL_CERT_FILE)" = "" ] && ok "readonly SSL_CERT_FILE left as-is (not exported over)" || bad "SSL_CERT_FILE=$(get "$out" SSL_CERT_FILE)"
cleared_seg="$(get "$out" LINE | sed -n 's/.*cleared empty \([^;]*\).*/\1/p')"
[ "$cleared_seg" = "SSL_CERT_DIR" ] \
  && ok "readonly var NOT reported as cleared (writable one is)" || bad "LINE=$(get "$out" LINE)"
grep -q 'WARN: readonly empty SSL_CERT_FILE' "$FIXTURE/stderr" && ok "readonly empty var WARNs" || bad "no readonly WARN: $(cat "$FIXTURE/stderr")"
out="$(run_norm "PM_CA_BUNDLE__TEST_CANDIDATES=$BUNDLE" SSL_CERT_FILE= RO:REQUESTS_CA_BUNDLE=)"
[ "$(get "$out" ALIVE)" = "1" ] && [ "$(get "$out" SSL_CERT_FILE)" = "$BUNDLE" ] && [ "$(get "$out" REQUESTS_CA_BUNDLE)" = "" ] \
  && ok "readonly empty REQUESTS_CA_BUNDLE: SSL_CERT_FILE still repaired, readonly var not written" || bad "out: $(printf '%s' "$out" | tr '\n' ' ') stderr: $(cat "$FIXTURE/stderr")"

# --- 13. test seam: set-but-EMPTY does not disable the built-in list ----------
builtin="$(env -u PM_CA_BUNDLE__TEST_CANDIDATES bash -c '. "$1"; pm_ca_bundle_candidates' _ "$FRAGMENT")"
seam_empty="$(env PM_CA_BUNDLE__TEST_CANDIDATES='' bash -c '. "$1"; pm_ca_bundle_candidates' _ "$FRAGMENT")"
[ -n "$builtin" ] && [ "$seam_empty" = "$builtin" ] && ok "empty PM_CA_BUNDLE__TEST_CANDIDATES falls back to the built-in list" || bad "empty seam changed candidates: '$seam_empty'"
printf '%s\n' "$builtin" | grep -qx /etc/ssl/certs/ca-certificates.crt && printf '%s\n' "$builtin" | grep -qx /etc/pki/tls/certs/ca-bundle.crt \
  && ok "built-in list carries Debian + RHEL bundles" || bad "built-in list: $builtin"

# --- 14. every env.shared loader calls normalize, UNCOMMENTED, AFTER loading --
# A fragment that exists but is never called is the failure this fleet
# repeats. Assert a live (non-comment) call line, and that it comes after the
# LAST line that loads the env file, so the empties exist when it runs.
# format: <file>|<ERE matching the env-load line>
while IFS='|' read -r f loadre; do
  [ -z "$f" ] && continue
  path="$REPO/$f"
  call_ln="$(grep -nE '^[^#]*pm_ca_bundle_normalize' "$path" | grep -vE 'pm_ca_bundle_normalize\(\)' | tail -1 | cut -d: -f1)"
  load_ln="$(grep -nE "$loadre" "$path" | tail -1 | cut -d: -f1)"
  if [ -z "$call_ln" ]; then
    bad "NOT wired (no live call): $f"
  elif [ -z "$load_ln" ]; then
    bad "loader pattern not found in $f (test out of date?): $loadre"
  elif [ "$call_ln" -gt "$load_ln" ]; then
    ok "wired after the env loader: $f (load:$load_ln < call:$call_ln)"
  else
    bad "call at $call_ln precedes env load at $load_ln: $f"
  fi
done <<'EOF'
deploy/provision/claude-pmoves.sh|set \+a; set -u
deploy/provision/codex-pmoves.sh|set \+a; set -u
deploy/provision/crush-pmoves.sh|set \+a; set -u
deploy/provision/hermes-pmoves.sh|set \+a; set -u
deploy/provision/kilo-pmoves.sh|set \+a; set -u
deploy/provision/kimi-pmoves.sh|set \+a; set -u
deploy/provision/pmoves-mini.sh|set \+a; set -u
pmoves/scripts/with-env.sh|^load_env_file "
pmoves/scripts/integration-auth-setup.sh|^ *set \+a
scripts/security/post-merge-verify.sh|set -a && source "\$_envf"
EOF
# The Makefile target is a one-liner: order within the recipe line.
mk="$(grep -E 'scripts/open_notebook_seed.py' "$REPO/pmoves/Makefile" | grep -E 'ENV_SHARED_FILE' | head -1)"
case "$mk" in
  *'set +a;'*'pm_ca_bundle_normalize;'*'open_notebook_seed.py'*) ok "wired after the env loader: pmoves/Makefile notebook-seed-models" ;;
  *) bad "pmoves/Makefile notebook-seed-models not wired in order: $mk" ;;
esac
# The generated launchers must come FROM the generator, not a hand edit.
grep -q 'pm_ca_bundle_normalize' "$REPO/pmoves/tools/pmoves_launcher_generator.py" \
  && ok "launcher generator template emits the call" || bad "generator template lacks the call (regen would drop it)"

# --- 15. with-env.sh end-to-end: empty guard in an env file -> bundle ---------
mkdir -p "$FIXTURE/pm/scripts"
cp "$REPO/pmoves/scripts/with-env.sh" "$REPO/pmoves/scripts/pm-ca-bundle.sh" "$FIXTURE/pm/scripts/"
printf 'SSL_CERT_FILE=\nSSL_CERT_DIR=\nREQUESTS_CA_BUNDLE=\nPM_PROBE=1\n' > "$FIXTURE/pm/env.shared"
res="$(env -i PATH="$PATH" HOME="$FIXTURE" PM_CA_BUNDLE__TEST_NO_CERTIFI=1 "PM_CA_BUNDLE__TEST_CANDIDATES=$BUNDLE" \
  bash "$FIXTURE/pm/scripts/with-env.sh" bash -c 'printf "%s|%s|%s|%s" "${PM_PROBE:-}" "${SSL_CERT_FILE-<UNSET>}" "${SSL_CERT_DIR-<UNSET>}" "${REQUESTS_CA_BUNDLE-<UNSET>}"' 2>"$FIXTURE/stderr")"
[ "$res" = "1|$BUNDLE|<UNSET>|$BUNDLE" ] && ok "with-env.sh: env file loaded AND CA vars normalized" || bad "with-env.sh got '$res' (stderr: $(head -c 300 "$FIXTURE/stderr"))"

echo
echo "pm-ca-bundle: $pass passed, $fail failed, $skip skipped"
[ "$fail" -eq 0 ]
