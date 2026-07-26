#!/usr/bin/env bash
# validate_chit_expansions.sh — enforce the CHIT two-meaning canon (issue #2224).
#
# Brand-owner canon (DARKXSIDE, 2026-06-09): CHIT has exactly two allowed
# expansions, chosen by context:
#   - concept   = "Cymatic Holographic Information Theory"   (educational / geometry-of-meaning lens)
#   - mechanism = "Compressed Hierarchical Information Transfer" (signing / secrets layer)
#
# Any other "<Qualifier> Information (Transfer|Token|Theory)" expansion of CHIT
# is a conflicting variant and fails this check.
#
# Usage:
#   bash scripts/validate_chit_expansions.sh          # verify, exit 1 on any variant
#   bash scripts/validate_chit_expansions.sh --list   # also print the two canon forms
#
# Scoped to the tracked superproject (git grep) — submodules are validated in
# their own trees.

set -uo pipefail
cd "$(git rev-parse --show-toplevel)" || exit 2

# The two canonical forms — allowed everywhere.
CONCEPT="Cymatic Holographic Information Theory"
MECHANISM="Compressed Hierarchical Information Transfer"

# Generic detector: any "<Word>[- ]<Word> Information (Transfer|Token|Theory)".
# Everything it finds that is NOT one of the two canon forms is a violation.
DETECT='[A-Z][a-z]+[- ][A-Z][a-z]+ Information (Transfer|Token|Theory|Transmission)'

FILE_GLOBS=('*.md' '*.py' '*.yaml' '*.yml' '*.json' '*.ts' '*.tsx')

if [[ "${1:-}" == "--list" ]]; then
  echo "Canon (concept):   $CONCEPT"
  echo "Canon (mechanism): $MECHANISM"
  echo
fi

# Collect every matching expansion occurrence, then drop the two canon forms.
violations="$(git grep -n -I -E "$DETECT" -- "${FILE_GLOBS[@]}" 2>/dev/null \
  | grep -vF "$CONCEPT" \
  | grep -vF "$MECHANISM" || true)"

if [[ -n "$violations" ]]; then
  echo "❌ CHIT expansion canon violated — non-canon variant(s) found:"
  echo
  echo "$violations" | sed 's/^/  /'
  echo
  n="$(echo "$violations" | grep -c .)"
  echo "  $n occurrence(s). Reconcile each to concept ('$CONCEPT')"
  echo "  or mechanism ('$MECHANISM') per its context, then re-run."
  exit 1
fi

# Sanity: the canonical PMOVESCHIT entry files must carry the concept canon.
canon_ok=0
for f in pmoves/docs/PMOVESCHIT/00_GLOSSARY.md pmoves/docs/PMOVESCHIT/01_WHAT_IS_CHIT.md; do
  if [[ -f "$f" ]] && grep -qF "$CONCEPT" "$f"; then
    canon_ok=$((canon_ok+1))
  else
    echo "⚠️  Expected concept canon ('$CONCEPT') in $f — not found."
  fi
done

echo "✅ CHIT expansion canon clean — zero non-canon variants across tracked docs/code."
[[ "$canon_ok" -eq 2 ]] || { echo "   (but canonical entry files are missing the concept form — see warnings above)"; exit 1; }
echo "   Canonical entry files carry the concept form."
exit 0
