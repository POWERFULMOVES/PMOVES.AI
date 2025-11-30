#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

WAIT_T_SHORT=${WAIT_T_SHORT:-60}
WAIT_T_MED=${WAIT_T_MED:-120}
WAIT_T_LONG=${WAIT_T_LONG:-180}

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
  echo "⏳ Parallel readiness — waiting on ${{#READY_CMDS[@]}} checks"
  local rc=0
  for entry in "${READY_CMDS[@]}"; do
    IFS='|' read -r name url out pid to <<<"$entry"
    if wait "$pid"; then status="OK"; else status="TIMEOUT"; rc=1; fi
    if [ -f "$out" ]; then status=$(cat "$out"); fi
    printf "  • %-24s %-60s %s\n" "$name" "$url" "$status"
  done
  rm -rf "$READY_TMP_DIR" || true
  return $rc
}

echo "⛳ Bootstrap env + Supabase CLI"
make ensure-env-shared >/dev/null 2>&1 || true
make supa-start
make supabase-bootstrap || true

echo "⛳ Start core services"
make up

echo "⛳ Start agents (APIs + UIs)"
if [ "${PUBLISHED_AGENTS:-0}" = "1" ]; then
  make up-agents-published || true
else
  make up-agents-ui || true
fi

echo "⛳ Start external stacks"
make up-external || true

echo "⛳ Start yt + invidious + channel-monitor"
make up-yt || true
make up-invidious || true
make channel-monitor-up || true

echo "⛳ Start optional media analyzers + tensorzero + n8n + Jellyfin AI"
make up-media || true
make up-tensorzero || true
make up-n8n || true
make up-jellyfin-ai || true

echo "⛳ Start monitoring"
make up-monitoring || true

echo "⛳ Start Console UI (dev)"
make ui-dev-start || true

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
  check_http_bg "TensorZero GW" "http://localhost:3000" "$WAIT_T_SHORT"
  check_http_bg "Jellyfin" "http://localhost:8096" "$WAIT_T_SHORT"
  check_http_bg "Firefly" "http://localhost:8082" "$WAIT_T_SHORT"
  check_http_bg "Wger" "http://localhost:8000" "$WAIT_T_SHORT"
  check_http_bg "Open Notebook" "http://localhost:8503" "$WAIT_T_SHORT"
  check_http_bg "Supabase Studio" "http://127.0.0.1:65433" "$WAIT_T_SHORT"
  ready_barrier || true
  wait_prom_targets "$WAIT_T_MED" || true
else
  wait_http "http://127.0.0.1:65421/rest/v1" $WAIT_T_LONG || true
  wait_http "http://localhost:${HIRAG_V2_HOST_PORT:-8086}/" $WAIT_T_MED || true
  wait_http "http://localhost:${HIRAG_V2_GPU_HOST_PORT:-8087}/" $WAIT_T_LONG || true
  wait_http "http://localhost:8088/healthz" $WAIT_T_SHORT || true
  wait_http "http://localhost:8091/healthz" $WAIT_T_SHORT || true
  wait_http "http://localhost:3737" $WAIT_T_SHORT || true
  wait_http "http://localhost:8091/mcp/describe" $WAIT_T_SHORT || true
  wait_http "http://localhost:8080/healthz" $WAIT_T_SHORT || true
  wait_http "http://localhost:8081" $WAIT_T_SHORT || true
  wait_http "http://localhost:8080/config/environment" $WAIT_T_SHORT || true
  wait_http "http://localhost:8080/mcp/commands" $WAIT_T_SHORT || true
  wait_http "http://localhost:8077/" $WAIT_T_SHORT || true
  wait_http "http://localhost:3002" $WAIT_T_SHORT || true
  wait_http "http://localhost:3100/ready" $WAIT_T_SHORT || true
  wait_prom_targets $WAIT_T_MED || true
  wait_http "http://localhost:8097/healthz" $WAIT_T_SHORT || true
  wait_http "http://localhost:8097/api/monitor/status" $WAIT_T_SHORT || true
  wait_http "${YTB}/yt/docs/catalog" $WAIT_T_SHORT || true
  if ! wait_http "http://localhost:3001" $WAIT_T_LONG; then \
    echo "⚠ Console UI not responding on :3001; recent dev log:"; \
    tail -n 80 ui/.pmoves_ui_dev.log 2>/dev/null || true; \
  fi
  wait_http "http://localhost:5678" $WAIT_T_SHORT || true
  wait_http "http://localhost:4000" $WAIT_T_SHORT || true
  wait_http "http://localhost:3000" $WAIT_T_SHORT || true
  wait_http "http://localhost:8096" $WAIT_T_SHORT || true
  wait_http "http://localhost:8082" $WAIT_T_SHORT || true
  wait_http "http://localhost:8000" $WAIT_T_SHORT || true
  wait_http "http://localhost:8503" $WAIT_T_SHORT || true
  wait_http "http://127.0.0.1:65433" $WAIT_T_SHORT || true
fi

echo "⛳ Capturing evidence"
# Ensure PMOVES.YT docs are fresh before capture
make yt-docs-sync || true
make evidence-auto || true

echo "⛳ Retro preflight summary (parallel table)"
PMOVES_RETRO_TIMEOUT=5 python3 pmoves/tools/flight_check_retro.py || true

echo "✔ Bring-up complete. Console: http://localhost:3001  Grafana: http://localhost:3002"
