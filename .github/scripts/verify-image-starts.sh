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
#   VERIFY_PLATFORMS         (default: host platform) comma-separated list, e.g.
#                            "linux/amd64,linux/arm64". EVERY listed platform is
#                            started and health-checked; any one failing fails
#                            the gate. Without this the runner silently picks
#                            the variant matching its own arch -- the X64
#                            self-hosted runner -- so an arm64-only startup
#                            regression shipped inside a signed multi-arch
#                            manifest with nothing ever having run it.
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

# One platform's worth of work: pull, run, poll, report. Returns non-zero on
# any failure so the caller can fail the whole gate.
check_one() {
  local platform_arg=("$@")
  local label="${PLATFORM_LABEL:-host}"

  if [ "${VERIFY_PULL:-1}" = "1" ]; then
    # Pull by the ref we were handed. Callers should hand us a DIGEST ref so that
    # what is verified is the exact manifest just pushed, not a mutable tag that a
    # concurrent run could have moved.
    docker pull "${platform_arg[@]}" "${IMAGE_REF}"
  fi

  # Publish to an ephemeral loopback port: a self-hosted runner may already have
  # the service's canonical port bound by a co-hosted fleet container.
  cid="$(docker run -d "${platform_arg[@]}" -p 127.0.0.1::"${VERIFY_PORT}" "${IMAGE_REF}")"

  # Check LIVENESS before the port. An entrypoint that dies at import is dead
  # before `docker port` can answer, so resolving the port first reported
  # "could not resolve a published host port" -- true, but it names the symptom
  # and hides the cause. That is the exact defect class this gate exists for,
  # so it must say so: report the exit code, and let cleanup print the traceback.
  if [ "$(docker inspect -f '{{.State.Running}}' "${cid}")" != "true" ]; then
    local early_code
    early_code="$(docker inspect -f '{{.State.ExitCode}}' "${cid}" 2>/dev/null || true)"
    if [ -z "${early_code}" ] || [ "${early_code}" = "0" ]; then
      # No usable exit code means the runtime never really started the container
      # -- on a per-platform leg that is almost always a missing emulator or an
      # arch absent from the manifest, NOT an application crash. Say which, so
      # the fix is "install QEMU / publish that arch", not "debug the app".
      echo "::error title=Runtime gate could not start this platform::[${label}] ${IMAGE_REF} produced no running container and no exit code. Usually the manifest has no ${label} variant, or binfmt/QEMU is not configured on this runner (docker/setup-qemu-action)."
    else
      echo "::error title=Published image does not start::[${label}] ${IMAGE_REF} exited with code ${early_code} before it could serve anything."
    fi
    return 1
  fi

  local host_port
  host_port="$(docker port "${cid}" "${VERIFY_PORT}/tcp" | head -n1 | sed 's/.*://')"
  if [ -z "${host_port}" ]; then
    echo "::error title=Runtime gate failed::[${label}] Container is running but published no host port for ${VERIFY_PORT}/tcp on ${IMAGE_REF}. Check that the service listens on ${VERIFY_PORT}."
    return 1
  fi
  echo "  [${label}] container=${cid:0:12} host_port=${host_port}"

  local deadline code body resp exit_code
  deadline=$(( $(date +%s) + timeout_s ))
  code=""
  while [ "$(date +%s)" -lt "${deadline}" ]; do
    # An exited container will never become healthy -- fail immediately with its
    # exit code rather than burning the whole timeout. This is the branch that
    # catches the pmoves-yt defect class (entrypoint dies at import).
    if [ "$(docker inspect -f '{{.State.Running}}' "${cid}")" != "true" ]; then
      exit_code="$(docker inspect -f '{{.State.ExitCode}}' "${cid}")"
      echo "::error title=Published image does not start::[${label}] ${IMAGE_REF} exited with code ${exit_code} before serving ${VERIFY_HEALTH_PATH}."
      return 1
    fi

    resp="$(curl -s -w '\n%{http_code}' \
      "http://127.0.0.1:${host_port}${VERIFY_HEALTH_PATH}" || true)"
    code="${resp##*$'\n'}"
    body="${resp%$'\n'*}"
    if [ "${code}" = "${expect}" ]; then
      echo "OK: [${label}] ${IMAGE_REF} answered ${VERIFY_HEALTH_PATH} with ${code}"
      echo "--- response body (first 500 bytes) ---"
      printf '%s\n' "${body}" | head -c 500
      echo
      return 0
    fi
    sleep 3
  done

  echo "::error title=Published image failed its health gate::[${label}] ${IMAGE_REF} did not answer ${VERIFY_HEALTH_PATH} with ${expect} within ${timeout_s}s (last status: ${code:-none})."
  return 1
}

# No VERIFY_PLATFORMS -> host platform only, which is the previous behaviour and
# is correct for a single-arch image. With it, every listed platform must pass;
# QEMU (docker/setup-qemu-action, already in this workflow) supplies the
# emulation where no native runner exists.
failed=0
if [ -z "${VERIFY_PLATFORMS:-}" ]; then
  PLATFORM_LABEL="host" check_one || failed=1
else
  IFS=',' read -r -a _platforms <<< "${VERIFY_PLATFORMS}"
  for platform in "${_platforms[@]}"; do
    platform="$(echo "${platform}" | tr -d '[:space:]')"
    [ -z "${platform}" ] && continue
    echo "=== platform: ${platform} ==="
    # cleanup runs per platform so one leg's container never outlives its check
    PLATFORM_LABEL="${platform}" check_one --platform "${platform}" || failed=1
    cleanup
    cid=""
  done
fi

if [ "${failed}" -ne 0 ]; then
  exit 1
fi
echo "Runtime gate passed for: ${VERIFY_PLATFORMS:-host platform}"
exit 0
