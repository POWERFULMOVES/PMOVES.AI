#!/usr/bin/env bash
# setup-runner.sh — Idempotent GitHub Actions runner registration on a target node
#
# Usage:
#   setup-runner.sh --target <user@host> [OPTIONS]
#
# Options:
#   --target HOST        SSH target (required)
#   --repo OWNER/REPO    GitHub repo (default: POWERFULMOVES/PMOVES.AI)
#   --lane LANE          Runner lane: ai-lab|vps|hotfix|<custom> (default: ai-lab)
#   --runner-name NAME   Override runner name (default: pmoves-<lane>-<hostname>)
#   --skip-docker-check  Skip Docker availability check on target
#   --dry-run            Print actions without executing
#
# Auth (checked in order):
#   GITHUB_PAT, GH_TOKEN, GITHUB_TOKEN  — PAT passed as ACCESS_TOKEN to runner container
#   (fallback) gh api registration token — short-lived (~1h), single-use
#
# Idempotency:
#   Case 1 — runner registered + online:   skip (no-op, exit 0)
#   Case 2 — runner registered + offline:  remove stale entry, re-register (exit 2)
#   Case 3 — runner not registered:        fresh register (exit 0)
#
# Exit codes:
#   0  success (registered or already healthy)
#   1  fatal (no auth, Docker unavailable, SSH unreachable)
#   2  drifted (stale removed + re-registered — caller should verify)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Defaults ---
TARGET=""
REPO="POWERFULMOVES/PMOVES.AI"
LANE="ai-lab"
RUNNER_NAME=""
SKIP_DOCKER_CHECK=false
DRY_RUN=false

# --- Arg parsing ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)             TARGET="$2"; shift 2 ;;
    --repo)               REPO="$2"; shift 2 ;;
    --lane)               LANE="$2"; shift 2 ;;
    --runner-name)        RUNNER_NAME="$2"; shift 2 ;;
    --skip-docker-check)  SKIP_DOCKER_CHECK=true; shift ;;
    --dry-run)            DRY_RUN=true; shift ;;
    *)                    echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "Usage: setup-runner.sh --target <user@host> [--repo OWNER/REPO] [--lane LANE]"
  echo ""
  echo "Lanes:  ai-lab (default)  vps  hotfix  <custom>"
  echo "Labels: ai-lab → self-hosted,ai-lab,gpu,Linux,X64"
  echo "        vps    → self-hosted,vps,Linux,X64"
  echo "        hotfix → self-hosted,hotfix,Linux,X64"
  echo "        other  → self-hosted,pmoves,<lane>,Linux,X64"
  exit 1
fi

# --- Helpers ---
PASS=0; FAIL=0; WARN=0

check() {
  local label="$1" status="$2" detail="${3:-}"
  if [[ "$status" == "pass" ]]; then
    echo "  PASS  $label${detail:+ — $detail}"
    PASS=$((PASS + 1))
  elif [[ "$status" == "warn" ]]; then
    echo "  WARN  $label${detail:+ — $detail}"
    WARN=$((WARN + 1))
  else
    echo "  FAIL  $label${detail:+ — $detail}"
    FAIL=$((FAIL + 1))
  fi
}

run_or_dry() {
  if $DRY_RUN; then
    echo "  [dry-run] $*"
  else
    "$@"
  fi
}

ssh_or_dry() {
  if $DRY_RUN; then
    echo "  [dry-run] ssh $TARGET: $*"
  else
    ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$TARGET" "$@"
  fi
}

# Derive hostname from target (strip user@ prefix)
TARGET_HOST="${TARGET##*@}"

# Derive runner name
if [[ -z "$RUNNER_NAME" ]]; then
  RUNNER_NAME="pmoves-${LANE}-${TARGET_HOST}"
fi

# Container name mirrors runner name
CONTAINER_NAME="pmoves-${LANE}-runner"

# Label mapping (matches local_cert_runners.py lanes 33-52)
case "$LANE" in
  ai-lab)  LABELS="self-hosted,ai-lab,gpu,Linux,X64" ;;
  vps)     LABELS="self-hosted,vps,Linux,X64" ;;
  hotfix)  LABELS="self-hosted,hotfix,Linux,X64" ;;
  *)       LABELS="self-hosted,pmoves,${LANE},Linux,X64" ;;
