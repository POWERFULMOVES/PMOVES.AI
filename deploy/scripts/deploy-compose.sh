#!/usr/bin/env bash
#
# deploy-compose.sh
#
# Docker Compose launcher for PMOVES local dev / PBnJ.
# Includes secrets-funnel pre-flight and post-deploy health checks.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MONO_ROOT="$(cd "${DEPLOY_ROOT}/.." && pwd)"
PMOVES_DIR="${MONO_ROOT}/pmoves"

# Allow overriding compose file and project name via env.
COMPOSE_FILE="${PMOVES_COMPOSE_FILE:-${PMOVES_DIR}/docker-compose.yml}"
PROJECT_NAME="${PMOVES_COMPOSE_PROJECT:-pmoves_local}"

# Health-check endpoints (service:port/path)
HEALTH_ENDPOINTS=(
  "agent-zero:8080/healthz"
  "archon:8091/healthz"
  "jellyfin-bridge:8093/healthz"
  "flute-gateway:8055/healthz"
  "media-video:8079/healthz"
  "extract-worker:8083/healthz"
)
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-5}"
STRICT="${STRICT:-false}"

usage() {
  cat <<EOF
PMOVES Docker Compose deploy script

Usage:
  $(basename "$0") {up|down|logs|health} [--strict]

Commands:
  up      Start local stack (detached) with pre-flight checks
  down    Stop stack and remove containers
  logs    Tail logs for all services
  health  Check health of running services

Options:
  --strict  Fail hard if secrets-funnel fails (default: warn and continue)

Env overrides:
  PMOVES_COMPOSE_FILE    Path to docker-compose file (default: ${COMPOSE_FILE})
  PMOVES_COMPOSE_PROJECT Docker Compose project name (default: ${PROJECT_NAME})
  HEALTH_TIMEOUT         Health check timeout in seconds (default: 5)
  SKIP_SECRETS_FUNNEL    Set to 1 to skip secrets-funnel pre-flight
EOF
}

ensure_compose() {
  if command -v docker compose >/dev/null 2>&1; then
    DOCKER_COMPOSE_BIN=("docker" "compose")
  elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE_BIN=("docker-compose")
  else
    echo "ERROR: docker compose or docker-compose is required but not found in PATH" >&2
    exit 1
  fi
}

ensure_files() {
  if [ ! -d "${PMOVES_DIR}" ]; then
    echo "ERROR: pmoves/ directory not found at ${PMOVES_DIR}" >&2
    exit 1
  fi

  if [ ! -f "${COMPOSE_FILE}" ]; then
    echo "ERROR: docker-compose file not found: ${COMPOSE_FILE}" >&2
    exit 1
  fi
}

preflight_env() {
  # Verify env.shared exists
  if [ ! -f "${PMOVES_DIR}/env.shared" ]; then
    echo "ERROR: pmoves/env.shared not found." >&2
    echo "  Run: make -C pmoves secrets-funnel" >&2
    exit 1
  fi
}

SECRETS_FUNNEL_OK=true

run_secrets_funnel() {
  if [ "${SKIP_SECRETS_FUNNEL:-0}" = "1" ]; then
    echo "  Skipping secrets-funnel (SKIP_SECRETS_FUNNEL=1)"
    return 0
  fi

  if [ -f "${PMOVES_DIR}/Makefile" ] && command -v make >/dev/null 2>&1; then
    if make -C "${PMOVES_DIR}" -n secrets-funnel >/dev/null 2>&1; then
      echo "  Running secrets-funnel..."
      if ! make -C "${PMOVES_DIR}" secrets-funnel; then
        SECRETS_FUNNEL_OK=false
        if [ "${STRICT}" = "true" ]; then
          echo "ERROR: secrets-funnel failed (--strict mode)" >&2
          exit 1
        fi
        echo "WARNING: secrets-funnel failed, continuing with existing env files" >&2
      fi
    fi
  fi
}

cmd_health() {
  echo "  Checking service health..."
  local pass=0 fail=0 skip=0
  for entry in "${HEALTH_ENDPOINTS[@]}"; do
    local svc="${entry%%:*}"
    local port_path="${entry#*:}"
    local port="${port_path%%/*}"
    local path="/${port_path#*/}"

    local url="http://127.0.0.1:${port}${path}"
    if curl -sf --max-time "${HEALTH_TIMEOUT}" "${url}" >/dev/null 2>&1; then
      echo "    [PASS] ${svc} (${url})"
      ((pass++)) || true
    else
      # Check if container is even running
      if "${DOCKER_COMPOSE_BIN[@]}" -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" ps --format json 2>/dev/null | grep -q "\"${svc}\""; then
        echo "    [FAIL] ${svc} (${url})"
        ((fail++)) || true
      else
        echo "    [SKIP] ${svc} (not running)"
        ((skip++)) || true
      fi
    fi
  done
  echo ""
  echo "  Health: ${pass} pass, ${fail} fail, ${skip} skip"
  return "${fail}"
}

cmd_up() {
  echo "=> Starting PMOVES local stack"
  echo "   Compose file: ${COMPOSE_FILE}"
  echo "   Project:      ${PROJECT_NAME}"

  # Pre-flight checks
  preflight_env
  run_secrets_funnel

  echo "  Launching containers..."
  "${DOCKER_COMPOSE_BIN[@]}" -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" up -d

  echo ""
  echo "  Waiting 10s for services to initialize..."
  sleep 10

  # Post-deploy health check (non-fatal)
  cmd_health || echo "  Some services unhealthy — check logs with: $(basename "$0") logs"

  echo ""
  if [ "${SECRETS_FUNNEL_OK}" = "false" ]; then
    echo "  WARNING: secrets-funnel failed during pre-flight"
  fi
  echo "=> Stack started. Project: ${PROJECT_NAME}"
}

cmd_down() {
  echo "=> Stopping PMOVES local stack"
  echo "   Project: ${PROJECT_NAME}"

  "${DOCKER_COMPOSE_BIN[@]}" -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" down
}

cmd_logs() {
  echo "=> Tailing logs for PMOVES local stack"
  echo "   Project: ${PROJECT_NAME}"

  "${DOCKER_COMPOSE_BIN[@]}" -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" logs -f
}

main() {
  if [ $# -lt 1 ]; then
    usage
    exit 2
  fi

  local cmd="$1"; shift || true

  # Parse remaining flags
  while [ $# -gt 0 ]; do
    case "$1" in
      --strict) STRICT=true; shift;;
      *) echo "Unknown flag: $1" >&2; usage; exit 2;;
    esac
  done

  ensure_compose
  ensure_files

  case "${cmd}" in
    up)
      cmd_up
      ;;
    down)
      cmd_down
      ;;
    logs)
      cmd_logs
      ;;
    health)
      cmd_health
      ;;
    *)
      echo "ERROR: Unknown command: ${cmd}" >&2
      usage
      exit 2
      ;;
  esac
}

main "$@"
