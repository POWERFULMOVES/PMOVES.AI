#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

WAIT_T_SHORT=${WAIT_T_SHORT:-60}
WAIT_T_MED=${WAIT_T_MED:-120}
WAIT_T_LONG=${WAIT_T_LONG:-180}
PUBLISHED_AGENTS=${PUBLISHED_AGENTS:-1}
RUN_UI_DEV=${RUN_UI_DEV:-0}
ENABLE_JELLYFIN_AI=${ENABLE_JELLYFIN_AI:-1}

# Service URLs
YTB=${YTB:-http://localhost:8077}

# Runtime-aware Supabase defaults.
# Auto-detect compose runtime if compose Supabase containers are present.
SUPABASE_RUNTIME=${SUPABASE_RUNTIME:-cli}
if docker ps --format '{{.Names}}' | grep -qE '^pmoves-supabase-(db|kong)-1$'; then
  SUPABASE_RUNTIME=compose
fi
if [ "$SUPABASE_RUNTIME" = "compose" ]; then
  SUPABASE_REST_READY_URL=${SUPABASE_REST_READY_URL:-http://127.0.0.1:3010/}
  SUPABASE_STUDIO_READY_URL=${SUPABASE_STUDIO_READY_URL:-http://127.0.0.1:3001}
else
  SUPABASE_REST_READY_URL=${SUPABASE_REST_READY_URL:-http://127.0.0.1:54321/rest/v1/}
  SUPABASE_STUDIO_READY_URL=${SUPABASE_STUDIO_READY_URL:-http://127.0.0.1:54323}
fi

if [ "$SUPABASE_RUNTIME" != "compose" ] && [ -f .supabase.status.env ]; then
  api_url="$(grep -m1 '^API_URL=' .supabase.status.env | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//')"
  studio_url="$(grep -m1 '^STUDIO_URL=' .supabase.status.env | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//')"
  if [ -n "${api_url:-}" ]; then
    SUPABASE_REST_READY_URL="${api_url}/rest/v1/"
  fi
  if [ -n "${studio_url:-}" ]; then
    SUPABASE_STUDIO_READY_URL="${studio_url}"
  fi
fi

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
    code=$(curl -s -o /dev/null -m 3 -w "%{http_code}" "$url" 2>/dev/null || true)
    [ -z "$code" ] && code=000
    if [ "$code" != "000" ] && [ "$code" -lt 500 ]; then echo "  OK: $url (HTTP $code)"; break; fi
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

wait_container_ready() { # container_name timeout_seconds
  local container="$1"; local timeout="${2:-$WAIT_T_SHORT}"; local start
  start=$(date +%s)
  while true; do
    if docker inspect "$container" >/dev/null 2>&1; then
      local running health
      running="$(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null || echo false)"
      health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container" 2>/dev/null || echo none)"
      if [ "$running" = "true" ] && { [ "$health" = "healthy" ] || [ "$health" = "none" ]; }; then
        return 0
      fi
    fi
    sleep 2
    now=$(date +%s)
    if (( now - start > timeout )); then
      return 1
    fi
  done
}

check_http_bg() { # name url timeout
  local name="$1"; local url="$2"; local timeout="${3:-$WAIT_T_SHORT}"
  local out="$READY_TMP_DIR/${name//[^A-Za-z0-9_\-]/_}.out"
  bash -c "start=\$(date +%s); while true; do code=\$(curl -s -o /dev/null -m 3 -w '%{http_code}' '$url' 2>/dev/null || true); [ -z \"\$code\" ] && code=000; if [ \"\$code\" != \"000\" ] && [ \"\$code\" -lt 500 ]; then echo OK > '$out' && exit 0; fi; sleep 2; now=\$(date +%s); [ \$((now-start)) -gt $timeout ] && echo TIMEOUT > '$out' && exit 1; done" &
  READY_CMDS+=("$name|$url|$out|$!|$timeout")
}

check_container_bg() { # name container timeout
  local name="$1"; local container="$2"; local timeout="${3:-$WAIT_T_SHORT}"
  local out="$READY_TMP_DIR/${name//[^A-Za-z0-9_\-]/_}.out"
  bash -c "start=\$(date +%s); while true; do if docker inspect '$container' >/dev/null 2>&1; then running=\$(docker inspect -f '{{.State.Running}}' '$container' 2>/dev/null || echo false); health=\$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' '$container' 2>/dev/null || echo none); if [ \"\$running\" = \"true\" ] && { [ \"\$health\" = \"healthy\" ] || [ \"\$health\" = \"none\" ]; }; then echo OK > '$out' && exit 0; fi; fi; sleep 2; now=\$(date +%s); [ \$((now-start)) -gt $timeout ] && echo TIMEOUT > '$out' && exit 1; done" &
  READY_CMDS+=("$name|container:$container|$out|$!|$timeout")
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
  # Some published images can drift from repo runtime expectations. If the
  # primary API is not reachable, fall back to local agents build to keep
  # production bring-up deterministic.
  if ! wait_http "http://localhost:8080/healthz" 45; then
    echo "⚠ Published Agent Zero failed readiness; falling back to local agents stack"
    # Published and local agent targets share container names. Hard-stop/remove
    # agent containers before fallback recreate to avoid "container is running"
    # races during compose service recreation.
    make down-agents >/dev/null 2>&1 || true
    docker compose -f docker-compose.agents.images.yml --profile agents stop \
      agent-zero archon archon-ui deepresearch supaserch mesh-agent publisher-discord >/dev/null 2>&1 || true
    docker compose -f docker-compose.agents.images.yml --profile agents rm -f \
      agent-zero archon archon-ui deepresearch supaserch mesh-agent publisher-discord >/dev/null 2>&1 || true
    docker rm -f \
      pmoves-agent-zero-1 pmoves-archon-1 pmoves-archon-ui-1 \
      pmoves-deepresearch-1 pmoves-supaserch-1 pmoves-mesh-agent-1 pmoves-publisher-discord-1 >/dev/null 2>&1 || true
    start_service "Agents + UIs (fallback)" "up-agents-ui" "true" || exit 1
  fi
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
if [ "${ENABLE_JELLYFIN_AI}" = "1" ]; then
  start_service "Jellyfin AI" "up-jellyfin-ai" "true" || exit 1
else
  echo "↷ Skipping Jellyfin AI overlay (ENABLE_JELLYFIN_AI=${ENABLE_JELLYFIN_AI})"
fi

echo "⛳ Start monitoring stack"
start_service "Monitoring" "up-monitoring" "true" || exit 1

echo "⛳ Start Console UI"
if [ "${RUN_UI_DEV}" = "1" ]; then
  start_service "Console UI" "ui-dev-start" "true" || exit 1
else
  echo "↷ Skipping Console UI dev server (RUN_UI_DEV=${RUN_UI_DEV})"
fi

echo "⛳ Waiting on key endpoints"
if [ "${PARALLEL:-0}" = "1" ]; then
  if [ "$SUPABASE_RUNTIME" = "compose" ]; then
    check_container_bg "Supabase PostgREST" "pmoves-supabase-postgrest-1" "$WAIT_T_LONG"
    check_container_bg "Supabase Studio" "pmoves-supabase-studio-1" "$WAIT_T_LONG"
  else
    check_http_bg "Supabase REST" "$SUPABASE_REST_READY_URL" "$WAIT_T_LONG"
    check_http_bg "Supabase Studio" "$SUPABASE_STUDIO_READY_URL" "$WAIT_T_SHORT"
  fi
  check_http_bg "Hi-RAG v2 CPU" "http://localhost:${HIRAG_V2_HOST_PORT:-8086}/" "$WAIT_T_MED"
  check_http_bg "Hi-RAG v2 GPU" "http://localhost:${HIRAG_V2_GPU_HOST_PORT:-8087}/" "$WAIT_T_LONG"
  # Use lightweight readiness for bring-up. Deep dependency checks are covered
  # later by archon-smoke / archon-rest-policy-smoke in verify-all.
  check_http_bg "Archon API" "http://localhost:8091/api/health" "$WAIT_T_MED"
  check_http_bg "Archon UI" "http://localhost:3737" "$WAIT_T_SHORT"
  check_http_bg "Archon MCP" "http://localhost:8091/mcp/describe" "$WAIT_T_SHORT"
  check_http_bg "Agent Zero API" "http://localhost:8080/healthz" "$WAIT_T_SHORT"
  check_http_bg "Agent Zero UI" "http://localhost:8081" "$WAIT_T_SHORT"
  check_http_bg "Agent Zero Env" "http://localhost:8080/config/environment" "$WAIT_T_SHORT"
  check_http_bg "Agent Zero MCP" "http://localhost:8080/mcp/commands" "$WAIT_T_SHORT"
  check_http_bg "PMOVES.YT" "http://localhost:8077/healthz" "$WAIT_T_SHORT"
  check_http_bg "Grafana" "http://localhost:3002" "$WAIT_T_SHORT"
  check_http_bg "Loki /ready" "http://localhost:3100/ready" "$WAIT_T_SHORT"
  check_container_bg "Channel Monitor" "pmoves-channel-monitor-1" "$WAIT_T_SHORT"
  check_http_bg "Monitor Status" "http://localhost:8097/api/monitor/status" "$WAIT_T_SHORT"
  check_http_bg "yt-dlp catalog" "${YTB}/yt/docs/catalog" "$WAIT_T_SHORT"
  if [ "${RUN_UI_DEV}" = "1" ]; then
    check_http_bg "Console UI" "http://localhost:3001" "$WAIT_T_LONG"
  fi
  check_http_bg "n8n UI" "http://localhost:5678" "$WAIT_T_SHORT"
  check_http_bg "TensorZero UI" "http://localhost:4000" "$WAIT_T_SHORT"
  check_http_bg "TensorZero GW" "http://localhost:3030/metrics" "$WAIT_T_SHORT"
  if [ "${ENABLE_JELLYFIN_AI}" = "1" ]; then
    check_http_bg "Jellyfin" "http://localhost:9096" "$WAIT_T_SHORT"
  fi
  check_container_bg "Presign" "pmoves-presign-1" "$WAIT_T_SHORT"
  check_container_bg "Firefly" "pmoves-firefly" "$WAIT_T_SHORT"
  check_container_bg "Wger" "pmoves-wger-nginx" "$WAIT_T_SHORT"
  check_container_bg "Open Notebook" "pmoves-open-notebook-ext-1" "$WAIT_T_SHORT"
  ready_barrier
  wait_prom_targets "$WAIT_T_MED" || TIMEOUT_SERVICES+=("Prometheus targets")
else
  if [ "$SUPABASE_RUNTIME" = "compose" ]; then
    wait_container_ready "pmoves-supabase-postgrest-1" $WAIT_T_LONG || TIMEOUT_SERVICES+=("Supabase PostgREST")
    wait_container_ready "pmoves-supabase-studio-1" $WAIT_T_LONG || TIMEOUT_SERVICES+=("Supabase Studio")
  else
    wait_http "$SUPABASE_REST_READY_URL" $WAIT_T_LONG || TIMEOUT_SERVICES+=("Supabase REST")
    wait_http "$SUPABASE_STUDIO_READY_URL" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Supabase Studio")
  fi
  wait_http "http://localhost:${HIRAG_V2_HOST_PORT:-8086}/" $WAIT_T_MED || TIMEOUT_SERVICES+=("Hi-RAG v2 CPU")
  wait_http "http://localhost:${HIRAG_V2_GPU_HOST_PORT:-8087}/" $WAIT_T_LONG || TIMEOUT_SERVICES+=("Hi-RAG v2 GPU")
  wait_container_ready "pmoves-presign-1" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Presign")
  wait_http "http://localhost:8091/api/health" $WAIT_T_MED || TIMEOUT_SERVICES+=("Archon API")
  wait_http "http://localhost:3737" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Archon UI")
  wait_http "http://localhost:8091/mcp/describe" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Archon MCP")
  wait_http "http://localhost:8080/healthz" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Agent Zero API")
  wait_http "http://localhost:8081" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Agent Zero UI")
  wait_http "http://localhost:8080/config/environment" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Agent Zero Env")
  wait_http "http://localhost:8080/mcp/commands" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Agent Zero MCP")
  wait_http "http://localhost:8077/healthz" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("PMOVES.YT")
  wait_http "http://localhost:3002" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Grafana")
  wait_http "http://localhost:3100/ready" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Loki")
  wait_prom_targets $WAIT_T_MED || TIMEOUT_SERVICES+=("Prometheus targets")
  wait_container_ready "pmoves-channel-monitor-1" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Channel Monitor")
  wait_http "http://localhost:8097/api/monitor/status" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Monitor Status API")
  wait_http "${YTB}/yt/docs/catalog" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("yt-dlp catalog")
  if [ "${RUN_UI_DEV}" = "1" ]; then
    if ! wait_http "http://localhost:3001" $WAIT_T_LONG; then
      echo "⚠ Console UI not responding on :3001; recent dev log:"
      tail -n 80 ui/.pmoves_ui_dev.log 2>/dev/null || echo "  (No log file found)"
      TIMEOUT_SERVICES+=("Console UI")
    fi
  fi
  wait_http "http://localhost:5678" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("n8n UI")
  wait_http "http://localhost:4000" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("TensorZero UI")
  wait_http "http://localhost:3030/metrics" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("TensorZero GW")
  if [ "${ENABLE_JELLYFIN_AI}" = "1" ]; then
    wait_http "http://localhost:9096" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Jellyfin")
  fi
  wait_container_ready "pmoves-firefly" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Firefly")
  wait_container_ready "pmoves-wger-nginx" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Wger")
  wait_container_ready "pmoves-open-notebook-ext-1" $WAIT_T_SHORT || TIMEOUT_SERVICES+=("Open Notebook")
fi

echo "⛳ Capturing evidence"
# Ensure PMOVES.YT docs are fresh before capture
if ! make yt-docs-sync; then
  echo "⚠ yt-docs-sync failed; continuing with stack validation"
  TIMEOUT_SERVICES+=("yt-docs-sync")
fi
if ! make evidence-auto; then
  echo "⚠ evidence-auto failed; continuing with stack validation"
  TIMEOUT_SERVICES+=("evidence-auto")
fi

echo "⛳ Retro preflight summary (parallel table)"
PMOVES_RETRO_TIMEOUT=5 python3 tools/flight_check_retro.py

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
    if [ "${RUN_UI_DEV}" = "1" ]; then
      echo "   Console:    http://localhost:3001"
    fi
    echo "   Grafana:    http://localhost:3002"
    echo "   Agent Zero: http://localhost:8081"
    echo "   Archon:     http://localhost:3737"
    echo ""
fi

echo "═══════════════════════════════════════════════════════════"
