#!/usr/bin/env bash
# One Kilo review attempt, run on the self-hosted runner host.
#
# usage: kilo_review_tier.sh <out_file> <meta_file>
#
# Runs kilo_review_in_container.sh inside node:22-slim (the runner user can
# `sudo -n docker`), writes the review to <out_file> and `key=value` lines to
# <meta_file>:
#   model=<resolved id>   rc=<exit code>
#   status=catalog-empty|no-candidate|timeout   (only when applicable)
#   reason=<human text>
# The caller classifies on `status`, never on reserved exit codes (kilo's own
# exit codes would collide with them).
#
# Credentials go to docker through an --env-file (mode 0600, deleted by the
# EXIT trap), never as `-e KEY=value` on the docker argv, where any local user
# could read them from /proc/<pid>/cmdline.
#
# Every container carries the label pmoves.kilo-review=<run id>, so the
# workflow's always() cleanup step can remove it after a job cancel/timeout.
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
tier_timeout="${KILO_TIER_TIMEOUT:-720}"
label="pmoves.kilo-review=${GITHUB_RUN_ID:-local}"

# Copy the in-container script to /tmp: the mount source must be a host path,
# and /tmp is what this lane has always mounted from (the workspace path is
# not assumed to be host-visible to the docker daemon).
umask 077
run_script="$(mktemp /tmp/kilo-review-run.XXXXXX.sh)"
err_log="$(mktemp /tmp/kilo-review-err.XXXXXX.log)"
# The run id is in the name so the workflow's always() sweep removes only
# THIS run's files if the wrapper is SIGKILLed before its trap runs.
env_file="$(mktemp "/tmp/kilo-review-env.${GITHUB_RUN_ID:-local}.XXXXXX")"
trap 'rm -f "$run_script" "$err_log" "$env_file"' EXIT
cp "$here/kilo_review_in_container.sh" "$run_script"
chmod 0644 "$run_script"
{
  printf 'KILOCODE_API_KEY=%s\n' "${KILOCODE_API_KEY:-}"
  printf 'KILO_API_KEY=%s\n' "${KILO_API_KEY:-}"
  printf 'KILO_REVIEW_MODEL=%s\n' "${KILO_REVIEW_MODEL:-}"
  printf 'KILO_REVIEW_MODEL_PREFERENCES=%s\n' "${KILO_REVIEW_MODEL_PREFERENCES:-}"
  printf 'KILO_EXCLUDE_MODELS=%s\n' "${KILO_EXCLUDE_MODELS:-}"
  printf 'KILO_IGNORE_OVERRIDE=%s\n' "${KILO_IGNORE_OVERRIDE:-}"
} > "$env_file"
name="kilo-review-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-0}-$$"

rc=0
timeout --kill-after=15 "$tier_timeout" \
  sudo -n docker run --rm --name "$name" --label "$label" \
    --env-file "$env_file" \
    -v "$diff_file":/tmp/kilo-review.diff:ro \
    -v "$prompt_file":/tmp/kilo-review-prompt.md:ro \
    -v "$run_script":/tmp/kilo-review-run.sh:ro \
    -w /tmp \
    node:22-slim bash /tmp/kilo-review-run.sh \
    > "$out" 2> "$err_log" || rc=$?

timed_out=0
if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
  # timeout(1) kills the docker CLIENT; the container would keep running.
  sudo -n docker rm -f "$name" >/dev/null 2>&1 || true
  timed_out=1
fi

# Replay the resolver's annotations into the runner log.
grep -E '^(::(error|warning|notice)::|  kilo/|valid ids)' "$err_log" || true
model="$(sed -n 's/^KILO_RESOLVED_MODEL=//p' "$err_log" | tail -n 1)"
status="$(sed -n 's/^KILO_TIER_STATUS=//p' "$err_log" | tail -n 1)"
echo "model=${model}" >> "$meta"
echo "rc=${rc}" >> "$meta"
if [ "$timed_out" -eq 1 ]; then
  echo "status=timeout" >> "$meta"
  echo "reason=timed out after ${tier_timeout}s" >> "$meta"
elif [ "$status" = "catalog-empty" ]; then
  echo "status=catalog-empty" >> "$meta"
  echo "reason=kilo catalog returned 0 ids (could-not-measure)" >> "$meta"
elif [ "$status" = "no-candidate" ]; then
  echo "status=no-candidate" >> "$meta"
  echo "reason=no untried catalog-valid model left in the preference list" >> "$meta"
elif [ "$rc" -ne 0 ]; then
  echo "reason=kilo run failed (exit ${rc})" >> "$meta"
fi
if [ "$rc" -ne 0 ] || [ ! -s "$out" ]; then
  echo "::group::kilo stderr (last 20 lines, exit ${rc})"
  tail -n 20 "$err_log" || true
  echo "::endgroup::"
fi
exit "$rc"
