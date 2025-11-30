#!/usr/bin/env bash
set -euo pipefail

STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
OUT_DIR="pmoves/PR_EVIDENCE"
MD_FILE="$OUT_DIR/${STAMP}_auto_capture.md"
LOG_FILE="$OUT_DIR/${STAMP}_auto_capture.txt"
mkdir -p "$OUT_DIR"

YTB="${PMOVES_YT_BASE_URL:-http://localhost:8077}"
GPU_PORT="${HIRAG_V2_GPU_HOST_PORT:-8087}"
CPU_PORT="${HIRAG_V2_HOST_PORT:-8086}"
PROM_PORT="${PROMETHEUS_HOST_PORT:-9090}"

echo "# Auto Evidence Capture ($STAMP)" > "$MD_FILE"
echo "" >> "$MD_FILE"
echo "Outputs stored in $LOG_FILE" >> "$MD_FILE"
echo "" >> "$MD_FILE"

log() { echo "$*" | tee -a "$LOG_FILE"; }
section() { echo -e "\n## $*\n" | tee -a "$LOG_FILE" >> "$MD_FILE"; }
block() {
  local title="$1"; shift
  echo -e "\n### $title\n" >> "$MD_FILE"
  echo '\n```' >> "$MD_FILE"
  cat >> "$MD_FILE"
  echo '\n```' >> "$MD_FILE"
}

curl_json() { # url label
  local url="$1"; local label="$2";
  section "$label"
  log "GET $url"
  if out=$(curl -m 5 -fsS "$url" 2>&1); then
    printf '%s' "$out" | jq . 2>/dev/null | tee -a "$LOG_FILE" || printf '%s' "$out" | tee -a "$LOG_FILE"
    printf '%s' "$out" | block "$label"
  else
    echo "ERROR" | tee -a "$LOG_FILE"
    printf 'Request failed for %s\n' "$url" | block "$label (error)"
  fi
}

curl_status() { # url label
  local url="$1"; local label="$2";
  section "$label"
  code=$(curl -m 5 -s -o /dev/null -w "%{http_code}" "$url" || true)
  log "$url -> HTTP $code"
  printf 'HTTP %s %s\n' "$code" "$url" | block "$label"
}

# Collects
curl_json "$YTB/yt/docs/catalog" "PMOVES.YT /yt/docs/catalog"
curl_json "$YTB/healthz" "PMOVES.YT /healthz"
section "PMOVES.YT /yt/docs/sync (POST)"
log "POST $YTB/yt/docs/sync"
sync_out=$(curl -m 10 -fsS -X POST "$YTB/yt/docs/sync" -H 'content-type: application/json' 2>&1 || true)
printf '%s' "$sync_out" | jq . 2>/dev/null | tee -a "$LOG_FILE" || printf '%s' "$sync_out" | tee -a "$LOG_FILE"
printf '%s' "$sync_out" | block "PMOVES.YT /yt/docs/sync"
curl_status "http://localhost:3100/ready" "Loki /ready"
curl_json "http://localhost:${GPU_PORT}/hirag/admin/stats" "Hi-RAG v2 GPU /hirag/admin/stats"
curl_json "http://localhost:${CPU_PORT}/hirag/admin/stats" "Hi-RAG v2 CPU /hirag/admin/stats"
curl_status "http://localhost:8088/healthz" "Presign /healthz"
curl_json "http://localhost:8097/api/monitor/status" "Channel Monitor /api/monitor/status"
curl_json "http://localhost:8097/api/monitor/stats" "Channel Monitor /api/monitor/stats"
section "Prometheus targets"
log "GET http://localhost:${PROM_PORT}/api/v1/targets"
pt=$(curl -m 5 -fsS "http://localhost:${PROM_PORT}/api/v1/targets" 2>/dev/null || true)
printf '%s' "$pt" | jq . 2>/dev/null | tee -a "$LOG_FILE" || printf '%s' "$pt" | tee -a "$LOG_FILE"
printf '%s' "$pt" | block "Prometheus /api/v1/targets"

section "PMOVES.YT /yt/download dry-run (test video)"
log "POST $YTB/yt/download (dry-run)"
read -r -d '' DRYJSON <<'JSON' || true
{
  "url": "https://www.youtube.com/watch?v=BaW_jenozKc",
  "namespace": "pmoves",
  "bucket": "assets",
  "format": "bv+ba/b",
  "yt_options": {
    "skip_download": true,
    "noplaylist": true,
    "write_info_json": false
  }
}
JSON
dry_out=$(curl -m 15 -fsS -X POST "$YTB/yt/download" -H 'content-type: application/json' -d "$DRYJSON" 2>&1 || true)
printf '%s' "$dry_out" | jq . 2>/dev/null | tee -a "$LOG_FILE" || printf '%s' "$dry_out" | tee -a "$LOG_FILE"
printf '%s' "$dry_out" | block "PMOVES.YT /yt/download (dry-run)"

echo "Evidence captured: $MD_FILE" | tee -a "$LOG_FILE"
