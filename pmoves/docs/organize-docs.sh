#!/bin/bash
# organize-docs.sh - Reorganize PMOVES.AI documentation
#
# This script organizes documentation into a structured hierarchy:
# - production/: Active operational documentation
# - archive/: Historical documentation (preserved for reference)
# - reference/: Architecture and design documentation
#
# Usage: ./organize-docs.sh [--dry-run]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS_DIR="${SCRIPT_DIR}/../docs"
PMOVES_DIR="${SCRIPT_DIR}/.."

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "DRY RUN MODE - No files will be moved"
fi

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd "$DOCS_DIR"

echo "📁 Reorganizing PMOVES.AI documentation..."
echo ""

# Create directory structure
echo "Creating directory structure..."
mkdir -p production/networking
mkdir -p production/deployment
mkdir -p production/runbooks
mkdir -p production/services
mkdir -p archive/audits/2026-02-07
mkdir -p archive/audits/2026-02-08
mkdir -p archive/audits/2026-02-09
mkdir -p archive/audits/2026-02-10
mkdir -p archive/docker
mkdir -p archive/supabase
mkdir -p reference/architecture
mkdir -p reference/integration

# Files to move to production/
PRODUCTION_FILES=(
    # Deployment
    "BRING_UP_GUIDE.md:production/deployment/"
    "DEPLOYMENT_STATUS_2026-02-09.md:production/deployment/"
    "PRODUCTION_VALIDATION_RUNBOOK.md:production/runbooks/"

    # Docker
    "DOCKER_BRING_UP_VALIDATION.md:production/deployment/"
    "DOCKER_COMPOSE_ENVIRONMENT_LOADING.md:production/deployment/"
    "DOCKER_COMPOSE_NETWORKING_GUIDE.md:production/networking/"
    "DOCKER_HARDENING.md:production/deployment/security/"
    "DOCKER_HARDENING_CHECKLIST.md:production/deployment/security/"
    "DOCKER_HARDENING_SUMMARY.md:production/deployment/security/"
    "DOCKER_PORT_FORWARDING_FIX_2026-02-10.md:production/networking/"
    "DOCKER_SECRETS_GUIDE.md:production/deployment/security/"

    # Networking
    "CROSS_PLATFORM_TASKS.md:production/deployment/"
    "BRING_UP_WSL2.md:production/deployment/wsl2.md"

    # Services
    "NATS_CONFIGURATION.md:production/services/"
)

# Files to move to archive/audits/
ARCHIVE_AUDITS=(
    "AUDIT_LOG_2026-02-07.md:archive/audits/2026-02-07/"
    "CI_AUDIT_REPORT_2026-02-08.md:archive/audits/2026-02-08/"
    "CI_INFRASTRUCTURE_AUDIT_2026-02-08.md:archive/audits/2026-02-08/"
    "CI_VALIDATION_SUMMARY_2026-02-08.md:archive/audits/2026-02-08/"
    "CODERABBIT_REVIEW_606_2026-02-08.md:archive/audits/2026-02-08/"
)

# Files to move to archive/docker/
ARCHIVE_DOCKER=(
    "DOCKER_COMPOSE_ENV_LOADING.md:archive/docker/"
    "DOCKER_GHCR_REVIEW_2026-02-08.md:archive/docker/"
)

# Files to move to archive/supabase/
ARCHIVE_SUPABASE=(
    "SUPABASE_FIX_SUMMARY_2026-02-09.md:archive/supabase/"
)

# Files to move to reference/architecture/
REFERENCE_ARCH=(
    "ARCHITECTURE_DISTRIBUTED.md:reference/architecture/"
    "DISTRIBUTED_COMPUTE_SERVICES.md:reference/architecture/"
    "DOCKING_ARCHITECTURE.md:reference/architecture/"
    "DYNAMIC_PORTS_GUIDE.md:reference/architecture/"
)

# Files to move to reference/integration/
REFERENCE_INTEGRATION=(
    "CHIT_AUDIT_TRACKING.md:reference/integration/chit/"
    "CHIT_INTEGRATION_STATUS.md:reference/integration/chit/"
    "CHIT_USER_GUIDE.md:reference/integration/chit/"
)

# Files to delete (duplicates, very old, or binary)
DELETE_FILES=(
    "CROSS_PLATFORM_TASKS.md.bak"  # Backup file
    "Building a Custom ChatGPT Connector with Docker MCP Toolkit.docx"  # Binary
    "Building a Custom ChatGPT Connector with Docker MCP Toolkit.pdf"   # Binary
)

# Helper function to move file
move_file() {
    local src="$1"
    local dest="$2"

    if [[ ! -f "$src" ]]; then
        echo "  ⚠️  Skipped (not found): $src"
        return
    fi

    local dest_dir="${dest%/*}"
    local dest_file="${dest_dir}/$(basename "$src")"

    # Check if destination already has file
    if [[ -f "$dest_file" ]]; then
        echo "  ⚠️  Skipped (dest exists): $src -> $dest"
        return
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "  Would move: $src -> $dest"
    else
        mkdir -p "$dest_dir"
        mv "$src" "$dest_file"
        echo "  ${GREEN}✓${NC} Moved: $src -> $dest"
    fi
}

# Helper function to delete file
delete_file() {
    local file="$1"

    if [[ ! -f "$file" ]]; then
        echo "  ⚠️  Skipped (not found): $file"
        return
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "  Would delete: $file"
    else
        rm "$file"
        echo "  ${YELLOW}🗑️${NC} Deleted: $file"
    fi
}

