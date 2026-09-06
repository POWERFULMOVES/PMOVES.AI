#!/usr/bin/env bash
# E2B deployment-mode resolution and credential SHAPE validation.
#
# Source this from any script that talks to an E2B control plane:
#   . "$PMOVES_DIR/scripts/e2b_mode.sh"
#   e2b_resolve_mode || exit 3      # sets E2B_MODE_RESOLVED + reason
#   e2b_validate_shapes || exit 3   # prefix + length + charset per mode
#
# ── Why this file exists ─────────────────────────────────────────────────────
# There are THREE E2B deployment modes with three DIFFERENT credential sets.
# Generalising from a single vendor page produced two wrong wirings in a row
# (notably: E2B_DOMAIN is the GCP self-host variable and is NOT used by the
# local self-host stack). The vendor sources are:
#   PMOVES-Danger-infra/self-host.md   -> self-host on GCP
#   PMOVES-Danger-infra/DEV-LOCAL.md   -> self-host local (bare metal)
#   https://e2b.dev/docs                -> e2b.dev cloud
#
#   mode            | required variables
#   ----------------|-------------------------------------------------------
#   cloud           | E2B_API_KEY                       (e2b_ + 40 hex)
#   selfhost-gcp    | E2B_ACCESS_TOKEN (sk_e2b_ + hex) + E2B_DOMAIN
#   selfhost-local  | E2B_API_KEY + E2B_ACCESS_TOKEN + E2B_API_URL
#                   |   + E2B_ENVD_API_URL         (NO E2B_DOMAIN)
#
# ── What the pinned client actually reads (measured, not assumed) ────────────
# e2b python SDK 2.6.4 (skills/PMOVES-agent-sandbox-skill/.../sandbox_cli),
# e2b/connection_config.py reads exactly five variables:
#   E2B_DOMAIN (default "e2b.app"), E2B_DEBUG, E2B_API_KEY, E2B_API_URL,
#   E2B_ACCESS_TOKEN.
# Two consequences the vendor dotenv block does not spell out:
#   * E2B_DEBUG=true is REQUIRED for the local stack. e2b/sandbox/main.py:198
#     returns `localhost:{port}` only when debug is set, and line 49 picks
#     http:// vs https:// off the same flag. Without it the SDK builds
#     `https://49983-<id>.e2b.app` and never reaches your local cluster.
#   * E2B_ENVD_API_URL has NO consumer at our pins. Grep counts (positive
#     control alongside): in PMOVES-E2B-Danger-Room (the SDK monorepo)
#     E2B_API_KEY matches 24 files, E2B_DOMAIN 17, E2B_ACCESS_TOKEN 10,
#     E2B_ENVD_API_URL 0. In PMOVES-Danger-infra it matches exactly one file:
#     DEV-LOCAL.md itself. The SDK derives the envd URL from debug + host
#     instead (main.py:49), so it targets localhost:49983 — NOT the
#     client-proxy port 3002 the doc names. We therefore validate the variable
#     when present but do not fail on it, and the runbook carries the
#     reachability caveat.
#
# ── Why SHAPE and not presence ───────────────────────────────────────────────
# `[ -n "$VAR" ]` passes a TRUNCATED secret. That is exactly how a two-character
# truncation in secrets delivery went unnoticed here: the key was "present" at
# every gate and only the provider rejected it, deep inside a provisioning call.
# Prefix + length + charset are checked per mode, and the expected length is
# mode-specific (the local seeded key is 32 hex; cloud is 40).
#
# ── Secret hygiene ───────────────────────────────────────────────────────────
# NOTHING in this file prints a credential value. Names, lengths, prefixes and
# verdicts only. `set +x` guards are deliberate: with `bash -x`, xtrace expands
# `[ -n "$E2B_API_KEY" ]` and would print the secret into the transcript. That
# has already happened once on this fleet.
set +x

# Canonical shapes. Keep in one place so the three modes cannot drift.
E2B_API_KEY_PREFIX="e2b_"
E2B_ACCESS_TOKEN_PREFIX="sk_e2b_"
E2B_API_KEY_HEX_CLOUD=40          # e2b.dev cloud keys
E2B_API_KEY_HEX_LOCAL=32          # DEV-LOCAL.md seeded key
E2B_ACCESS_TOKEN_HEX=32           # sk_e2b_ + 32 hex (both self-host modes)

E2B_MODE_RESOLVED=""
E2B_MODE_REASON=""
E2B_SHAPE_ERRORS=0

_e2b_log() { echo "[e2b-mode] $*"; }

# e2b_known_modes -> prints the selectable mode names
e2b_known_modes() { echo "cloud selfhost-gcp selfhost-local"; }

# _e2b_is_hex <string> <expected_len>
_e2b_is_hex() {
  set +x
  local s="$1" n="$2"
  [ "${#s}" -eq "$n" ] || return 1
  case "$s" in
    *[!0-9a-fA-F]*) return 1 ;;
    *) return 0 ;;
  esac
}

