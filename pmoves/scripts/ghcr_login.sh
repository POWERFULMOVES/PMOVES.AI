#!/usr/bin/env bash
# ghcr_login.sh — log this node's Docker daemon in to ghcr.io (backs `make docker-login`).
#
# Two token sources, checked in this order:
#
#   1. GHCR_READ_TOKEN_FILE (read-only node pulls). Wins whenever it is set:
#      it is read BEFORE with-env.sh is sourced, so neither exported
#      GHCR_TOKEN/GH_PAT_PUBLISH nor an env file can displace it. The file
#      must be mode 0600 and hold a classic PAT (ghp_ + 36), because GitHub
#      Packages only accepts classic PATs (GitHub docs,
#      data/reusables/package_registry/packages-classic-pat-only.md); a
#      fine-grained PAT or App installation token is not a documented GHCR
#      credential. The username is GHCR_READ_USERNAME and must be the PAT owner.
#   2. The legacy publish chain: GHCR_TOKEN > GH_PAT_PUBLISH > GITHUB_TOKEN >
#      `gh auth token` > GHCR_TOKEN_FILE, after loading env files.
#
# The token reaches docker on stdin only (--password-stdin), never on argv,
# and is never printed. DRY_RUN=1 validates everything and prints only the
# user, the registry and the token SOURCE name.
#
# Without a docker credential helper (pass / secretservice), docker stores the
# login base64-encoded in ~/.docker/config.json (Docker docs, docker login
# "Credential stores").
set -uo pipefail

REGISTRY="ghcr.io"
read_file="${GHCR_READ_TOKEN_FILE:-}"
read_user="${GHCR_READ_USERNAME:-}"
dry_run="${DRY_RUN:-}"

die() { echo "✖ $*" >&2; exit 1; }

file_mode() {
  stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null
}

if [ -n "$read_file" ]; then
  read_file="${read_file/#\~/$HOME}"
  source_name="GHCR_READ_TOKEN_FILE"
  [ -f "$read_file" ] || die "GHCR_READ_TOKEN_FILE is not a regular file: $read_file"
  mode="$(file_mode "$read_file")"
  [ "$mode" = "600" ] || die "GHCR_READ_TOKEN_FILE must be mode 0600 (is ${mode:-unknown}): chmod 600 $read_file"
  [ -n "$read_user" ] || die "GHCR_USERNAME (the PAT owner's GitHub login) is required with GHCR_READ_TOKEN_FILE"
  user="$read_user"
  token="$(tr -d '\r\n' < "$read_file")"
  [[ "$token" =~ ^ghp_[A-Za-z0-9]{36}$ ]] \
    || die "GHCR_READ_TOKEN_FILE does not hold a classic PAT (ghp_ + 36 alphanumerics); GitHub Packages accepts only classic PATs"
else
  cd "$(dirname "$0")/.." || die "cannot cd to pmoves/"
  . ./scripts/with-env.sh
  set +e  # with-env.sh turns errexit on in the caller
  user="${GHCR_USERNAME:-${GITHUB_ACTOR:-$(gh api user -q .login 2>/dev/null || true)}}"
  source_name=""
  token=""
  for k in GHCR_TOKEN GH_PAT_PUBLISH GITHUB_TOKEN; do
    if [ -n "${!k:-}" ]; then token="${!k}"; source_name="$k"; break; fi
  done
  if [ -z "$token" ]; then
    token="$(gh auth token 2>/dev/null || true)"
    [ -n "$token" ] && source_name="gh auth token"
  fi
  if [ -z "$token" ] && [ -n "${GHCR_TOKEN_FILE:-}" ] && [ -f "${GHCR_TOKEN_FILE}" ]; then
    token="$(cat "${GHCR_TOKEN_FILE}")"; source_name="GHCR_TOKEN_FILE"
  fi
  if [ -z "$user" ] || [ -z "$token" ]; then
    die "Missing GHCR credentials. Set GHCR_USERNAME and GHCR_TOKEN (or GH_PAT_PUBLISH), or GHCR_READ_TOKEN_FILE for read-only pulls."
  fi
fi

if [ -n "$dry_run" ] && [ "$dry_run" != "0" ]; then
  echo "dry-run: docker login $REGISTRY as $user (token source: $source_name)"
  exit 0
fi

printf "%s" "$token" | docker login "$REGISTRY" -u "$user" --password-stdin >/dev/null \
  && echo "✔ GHCR login ok as $user (token source: $source_name)"