esac

echo "============================================"
echo "  PMOVES Runner Registration"
echo "============================================"
echo "  Target:  $TARGET"
echo "  Repo:    $REPO"
echo "  Lane:    $LANE"
echo "  Name:    $RUNNER_NAME"
echo "  Labels:  $LABELS"
$DRY_RUN && echo "  Mode:    DRY RUN (no changes)"
echo ""

# --- Pre-flight: gh CLI ---
echo "[pre-flight]"
if ! command -v gh > /dev/null 2>&1; then
  check "gh CLI" "fail" "not found — run: gh auth login"
  exit 1
fi
if ! gh auth status > /dev/null 2>&1; then
  check "gh auth" "fail" "not authenticated — run: gh auth login"
  exit 1
fi
check "gh CLI" "pass" "$(gh --version 2>/dev/null | head -1)"
echo ""

# --- Pre-flight: SSH ---
echo "[ssh]"
if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$TARGET" "echo ok" > /dev/null 2>&1; then
  check "SSH $TARGET" "fail" "unreachable"
  exit 1
fi
check "SSH $TARGET" "pass"
echo ""

# --- Pre-flight: Docker on target ---
echo "[docker]"
if ! $SKIP_DOCKER_CHECK; then
  if ssh_or_dry "which docker > /dev/null 2>&1" 2>/dev/null; then
    DOCKER_VER="unknown (dry-run)"
    $DRY_RUN || DOCKER_VER=$(ssh -o ConnectTimeout=5 "$TARGET" "docker --version 2>/dev/null" || echo "unknown")
    check "Docker on target" "pass" "$DOCKER_VER"
  else
    check "Docker on target" "fail" "not found — install Docker before registering runner"
    exit 1
  fi
else
  check "Docker check" "warn" "skipped (--skip-docker-check)"
fi
echo ""

# --- Auth resolution ---
echo "[auth]"
PAT=""
AUTH_MODE=""

