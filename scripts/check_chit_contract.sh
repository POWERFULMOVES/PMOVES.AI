#!/usr/bin/env bash

# Local helper to mirror the CHIT contract workflow checks.

set -euo pipefail

if ! command -v rg >/dev/null 2>&1; then
  echo "ripgrep (rg) is required. Install it and re-run."
  exit 127
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

sql_search_path="$REPO_ROOT/pmoves/supabase"
services_search_path="$REPO_ROOT/pmoves/services"

status_ok() {
  printf '✅ %s\n' "$1"
}

status_fail() {
  printf '❌ %s\n' "$1" >&2
  exit 1
}

PATTERN_TABLES_BASE='create table .*('
PATTERN_TABLES_SUFFIX='anchors|constellations|shape_points|shape_index)'
PATTERN_TABLES="${PATTERN_TABLES_BASE}${PATTERN_TABLES_SUFFIX}"

rg -ni --iglob '*.sql' "$PATTERN_TABLES" "$sql_search_path" \
  && status_ok "CHIT tables present" || status_fail "Missing CHIT tables"

rg -n '@(app|router)\.post\("/geometry/event"' "$services_search_path" \
  || rg -n 'POST /geometry/event' "$services_search_path" \
  && status_ok "POST /geometry/event endpoint present" \
  || status_fail "Missing endpoint POST /geometry/event"

rg -n '@(app|router)\.get\("/shape/point/.*/jump"' "$services_search_path" \
  || rg -n 'GET /shape/point/.*/jump' "$services_search_path" \
  && status_ok "GET /shape/point/.../jump endpoint present" \
  || status_fail "Missing endpoint GET /shape/point/.../jump"

rg -n '@(app|router)\.post\("/geometry/decode/(text|image|audio)"' "$services_search_path" \
  || rg -n '/geometry/decode/(text|image|audio)' "$services_search_path" \
  && status_ok "/geometry/decode/* endpoint present" \
  || status_fail "Missing endpoint /geometry/decode/(text|image|audio)"

rg -n '@(app|router)\.post\("/geometry/calibration/report"' "$services_search_path" \
  || rg -n '/geometry/calibration/report' "$services_search_path" \
  && status_ok "/geometry/calibration/report endpoint present" \
  || status_fail "Missing endpoint /geometry/calibration/report"

rg -n 'geometry.cgp.v1' -S "$REPO_ROOT" \
  && status_ok "geometry.cgp.v1 event publish present" \
  || status_fail "Missing geometry.cgp.v1 event publish"

rg -n 'CHIT_REQUIRE_SIGNATURE' -S "$REPO_ROOT" \
  && status_ok "CHIT_REQUIRE_SIGNATURE flag present" \
  || status_fail "Missing CHIT_REQUIRE_SIGNATURE flag"

rg -n 'CHIT_PASSPHRASE' -S "$REPO_ROOT" \
  && status_ok "CHIT_PASSPHRASE flag present" \
  || status_fail "Missing CHIT_PASSPHRASE flag"

rg -n 'CHIT_DECRYPT_ANCHORS' -S "$REPO_ROOT" \
  && status_ok "CHIT_DECRYPT_ANCHORS flag present" \
  || status_fail "Missing CHIT_DECRYPT_ANCHORS flag"

rg -n 'CHIT_CODEBOOK_PATH' -S "$REPO_ROOT" \
  && status_ok "CHIT_CODEBOOK_PATH flag present" \
  || status_fail "Missing CHIT_CODEBOOK_PATH flag"

rg -n 'CHIT_T5_MODEL' -S "$REPO_ROOT" \
  && status_ok "CHIT_T5_MODEL flag present" \
  || status_fail "Missing CHIT_T5_MODEL flag"

printf 'All CHIT contract checks passed locally.\n'