# Execute moves
echo ""
echo "📋 Moving production documentation..."
for entry in "${PRODUCTION_FILES[@]}"; do
    IFS=':' read -r src dest <<< "$entry"
    move_file "$src" "$dest"
done

echo ""
echo "📋 Moving audit archives..."
for entry in "${ARCHIVE_AUDITS[@]}"; do
    IFS=':' read -r src dest <<< "$entry"
    move_file "$src" "$dest"
done

echo ""
echo "📋 Moving docker archives..."
for entry in "${ARCHIVE_DOCKER[@]}"; do
    IFS=':' read -r src dest <<< "$entry"
    move_file "$src" "$dest"
done

echo ""
echo "📋 Moving Supabase archives..."
for entry in "${ARCHIVE_SUPABASE[@]}"; do
    IFS=':' read -r src dest <<< "$entry"
    move_file "$src" "$dest"
done

echo ""
echo "📋 Moving reference documentation..."
for entry in "${REFERENCE_ARCH[@]}"; do
    IFS=':' read -r src dest <<< "$entry"
    move_file "$src" "$dest"
done

echo ""
echo "📋 Moving integration documentation..."
for entry in "${REFERENCE_INTEGRATION[@]}"; do
    IFS=':' read -r src dest <<< "$entry"
    move_file "$src" "$dest"
done

echo ""
echo "📋 Deleting duplicate/binary files..."
for file in "${DELETE_FILES[@]}"; do
    delete_file "$file"
done

# Create index files
echo ""
echo "📋 Creating index files..."

# Main index
cat > INDEX.md << 'EOF'
# PMOVES.AI Documentation

## Quick Links

- [Production Runbooks](production/) - Operational procedures
- [Service Documentation](production/services/) - Service-specific docs
- [Reference](reference/) - Architecture and integration
- [Archive](archive/) - Historical documentation

## Categories

### Production
Active operational documentation for running PMOVES.AI in production.

- **Deployment**: Bring-up guides, WSL2 setup
- **Networking**: Docker networking, port configuration
- **Runbooks**: Validation procedures, troubleshooting

### Reference
Architecture and design documentation.

- **Architecture**: Distributed systems, service design
- **Integration**: CHIT protocol, NATS messaging

### Archive
Historical documentation preserved for reference.

- **Audits**: CI/CD infrastructure audits (by date)
- **Docker**: Docker configuration history
- **Supabase**: Supabase migration history

## Finding Documentation

### For Operators
See the [production/](production/) directory for:
- How to bring up PMOVES.AI services
- Troubleshooting common issues
- Security hardening procedures

### For Developers
See the [reference/](reference/) directory for:
- System architecture overview
- Service integration patterns
- API documentation

### For Debugging
See the [archive/](archive/) directory for:
- Historical issue resolution
- Previous configuration decisions
- Audit trail of changes
EOF

# Production index
cat > production/INDEX.md << 'EOF'
# Production Documentation

Operational documentation for running PMOVES.AI in production.

## Categories

- [Deployment](deployment/) - Service bring-up and configuration
- [Networking](networking/) - Network configuration and troubleshooting
- [Runbooks](runbooks/) - Operational procedures
- [Services](services/) - Service-specific documentation

## Quick Start

1. **First-time Setup**: See [deployment/BRING_UP_GUIDE.md](deployment/BRING_UP_GUIDE.md)
2. **Security**: See [deployment/DOCKER_HARDENING.md](deployment/DOCKER_HARDENING.md)
3. **Troubleshooting**: See [runbooks/](runbooks/)

## Deployment

- [Bring Up Guide](deployment/BRING_UP_GUIDE.md) - Initial setup
- [Deployment Status](deployment/DEPLOYMENT_STATUS_2026-02-09.md) - Current status
- [WSL2 Setup](deployment/BRING_UP_WSL2.md) - WSL2-specific instructions

## Networking

- [Docker Compose Networking](networking/DOCKER_COMPOSE_NETWORKING_GUIDE.md)
- [Port Forwarding](networking/DOCKER_PORT_FORWARDING_FIX_2026-02-10.md)
- [Environment Loading](networking/DOCKER_COMPOSE_ENVIRONMENT_LOADING.md)

## Security

- [Docker Hardening](deployment/DOCKER_HARDENING.md)
- [Hardening Checklist](deployment/DOCKER_HARDENING_CHECKLIST.md)
- [Secrets Guide](deployment/DOCKER_SECRETS_GUIDE.md)
EOF

# Archive index
cat > archive/INDEX.md << 'EOF'
# Documentation Archive

Historical documentation preserved for reference. Organized by date and topic.

## Audit History

- [2026-02-10](audits/2026-02-10/) - Infrastructure fixes, Supabase migration
- [2026-02-09](audits/2026-02-09/) - Deployment status
- [2026-02-08](audits/2026-02-08/) - CI/CD infrastructure audit
- [2026-02-07](audits/2026-02-07/) - Initial audit

## Topic Archives

- [Docker](docker/) - Docker configuration history
- [Supabase](supabase/) - Supabase migration history

## Purpose

This archive preserves historical documentation for:
- Understanding past decisions and issues
- Reference when similar issues recur
- Audit trail of system evolution
EOF

echo ""
echo "${GREEN}✓ Documentation reorganization complete!${NC}"
echo ""
echo "Summary:"
echo "  - Production docs: production/"
echo "  - Reference docs: reference/"
echo "  - Archive: archive/"
echo ""
echo "Run 'git add -A pmoves/docs/' to stage all changes."
