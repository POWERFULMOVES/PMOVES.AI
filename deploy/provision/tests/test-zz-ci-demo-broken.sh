#!/usr/bin/env bash
# DELIBERATELY BROKEN demo test for the launcher-tests workflow's
# fail-on-failure proof. Removed immediately after the red run is captured.
pass=0; fail=0
printf '  PASS  demo harness runs\n'; pass=$((pass+1))
printf '  FAIL  deliberately broken assertion (rc must be 1)\n'; fail=$((fail+1))
printf 'demo: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