# _e2b_shape_report <var_name> <prefix> <expected_hex_len...>
# Reports on the VALUE of the named variable without ever printing it.
# Returns 0 when the shape matches one of the accepted hex lengths.
_e2b_shape_report() {
  set +x
  local name="$1" prefix="$2"; shift 2
  local val="${!name:-}"
  if [ -z "$val" ]; then
    _e2b_log "$name: UNSET (required for mode $E2B_MODE_RESOLVED)"
    E2B_SHAPE_ERRORS=$((E2B_SHAPE_ERRORS + 1))
    return 1
  fi
  local total="${#val}"
  case "$val" in
    "$prefix"*) : ;;
    *)
      # Do not echo the value. Report the observed prefix length only.
      _e2b_log "$name: MALFORMED — missing the '${prefix}' prefix (length ${total}). A truncated secret passes a [ -n ] test; it does not pass this one."
      E2B_SHAPE_ERRORS=$((E2B_SHAPE_ERRORS + 1))
      return 1 ;;
  esac
  local body="${val#"$prefix"}"
  local want
  for want in "$@"; do
    if _e2b_is_hex "$body" "$want"; then
      _e2b_log "$name: shape OK (${prefix} + ${want} hex, total length ${total})"
      return 0
    fi
  done
  _e2b_log "$name: MALFORMED — '${prefix}' prefix present but body is ${#body} chars (expected hex of length: $*). Total length ${total}."
  E2B_SHAPE_ERRORS=$((E2B_SHAPE_ERRORS + 1))
  return 1
}

# _e2b_require_url <var_name>
_e2b_require_url() {
  set +x
  local name="$1"
  # NOTE: the indirect expansion MUST be a separate statement. `local n="$1"
  # v="${!n:-}"` in one `local` is an "invalid indirect expansion" fatal error.
  local val="${!name:-}"
  if [ -z "$val" ]; then
    _e2b_log "$name: UNSET (required for mode $E2B_MODE_RESOLVED)"
    E2B_SHAPE_ERRORS=$((E2B_SHAPE_ERRORS + 1))
    return 1
  fi
  case "$val" in
    http://*|https://*) _e2b_log "$name: $val" ; return 0 ;;
    *) _e2b_log "$name: MALFORMED — expected an http(s):// URL"
       E2B_SHAPE_ERRORS=$((E2B_SHAPE_ERRORS + 1)); return 1 ;;
  esac
}

# _e2b_forbid <var_name> <why>
_e2b_forbid() {
  set +x
  local name="$1" why="$2"
  if [ -n "${!name:-}" ]; then
    _e2b_log "$name: SET but not used by mode $E2B_MODE_RESOLVED — $why"
  fi
}

# e2b_resolve_mode
#   Explicit: E2B_MODE=cloud|selfhost-gcp|selfhost-local
#   Default:  selfhost-local  (operator decision 2026-09-06: self-host approved)
#   E2B_MODE=auto infers from which variables are present.
e2b_resolve_mode() {
  set +x
  local requested="${E2B_MODE:-selfhost-local}"
  case "$requested" in
    cloud|selfhost-gcp|selfhost-local)
      E2B_MODE_RESOLVED="$requested"
      E2B_MODE_REASON="explicit (E2B_MODE=$requested)"
      [ -n "${E2B_MODE:-}" ] || E2B_MODE_REASON="default (self-host local; set E2B_MODE to override)"
      ;;
    auto)
      if [ -n "${E2B_API_URL:-}" ] || [ -n "${E2B_ENVD_API_URL:-}" ]; then
        E2B_MODE_RESOLVED="selfhost-local"; E2B_MODE_REASON="auto: E2B_API_URL/E2B_ENVD_API_URL present"
      elif [ -n "${E2B_DOMAIN:-}" ]; then
        E2B_MODE_RESOLVED="selfhost-gcp"; E2B_MODE_REASON="auto: E2B_DOMAIN present"
      elif [ -n "${E2B_API_KEY:-}" ]; then
        E2B_MODE_RESOLVED="cloud"; E2B_MODE_REASON="auto: only E2B_API_KEY present"
      else
        _e2b_log "cannot infer a mode — none of E2B_API_URL, E2B_DOMAIN, E2B_API_KEY are set"
        return 1
      fi
      ;;
    *)
      _e2b_log "unknown E2B_MODE='$requested' (want one of: $(e2b_known_modes) auto)"
      return 1 ;;
  esac
  _e2b_log "mode: $E2B_MODE_RESOLVED — $E2B_MODE_REASON"
  export E2B_MODE_RESOLVED
  return 0
}

