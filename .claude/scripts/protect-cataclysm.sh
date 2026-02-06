#!/bin/bash
# CATACLYSM_STUDIOS_INC Protection Script
# This script verifies the integrity of the CATACLYSM_STUDIOS_INC folder
# and provides restoration if files are missing.

set -e

CATACLYSM_DIR="CATACLYSM_STUDIOS_INC"
EXPECTED_FILES=189
BACKUP_BRANCH="origin/PMOVES.AI-Edition-Hardened"

echo "=== CATACLYSM_STUDIOS_INC Protection Check ==="
echo "Expected files: $EXPECTED_FILES"

# Check if directory exists
if [ ! -d "$CATACLYSM_DIR" ]; then
    echo "❌ ERROR: $CATACLYSM_DIR directory is MISSING!"
    echo "Restoring from $BACKUP_BRANCH..."
    git checkout "$BACKUP_BRANCH" -- "$CATACLYSM_DIR/"
    echo "✅ Restored $CATACLYSM_DIR"
    exit 0
fi

# Count files
FILE_COUNT=$(find "$CATACLYSM_DIR" -type f | wc -l)
echo "Current files: $FILE_COUNT"

# Check if file count matches expected
if [ "$FILE_COUNT" -lt "$EXPECTED_FILES" ]; then
    echo "⚠️  WARNING: $CATACLYSM_DIR has fewer files than expected!"
    echo "Expected: $EXPECTED_FILES, Found: $FILE_COUNT"
    read -p "Restore from $BACKUP_BRANCH? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git checkout "$BACKUP_BRANCH" -- "$CATACLYSM_DIR/"
        echo "✅ Restored $CATACLYSM_DIR"
    else
        echo "Skipping restoration"
    fi
else
    echo "✅ $CATACLYSM_DIR is intact with $FILE_COUNT files"
fi

# Verify critical subdirectories
echo "Verifying subdirectories..."
for subdir in ABOUT PMOVES-PROVISIONS; do
    if [ -d "$CATACLYSM_DIR/$subdir" ]; then
        echo "  ✅ $subdir exists"
    else
        echo "  ❌ $subdir MISSING!"
    fi
done

echo "=== Protection Check Complete ==="
