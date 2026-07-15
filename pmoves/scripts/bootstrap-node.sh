#!/usr/bin/env bash
# bootstrap-node.sh — §1463 PR-A: idempotent node bootstrap
#
# Enrolls a node into the PMOVES mesh: Tailscale, Docker network, NATS health,
# runner label assignment, and mesh announce. Safe to re-run at any time.
#
# Usage:
#   bash pmoves/scripts/bootstrap-node.sh --node-id pmoves-rdna4 --profile rdna4-workstation
#
# Environment variables (optional):
#   TAILSCALE_AUTHKEY   — auto-enroll Tailscale (skip step if unset)
#   NATS_URL            — NATS server URL (default: nats://localhost:4222)
#   RUNNER_TOKEN        — GitHub Actions runner token (skip step if unset)
#
# Exit codes: 0 = fully enrolled (or all skippable steps skipped), 1 = fatal error, 2 = docker not available

set -euo pipefail

# ── helpers ───────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[0;33m'
DIM='\033[2m'
RST='\033[0m'

ok()       { echo -e "  ${GRN}✔${RST}  $*"; }
fail()     { echo -e "  ${RED}✗${RST}  $*"; ERRORS=$((ERRORS+1)); }
warn()     { echo -e "  ${YLW}⚠${RST}  $*"; WARNINGS=$((WARNINGS+1)); }
info()     { echo -e "  ${DIM}ℹ${RST}  $*"; }
dim()      { echo -e "${DIM}     $*${RST}"; }
ok_sum()   { echo -e "  ${GRN}✔${RST}  $*"; }
fail_sum() { echo -e "  ${RED}✗${RST}  $*"; }
warn_sum() { echo -e "  ${YLW}⚠${RST}  $*"; }

ERRORS=0
WARNINGS=0

# ── argument parsing ──────────────────────────────────────────────────────────

NODE_ID=""
PROFILE=""

usage() {
  echo ""
  echo "Usage: bash pmoves/scripts/bootstrap-node.sh --node-id <id> --profile <profile>"
  echo ""
  echo "Options:"
  echo "  --node-id   <id>       Node identifier (e.g. pmoves-rdna4)"
  echo "  --profile   <name>     Profile name (must exist at pmoves/config/profiles/<name>.yaml)"
  echo "  --help                 Show this help"
  echo ""
  echo "Environment variables:"
  echo "  TAILSCALE_AUTHKEY      Auto-enroll Tailscale (skipped if unset)"
  echo "  NATS_URL               NATS server URL (default: nats://localhost:4222)"
  echo "  RUNNER_TOKEN           GitHub Actions runner token (skipped if unset)"
  echo ""
  echo "Exit codes:"
  echo "  0  Fully enrolled (or all skippable steps skipped with warnings)"
  echo "  1  Profile missing or other fatal error"
  echo "  2  Docker not available"
  echo ""
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --node-id)
      [[ "${2:-}" == --* ]] && { echo "ERROR: --node-id requires a value" >&2; exit 1; }
      NODE_ID="${2:-}"; shift 2 ;;
    --profile)
      [[ "${2:-}" == --* ]] && { echo "ERROR: --profile requires a value" >&2; exit 1; }
      PROFILE="${2:-}"; shift 2 ;;
    --help|-h)  usage; exit 0 ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$NODE_ID" ]] || [[ -z "$PROFILE" ]]; then
  echo "ERROR: --node-id and --profile are required" >&2
  usage >&2
  exit 1
fi

if [[ ! "$NODE_ID" =~ ^[a-zA-Z0-9_-]+$ ]]; then
  echo "ERROR: --node-id '$NODE_ID' contains invalid characters (use [a-zA-Z0-9_-] only)" >&2
  exit 1
fi
if [[ ! "$PROFILE" =~ ^[a-zA-Z0-9_-]+$ ]]; then
  echo "ERROR: --profile '$PROFILE' contains invalid characters (use [a-zA-Z0-9_-] only)" >&2
  exit 1
fi

# ── locate repo root ──────────────────────────────────────────────────────────

# Resolve repo root: script lives at <root>/pmoves/scripts/bootstrap-node.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── banner ────────────────────────────────────────────────────────────────────

echo ""
echo "=== PMOVES Node Bootstrap ==="
echo ""
dim "node-id : $NODE_ID"
dim "profile : $PROFILE"
dim "repo    : $REPO_ROOT"
dim "nats    : ${NATS_URL:-nats://localhost:4222}"

# ── Step 1 — Tailscale enrollment check ───────────────────────────────────────

echo ""
echo "=== Step 1: Tailscale Enrollment ==="

if ! command -v tailscale >/dev/null 2>&1; then
  warn "tailscale CLI not found — skipping enrollment"
else
  ts_status=$(tailscale status 2>/dev/null || true)
  if echo "$ts_status" | grep -qF "$NODE_ID"; then
    ok "Tailscale: $NODE_ID already enrolled"
  else
    if [[ -z "${TAILSCALE_AUTHKEY:-}" ]]; then
      warn "TAILSCALE_AUTHKEY not set — skipping Tailscale enrollment"
      dim "Set TAILSCALE_AUTHKEY to auto-enroll, or run: sudo tailscale up --hostname=$NODE_ID"
    else
      info "Enrolling '$NODE_ID' in tailnet..."
      if tailscale up --auth-key="$TAILSCALE_AUTHKEY" --hostname="$NODE_ID"; then
        ok "Tailscale: enrolled as $NODE_ID"
      else
        fail "tailscale up failed — check auth key and tailscaled status"
      fi
    fi
  fi
