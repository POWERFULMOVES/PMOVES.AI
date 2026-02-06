#!/bin/bash

# PMOVES.AI Upstream Fork Sync Script
# Syncs forked submodules with their upstream repositories
#
# Usage:
#   ./sync-upstream-forks.sh [submodule-name] [--dry-run]
#
# Examples:
#   ./sync-upstream-forks.sh                           # Sync all known forks
#   ./sync-upstream-forks.sh PMOVES-Wealth           # Sync specific fork
#   ./sync-upstream-forks.sh --dry-run               # Show what would be done
#
# Known Forks:
#   - PMOVES-A2UI (upstream: google/A2UI)
#   - PMOVES-n8n (upstream: n8n-io/n8n)
#   - Pmoves-Health-wger (upstream: wger-project/wger)
#   - PMOVES-Wealth (upstream: firefly-iii/firefly-iii)
#   - PMOVES-AgentGym (upstream: WooooDyy/AgentGym)
#   - PMOVES-Open-Notebook (upstream: lfnovo/open-notebook)
#   - PMOVES-Pipecat (upstream: pipecat-ai/pipecat)
#   - PMOVES-tensorzero (upstream: tensorzero/tensorzero)

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$PROJECT_ROOT/pmoves/logs/sync-upstream-$(date +%Y%m%d-%H%M%S).log"
DRY_RUN=false

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Known forks configuration
declare -A FORKS=(
    ["PMOVES-A2UI"]="google/A2UI"
    ["PMOVES-n8n"]="n8n-io/n8n"
    ["Pmoves-Health-wger"]="wger-project/wger"
    ["PMOVES-Wealth"]="firefly-iii/firefly-iii"
    ["PMOVES-AgentGym"]="WooooDyy/AgentGym"
    ["PMOVES-Open-Notebook"]="lfnovo/open-notebook"
    ["PMOVES-Pipecat"]="pipecat-ai/pipecat"
    ["PMOVES-tensorzero"]="tensorzero/tensorzero"
)

# Logging functions
log() {
    echo -e "${NC}[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR] $1${NC}" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${BLUE}[INFO] $1${NC}" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN] $1${NC}" | tee -a "$LOG_FILE"
}

# Check if we're in the PMOVES.AI root directory
if [[ ! -f "$PROJECT_ROOT/.gitmodules" ]]; then
    log_error "Not in PMOVES.AI root directory. .gitmodules not found."
    exit 1
fi

# Parse arguments
SUBMODULE_NAME=""
for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            log_info "DRY RUN MODE - No changes will be made"
            shift
            ;;
        -*)
            log_error "Unknown option: $arg"
            exit 1
            ;;
        *)
            SUBMODULE_NAME="$arg"
            shift
            ;;
    esac
done

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/pmoves/logs"

