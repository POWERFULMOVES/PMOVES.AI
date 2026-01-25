#!/usr/bin/env bash
#
# PMOVES.AI Production Bring-Up Script
# =====================================
# Starts ALL services in documented dependency order.
# Uses hardened make targets that source env.shared automatically.
#
# Usage:
#   PUBLISHED_AGENTS=1 PARALLEL=1 bash tools/bringup_with_ui.sh
#
# Environment Variables:
#   PUBLISHED_AGENTS=1  - Use published agent images (production mode)
#   PARALLEL=1          - Enable parallel health checks (faster)
#   RUN_MIGRATIONS=1    - Run database migrations (fresh DB only)
#   WAIT_T_SHORT        - Short timeout in seconds (default: 60)
#   WAIT_T_MED          - Medium timeout in seconds (default: 120)
#   WAIT_T_LONG         - Long timeout in seconds (default: 180)
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Load environment for all docker compose commands
export LOAD_ENV_SHARED=". ./scripts/with-env.sh"

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

echo "═══════════════════════════════════════════════════════════"
echo "  PMOVES.AI Production Bring-Up"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Configuration:"
echo "  PUBLISHED_AGENTS=${PUBLISHED_AGENTS:-0} (1=production images)"
echo "  PARALLEL=${PARALLEL:-0} (1=parallel health checks)"
echo "  RUN_MIGRATIONS=${RUN_MIGRATIONS:-0} (1=fresh DB setup)"
echo ""

# =============================================================================
# PHASE 0: Environment Setup
# =============================================================================
echo "⛳ PHASE 0: Environment Setup"
echo "─────────────────────────────────────────────────────────────"
if ! make ensure-env-shared 2>&1; then
    echo "❌ Environment setup failed. Run 'make ensure-env-shared' separately to diagnose."
    exit 1
fi
echo ""

# =============================================================================
# PHASE 1: Observability (START FIRST - captures all logs from here)
# =============================================================================
echo "⛳ PHASE 1: Observability Stack (START FIRST)"
echo "─────────────────────────────────────────────────────────────"
echo "→ Starting Prometheus, Grafana, Loki, Promtail, cAdvisor..."
start_service "Observability" "up-obs" "true" || exit 1
echo ""

# =============================================================================
# PHASE 2: Supabase (Database & Auth)
# =============================================================================
echo "⛳ PHASE 2: Supabase (Database & Auth)"
echo "─────────────────────────────────────────────────────────────"
if make supa-status >/dev/null 2>&1; then
  echo "✔ Supabase already running"
else
  start_service "Supabase" "supa-start" "true" || exit 1
fi

# Only run bootstrap/migrations when explicitly requested (fresh DB)
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  if ! make supabase-bootstrap; then
    echo "❌ Database migrations failed. This is required when RUN_MIGRATIONS=1."
    echo "   Fix migration issues and re-run, or unset RUN_MIGRATIONS to skip."
    exit 1
  fi
fi
echo ""

# =============================================================================
# PHASE 3: Data Tier (Storage Backends)
# =============================================================================
echo "⛳ PHASE 3: Data Tier (Qdrant, Neo4j, Meilisearch, MinIO)"
echo "─────────────────────────────────────────────────────────────"
start_service "Data Tier" "up-data-tier" "true" || exit 1
echo ""

# =============================================================================
# PHASE 4: Message Bus (NATS - Event Coordination)
# =============================================================================
echo "⛳ PHASE 4: Message Bus (NATS)"
echo "─────────────────────────────────────────────────────────────"
start_service "NATS Bus" "up-bus" "true" || exit 1
echo ""

# =============================================================================
# PHASE 5: LLM Gateway (TensorZero)
# =============================================================================
echo "⛳ PHASE 5: LLM Gateway (TensorZero + ClickHouse)"
echo "─────────────────────────────────────────────────────────────"
start_service "TensorZero" "up-tensorzero" "true" || exit 1
echo ""

# =============================================================================
# PHASE 6: Core Services
# =============================================================================
echo "⛳ PHASE 6: Core Services (PostgREST, Hi-RAG, Presign, etc.)"
echo "─────────────────────────────────────────────────────────────"
start_service "Core Services" "up" "true" || exit 1
echo ""

# =============================================================================
# PHASE 7: Agent Services
# =============================================================================
echo "⛳ PHASE 7: Agent Services"
echo "─────────────────────────────────────────────────────────────"
if [ "${PUBLISHED_AGENTS:-0}" = "1" ]; then
  echo "→ Using published agent images (PRODUCTION mode)"
  start_service "Published Agents" "up-agents-published" "true" || exit 1
  PRODUCTION_MODE=1
else
  echo "→ Using local agent builds (DEV mode)"
  start_service "Agents + UIs" "up-agents-ui" "true" || exit 1
  PRODUCTION_MODE=0
fi
echo ""