fi

# ── Step 2 — Profile file existence check ─────────────────────────────────────

echo ""
echo "=== Step 2: Profile Validation ==="

PROFILE_PATH="${REPO_ROOT}/pmoves/config/profiles/${PROFILE}.yaml"

if [[ -f "$PROFILE_PATH" ]]; then
  ok "Profile found: pmoves/config/profiles/${PROFILE}.yaml"
else
  echo -e "  ${RED}✗${RST}  ERROR: Profile not found: pmoves/config/profiles/${PROFILE}.yaml" >&2
  echo "" >&2
  echo "  Run: python deploy/provision/json-to-profile.py --node-id $NODE_ID --profile $PROFILE to generate it" >&2
  echo "" >&2
  exit 1
fi

# ── Step 3 — Docker network pre-flight ───────────────────────────────────────

echo ""
echo "=== Step 3: Docker Network Pre-flight ==="

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: docker not available or daemon not running" >&2
  exit 2
fi

if docker network inspect pmoves_bus >/dev/null 2>&1; then
  actual_subnet=$(docker network inspect pmoves_bus --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null || echo "unknown")
  if [[ "$actual_subnet" == "172.30.3.0/24" ]]; then
    ok "pmoves_bus network already exists (subnet=$actual_subnet)"
  else
    warn "pmoves_bus exists but subnet mismatch: got=$actual_subnet expected=172.30.3.0/24"
  fi
else
  info "Creating pmoves_bus network (172.30.3.0/24, internal)..."
  if docker network create --driver bridge --subnet 172.30.3.0/24 --internal pmoves_bus; then
    ok "pmoves_bus network created — subnet=172.30.3.0/24"
  else
    fail "docker network create pmoves_bus failed — check Docker daemon"
    exit 1
  fi
fi

# ── Step 4 — NATS connectivity probe ─────────────────────────────────────────

echo ""
echo "=== Step 4: NATS Connectivity Probe ==="

if command -v nats >/dev/null 2>&1; then
    if nats server ping --server "${NATS_URL:-nats://localhost:4222}" 2>/dev/null; then
        ok "NATS connectivity: server ping OK"
    else
        warn "NATS server ping failed — NATS may not be running (non-fatal)"
    fi
else
    warn "nats CLI not found — skipping NATS connectivity probe"
fi

# ── Step 5 — Runner label assignment ─────────────────────────────────────────

echo ""
echo "=== Step 5: Runner Label Assignment ==="

if [[ -n "${RUNNER_TOKEN:-}" ]]; then
  info "RUNNER_TOKEN set — runner registration is manual via GitHub UI or gh CLI"
  dim "gh CLI example:"
  dim "  gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners/registration-token --method POST"
  dim "  ./config.sh --url https://github.com/POWERFULMOVES/PMOVES.AI --token <token> --labels $NODE_ID,$PROFILE"
  warn "RUNNER_TOKEN set but runner registration is manual — see commands above"
else
  dim "RUNNER_TOKEN not set — skipping runner registration"
fi

# ── Step 6 — Mesh announce ───────────────────────────────────────────────────

echo ""
echo "=== Step 6: Mesh Announce ==="

PAYLOAD="{\"node_id\":\"$NODE_ID\",\"profile\":\"$PROFILE\",\"status\":\"online\",\"ts\":$(date +%s)}"

if ! command -v nats >/dev/null 2>&1; then
  warn "nats CLI not found — mesh announce skipped"
  dim "Install nats CLI to enable automatic mesh announce on bootstrap"
else
  info "Publishing mesh.node.announce.v1..."
  dim "payload: $PAYLOAD"
  if echo "$PAYLOAD" | nats pub --server "${NATS_URL:-nats://localhost:4222}" mesh.node.announce.v1; then
    ok "Mesh announce published — subject=mesh.node.announce.v1"
  else
    warn "nats pub failed — NATS may not be running; announce skipped"
    dim "Re-run bootstrap once NATS is up to announce this node"
  fi
fi

# ── Step 7 — MCP bootstrap ───────────────────────────────────────────────────

echo ""
echo "=== Step 7: MCP Bootstrap ==="

if [[ "${PMOVES_BOOTSTRAP_MCPS:-1}" == "0" ]]; then
  info "PMOVES_BOOTSTRAP_MCPS=0 — skipping MCP bootstrap"
else
  info "Running PMOVES MCP bootstrap (set PMOVES_BOOTSTRAP_MCPS=0 to skip)..."
  if make -C "${REPO_ROOT}/pmoves" --no-print-directory mcp-bootstrap; then
    ok "MCP bootstrap complete"
  else
    warn "MCP bootstrap reported errors — some clients may need manual configuration"
    dim "Inspect with: make -C pmoves mcp-bootstrap-check"
  fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "=== Summary ==="

if [[ $ERRORS -eq 0 ]] && [[ $WARNINGS -eq 0 ]]; then
  ok_sum "Node '$NODE_ID' fully bootstrapped — all steps passed"
elif [[ $ERRORS -eq 0 ]]; then
  warn_sum "$WARNINGS warning(s) — node '$NODE_ID' bootstrapped with skipped steps (see above)"
else
  fail_sum "$ERRORS error(s) — bootstrap incomplete for node '$NODE_ID'"
  echo ""
  echo "  Re-run after resolving errors above."
fi

echo ""

[[ $ERRORS -gt 0 ]] && exit 1 || exit 0
