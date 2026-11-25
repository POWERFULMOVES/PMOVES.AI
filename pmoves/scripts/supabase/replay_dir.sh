#!/usr/bin/env bash
# replay_dir.sh <dir-under-initdb-mount> — replay every .sql in a mounted dir
# with per-file OK/SKIP/FAIL status. SKIP = the file self-guarded (psql \quit
# with a SKIPPED echo, e.g. 17_persona_seed on a fresh volume pending the
# migration ledger). FAIL names the first ERROR line and the remediation road.
set -u
dir="$1"
shopt -s nullglob
files=("$dir"/*.sql)
if [ ${#files[@]} -eq 0 ]; then exit 0; fi
for f in "${files[@]}"; do
    name=$(basename "$f")
    log=$(mktemp)
    if psql -U supabase_admin -h 127.0.0.1 -d postgres -f "$f" >"$log" 2>&1; then
        if grep -q '^SKIPPED' "$log"; then
            echo "SKIP: $name — $(grep -m1 '^SKIPPED' "$log" | cut -c1-140)"
        else
            echo "OK: $name"
        fi
    else
        echo "WARN: $name FAILED :: $(grep -im1 'ERROR' "$log" | cut -c1-140)"
        echo "  remediation: make supa-migrate (ledgered road), then re-run"
    fi
    rm -f "$log"
done
