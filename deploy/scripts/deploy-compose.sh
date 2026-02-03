#!/usr/bin/env bash
#
# deploy-compose.sh
#
# Simple Docker Compose launcher for PMOVES local dev / PBnJ.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MONO_ROOT="$(cd "${DEPLOY_ROOT}/.." && pwd)"
PMOVES_DIR="${MONO_ROOT}/pmoves"

# Allow overriding compose file and project name via env.
COMPOSE_FILE="${PMOVES_COMPOSE_FILE:-${PMOVES_DIR}/docker-compose.yml}"
PROJECT_NAME="${PMOVES_COMPOSE_PROJECT:-pmoves_local}"

usage() {
  cat <<EOF
PMOVES Docker Compose deploy script

Usage:
  $(basename "$0") {up|down|logs}

Commands:
  up      Start local stack (detached)
  down    Stop stack and remove containers
  logs    Tail logs for all services

Env overrides:
  PMOVES_COMPOSE_FILE    Path to docker-compose file (default: ${COMPOSE_FILE})
  PMOVES_COMPOSE_PROJECT Docker Compose project name (default: ${PROJECT_NAME})
EOF
}

ensure_compose() {
  if command -v docker compose >/dev/null 2>&1; then
    DOCKER_COMPOSE_BIN=("docker" "compose")
  elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE_BIN=("docker-compose")
  else
    echo "✖ docker compose or docker-compose is required but not found in PATH" >&2
    exit 1
  fi
}

ensure_files() {
  if [ ! -d "${PMOVES_DIR}" ]; then
    echo "✖ pmoves/ directory not found at ${PMOVES_DIR}" >&2
    exit 1
  fi

  if [ ! -f "${COMPOSE_FILE}" ]; then
    echo "✖ docker-compose file not found: ${COMPOSE_FILE}" >&2
    exit 1
  fi
}

cmd_up() {
  echo "➜ Starting PMOVES local stack"
  echo "   Compose file: ${COMPOSE_FILE}"
  echo "   Project:      ${PROJECT_NAME}"

  "${DOCKER_COMPOSE_BIN[@]}" -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" up -d
}

cmd_down() {
  echo "➜ Stopping PMOVES local stack"
  echo "   Project: ${PROJECT_NAME}"

  "${DOCKER_COMPOSE_BIN[@]}" -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" down
}

cmd_logs() {
  echo "➜ Tailing logs for PMOVES local stack"
  echo "   Project: ${PROJECT_NAME}"

  "${DOCKER_COMPOSE_BIN[@]}" -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" logs -f
}

main() {
  if [ $# -lt 1 ]; then
    usage
    exit 2
  fi

  local cmd="$1"; shift || true

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
    *)
      echo "✖ Unknown command: ${cmd}" >&2
      usage
      exit 2
      ;;
  esac
}

main "$@"
