#!/usr/bin/env bash
# JWT Alias Sunset Migration Script
# Owner-Decision C: deprecate SUPABASE_JWT_SECRET + 5 service aliases
# Sunset: 2026-05-26
# Usage:
#   chmod +x pmoves/scripts/sunset_jwt_aliases.sh
#   # Dry run (no changes):
#   pmoves/scripts/sunset_jwt_aliases.sh --dry-run
#   # Apply:
#   pmoves/scripts/sunset_jwt_aliases.sh
#
# What this does:
#   1. Compose files: strips `:-${SUPABASE_JWT_SECRET}` fallback, keeps `${JWT_SECRET}`
#   2. Application code: replaces `SUPABASE_JWT_SECRET` env var reads with `JWT_SECRET`
#   3. Env examples: updates variable names
#   4. Skips submodule directories (PMOVES-DoX, PMOVES-Archon, etc.) — they have their own migration

set -euo pipefail

DRY_RUN="${1:---apply}"
if [[ "$DRY_RUN" == "--dry-run" ]]; then
    echo "=== DRY RUN — no files will be modified ==="
    SED_CMD="sed --dry-run"
    # macOS compat: fall back to gsed if available
    if command -v gsed &>/dev/null; then SED_CMD="gsed -n"; fi
else
    echo "=== APPLYING JWT alias sunset changes ==="
    SED_CMD="sed -i"
    if [[ "$(uname)" == "Darwin" ]]; then SED_CMD="sed -i ''"; fi
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CD="$DRY_RUN"

# Counters
CHANGED=0
SKIPPED_SUBMODULE=0
SKIPPED_NO_MATCH=0

# Submodule directories to skip (they manage their own migration)
SUBMODULES=(
    "PMOVES-DoX"
    "PMOVES-Archon"
    "PMOVES-BoTZ"
    "PMOVES-supabase"
    "PMOVES-n8n"
    "PMOVES-transcribe-and-fetch"
    "PMOVES-DoX/external"
    "PMOVES-Archon/external"
)

is_submodule() {
    local path="$1"
    for sub in "${SUBMODULES[@]}"; do
        if [[ "$path" == "$REPO_ROOT/$sub"* ]]; then
            return 0
        fi
    done
    return 1
}

#############################################
# Phase 1: Compose files — strip SUPABASE fallback
#############################################
echo ""
echo "Phase 1: Compose files — strip :-\${SUPABASE_JWT_SECRET} fallback"
echo "---------------------------------------------------------------"

while IFS= read -r -d '' file; do
    if is_submodule "$file"; then
        SKIPPED_SUBMODULE=$((SKIPPED_SUBMODULE + 1))
        continue
    fi

    # Pattern: ${JWT_SECRET:-${SUPABASE_JWT_SECRET}} → ${JWT_SECRET}
    # Also handles: ${JWT_SECRET:-${SUPABASE_JWT_SECRET:-}} → ${JWT_SECRET}
    if grep -q 'JWT_SECRET:-\${SUPABASE_JWT_SECRET' "$file" 2>/dev/null; then
        echo "  [COMPOSE] $file"
        if [[ "$DRY_RUN" != "--dry-run" ]]; then
            # Replace ${JWT_SECRET:-${SUPABASE_JWT_SECRET...}} with ${JWT_SECRET}
            perl -i -pe 's/\$\{JWT_SECRET:-\$\{SUPABASE_JWT_SECRET(?::-)?\}\}/\$\{JWT_SECRET\}/g' "$file"
        fi
        CHANGED=$((CHANGED + 1))
    fi
done < <(find "$REPO_ROOT" -name 'docker-compose*.yml' -print0 2>/dev/null)

#############################################
# Phase 2: Python code — SUPABASE_JWT_SECRET → JWT_SECRET
#############################################
echo ""
echo "Phase 2: Python code — SUPABASE_JWT_SECRET → JWT_SECRET"
echo "--------------------------------------------------------"

while IFS= read -r -d '' file; do
    if is_submodule "$file"; then
        SKIPPED_SUBMODULE=$((SKIPPED_SUBMODULE + 1))
        continue
    fi

    if grep -q 'SUPABASE_JWT_SECRET' "$file" 2>/dev/null; then
        echo "  [PY] $file"
        if [[ "$DRY_RUN" != "--dry-run" ]]; then
            sed -i 's/SUPABASE_JWT_SECRET/JWT_SECRET/g' "$file"
        fi
        CHANGED=$((CHANGED + 1))
    fi
done < <(find "$REPO_ROOT/pmoves" -name '*.py' -print0 2>/dev/null)

