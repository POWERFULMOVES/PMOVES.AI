#!/usr/bin/env bash
# pmoves-mesh-preflight — catalog-driven /healthz snapshot
# Exits 0 if all services pass, 1 if any are unhealthy.
set -u
set -o pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
CATALOG="${REPO_ROOT}/.claude/CATALOG.md"

if [[ ! -f "${CATALOG}" ]]; then
  echo "ERROR: catalog not found at ${CATALOG}" >&2
  exit 2
fi

# Services with a non-/healthz liveness path. Extend as catalog notes new exceptions.
declare -A SPECIAL_PATHS=(
  ["8105"]="/health"            # Cipher Memory exposes /health
  ["8123"]="/ping"              # ClickHouse
  ["7860"]="/gradio_api/info"   # Ultimate-TTS-Studio
  ["6333"]="/healthz"           # Qdrant (default /healthz)
)

# Skip ports that have no HTTP interface or live behind auth/proxy.
declare -A SKIP_PORTS=(
  ["7687"]="neo4j-bolt"
  ["4222"]="nats-tcp"
  ["9223"]="nats-ws"
  ["9222"]="nats-ws-docked"
  ["54323"]="supabase-studio"
)

# Extract `:<port>` mentions from catalog, dedupe, keep numeric order.
mapfile -t PORTS < <(grep -oE ':[0-9]{2,5}' "${CATALOG}" | tr -d ':' | sort -un)

if [[ ${#PORTS[@]} -eq 0 ]]; then
  echo "ERROR: no ports parsed from ${CATALOG}" >&2
  exit 2
fi

printf "%-30s | %-5s | %-6s | %-10s\n" "service" "port" "status" "latency_ms"
printf -- "------------------------------+-------+--------+-----------\n"

fail_count=0
total=0

for port in "${PORTS[@]}"; do
  if [[ -n "${SKIP_PORTS[$port]:-}" ]]; then
    continue
  fi
  total=$((total + 1))

  # Resolve label: first catalog line that mentions this port; fall back to "service-<port>".
  label="$(grep -m1 -E ":${port}\b" "${CATALOG}" | sed -nE 's/^\*\*([^*]+)\*\*.*/\1/p' | head -n1)"
  if [[ -z "${label}" ]]; then
    label="service-${port}"
  fi
  # Sanitize label whitespace
  label="$(echo "${label}" | tr -s ' ' | sed 's/^ //;s/ $//')"

  path="${SPECIAL_PATHS[$port]:-/healthz}"
  url="http://127.0.0.1:${port}${path}"

  # Two-pass curl: capture HTTP code + elapsed seconds; convert to ms.
  output="$(curl -sS --max-time 3 -o /dev/null -w '%{http_code} %{time_total}' "${url}" 2>/dev/null || echo '000 0')"
  http_code="${output% *}"
  time_total="${output#* }"
  # Convert seconds (float) to ms (int) without bc.
  latency_ms="$(awk -v t="${time_total}" 'BEGIN{printf "%d", t*1000}')"

  if [[ "${http_code}" =~ ^[23] ]]; then
    status="${http_code}"
  else
    status="${http_code}"
    fail_count=$((fail_count + 1))
  fi

  printf "%-30.30s | %-5s | %-6s | %-10s\n" "${label}" "${port}" "${status}" "${latency_ms}"
done

echo ""
if [[ ${fail_count} -gt 0 ]]; then
  echo "FAIL: ${fail_count} of ${total} service(s) unhealthy"
  exit 1
fi
echo "PASS: all ${total} catalog services healthy"
exit 0