# Sync function
sync_fork() {
    local submodule="$1"
    local upstream="${FORKS[$submodule]}"

    if [[ -z "$upstream" ]]; then
        log_error "Unknown fork: $submodule"
        return 1
    fi

    log_info "================================================"
    log_info "Syncing $submodule (upstream: $upstream)"
    log_info "================================================"

    # Change to submodule directory
    cd "$PROJECT_ROOT/$submodule" || {
        log_error "Cannot enter submodule directory: $submodule"
        return 1
    }

    # Check if it's a git repository
    if [[ ! -d ".git" ]]; then
        log_error "$submodule is not a git repository"
        return 1
    fi

    # Get current branch
    local current_branch
    current_branch=$(git rev-parse --abbrev-ref HEAD)
    log_info "Current branch: $current_branch"

    # Add upstream remote if not present
    if ! git remote -v | grep -q "^upstream"; then
        if [[ "$DRY_RUN" == "true" ]]; then
            log_info "DRY RUN: Would add upstream remote: $upstream"
        else
            git remote add upstream "https://github.com/$upstream.git" || {
                log_error "Failed to add upstream remote"
                return 1
            }
            log_success "Added upstream remote: $upstream"
        fi
    else
        log_info "Upstream remote already exists"
    fi

    # Fetch upstream
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would fetch upstream"
    else
        git fetch upstream || {
            log_error "Failed to fetch upstream"
            return 1
        }
        log_success "Fetched upstream changes"
    fi

    # Determine upstream branch (main or master)
    local upstream_branch="main"
    if ! git rev-parse upstream/main >/dev/null 2>&1; then
        upstream_branch="master"
    fi
    log_info "Upstream branch: $upstream_branch"

    # Check divergence
    local ahead behind
    ahead=$(git rev-list --count upstream/$upstream_branch..HEAD 2>/dev/null || echo 0)
    behind=$(git rev-list --count HEAD..upstream/$upstream_branch 2>/dev/null || echo 0)

    log_info "Divergence: $ahead commits ahead of upstream, $behind commits behind upstream"

    if [[ $behind -eq 0 && $ahead -gt 0 ]]; then
        log_warn "We are AHEAD of upstream by $ahead commits (PMOVES enhancements)"
        log_info "Upstream changes:"
        git log --oneline -n 5 HEAD..upstream/$upstream_branch 2>/dev/null || true
    elif [[ $behind -gt 0 ]]; then
        log_warn "We are BEHIND upstream by $behind commits (security updates available!)"
        log_info "Missing upstream changes:"
        git log --oneline -n 5 upstream/$upstream_branch..HEAD 2>/dev/null || true
    else
        log_success "Already in sync with upstream"
        cd "$PROJECT_ROOT"
        return 0
    fi

    # Ask for confirmation before merging
    if [[ "$DRY_RUN" == "false" ]]; then
        if [[ $behind -gt 0 ]]; then
            echo -e "${YELLOW}Merge $behind upstream changes into $submodule? (y/N): ${NC}"
            read -r response
            if [[ ! "$response" =~ ^[Yy]$ ]]; then
                log_info "Skipping merge for $submodule"
                cd "$PROJECT_ROOT"
                return 0
            fi
        fi
    fi

    # Create sync branch
    local sync_branch="sync-upstream-$(date +%Y%m%d-%H%M%S)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would create sync branch: $sync_branch"
    else
        git checkout -b "$sync_branch" 2>/dev/null || {
            log_error "Failed to create sync branch $sync_branch"
            cd "$PROJECT_ROOT"
            return 1
        }
        log_success "Created sync branch: $sync_branch"

        # Attempt merge
        if git merge "upstream/$upstream_branch" --no-edit --no-ff 2>/dev/null; then
            log_success "Merged upstream changes cleanly"
        else
            log_error "Merge conflicts detected! Manual resolution required."
            log_info "Resolve conflicts in: $sync_branch"
            log_info "Current directory: $(pwd)"
            cd "$PROJECT_ROOT"
            return 1
        fi

        # Return to original branch
        git checkout "$current_branch" 2>/dev/null || true
        log_info "Returned to original branch: $current_branch"
        log_info "Review merge in: $sync_branch"
        log_info "To keep: git merge $sync_branch"
        log_info "To discard: git branch -D $sync_branch"
    fi

    cd "$PROJECT_ROOT"
}

# Main execution
log_info "Starting upstream fork sync..."
log_info "Project root: $PROJECT_ROOT"
log_info "Log file: $LOG_FILE"

# If specific submodule provided
if [[ -n "$SUBMODULE_NAME" ]]; then
    if [[ -v "FORKS[$SUBMODULE_NAME]" ]]; then
        sync_fork "$SUBMODULE_NAME"
    else
        log_error "Unknown submodule: $SUBMODULE_NAME"
        log_info "Available submodules: ${!FORKS[@]}"
        exit 1
    fi
else
    # Sync all known forks
    log_info "Syncing all known forks..."
    for submodule in "${!FORKS[@]}"; do
        echo ""
        sync_fork "$submodule"
        echo ""
    done
fi

log_success "================================================"
log_success "Sync operations completed"
if [[ "$DRY_RUN" == "true" ]]; then
    log_info "DRY RUN MODE - No changes were made"
fi
log_success "================================================"
