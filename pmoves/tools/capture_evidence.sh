#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
OUT_DIR="pmoves/PR_EVIDENCE/${STAMP}"
mkdir -p "$OUT_DIR"

probe() {
  local name="$1"
  local url="$2"
  local out="$OUT_DIR/${name}.txt"
  {
    echo "name=$name"
    echo "url=$url"
    echo "timestamp=$(date -Iseconds)"
    code="$(curl -s -o /tmp/pmoves_probe_body.$$ -w "%{http_code}" "$url" || true)"
    echo "http_code=$code"
    echo "--- body ---"
    cat /tmp/pmoves_probe_body.$$ 2>/dev/null || true
    rm -f /tmp/pmoves_probe_body.$$ 2>/dev/null || true
  } >"$out"
}

{
  echo "timestamp=$(date -Iseconds)"
  echo "cwd=$PWD"
} > "$OUT_DIR/meta.txt"

docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' > "$OUT_DIR/docker_ps.txt" || true

probe "agent_zero_health" "http://localhost:8080/healthz"
probe "archon_health" "http://localhost:8091/healthz"
probe "yt_catalog" "http://localhost:8077/yt/docs/catalog"
probe "hirag_v2_cpu" "http://localhost:8086/hirag/admin/stats"
probe "hirag_v2_gpu" "http://localhost:8087/hirag/admin/stats"
probe "channel_monitor_health" "http://localhost:8097/healthz"
probe "tensorzero_health" "http://localhost:3030/healthz"
probe "loki_ready" "http://localhost:3100/ready"

echo "✔ Evidence captured: $OUT_DIR"
