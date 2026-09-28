#!/usr/bin/env bash
# shellcheck disable=SC2034  # PM_CA_BUNDLE_LINE is this fragment's OUTPUT, read by the caller
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
#     (measured 2026-09-28: system python3 is fixed by unsetting either; a
#     uv-managed cpython needs SSL_CERT_DIR unset; miniforge needs
#     SSL_CERT_FILE unset).
#   * huggingface_hub's Xet backend (Rust reqwest) fails with
#     `Reqwest error: builder error` on SSL_CERT_FILE="" alone.
#   * curl, git, pip and uv's default rustls roots ignore the empty values,
#     which is why the failure looked python-only and intermittent.
#
# WHOSE VALUES ARE "KEPT"
# -----------------------
# By the time this runs, the env.shared loader has already OVERWRITTEN any
# value for these keys that was exported in the invoking shell — env.shared
# carries all five keys, so a shell export is replaced by "". That is
# pre-existing loader behaviour and is NOT changed here. The non-empty values
# this function can see, and therefore keeps, are ones set by a LATER-loaded
# env file (a tier file or .env.local overlay in with-env.sh), or a non-empty
# value written into env.shared itself.
#
# THE CONTRACT
# ------------
# pm_ca_bundle_normalize
#
#   1. Unsets each of the five vars above that is SET BUT EMPTY. A readonly
#      var cannot be unset; it is skipped (named in the WARN), not reported as
#      cleared, and never makes the call fail.
#   2. If ANY of the five is then non-empty, a CA is configured some other way
#      and NOTHING is exported. This matters because the clients pick by
#      precedence, not by merging: httpx and OpenSSL prefer SSL_CERT_FILE over
#      SSL_CERT_DIR, and requests prefers REQUESTS_CA_BUNDLE over
#      CURL_CA_BUNDLE — so filling in the system bundle beside a configured
#      SSL_CERT_DIR or CURL_CA_BUNDLE would silently shadow it (e.g. a
#      corporate/MITM root).
#   3. Only when no CA variable of any kind is set: resolve the system CA
#      bundle for this OS and export it as SSL_CERT_FILE and
#      REQUESTS_CA_BUNDLE. (Setting it — not merely unsetting — is what
#      repairs interpreters whose compiled default path is wrong, e.g. Git
#      Bash.)
#   4. Fails OPEN, loudly: if no bundle is found it prints a WARN to stderr
#      naming every path it tried, leaves the vars UNSET (not empty), and
#      returns 0. It always returns 0, so a bare call is safe under
#      `set -euo pipefail`.
#
# Sets PM_CA_BUNDLE_LINE to a one-line description of what it did ("" when
# the environment was already sound and nothing changed). Launchers print it;
# with-env.sh stays quiet because it runs under every make target.
#
# Deliberately NOT done: UV_NATIVE_TLS. uv's default bundled roots work here,
# and UV_NATIVE_TLS=1 under the empty-var condition fails with "No CA
# certificates were loaded from the system" — it makes things worse.
#
# Bash-only (local, ${!name}, process substitution). Every caller is bash:
# the launchers and with-env.sh have bash shebangs or are run via `bash`.
#
# TEST SEAMS — for deploy/provision/tests/test-pm-ca-bundle.sh ONLY, not a
# supported configuration surface (configure a CA with the standard variables
# above instead):
#   PM_CA_BUNDLE__TEST_CANDIDATES  newline-separated list replacing the
#                                  built-in candidates; ignored when empty
#   PM_CA_BUNDLE__TEST_NO_CERTIFI  =1 disables the `python -m certifi` probe

pm_ca_bundle_candidates() {
  if [ -n "${PM_CA_BUNDLE__TEST_CANDIDATES:-}" ]; then
    printf '%s\n' "$PM_CA_BUNDLE__TEST_CANDIDATES"
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

# pm_ca_bundle_is_readonly <name> — 0 if the variable carries the r attribute.
pm_ca_bundle_is_readonly() {
  local _decl _flags
  _decl="$(declare -p "$1" 2>/dev/null)" || return 1
  _flags="${_decl#declare -}"
  _flags="${_flags%% *}"
  case "$_flags" in *r*) return 0 ;; esac
  return 1
}

pm_ca_bundle_normalize() {
  PM_CA_BUNDLE_LINE=""
  local _v _cleared="" _ro="" _configured="" _bundle="" _tried="" _c _py _native _note=""
  local _vars="SSL_CERT_FILE SSL_CERT_DIR REQUESTS_CA_BUNDLE CURL_CA_BUNDLE NODE_EXTRA_CA_CERTS"

  for _v in $_vars; do
    if [ -n "${!_v+x}" ] && [ -z "${!_v}" ]; then
      if pm_ca_bundle_is_readonly "$_v"; then
        _ro="${_ro:+$_ro }$_v"
        continue
      fi
      unset "$_v"
      _cleared="${_cleared:+$_cleared }$_v"
    fi
  done
  if [ -n "$_cleared" ]; then
    _note="${_note}; cleared empty $_cleared"
  fi
  if [ -n "$_ro" ]; then
    echo "[pm-ca-bundle] WARN: readonly empty $_ro cannot be cleared; left as-is (python TLS may still fail)." >&2
    _note="${_note}; readonly empty $_ro left as-is"
  fi

  for _v in $_vars; do
    if [ -n "${!_v:-}" ]; then
      _configured="${_configured:+$_configured }$_v"
    fi
  done

  if [ -n "$_configured" ]; then
    # A CA is configured by a later-loaded env file (tier file / .env.local)
    # or by env.shared itself. Keep it and add nothing beside it.
    if [ -n "${SSL_CERT_FILE:-}" ] && [ ! -r "$SSL_CERT_FILE" ]; then
      echo "[pm-ca-bundle] WARN: SSL_CERT_FILE=$SSL_CERT_FILE is not a readable file; kept as configured." >&2
    fi
    if [ -n "${SSL_CERT_DIR:-}" ] && [ ! -d "$SSL_CERT_DIR" ]; then
      echo "[pm-ca-bundle] WARN: SSL_CERT_DIR=$SSL_CERT_DIR is not a directory; kept as configured." >&2
    fi
    if [ -n "$_note" ]; then
      PM_CA_BUNDLE_LINE="ca-bundle: kept configured $_configured${_note}"
    fi
    return 0
  fi

  if [ -n "${SSL_CERT_FILE+x}" ]; then
    # Only reachable when SSL_CERT_FILE is readonly-empty: exporting it would
    # abort a `set -e` caller, so stop here (already WARNed above).
    PM_CA_BUNDLE_LINE="ca-bundle: NOT SET${_note}"
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

  if [ -z "$_bundle" ] && [ "${PM_CA_BUNDLE__TEST_NO_CERTIFI:-0}" != "1" ]; then
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
    PM_CA_BUNDLE_LINE="ca-bundle: NOT FOUND${_note}"
    return 0
  fi

  # Git Bash: native Windows programs cannot open an MSYS path.
  _native="$_bundle"
  if command -v cygpath >/dev/null 2>&1; then
    _native="$(cygpath -m "$_bundle" 2>/dev/null || printf '%s' "$_bundle")"
  fi

  export SSL_CERT_FILE="$_native"
  # REQUESTS_CA_BUNDLE is unset here unless it is readonly-empty; never write
  # a readonly var.
  if [ -z "${REQUESTS_CA_BUNDLE+x}" ]; then
    export REQUESTS_CA_BUNDLE="$_native"
  fi
  PM_CA_BUNDLE_LINE="ca-bundle: SSL_CERT_FILE=$_native${_note}"
  return 0
}
