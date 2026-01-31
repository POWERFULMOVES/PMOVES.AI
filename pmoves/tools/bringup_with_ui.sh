#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

WAIT_T_SHORT=${WAIT_T_SHORT:-60}
WAIT_T_MED=${WAIT_T_MED:-120}
WAIT_T_LONG=${WAIT_T_LONG:-180}

# Service URLs
YTB=${YTB:-http://localhost:8077}

# Track failed services for reporting
declare -a FAILED_SERVICES=()
declare -a TIMEOUT_SERVICES=()

# Error reporting function
report_failure() {
    local service="$1"
    local message="${2:-Failed to start}"
    echo "❌ $service: $message" >&2
    FAILED_SERVICES+=("$service")
}

# Service start wrapper with error handling
start_service() {
    local name="$1"
    local target="${2:-up}"
    local is_critical="${3:-true}"

    echo "→ Starting $name..."
    if make "$target" 2>&1; then
        echo "  ✓ $name started"
        return 0
    else
        local rc=$?
        if [ "$is_critical" = "true" ]; then
            report_failure "$name" "exited with code $rc"
            return 1
        else
            echo "  ⚠ $name failed (non-critical for now)"
            TIMEOUT_SERVICES+=("$name")
            return 0
        fi
    fi
}

wait_http() { # url timeout_seconds
  local url="$1"; local timeout="${2:-$WAIT_T_SHORT}"; local start=$(date +%s)
  echo "→ Waiting for $url (timeout ${timeout}s)"
  while true; do
    if curl -fsS -m 3 "$url" >/dev/null 2>&1; then echo "  OK: $url"; break; fi
    sleep 2
    now=$(date +%s); if (( now - start > timeout )); then echo "  TIMEOUT: $url"; return 1; fi
  done
}

wait_prom_targets() { # timeout_seconds
  local timeout="${1:-$WAIT_T_SHORT}"; local start=$(date +%s)
  local url="http://localhost:${PROMETHEUS_HOST_PORT:-9090}/api/v1/targets"
  echo "→ Waiting for Prometheus targets (timeout ${timeout}s)"
  while true; do
    if out=$(curl -fsS -m 5 "$url" 2>/dev/null); then
      n=$(printf '%s' "$out" | jq -r '.data.activeTargets | length' 2>/dev/null || echo 0)
      if [ "${n:-0}" -gt 0 ]; then echo "  OK: $n targets"; break; fi
    fi
    sleep 2
    now=$(date +%s); if (( now - start > timeout )); then echo "  TIMEOUT: Prometheus targets"; return 1; fi
  done
}

# Parallel readiness (background curl checks + barrier)
declare -a READY_CMDS=()
READY_TMP_DIR="${TMPDIR:-/tmp}/pmoves_ready_$RANDOM"
mkdir -p "$READY_TMP_DIR"

check_http_bg() { # name url timeout
  local name="$1"; local url="$2"; local timeout="${3:-$WAIT_T_SHORT}"
  local out="$READY_TMP_DIR/${name//[^A-Za-z0-9_\-]/_}.out"
  bash -c "start=\$(date +%s); while true; do curl -fsS -m 3 '$url' >/dev/null 2>&1 && echo OK > '$out' && exit 0; sleep 2; now=\$(date +%s); [ \$((now-start)) -gt $timeout ] && echo TIMEOUT > '$out' && exit 1; done" &
  READY_CMDS+=("$name|$url|$out|$!|$timeout")
}

ready_barrier() {
  echo "⏳ Parallel readiness — waiting on ${#READY_CMDS[@]} checks"
  local rc=0
  for entry in "${READY_CMDS[@]}"; do
    IFS='|' read -r name url out pid to <<<"$entry"
    if wait "$pid"; then status="OK"; else status="TIMEOUT"; rc=1; TIMEOUT_SERVICES+=("$name"); fi
    if [ -f "$out" ]; then status=$(cat "$out"); fi
    printf "  • %-24s %-60s %s\n" "$name" "$url" "$status"
  done
  rm -rf "$READY_TMP_DIR" || echo "  ⚠ Failed to cleanup $READY_TMP_DIR" >&2
  return $rc
}

echo "⛳ Bootstrap env + Supabase CLI"
if ! make ensure-env-shared 2>&1; then
    echo "❌ Environment setup failed. Run 'make ensure-env-shared' separately to diagnose."
    exit 1
fi

# Production: only start Supabase, don't reset DB
if make supa-status >/dev/null 2>&1; then
  echo "✔ Supabase already running"
else
  if ! make supa-start; then
      echo "❌ Supabase failed to start. Check Docker and port availability."
      exit 1
  fi
fi

# Only run bootstrap/migrations in dev mode (explicit flag) - FAIL ON ERROR
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  if ! make supabase-bootstrap; then
    echo "❌ Database migrations failed. This is required when RUN_MIGRATIONS=1."
    echo "   Fix migration issues and re-run, or unset RUN_MIGRATIONS to skip."
    exit 1
  fi
fi

echo "⛳ Start core services"
start_service "Core Services" "up" "true" || exit 1

echo "⛳ Start agents (APIs + UIs)"
if [ "${PUBLISHED_AGENTS:-0}" = "1" ]; then
  start_service "Published Agents" "up-agents-published" "true" || exit 1
else
  start_service "Agents + UIs" "up-agents-ui" "true" || exit 1
fi

echo "⛳ Start integration services"
start_service "External Stacks" "up-external" "true" || exit 1
start_service "PMOVES.YT" "up-yt" "true" || exit 1
start_service "Invidious" "up-invidious" "true" || exit 1
start_service "Channel Monitor" "channel-monitor-up" "true" || exit 1

echo "⛳ Start media and AI services"
start_service "Media Pipeline" "up-media" "true" || exit 1
start_service "TensorZero" "up-tensorzero" "true" || exit 1
start_service "n8n" "up-n8n" "true" || exit 1
start_service "Jellyfin AI" "up-jellyfin-ai" "true" || exit 1

echo "⛳ Start monitoring stack"
start_service "Monitoring" "up-monitoring" "true" || exit 1

echo "⛳ Start Console UI"
start_service "Console UI" "ui-dev-start" "true" || exit 1

echo "⛳ Waiting on key endpoints"
if [ "${PARALLEL:-0}" = "1" ]; then
  check_http_bg "Supabase REST" "http://127.0.0.1:65421/rest/v1" "$WAIT_T_LONG"
  check_http_bg "Hi-RAG v2 CPU" "http://localhost:${HIRAG_V2_HOST_PORT:-8086}/" "$WAIT_T_MED"
  check_http_bg "Hi-RAG v2 GPU" "http://localhost:${HIRAG_V2_GPU_HOST_PORT:-8087}/" "$WAIT_T_LONG"
  check_http_bg "Presign" "http://localhost:8088/healthz" "$WAIT_T_SHORT"
  check_http_bg "Archon API" "http://localhost:8091/healthz" "$WAIT_T_SHORT"
  check_http_bg "Archon UI" "http://localhost:3737" "$WAIT_T_SHORT"
  check_http_bg "Archon MCP" "http://localhost:8091/mcp/describe" "$WAIT_T_SHORT"
  check_http_bg "Agent Zero API" "http://localhost:8080/healthz" "$WAIT_T_SHORT"
  check_http_bg "Agent Zero UI" "http://localhost:8081" "$WAIT_T_SHORT"
  check_http_bg "Agent Zero Env" "http://localhost:8080/config/environment" "$WAIT_T_SHORT"
  check_http_bg "Agent Zero MCP" "http://localhost:8080/mcp/commands" "$WAIT_T_SHORT"
  check_http_bg "PMOVES.YT" "http://localhost:8077/" "$WAIT_T_SHORT"
  check_http_bg "Grafana" "http://localhost:3002" "$WAIT_T_SHORT"
  check_http_bg "Loki /ready" "http://localhost:3100/ready" "$WAIT_T_SHORT"
  check_http_bg "Channel Monitor" "http://localhost:8097/healthz" "$WAIT_T_SHORT"
  check_http_bg "Monitor Status" "http://localhost:8097/api/monitor/status" "$WAIT_T_SHORT"
  check_http_bg "yt-dlp catalog" "${YTB}/yt/docs/catalog" "$WAIT_T_SHORT"
  check_http_bg "Console UI" "http://localhost:3001" "$WAIT_T_LONG"
  check_http_bg "n8n UI" "http://localhost:5678" "$WAIT_T_SHORT"
  check_http_bg "TensorZero UI" "http://localhost:4000" "$WAIT_T_SHORT"
  check_http_bg "TensorZero GW" "http://localhost:3030" "$WAIT_T_SHORT"
  check_http_bg "Jellyfin" "http://localhost:8096" "$WAIT_T_SHORT"
  check_http_bg "Firefly" "http://localhost:8082" "$WAIT_T_SHORT"
  check_http_bg "Wger" "http://localhost:8000" "$WAIT_T_SHORT"
  check_http_bg "Open Notebook" "http://localhost:8503" "$WAIT_T_SHORT"
  check_http_bg "Supabase Studio" "http://127.0.0.1:65433" "$WAIT_T_SHORT"
  ready_barrier
  wait_prom_targets "$WAIT_T_MED"
else
  wait_http "http://127.0.0.1:65421/rest/v1" $WAIT_T_LONG || TIMEOUT_SERVICES+=("Supabase REST")
  wait_http "http://localhost:${HIRAG_V2_HOST_PORT:-8086}/" $WAIT_T_MED || TIMEOUT_SERVICES+=("Hi-RAG v2 CPU")
  wait_http "http://localhost:${HIRAG_V2_GPU_HOST_PORT:-8087}/" $WAIT_T_LONG || TIMEOUT_SERVICES+=("Hi-RAG v2 GPU")
  wait_http "http://localhost:8088/healthz" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Presign")
  wait_http "http://localhost:8091/healthz" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Archon API")
  wait_http "http://localhost:3737" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Archon UI")
  wait_http "http://localhost:8091/mcp/describe" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Archon MCP")
  wait_http "http://localhost:8080/healthz" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Agent Zero API")
  wait_http "http://localhost:8081" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Agent Zero UI")
  wait_http "http://localhost:8080/config/environment" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Agent Zero Env")
  wait_http "http://localhost:8080/mcp/commands" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Agent Zero MCP")
  wait_http "http://localhost:8077/" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("PMOVES.YT")
  wait_http "http://localhost:3002" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Grafana")
  wait_http "http://localhost:3100/ready" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Loki")
  wait_prom_targets $WAIT_T_MED || TIMEOUT_SERVICES+=("Prometheus targets")
  wait_http "http://localhost:8097/healthz" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Channel Monitor")
  wait_http "http://localhost:8097/api/monitor/status" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Monitor Status API")
  wait_http "${YTB}/yt/docs/catalog" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("yt-dlp catalog")
  if ! wait_http "http://localhost:3001" $WAIT_T_LONG; then
    echo "⚠ Console UI not responding on :3001; recent dev log:"
    tail -n 80 ui/.pmoves_ui_dev.log 2>/dev/null || echo "  (No log file found)"
    TIMEOUT_SERVICES+=("Console UI")
  fi
  wait_http "http://localhost:5678" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("n8n UI")
  wait_http "http://localhost:4000" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("TensorZero UI")
  wait_http "http://localhost:3030" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("TensorZero GW")
  wait_http "http://localhost:8096" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Jellyfin")
  wait_http "http://localhost:8082" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Firefly")
  wait_http "http://localhost:8000" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Wger")
  wait_http "http://localhost:8503" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Open Notebook")
  wait_http "http://127.0.0.1:65433" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Supabase Studio")
fi

echo "⛳ Capturing evidence"
# Ensure PMOVES.YT docs are fresh before capture
make yt-docs-sync
make evidence-auto

echo "⛳ Retro preflight summary (parallel table)"
PMOVES_RETRO_TIMEOUT=5 python3 pmoves/tools/flight_check_retro.py

# Final status report
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  BRING-UP STATUS REPORT"
echo "═══════════════════════════════════════════════════════════"

if [ ${#FAILED_SERVICES[@]} -gt 0 ]; then
    echo ""
    echo "❌ FAILED SERVICES (startup failed):"
    for svc in "${FAILED_SERVICES[@]}"; do
        echo "   • $svc"
    done
    echo ""
    echo "   Run 'make logs' to view error logs for failed services."
    echo "   Check port conflicts with: 'docker ps' and 'netstat -tulpn | grep LISTEN'"
    echo ""
    exit 1
fi

if [ ${#TIMEOUT_SERVICES[@]} -gt 0 ]; then
    echo ""
    echo "⚠️  TIMEOUT SERVICES (not ready within expected time):"
    for svc in "${TIMEOUT_SERVICES[@]}"; do
        echo "   • $svc"
    done
    echo ""
    echo "   Services may still be starting. Check with: 'make ps'"
    echo "   View logs: 'make logs' or 'docker logs <service>'"
    echo ""
fi

if [ ${#FAILED_SERVICES[@]} -eq 0 ] && [ ${#TIMEOUT_SERVICES[@]} -eq 0 ]; then
    echo ""
    echo "✅ ALL SERVICES STARTED SUCCESSFULLY"
    echo ""
    echo "   Console:    http://localhost:3001"
    echo "   Grafana:    http://localhost:3002"
    echo "   Agent Zero: http://localhost:8081"
    echo "   Archon:     http://localhost:3737"
    echo ""
fi

echo "═══════════════════════════════════════════════════════════"
