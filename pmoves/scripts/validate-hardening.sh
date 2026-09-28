#!/bin/bash
# PMOVES.AI Docker Hardening Validation
#
# Usage:
#   ./pmoves/scripts/validate-hardening.sh [service_name]
#
# Exit codes (do NOT collapse these; `make` does, so call this directly):
#   0  clean
#   1  new finding(s) and/or stale baseline entry(ies)
#   3  COULD NOT MEASURE - never the same thing as a pass
#
# This is a thin wrapper. The checks live in
# pmoves/tools/compose_hardening_ratchet.py, which parses the overlay as YAML
# and ratchets its findings against
# pmoves/configs/hardening_ratchet/_compose_known_gaps.yaml.
#
# WHY IT IS NO LONGER A SHELL SCRIPT OF ITS OWN
# ---------------------------------------------
# The previous 103-line grep implementation printed
# "112 passed, 43 warnings, 0 errors" and exited 0. It could only fail on the
# literal string `user: "0:0"`; a non-numeric `user:` fell through its regex
# with no `else` and incremented nothing at all; and its service discovery
# scored three entries from the top-level `secrets:` block as if they were
# containers. See findings H2 and M5 in
# pmoves/docs/audit/HARDENING_VENDOR_RECONCILE_2026-09-20.md and the module
# docstring of the tool.
#
# REQUIRED STATUS CHECK. This runs in two places: advisorily in
# .github/workflows/hardening-validation.yml (which also uploads the report
# artifact), and BLOCKING as the `compose-hardening-check` job in
# .github/workflows/merge-gate.yml, which merge-decision aggregates. It had to
# be re-implemented there rather than aggregated from hardening-validation.yml
# because `needs:` cannot reference a job in another workflow file -- so until
# then this script fired on every PR and blocked nothing.
#
# Promoted when the tree measured 28 findings, 0 new, exit 0, so promotion
# blocked nothing that existed and blocks the next regression. If you are
# reading this because the gate went red: restore the property on the service.
# Adding a baseline entry to make it green re-opens the ratchet.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TOOL="${REPO_ROOT}/pmoves/tools/compose_hardening_ratchet.py"

if [[ ! -f "$TOOL" ]]; then
    echo "COULD NOT MEASURE: tool not found: $TOOL" >&2
    exit 3
fi

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "COULD NOT MEASURE: $PY not on PATH" >&2
    exit 3
fi

exec "$PY" "$TOOL" "$@"
