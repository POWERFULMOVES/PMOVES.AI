#!/usr/bin/env bash
#
# verify-services.sh
#
# Standalone health-check script for PMOVES services.
# Hits /healthz for each configured service, reports pass/fail with timing.
# Used by PBnJ, CI, and manual verification.
#
# Usage:
#   verify-services.sh [--json] [--timeout SECONDS]
#
# Exit code: number of failed services (0 = all healthy)
#

set -euo pipefail

TIMEOUT="${TIMEOUT:-5}"
OUTPUT_JSON=false
EXPECTED_SERVICES=""

# Service catalog: name port path
SERVICES=(
  "agent-zero        8080 /healthz"
  "archon            8091 /healthz"
  "botz-gateway      8081 /healthz"
  "jellyfin-bridge   8093 /healthz"
  "flute-gateway     8055 /healthz"
  "media-video       8079 /healthz"
  "media-audio       8082 /healthz"
  "extract-worker    8083 /healthz"
  "ffmpeg-whisper    8078 /healthz"
  "channel-monitor   8097 /healthz"
  "deepresearch      8098 /healthz"
  "supaserch         8099 /healthz"
  "presign           8088 /healthz"
  "pdf-ingest        8092 /healthz"
  "langextract       8084 /healthz"
  "notebook-sync     8095 /healthz"
  "publisher-discord 8094 /healthz"
  "render-webhook    8085 /healthz"
  "cipher-memory     8105 /health"
  "pmoves-yt         8077 /healthz"
  "nats              8222 /varz"
  "meilisearch       7700 /health"
  "qdrant            6333 /healthz"
  "minio             9000 /minio/health/live"
  "prometheus        9090 /-/healthy"
  "grafana           3000 /api/health"
  "tensorzero        3030 /health"
  "tensorzero-ui     4000 /"
)

usage() {
  cat <<EOF
PMOVES Service Health Verifier

Usage:
  $(basename "$0") [--json] [--timeout SECONDS] [--expected SERVICES]

Options:
  --json      Output results as JSON
  --timeout   HTTP timeout per service in seconds (default: ${TIMEOUT})
  --expected  Comma-separated list of service names that MUST be running.
              Services in this list returning 000 are classified as FAIL
              instead of SKIP. (default: all services treated as optional)
EOF
}

# Parse args
while [ $# -gt 0 ]; do
  case "$1" in
    --json)     OUTPUT_JSON=true; shift;;
    --timeout)  TIMEOUT="$2"; shift 2;;
    --expected) EXPECTED_SERVICES="$2"; shift 2;;
    -h|--help)  usage; exit 0;;
    *)          echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

_is_expected() {
  local svc="$1"
  if [ -z "${EXPECTED_SERVICES}" ]; then
    return 1  # no expected list → not expected
  fi
  echo ",${EXPECTED_SERVICES}," | grep -q ",${svc},"
}

pass=0
fail=0
skip=0
results=()

for entry in "${SERVICES[@]}"; do
  read -r name port path <<< "${entry}"
  url="http://127.0.0.1:${port}${path}"

  start_ms=$(($(date +%s%N 2>/dev/null || echo 0) / 1000000))
  status="unknown"
  http_code=""

  if http_code=$(curl -sf -o /dev/null -w "%{http_code}" --max-time "${TIMEOUT}" "${url}" 2>/dev/null); then
    end_ms=$(($(date +%s%N 2>/dev/null || echo 0) / 1000000))
    latency_ms=$(( end_ms - start_ms ))
    status="pass"
    ((pass++)) || true
  else
    end_ms=$(($(date +%s%N 2>/dev/null || echo 0) / 1000000))
    latency_ms=$(( end_ms - start_ms ))
    if [ -z "${http_code}" ] || [ "${http_code}" = "000" ]; then
      if _is_expected "${name}"; then
        status="fail"
        ((fail++)) || true
      else
        status="skip"
        ((skip++)) || true
      fi
    else
      status="fail"
      ((fail++)) || true
    fi
  fi

  if [ "${OUTPUT_JSON}" = "true" ]; then
    results+=("{\"service\":\"${name}\",\"port\":${port},\"status\":\"${status}\",\"http_code\":\"${http_code}\",\"latency_ms\":${latency_ms}}")
  else
    case "${status}" in
      pass) printf "  [PASS] %-22s %s (%dms)\n" "${name}" "${url}" "${latency_ms}";;
      fail) printf "  [FAIL] %-22s %s (HTTP %s, %dms)\n" "${name}" "${url}" "${http_code}" "${latency_ms}";;
      skip) printf "  [SKIP] %-22s %s (not reachable)\n" "${name}" "${url}";;
    esac
  fi
done

if [ "${OUTPUT_JSON}" = "true" ]; then
  # Join results array
  json_arr=$(IFS=,; echo "${results[*]}")
  echo "{\"pass\":${pass},\"fail\":${fail},\"skip\":${skip},\"total\":$((pass+fail+skip)),\"services\":[${json_arr}]}"
else
  echo ""
  echo "  Summary: ${pass} pass, ${fail} fail, ${skip} skip ($(( pass + fail + skip )) total)"
fi

exit "${fail}"
