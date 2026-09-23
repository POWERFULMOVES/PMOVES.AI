#!/usr/bin/env bash
# One Kilo review attempt, run on the self-hosted runner host.
#
# usage: kilo_review_tier.sh <out_file> <meta_file>
#
# Runs kilo_review_in_container.sh inside node:22-slim (the runner user can
# `sudo -n docker`), writes the review to <out_file> and `key=value` lines to
# <meta_file> (model=, rc=, reason=). Exit code is the container's (see the
# in-container script for its meaning), or 124 on timeout.
#
# Called by review_chain.py for tier 1 (kilo-primary) and tier 3
# (kilo-alternate, with KILO_IGNORE_OVERRIDE=1 and KILO_EXCLUDE_MODELS set).
set -euo pipefail

out="$1"
meta="$2"
: > "$out"
: > "$meta"

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
diff_file="${REVIEW_DIFF:-/tmp/kilo-review.diff}"
prompt_file="${REVIEW_PROMPT:-/tmp/kilo-review-prompt.md}"
tier_timeout="${KILO_TIER_TIMEOUT:-900}"

# Copy the in-container script to /tmp: the mount source must be a host path,
# and /tmp is what this lane has always mounted from (the workspace path is
# not assumed to be host-visible to the docker daemon).
run_script="$(mktemp /tmp/kilo-review-run.XXXXXX.sh)"
err_log="$(mktemp /tmp/kilo-review-err.XXXXXX.log)"
cp "$here/kilo_review_in_container.sh" "$run_script"
chmod 0644 "$run_script"
name="kilo-review-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-0}-$$"

rc=0
timeout --kill-after=15 "$tier_timeout" \
  sudo -n docker run --rm --name "$name" \
    -e KILOCODE_API_KEY="${KILOCODE_API_KEY:-}" \
    -e KILO_API_KEY="${KILO_API_KEY:-}" \
    -e KILO_REVIEW_MODEL="${KILO_REVIEW_MODEL:-}" \
    -e KILO_REVIEW_MODEL_PREFERENCES="${KILO_REVIEW_MODEL_PREFERENCES:-}" \
    -e KILO_EXCLUDE_MODELS="${KILO_EXCLUDE_MODELS:-}" \
    -e KILO_IGNORE_OVERRIDE="${KILO_IGNORE_OVERRIDE:-}" \
    -v "$diff_file":/tmp/kilo-review.diff:ro \
    -v "$prompt_file":/tmp/kilo-review-prompt.md:ro \
    -v "$run_script":/tmp/kilo-review-run.sh:ro \
    -w /tmp \
    node:22-slim bash /tmp/kilo-review-run.sh \
    > "$out" 2> "$err_log" || rc=$?

if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
  # timeout(1) kills the docker CLIENT; the container would keep running.
  sudo -n docker rm -f "$name" >/dev/null 2>&1 || true
  echo "reason=timed out after ${tier_timeout}s" >> "$meta"
  rc=124
fi

# Replay the resolver's annotations into the runner log.
grep -E '^(::(error|warning|notice)::|  kilo/|valid ids)' "$err_log" || true
model="$(sed -n 's/^KILO_RESOLVED_MODEL=//p' "$err_log" | tail -n 1)"
echo "model=${model}" >> "$meta"
echo "rc=${rc}" >> "$meta"
case "$rc" in
  0) ;;
  3) echo "reason=kilo catalog returned 0 ids (could-not-measure)" >> "$meta" ;;
  4) echo "reason=no untried catalog-valid model left in the preference list" >> "$meta" ;;
  124) ;;
  *)
    echo "reason=kilo run failed (exit ${rc})" >> "$meta"
    echo "::group::kilo stderr (last 20 lines, exit ${rc})"
    tail -n 20 "$err_log" || true
    echo "::endgroup::"
    ;;
esac
if [ "$rc" -eq 0 ] && [ ! -s "$out" ]; then
  echo "::group::kilo stderr (last 20 lines; exited 0 with no output)"
  tail -n 20 "$err_log" || true
  echo "::endgroup::"
fi
rm -f "$run_script" "$err_log"
exit "$rc"
