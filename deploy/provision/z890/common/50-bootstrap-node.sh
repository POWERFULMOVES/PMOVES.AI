#!/usr/bin/env bash
# Z890 Claw Bootstrap (delegate to pmoves/scripts/claws/bootstrap-node.sh)
#
# The heavy lifting is done by the existing canonical claw bootstrap script.
# This wrapper just:
#   1. Resolves the correct scope from profile.yaml (always 'z890')
#   2. Uses localhost as target (since we're running on the Z890 itself)
#   3. Skips SSH checks (we ARE the target)
#
# See pmoves/scripts/claws/bootstrap-node.sh for what actually happens:
#   - Claw scope deploy (openclaw.json + exec-approvals + CLAUDE.md)
#   - Claude Code CLI + Ollama + gh CLI install
#   - Glances monitoring setup
#   - verify-claw.sh smoke check

set -euo pipefail

PROFILE_YAML="${PROFILE_YAML:-/opt/pmoves/profile.yaml}"
CLONE_DIR="${PMOVES_CLONE_DIR:-/opt/pmoves}"

log() { echo "[bootstrap-node] $*" >&2; }

scope_from_profile() {
  if [[ -r "$PROFILE_YAML" ]]; then
    awk -F': ' '/^pmoves_scope:/{gsub(/[ \t]/,"",$2);print $2;exit}' "$PROFILE_YAML" | tr -d '"'
  else
    echo "z890"
  fi
}

main() {
  local script="$CLONE_DIR/pmoves/scripts/claws/bootstrap-node.sh"
  if [[ ! -x "$script" ]] && [[ ! -f "$script" ]]; then
    log "ERROR: $script not found. Did 40-repo-clone.sh complete?"
    exit 1
  fi

  local scope target
  scope="$(scope_from_profile)"
  target="${SUDO_USER:-$USER}@localhost"

  log "Delegating to claws/bootstrap-node.sh (scope=$scope target=$target)"
  bash "$script" --scope "$scope" --target "$target" --skip-ssh || {
    log "WARN: claw bootstrap returned non-zero — operator should review logs"
    return 1
  }
  log "Claw bootstrap complete."
}

main "$@"