for var in GITHUB_PAT GH_TOKEN GITHUB_TOKEN; do
  val="${!var:-}"
  if [[ -n "$val" && "$val" != "placeholder" && ${#val} -gt 10 ]]; then
    PAT="$val"
    AUTH_MODE="pat ($var)"
    break
  fi
done

if [[ -n "$PAT" ]]; then
  check "Auth" "pass" "$AUTH_MODE"
else
  check "Auth" "warn" "no PAT found — will use short-lived registration token"
  AUTH_MODE="registration-token"
fi
echo ""

# --- Check existing runner state ---
echo "[runner state]"
RUNNER_JSON=$(gh api "repos/${REPO}/actions/runners" --paginate 2>/dev/null | \
  jq -sc '[.[].runners[] | select(.name == "'"${RUNNER_NAME}"'")]' 2>/dev/null || echo "[]")

RUNNER_COUNT=$(echo "$RUNNER_JSON" | jq 'length')
RUNNER_ID=$(echo "$RUNNER_JSON" | jq -r '.[0].id // empty')
RUNNER_STATUS=$(echo "$RUNNER_JSON" | jq -r '.[0].status // empty')

if [[ "$RUNNER_COUNT" -gt 1 ]]; then
  check "Runner uniqueness" "warn" "$RUNNER_COUNT runners named '$RUNNER_NAME' — using first match"
fi

echo "  Runner '$RUNNER_NAME': count=$RUNNER_COUNT status=${RUNNER_STATUS:-none}"
echo ""

# --- Case routing ---
if [[ -n "$RUNNER_ID" && "$RUNNER_STATUS" == "online" ]]; then
  # Case 1: online — no-op
  echo "[case 1: online — skip]"
  check "Runner $RUNNER_NAME" "pass" "already online (id=$RUNNER_ID)"
  echo ""
  echo "=== Results: $PASS passed, $FAIL failed, $WARN warnings ==="
  exit 0

elif [[ -n "$RUNNER_ID" && "$RUNNER_STATUS" != "online" ]]; then
  # Case 2: drifted — remove + re-register
  echo "[case 2: offline/drifted — remove + re-register]"
  check "Stale runner detected" "warn" "status=$RUNNER_STATUS id=$RUNNER_ID"

  echo "  Removing stale runner entry from GitHub..."
  run_or_dry gh api --method DELETE "repos/${REPO}/actions/runners/${RUNNER_ID}"

  echo "  Removing old container on target..."
  ssh_or_dry "docker rm -f ${CONTAINER_NAME} > /dev/null 2>&1 || true"
  check "Stale cleanup" "pass"
  echo ""
  CASE=2

else
  # Case 3: not registered
  echo "[case 3: not registered — fresh register]"
  CASE=0
fi

# --- Get registration token ---
echo "[registration]"
REG_TOKEN=$(gh api --method POST "repos/${REPO}/actions/runners/registration-token" \
  --jq '.token' 2>/dev/null || true)

if [[ -z "$REG_TOKEN" ]]; then
  check "Registration token" "fail" "gh api call failed — check REPO and gh auth scopes"
  exit 1
fi
check "Registration token" "pass" "obtained (valid ~1h)"

# Choose env var name for auth in container
if [[ -n "$PAT" ]]; then
  AUTH_ENV_VAR="ACCESS_TOKEN"
  AUTH_VAL="$PAT"
else
  AUTH_ENV_VAR="RUNNER_TOKEN"
  AUTH_VAL="$REG_TOKEN"
fi

# --- Launch runner container on target ---
echo ""
echo "[container]"
VOLUME_PATH="\$HOME/.config/pmoves"

DOCKER_CMD="docker run -d \\
  --restart unless-stopped \\
  --name ${CONTAINER_NAME} \\
  -e RUNNER_ALLOW_RUNNER_REUSE=true \\
  -e REPO_URL=https://github.com/${REPO} \\
  -e RUNNER_NAME=${RUNNER_NAME} \\
  -e LABELS=${LABELS} \\
  -e RUNNER_WORKDIR=/tmp/runner-${LANE} \\
  -e ${AUTH_ENV_VAR} \\
  -v ${VOLUME_PATH}:/root/.config/pmoves \\
  myoung34/github-runner:latest"

if $DRY_RUN; then
  echo "  [dry-run] ssh $TARGET with ${AUTH_ENV_VAR} injected:"
  echo "  $DOCKER_CMD"
  check "Container launch" "pass" "dry-run"
else
  # Pass auth token via SSH env to keep it out of process args on the target
  # shellcheck disable=SC2029
  if ssh -o ConnectTimeout=10 "$TARGET" \
    "export ${AUTH_ENV_VAR}='${AUTH_VAL}'; ${DOCKER_CMD}" > /dev/null 2>&1; then
    check "Container launch" "pass" "$CONTAINER_NAME started"
  else
    check "Container launch" "fail" "docker run failed on $TARGET"
    exit 1
  fi
fi
echo ""

# --- Poll until online (skip in dry-run) ---
echo "[verify online]"
if $DRY_RUN; then
  check "Runner online" "pass" "dry-run (skipped poll)"
else
  RETRIES=8
  SLEEP=6
  ONLINE=false
  for i in $(seq 1 $RETRIES); do
    CURRENT_STATUS=$(gh api "repos/${REPO}/actions/runners" \
      --jq ".runners[] | select(.name == \"${RUNNER_NAME}\") | .status" 2>/dev/null || echo "")
    if [[ "$CURRENT_STATUS" == "online" ]]; then
      ONLINE=true
      break
    fi
    echo "  Waiting for runner (attempt $i/$RETRIES, status=${CURRENT_STATUS:-unknown})..."
    sleep $SLEEP
  done

  if $ONLINE; then
    check "Runner online" "pass" "$RUNNER_NAME"
  else
    check "Runner online" "warn" "not yet online after $((RETRIES * SLEEP))s — may still be registering"
  fi
fi
echo ""

echo "=== Results: $PASS passed, $FAIL failed, $WARN warnings ==="
[[ $FAIL -gt 0 ]] && exit 1
[[ $CASE -eq 2 ]] && exit 2
exit 0
