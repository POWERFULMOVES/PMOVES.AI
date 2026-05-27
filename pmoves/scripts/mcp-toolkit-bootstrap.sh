#!/usr/bin/env bash
# Per-node bootstrap for Docker MCP Toolkit + the canonical PMOVES profile.
#
# Idempotent — safe to re-run. Verifies the Toolkit CLI, pulls the canonical
# profile OCI artifact, imports it locally. Does NOT connect any client (that
# step mutates per-client config and requires explicit authorization per
# pmoves/docs/operations/MCP_TOOLKIT.md § 4).
#
# Usage: bash pmoves/scripts/mcp-toolkit-bootstrap.sh
# Make target: make mcp-toolkit-bootstrap

set -euo pipefail

PROFILE_OCI_REF="${PMOVES_MCP_PROFILE_REF:-docker.io/darkxside/pmoves_5090_web:latest}"
PROFILE_ID="${PMOVES_MCP_PROFILE_ID:-pmoves_5090_web}"
MIN_TOOLKIT_VERSION="${PMOVES_MCP_TOOLKIT_MIN:-v0.42.0}"

color() { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
info() { color "1;34" "[mcp-bootstrap] $*"; }
warn() { color "1;33" "[mcp-bootstrap] WARN: $*" >&2; }
fail() { color "1;31" "[mcp-bootstrap] FAIL: $*" >&2; exit 1; }

info "Verifying docker mcp CLI presence"
if ! command -v docker >/dev/null 2>&1; then
  fail "docker not on PATH. Install Docker Desktop (Windows/macOS) or Docker Engine + buildx (Linux)."
fi

if ! docker mcp version >/dev/null 2>&1; then
  fail "Docker MCP Toolkit plugin not installed. Enable MCP Toolkit in Docker Desktop settings, or install docker-mcp-plugin manually."
fi

ACTUAL_VERSION="$(docker mcp version 2>&1 | head -1 | tr -d '[:space:]')"
info "docker mcp version: ${ACTUAL_VERSION} (floor: ${MIN_TOOLKIT_VERSION})"
# Best-effort floor check — alphasort works for vMAJOR.MINOR.PATCH up to two-digit components.
if [ "$(printf '%s\n%s\n' "${MIN_TOOLKIT_VERSION}" "${ACTUAL_VERSION}" | sort -V | head -1)" != "${MIN_TOOLKIT_VERSION}" ]; then
  warn "Toolkit version below pinned floor (${MIN_TOOLKIT_VERSION}). Profile import may still work but supply-chain audit is recommended before continuing."
fi

REFRESH="${PMOVES_MCP_REFRESH:-0}"

info "Checking whether profile '${PROFILE_ID}' is already imported"
if docker mcp profile ls 2>/dev/null | awk 'NR>1 {print $1}' | grep -Fxq "${PROFILE_ID}"; then
  if [ "${REFRESH}" = "1" ]; then
    info "Profile '${PROFILE_ID}' present — refreshing (PMOVES_MCP_REFRESH=1): removing then re-pulling"
    docker mcp profile remove "${PROFILE_ID}" >/dev/null || warn "remove returned non-zero — continuing"
  else
    info "Profile '${PROFILE_ID}' already present — skipping pull (re-run with PMOVES_MCP_REFRESH=1 to force re-pull)"
    PULL_SKIPPED=1
  fi
fi

if [ "${PULL_SKIPPED:-0}" != "1" ]; then
  info "Pulling profile artifact: ${PROFILE_OCI_REF}"
  if ! docker mcp profile pull "${PROFILE_OCI_REF}"; then
    fail "Failed to pull profile from ${PROFILE_OCI_REF}. Check Docker Hub credentials and network."
  fi
fi

info "Verifying profile is importable"
if ! docker mcp profile show "${PROFILE_ID}" >/dev/null 2>&1; then
  fail "Profile '${PROFILE_ID}' not visible after pull. Inspect with: docker mcp profile ls"
fi

info "Bootstrap complete. Profile '${PROFILE_ID}' is available."
echo
echo "Next steps:"
echo "  • Populate secrets non-interactively: make mcp-toolkit-secrets-sync"
echo "  • Inspect connection state:           make mcp-toolkit-status"
echo "  • Connect Claude Code to profile:     docker mcp client connect claude-code --profile ${PROFILE_ID}"
echo "    (this mutates .claude/mcp.json — review the diff before committing)"
echo
echo "OAuth-mediated Cloudflare servers (13 of 25) need a one-time interactive"
echo "browser authorize per node. See pmoves/docs/operations/MCP_TOOLKIT.md § 5."
