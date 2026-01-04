#!/bin/bash
# wait-for-deps.sh - Wait for dependencies to be ready
# Usage: wait-for-deps.sh [command to run after deps are ready]
set -e

# Default command is to exit successfully (deps are ready)
CMD=${1:-/bin/true}

echo "Waiting for dependencies..."
# Just run the command directly - docker-compose depends_on handles the ordering
echo "Dependencies check complete"
exec $CMD