# =============================================================================
# PHASE 8: Worker Services
# =============================================================================
echo "⛳ PHASE 8: Worker Services"
echo "─────────────────────────────────────────────────────────────"
start_service "Workers" "up-workers" "false" || true  # Non-critical
echo ""

# =============================================================================
# PHASE 9: Media Services
# =============================================================================
echo "⛳ PHASE 9: Media Services"
echo "─────────────────────────────────────────────────────────────"
start_service "Media Pipeline" "up-media" "false" || true  # Non-critical
start_service "PMOVES.YT" "up-yt" "false" || true  # Non-critical
echo ""

# =============================================================================
# PHASE 10: Integration Services
# =============================================================================
echo "⛳ PHASE 10: Integration Services"
echo "─────────────────────────────────────────────────────────────"
start_service "External Stacks" "up-external" "false" || true  # Non-critical
start_service "n8n" "up-n8n" "false" || true  # Non-critical
start_service "Invidious" "up-invidious" "false" || true  # Non-critical
start_service "Channel Monitor" "channel-monitor-up" "false" || true  # Non-critical
echo ""

# =============================================================================
# PHASE 11: User Interface
# =============================================================================
echo "⛳ PHASE 11: User Interface"
echo "─────────────────────────────────────────────────────────────"
if [ "${PRODUCTION_MODE:-0}" = "1" ]; then
  start_service "Production UI" "up-ui" "true" || exit 1
  UI_PORT=4482
  UI_NAME="PMOVES UI"
else
  start_service "Console UI" "ui-dev-start" "true" || exit 1
  UI_PORT=3001
  UI_NAME="Console UI"
fi
echo ""

# =============================================================================
# PHASE 12: Health Checks
# =============================================================================
echo "⛳ PHASE 12: Health Checks"
echo "─────────────────────────────────────────────────────────────"
echo "→ Waiting for services to become ready..."
echo ""

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
  check_http_bg "Prometheus" "http://localhost:9090" "$WAIT_T_SHORT"
  check_http_bg "Channel Monitor" "http://localhost:8097/healthz" "$WAIT_T_SHORT"
  check_http_bg "yt-dlp catalog" "${YTB}/yt/docs/catalog" "$WAIT_T_SHORT"
  check_http_bg "$UI_NAME" "http://localhost:${UI_PORT}" "$WAIT_T_LONG"
  check_http_bg "TensorZero GW" "http://localhost:3030" "$WAIT_T_SHORT"
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
  wait_http "http://localhost:9090" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Prometheus")
  wait_http "http://localhost:3100/ready" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Loki")
  wait_prom_targets $WAIT_T_MED || TIMEOUT_SERVICES+=("Prometheus targets")
  wait_http "http://localhost:8097/healthz" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Channel Monitor")
  wait_http "${YTB}/yt/docs/catalog" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("yt-dlp catalog")
  if ! wait_http "http://localhost:${UI_PORT}" $WAIT_T_LONG; then
    if [ "${PRODUCTION_MODE:-0}" = "1" ]; then
      echo "⚠ Production UI not responding on :4482"
      docker logs pmoves-ui-1 --tail 80 2>/dev/null || echo "  (No container logs found)"
    else
      echo "⚠ Console UI not responding on :3001; recent dev log:"
      tail -n 80 ui/.pmoves_ui_dev.log 2>/dev/null || echo "  (No log file found)"
    fi
    TIMEOUT_SERVICES+=("$UI_NAME")
  fi
  wait_http "http://localhost:3030" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("TensorZero GW")
fi

echo ""

# =============================================================================
# PHASE 13: Evidence & Summary
# =============================================================================
echo "⛳ PHASE 13: Evidence Collection"
echo "─────────────────────────────────────────────────────────────"
echo "→ Syncing PMOVES.YT docs..."
make yt-docs-sync 2>/dev/null || echo "  ⚠ PMOVES.YT docs sync skipped"
echo "→ Capturing evidence..."
make evidence-auto 2>/dev/null || echo "  ⚠ Evidence capture had issues"
echo ""

echo "⛳ Retro Preflight Summary"
echo "─────────────────────────────────────────────────────────────"
PMOVES_RETRO_TIMEOUT=5 python3 pmoves/tools/flight_check_retro.py 2>/dev/null || echo "  ⚠ Flight check retro skipped"
echo ""

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
    echo "   Dashboard (UI):  http://localhost:${UI_PORT}"
    echo "   Grafana:         http://localhost:3002"
    echo "   Prometheus:      http://localhost:9090"
    echo "   Agent Zero:      http://localhost:8081"
    echo "   Archon:          http://localhost:3737"
    echo "   TensorZero UI:   http://localhost:4000"
    echo "   Supabase Studio: http://127.0.0.1:65433"
    echo ""
fi

echo "═══════════════════════════════════════════════════════════"