#############################################
# Phase 3: Shell scripts
#############################################
echo ""
echo "Phase 3: Shell scripts — SUPABASE_JWT_SECRET → JWT_SECRET"
echo "------------------------------------------------------------"

while IFS= read -r -d '' file; do
    if is_submodule "$file"; then
        SKIPPED_SUBMODULE=$((SKIPPED_SUBMODULE + 1))
        continue
    fi

    if grep -q 'SUPABASE_JWT_SECRET' "$file" 2>/dev/null; then
        echo "  [SH] $file"
        if [[ "$DRY_RUN" != "--dry-run" ]]; then
            sed -i 's/SUPABASE_JWT_SECRET/JWT_SECRET/g' "$file"
        fi
        CHANGED=$((CHANGED + 1))
    fi
done < <(find "$REPO_ROOT/pmoves" -name '*.sh' -print0 2>/dev/null)

#############################################
# Phase 4: Env examples
#############################################
echo ""
echo "Phase 4: Env examples — update variable names"
echo "-----------------------------------------------"

while IFS= read -r -d '' file; do
    if is_submodule "$file"; then
        SKIPPED_SUBMODULE=$((SKIPPED_SUBMODULE + 1))
        continue
    fi

    if grep -q 'SUPABASE_JWT_SECRET' "$file" 2>/dev/null; then
        echo "  [ENV] $file"
        if [[ "$DRY_RUN" != "--dry-run" ]]; then
            sed -i 's/SUPABASE_JWT_SECRET/JWT_SECRET/g' "$file"
        fi
        CHANGED=$((CHANGED + 1))
    fi
done < <(find "$REPO_ROOT/pmoves" -name '*.env*' -print0 2>/dev/null)

#############################################
# Phase 5: YAML config (non-compose)
#############################################
echo ""
echo "Phase 5: YAML configs — update references"
echo "-------------------------------------------"

while IFS= read -r -d '' file; do
    if is_submodule "$file"; then
        SKIPPED_SUBMODULE=$((SKIPPED_SUBMODULE + 1))
        continue
    fi

    if grep -q 'SUPABASE_JWT_SECRET' "$file" 2>/dev/null; then
        echo "  [YAML] $file"
        if [[ "$DRY_RUN" != "--dry-run" ]]; then
            sed -i 's/SUPABASE_JWT_SECRET/JWT_SECRET/g' "$file"
        fi
        CHANGED=$((CHANGED + 1))
    fi
done < <(find "$REPO_ROOT/pmoves" -name '*.yaml' -o -name '*.yml' -print0 2>/dev/null | grep -v docker-compose)

#############################################
# Phase 6: Markdown docs
#############################################
echo ""
echo "Phase 6: Markdown docs — update references"
echo "--------------------------------------------"

while IFS= read -r -d '' file; do
    if is_submodule "$file"; then
        SKIPPED_SUBMODULE=$((SKIPPED_SUBMODULE + 1))
        continue
    fi

    if grep -q 'SUPABASE_JWT_SECRET' "$file" 2>/dev/null; then
        echo "  [MD] $file"
        if [[ "$DRY_RUN" != "--dry-run" ]]; then
            sed -i 's/SUPABASE_JWT_SECRET/JWT_SECRET/g' "$file"
        fi
        CHANGED=$((CHANGED + 1))
    fi
done < <(find "$REPO_ROOT/pmoves" -name '*.md' -print0 2>/dev/null)

#############################################
# Summary
#############################################
echo ""
echo "============================="
echo "  Migration Summary"
echo "============================="
echo "  Files changed:   $CHANGED"
echo "  Submodules skip: $SKIPPED_SUBMODULE"
echo ""
echo "  Submodules needing separate migration:"
for sub in "${SUBMODULES[@]}"; do
    count=$(grep -rl 'SUPABASE_JWT_SECRET' "$REPO_ROOT/$sub" 2>/dev/null | wc -l)
    if [[ "$count" -gt 0 ]]; then
        echo "    $sub: $count files"
    fi
done
echo ""
if [[ "$DRY_RUN" == "--dry-run" ]]; then
    echo "  ⚠️  DRY RUN — re-run without --dry-run to apply"
else
    echo "  ✅ Migration applied"
    echo ""
    echo "  Post-migration steps:"
    echo "    1. Run: pmoves/scripts/sunset_jwt_aliases.sh --dry-run  # verify zero hits"
    echo "    2. Run: python -m pytest pmoves/tests/  # verify nothing breaks"
    echo "    3. Update submodule repos separately"
    echo "    4. Update GitHub Actions secrets if SUPABASE_JWT_SECRET is stored there"
fi
