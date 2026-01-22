#!/usr/bin/env bash
#
# deploy-k8s.sh
#
# PBnJ-friendly Kubernetes orchestration for PMOVES.
#
# Usage:
#   deploy-k8s.sh {apply|delete|status} [--target ai-lab|kvm4|local] [--context CTX] [--namespace NS] [--kubeconfig PATH]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
K8S_ROOT="${DEPLOY_ROOT}/k8s"

usage() {
  cat <<EOF
PMOVES K8s deploy script

Usage:
  $(basename "$0") {apply|delete|status} [--target ai-lab|kvm4|local] [--context CTX] [--namespace NS] [--kubeconfig PATH]

Commands:
  apply      Apply/update manifests for the target cluster
  delete     Delete manifests for the target cluster
  status     Show status for the target (pods, services, ingress)

Options:
  --target       Deployment target (default: ai-lab)
                 Values: ai-lab, kvm4, local
  --context      kubectl context override
  --namespace    Kubernetes namespace override
  --kubeconfig   Path to kubeconfig file

Environment overrides:
  PMOVES_K8S_CONTEXT_AI_LAB
  PMOVES_K8S_CONTEXT_KVM4
  PMOVES_K8S_CONTEXT_LOCAL

  PMOVES_K8S_NS_AI_LAB
  PMOVES_K8S_NS_KVM4
  PMOVES_K8S_NS_LOCAL
EOF
}

ensure_kubectl() {
  if ! command -v kubectl >/dev/null 2>&1; then
    echo "✖ kubectl is required but not found in PATH" >&2
    exit 1
  fi
}

# Resolve per-target defaults.
configure_target() {
  local target="$1"

  case "${target}" in
    ai-lab)
      TARGET_NAME="ai-lab"
      KUSTOMIZE_DIR="${K8S_ROOT}/ai-lab"
      : "${KUBE_CONTEXT:=${PMOVES_K8S_CONTEXT_AI_LAB:-ai-lab}}"
      : "${NAMESPACE:=${PMOVES_K8S_NS_AI_LAB:-pmoves}}"
      ;;
    kvm4)
      TARGET_NAME="kvm4"
      KUSTOMIZE_DIR="${K8S_ROOT}/kvm4"
      : "${KUBE_CONTEXT:=${PMOVES_K8S_CONTEXT_KVM4:-kvm4}}"
      : "${NAMESPACE:=${PMOVES_K8S_NS_KVM4:-pmoves}}"
      ;;
    local)
      TARGET_NAME="local"
      KUSTOMIZE_DIR="${K8S_ROOT}/local"
      : "${KUBE_CONTEXT:=${PMOVES_K8S_CONTEXT_LOCAL:-kind-pmoves}}"
      : "${NAMESPACE:=${PMOVES_K8S_NS_LOCAL:-pmoves-dev}}"
      ;;
    *)
      echo "✖ Unknown target: ${target}" >&2
      echo "  Valid targets: ai-lab, kvm4, local" >&2
      exit 2
      ;;
  esac

  if [ ! -d "${KUSTOMIZE_DIR}" ]; then
    echo "✖ K8s directory not found for target ${TARGET_NAME}: ${KUSTOMIZE_DIR}" >&2
    exit 1
  fi
}

build_kubectl_args() {
  KUBECTL_ARGS=()
  if [ -n "${KUBE_CONTEXT:-}" ]; then
    KUBECTL_ARGS+=(--context "${KUBE_CONTEXT}")
  fi
  if [ -n "${KUBECONFIG_PATH:-}" ]; then
    KUBECTL_ARGS+=(--kubeconfig "${KUBECONFIG_PATH}")
  fi
  KUBECTL_ARGS+=(-n "${NAMESPACE}")
}

do_apply() {
  echo "➜ Applying manifests for target ${TARGET_NAME}"
  echo "   Context:   ${KUBE_CONTEXT}"
  echo "   Namespace: ${NAMESPACE}"
  echo "   Source:    ${KUSTOMIZE_DIR}"

  build_kubectl_args

  if [ -f "${KUSTOMIZE_DIR}/kustomization.yaml" ] || [ -f "${KUSTOMIZE_DIR}/kustomization.yml" ]; then
    kubectl "${KUBECTL_ARGS[@]}" apply -k "${KUSTOMIZE_DIR}"
  else
    kubectl "${KUBECTL_ARGS[@]}" apply -f "${KUSTOMIZE_DIR}"
  fi
}

do_delete() {
  echo "➜ Deleting manifests for target ${TARGET_NAME}"
  echo "   Context:   ${KUBE_CONTEXT}"
  echo "   Namespace: ${NAMESPACE}"
  echo "   Source:    ${KUSTOMIZE_DIR}"

  build_kubectl_args

  if [ -f "${KUSTOMIZE_DIR}/kustomization.yaml" ] || [ -f "${KUSTOMIZE_DIR}/kustomization.yml" ]; then
    kubectl "${KUBECTL_ARGS[@]}" delete -k "${KUSTOMIZE_DIR}" --ignore-not-found
  else
    kubectl "${KUBECTL_ARGS[@]}" delete -f "${KUSTOMIZE_DIR}" --ignore-not-found
  fi
}

do_status() {
  echo "➜ Status for target ${TARGET_NAME}"
  echo "   Context:   ${KUBE_CONTEXT}"
  echo "   Namespace: ${NAMESPACE}"

  build_kubectl_args

  kubectl "${KUBECTL_ARGS[@]}" get pods,svc,ingress || true
}

main() {
  if [ $# -lt 1 ]; then
    usage
    exit 2
  fi

  local cmd="$1"; shift || true

  TARGET="ai-lab"
  KUBE_CONTEXT=""
  NAMESPACE=""
  KUBECONFIG_PATH=""

  # Parse flags
  while [ $# -gt 0 ]; do
    case "$1" in
      --target)
        TARGET="$2"; shift 2;;
      --context)
        KUBE_CONTEXT="$2"; shift 2;;
      --namespace|--ns)
        NAMESPACE="$2"; shift 2;;
      --kubeconfig)
        KUBECONFIG_PATH="$2"; shift 2;;
      -h|--help)
        usage; exit 0;;
      *)
        echo "✖ Unknown argument: $1" >&2
        usage
        exit 2;;
    esac
  done

  ensure_kubectl
  configure_target "${TARGET}"

  case "${cmd}" in
    apply)
      do_apply
      ;;
    delete)
      do_delete
      ;;
    status)
      do_status
      ;;
    *)
      echo "✖ Unknown command: ${cmd}" >&2
      usage
      exit 2
      ;;
  esac
}

main "$@"
