#!/usr/bin/env bash
# deploy-vps-cluster.sh — Deploy Kilo Code claws to all Hostinger KVM nodes
# Usage: deploy-vps-cluster.sh [--dry-run] [--nodes kvm4-1,kvm4-2,kvm2]
#
# Reads target IPs from environment (HOSTINGER_KVM*_IP) or GitHub Secrets.
# Deploys in parallel or sequentially based on --sequential flag.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DRY_RUN=false
SEQUENTIAL=false
NODES="kvm4-1,kvm4-2,kvm2"
TAILSCALE_AUTH_KEY="${TAILSCALE_AUTH_KEY:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)     DRY_RUN=true; shift ;;
    --sequential)  SEQUENTIAL=true; shift ;;
    --nodes)       NODES="$2"; shift 2 ;;
    --tailscale-auth-key) TAILSCALE_AUTH_KEY="$2"; shift 2 ;;
    *)             echo "Unknown arg: $1"; exit 1 ;;
  esac
done

echo "============================================"
echo "  PMOVES VPS Cluster Deployment"
echo "============================================"
echo "Nodes: $NODES"
echo "Dry run: $DRY_RUN"
echo "Sequential: $SEQUENTIAL"
echo ""

# --- Resolve targets from environment ---
declare -A TARGETS

resolve_target() {
  local node="$1"
  local ip_var user_var ip user

  case "$node" in
    kvm4-1)
      ip_var="HOSTINGER_KVM4_1_IP"
      user_var="HOSTINGER_KVM4_1_USER"
      ;;
    kvm4-2)
      ip_var="HOSTINGER_KVM4_2_IP"
      user_var="HOSTINGER_KVM4_2_USER"
      ;;
    kvm2)
      ip_var="HOSTINGER_KVM2_IP"
      user_var="HOSTINGER_KVM2_USER"
      ;;
    *)
      echo "ERROR: Unknown node: $node"
      return 1
      ;;
  esac

  ip="${!ip_var:-}"
  user="${!user_var:-root}"

  if [[ -z "$ip" ]]; then
    # Try to pull from gh secret
    ip=$(gh secret list --json name,value 2>/dev/null | jq -r ".[] | select(.name==\"$ip_var\") | .value" 2>/dev/null || echo "")
  fi

  if [[ -z "$ip" ]]; then
    echo "WARNING: No IP for $node (set $ip_var or add to GH secrets)"
    return 1
  fi

  TARGETS[$node]="${user}@${ip}"
}

# Resolve all targets
IFS=',' read -ra NODE_LIST <<< "$NODES"
RESOLVED=0
SKIPPED=0

for node in "${NODE_LIST[@]}"; do
  if resolve_target "$node"; then
    echo "  $node -> ${TARGETS[$node]}"
    ((RESOLVED++))
  else
    ((SKIPPED++))
  fi
done

echo ""
echo "Resolved: $RESOLVED nodes, Skipped: $SKIPPED"
echo ""

if [[ $RESOLVED -eq 0 ]]; then
  echo "ERROR: No nodes resolved. Set HOSTINGER_KVM*_IP environment variables."
  echo ""
  echo "Example:"
  echo "  export HOSTINGER_KVM4_1_IP=<ip>"
  echo "  export HOSTINGER_KVM4_2_IP=<ip>"
  echo "  export HOSTINGER_KVM2_IP=<ip>"
  exit 1
fi

# --- Deploy ---
PASS=0
FAIL=0
PIDS=()

deploy_node() {
  local node="$1"
  local target="${TARGETS[$node]}"
  local extra_args=""

  if $DRY_RUN; then extra_args="--dry-run"; fi
  if [[ -n "$TAILSCALE_AUTH_KEY" ]]; then extra_args="$extra_args --tailscale-auth-key $TAILSCALE_AUTH_KEY"; fi

  echo ""
  echo ">>> Deploying $node ($target) <<<"
  if "$SCRIPT_DIR/migrate-vps.sh" --node "$node" --target "$target" $extra_args; then
    echo ">>> $node: SUCCESS <<<"
    return 0
  else
    echo ">>> $node: FAILED <<<"
    return 1
  fi
}

if $SEQUENTIAL; then
  for node in "${!TARGETS[@]}"; do
    if deploy_node "$node"; then
      ((PASS++))
    else
      ((FAIL++))
    fi
  done
else
  # Parallel deployment
  for node in "${!TARGETS[@]}"; do
    deploy_node "$node" &
    PIDS+=($!)
  done

  # Wait for all
  for i in "${!PIDS[@]}"; do
    if wait "${PIDS[$i]}"; then
      ((PASS++))
    else
      ((FAIL++))
    fi
  done
fi

echo ""
echo "============================================"
echo "  Cluster Deployment Results"
echo "============================================"
echo "Passed: $PASS"
echo "Failed: $FAIL"
echo "Skipped: $SKIPPED"
echo ""

if [[ $FAIL -gt 0 ]]; then
  echo "Some nodes failed. Check output above for details."
  echo "Re-run with --sequential for easier debugging."
  exit 1
fi

echo "All nodes deployed successfully."
echo ""
echo "Next steps:"
echo "  make -C pmoves claws-status     # Fleet health check"
echo "  make -C pmoves claw-verify SCOPE=kvm4-1  # Verify specific node"
