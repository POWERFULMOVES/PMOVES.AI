#!/usr/bin/env bash
# pm-ca-bundle.sh — keep HOST TLS working after env.shared is loaded.
# ===========================================================================
# WHY THIS EXISTS
# ---------------
# pmoves/bootstrap/registry.json writes these keys into env.shared with an
# EMPTY value, on purpose, as a container leak guard (a Windows host path in
# SSL_CERT_FILE must never reach a Linux container):
#
#     SSL_CERT_FILE=  SSL_CERT_DIR=  REQUESTS_CA_BUNDLE=  CURL_CA_BUNDLE=
#     NODE_EXTRA_CA_CERTS=
#
# That is correct inside a container. On the HOST it is a defect: every
# launcher (deploy/provision/*-pmoves.sh) and pmoves/scripts/with-env.sh
# source env.shared with `set -a`, which EXPORTS the empty values into the
# agent session and every child it spawns. "Set to empty" is not "unset":
#
#   * OpenSSL (every CPython `ssl`, urllib, httpx) reads getenv(SSL_CERT_FILE)
#     and, when it is non-NULL, loads THAT file — "" — instead of the compiled
#     default. Result: `CERTIFICATE_VERIFY_FAILED unable to get local issuer
#     certificate`. Which of the two empty vars bites depends on the build
#     (measured on Knuckles 2026-09-28: system python3 needs either unset; the
#     uv-managed cpython needs SSL_CERT_DIR unset; miniforge needs
#     SSL_CERT_FILE unset).
#   * huggingface_hub's Xet backend (Rust reqwest) fails with
#     `Reqwest error: builder error` on SSL_CERT_FILE="" alone.
#   * curl, git, pip and uv's default rustls roots ignore the empty values,
#     which is why the failure looked python-only and intermittent.
#
# THE CONTRACT
# ------------
# pm_ca_bundle_normalize
#
#   1. Unsets each of the five vars above that is SET BUT EMPTY. A non-empty
#      value is an operator choice and is never touched.
#   2. If SSL_CERT_FILE is then unset, resolves the system CA bundle for this
#      OS and exports it as SSL_CERT_FILE, and as REQUESTS_CA_BUNDLE only if
#      that is unset too. (Setting it — not merely unsetting — is what repairs
#      interpreters whose compiled default path is wrong, e.g. Git Bash.)
#   3. Fails OPEN, loudly: if no bundle is found it prints a WARN to stderr
#      naming every path it tried, and returns 0. It never aborts a launcher.
#
# Sets PM_CA_BUNDLE_LINE to a one-line description of what it did ("" when
# the environment was already sound and nothing changed). Launchers print it;
# with-env.sh stays quiet because it runs under every make target.
#
# Deliberately NOT done: UV_NATIVE_TLS. uv's default bundled roots work here,
# and UV_NATIVE_TLS=1 under the empty-var condition fails with "No CA
# certificates were loaded from the system" — it makes things worse.
#
# Test seams (tests only): PM_CA_BUNDLE_CANDIDATES (newline-separated list
# replacing the built-in candidates) and PM_CA_BUNDLE_NO_CERTIFI=1.
# Tests: deploy/provision/tests/test-pm-ca-bundle.sh
#
# Safe under `set -euo pipefail` in the caller: every probe is guarded.

pm_ca_bundle_candidates() {
  if [ -n "${PM_CA_BUNDLE_CANDIDATES+x}" ]; then
    printf '%s\n' "$PM_CA_BUNDLE_CANDIDATES"
    return 0
  fi
  # Debian/Ubuntu, RHEL/Fedora (two layouts), openSUSE, Alpine/macOS/BSD,
  # Git Bash on Windows (MSYS root, then the mingw64 copy).
  printf '%s\n' \
    /etc/ssl/certs/ca-certificates.crt \
    /etc/pki/tls/certs/ca-bundle.crt \
    /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem \
    /etc/ssl/ca-bundle.pem \
    /etc/ssl/cert.pem \
    /usr/ssl/certs/ca-bundle.crt \
    /mingw64/ssl/certs/ca-bundle.crt
}

pm_ca_bundle_normalize() {
  PM_CA_BUNDLE_LINE=""
  local _v _cleared="" _bundle="" _tried="" _c _py _native
  for _v in SSL_CERT_FILE SSL_CERT_DIR REQUESTS_CA_BUNDLE CURL_CA_BUNDLE NODE_EXTRA_CA_CERTS; do
    if [ -n "${!_v+x}" ] && [ -z "${!_v}" ]; then
      unset "$_v"
      _cleared="${_cleared:+$_cleared }$_v"
    fi
  done

  if [ -n "${SSL_CERT_FILE:-}" ]; then
    # Operator-set: keep it. Warn if it cannot work, but do not "fix" it.
    if [ ! -r "$SSL_CERT_FILE" ]; then
      echo "[pm-ca-bundle] WARN: SSL_CERT_FILE=$SSL_CERT_FILE is not a readable file; kept as set (operator value)." >&2
    fi
    if [ -n "$_cleared" ]; then
      PM_CA_BUNDLE_LINE="ca-bundle: cleared empty $_cleared; kept operator SSL_CERT_FILE"
    fi
    return 0
  fi

  while IFS= read -r _c; do
    [ -z "$_c" ] && continue
    _tried="${_tried:+$_tried, }$_c"
    if [ -f "$_c" ] && [ -r "$_c" ] && [ -s "$_c" ]; then
      _bundle="$_c"
      break
    fi
  done < <(pm_ca_bundle_candidates)

  if [ -z "$_bundle" ] && [ "${PM_CA_BUNDLE_NO_CERTIFI:-0}" != "1" ]; then
    for _py in python3 python; do
      command -v "$_py" >/dev/null 2>&1 || continue
      _c="$("$_py" -c 'import certifi; print(certifi.where())' 2>/dev/null || true)"
      _tried="${_tried:+$_tried, }$_py -m certifi"
      if [ -n "$_c" ] && [ -r "$_c" ]; then
        _bundle="$_c"
        break
      fi
    done
  fi

  if [ -z "$_bundle" ]; then
    echo "[pm-ca-bundle] WARN: no CA bundle found (tried: ${_tried:-nothing}); SSL_CERT_FILE left unset — python TLS falls back to its compiled default." >&2
    PM_CA_BUNDLE_LINE="ca-bundle: NOT FOUND${_cleared:+; cleared empty $_cleared}"
    return 0
  fi

  # Git Bash: native Windows programs cannot open an MSYS path.
  _native="$_bundle"
  if command -v cygpath >/dev/null 2>&1; then
    _native="$(cygpath -m "$_bundle" 2>/dev/null || printf '%s' "$_bundle")"
  fi

  export SSL_CERT_FILE="$_native"
  if [ -z "${REQUESTS_CA_BUNDLE+x}" ]; then
    export REQUESTS_CA_BUNDLE="$_native"
  fi
  PM_CA_BUNDLE_LINE="ca-bundle: SSL_CERT_FILE=$_native${_cleared:+ (cleared empty $_cleared)}"
  return 0
}
