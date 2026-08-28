#!/usr/bin/env bash
# Runtime gate for published container images.
#
# WHY THIS EXISTS: integrations-ghcr.yml published ghcr.io/powerfulmoves/pmoves-yt
# green for five months while the artifact could not start at all -- its entrypoint
# raised IndexError at import. A build that succeeds is not evidence that an image
# runs, and nothing in the matrix ever started a container. This script is that
# missing step. See pmoves/docs/services/pmoves-yt/RUNBOOK.md section 1.3.
#
# It is a standalone script, not inline workflow YAML, so that the exact code CI
# runs can also be run locally against a locally-built image -- including as a
# NEGATIVE CONTROL to prove the gate can fail.
#
# Usage:
#   VERIFY_PORT=8077 VERIFY_HEALTH_PATH=/healthz \
#     .github/scripts/verify-image-starts.sh ghcr.io/owner/img@sha256:...
#
# Env:
#   VERIFY_PORT              (required) container port the service listens on
#   VERIFY_HEALTH_PATH       (required) HTTP path expected to answer 200
#   VERIFY_TIMEOUT_SECONDS   (default 120) how long to wait for the first 200
#   VERIFY_PULL              (default 1) set 0 to verify an image already local
#   VERIFY_EXPECT_STATUS     (default 200) expected HTTP status
#
# Exit codes:
#   0  container started and the health path answered as expected
#   1  container exited, never became healthy, or bad arguments
set -euo pipefail

IMAGE_REF="${1:-}"
if [ -z "${IMAGE_REF}" ]; then
  echo "usage: $0 <image-ref>" >&2
  exit 1
fi
if [ -z "${VERIFY_PORT:-}" ] || [ -z "${VERIFY_HEALTH_PATH:-}" ]; then
  echo "VERIFY_PORT and VERIFY_HEALTH_PATH are required" >&2
  exit 1
fi

timeout_s="${VERIFY_TIMEOUT_SECONDS:-120}"
expect="${VERIFY_EXPECT_STATUS:-200}"
cid=""

cleanup() {
  if [ -n "${cid}" ]; then
    echo "--- container logs (last 100 lines) ---"
    docker logs "${cid}" 2>&1 | tail -n 100 || true
    docker rm -f "${cid}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "Runtime gate: ${IMAGE_REF}"
echo "  port=${VERIFY_PORT} path=${VERIFY_HEALTH_PATH} expect=${expect} timeout=${timeout_s}s"

if [ "${VERIFY_PULL:-1}" = "1" ]; then
  # Pull by the ref we were handed. Callers should hand us a DIGEST ref so that
  # what is verified is the exact manifest just pushed, not a mutable tag that a
  # concurrent run could have moved.
  docker pull "${IMAGE_REF}"
fi

# Publish to an ephemeral loopback port: a self-hosted runner may already have
# the service's canonical port bound by a co-hosted fleet container.
cid="$(docker run -d -p 127.0.0.1::"${VERIFY_PORT}" "${IMAGE_REF}")"

host_port="$(docker port "${cid}" "${VERIFY_PORT}/tcp" | head -n1 | sed 's/.*://')"
if [ -z "${host_port}" ]; then
  echo "::error title=Runtime gate failed::Could not resolve a published host port for ${VERIFY_PORT}/tcp on ${IMAGE_REF}."
  exit 1
fi
echo "  container=${cid:0:12} host_port=${host_port}"

deadline=$(( $(date +%s) + timeout_s ))
code=""
body=""
while [ "$(date +%s)" -lt "${deadline}" ]; do
  # An exited container will never become healthy -- fail immediately with its
  # exit code rather than burning the whole timeout. This is the branch that
  # catches the pmoves-yt defect class (entrypoint dies at import).
  if [ "$(docker inspect -f '{{.State.Running}}' "${cid}")" != "true" ]; then
    exit_code="$(docker inspect -f '{{.State.ExitCode}}' "${cid}")"
    echo "::error title=Published image does not start::${IMAGE_REF} exited with code ${exit_code} before serving ${VERIFY_HEALTH_PATH}."
    exit 1
  fi

  resp="$(curl -s -w '\n%{http_code}' \
    "http://127.0.0.1:${host_port}${VERIFY_HEALTH_PATH}" || true)"
  code="${resp##*$'\n'}"
  body="${resp%$'\n'*}"
  if [ "${code}" = "${expect}" ]; then
    echo "OK: ${IMAGE_REF} answered ${VERIFY_HEALTH_PATH} with ${code}"
    echo "--- response body (first 500 bytes) ---"
    printf '%s\n' "${body}" | head -c 500
    echo
    exit 0
  fi
  sleep 3
done

echo "::error title=Published image failed its health gate::${IMAGE_REF} did not answer ${VERIFY_HEALTH_PATH} with ${expect} within ${timeout_s}s (last status: ${code:-none})."
exit 1