# e2b_apply_mode_env — export the NON-SECRET knobs that the selected mode
# implies. Mode selection has to actually configure the client, not just judge
# it. Only E2B_DEBUG qualifies: it is a routing flag, not a credential, and the
# local stack is unreachable without it. Credentials are NEVER defaulted here —
# a missing secret must stay a delivery failure, not something a script papers
# over.
e2b_apply_mode_env() {
  set +x
  [ -n "$E2B_MODE_RESOLVED" ] || { _e2b_log "e2b_resolve_mode must run first"; return 1; }
  if [ "$E2B_MODE_RESOLVED" = "selfhost-local" ] && [ -z "${E2B_DEBUG:-}" ]; then
    export E2B_DEBUG=true
    _e2b_log "E2B_DEBUG: defaulted to true by mode selection (selfhost-local routing flag, not a secret)"
  fi
  return 0
}

# e2b_validate_shapes — per-mode required set + shape checks.
# Returns 0 clean, 1 when any variable is missing or malformed.
e2b_validate_shapes() {
  set +x
  E2B_SHAPE_ERRORS=0
  [ -n "$E2B_MODE_RESOLVED" ] || { _e2b_log "e2b_resolve_mode must run first"; return 1; }
  case "$E2B_MODE_RESOLVED" in
    cloud)
      _e2b_shape_report E2B_API_KEY "$E2B_API_KEY_PREFIX" "$E2B_API_KEY_HEX_CLOUD"
      _e2b_forbid E2B_API_URL "cloud talks to https://api.e2b.dev; unset it or switch to E2B_MODE=selfhost-local"
      _e2b_forbid E2B_DOMAIN "E2B_DOMAIN is the GCP self-host variable"
      ;;
    selfhost-gcp)
      # self-host.md: the cluster is addressed by domain; the CLI/SDK
      # authenticate with the access token (sk_e2b_).
      _e2b_shape_report E2B_ACCESS_TOKEN "$E2B_ACCESS_TOKEN_PREFIX" "$E2B_ACCESS_TOKEN_HEX"
      if [ -z "${E2B_DOMAIN:-}" ]; then
        _e2b_log "E2B_DOMAIN: UNSET (required for mode selfhost-gcp)"
        E2B_SHAPE_ERRORS=$((E2B_SHAPE_ERRORS + 1))
      else
        _e2b_log "E2B_DOMAIN: ${E2B_DOMAIN}"
      fi
      ;;
    selfhost-local)
      # DEV-LOCAL.md "Client configuration" block: four variables, NO E2B_DOMAIN.
      # Accept both hex widths for the API key: the seeded local key is 32 hex,
      # but an operator may mint a 40-hex key against a local API.
      _e2b_shape_report E2B_API_KEY "$E2B_API_KEY_PREFIX" "$E2B_API_KEY_HEX_LOCAL" "$E2B_API_KEY_HEX_CLOUD"
      _e2b_shape_report E2B_ACCESS_TOKEN "$E2B_ACCESS_TOKEN_PREFIX" "$E2B_ACCESS_TOKEN_HEX"
      _e2b_require_url E2B_API_URL
      # E2B_DEBUG is not in the vendor dotenv block but the pinned SDK cannot
      # reach a local cluster without it (see header). Fail on it.
      if [ "${E2B_DEBUG:-}" = "true" ]; then
        _e2b_log "E2B_DEBUG: true (required — SDK routes to localhost over http)"
      else
        _e2b_log "E2B_DEBUG: '${E2B_DEBUG:-<unset>}' — MUST be 'true' for selfhost-local. e2b/sandbox/main.py:198 only returns localhost:<port> when debug is set; otherwise the SDK builds https://<port>-<id>.e2b.app and never reaches your cluster."
        E2B_SHAPE_ERRORS=$((E2B_SHAPE_ERRORS + 1))
      fi
      # Advisory only: declared by DEV-LOCAL.md, zero consumers at our pins.
      if [ -n "${E2B_ENVD_API_URL:-}" ]; then
        _e2b_log "E2B_ENVD_API_URL: ${E2B_ENVD_API_URL} (declared by DEV-LOCAL.md; the pinned python SDK does not read it — it derives envd from E2B_DEBUG and targets localhost:49983)"
      else
        _e2b_log "E2B_ENVD_API_URL: unset (advisory — no consumer at our pins; set it for JS/CLI parity with DEV-LOCAL.md)"
      fi
      _e2b_forbid E2B_DOMAIN "DEV-LOCAL.md does not use E2B_DOMAIN for the local stack — it is the GCP self-host variable and setting it here can misroute the SDK"
      ;;
  esac
  if [ "$E2B_SHAPE_ERRORS" -gt 0 ]; then
    _e2b_log "shape validation FAILED ($E2B_SHAPE_ERRORS problem(s)) for mode $E2B_MODE_RESOLVED"
    return 1
  fi
  _e2b_log "shape validation OK for mode $E2B_MODE_RESOLVED"
  return 0
}
