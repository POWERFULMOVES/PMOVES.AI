#!/usr/bin/env bash
# Runs INSIDE the node:22-slim review container (see kilo_review_tier.sh).
#
# Installs the pinned Kilo CLI, queries the LIVE model catalog, resolves and
# validates a model, then reviews. Status goes to stderr as
# ::error::/::warning::/::notice:: lines plus a KILO_RESOLVED_MODEL= marker; the
# host replays them (workflow commands are only parsed from the runner's own
# log, not from a redirected file). The review itself is stdout.
#
# Model selection — never trusted, always checked against the live catalog:
#   KILO_REVIEW_MODEL             explicit override (primary tier only)
#   KILO_REVIEW_MODEL_PREFERENCES space-separated, ordered preference list
#   KILO_EXCLUDE_MODELS           space-separated ids already tried this run
#                                 (set by the fallback tier; skipped here)
#   KILO_IGNORE_OVERRIDE          non-empty -> fallback tier: ignore the
#                                 override, walk the preference list
#
# Exit codes: 0 = review written to stdout (validity is judged by the
# caller); anything else = failure. Tier STATUS is NOT an exit code (kilo's
# own exit codes would collide with any code reserved here): it is a
# `KILO_TIER_STATUS=<status>` marker line on stderr, which the host wrapper
# copies into its meta file:
#   catalog-empty  could-not-measure: the catalog query returned 0 ids
#   no-candidate   fallback tier only: every catalog-valid preference was
#                  already tried
#
# Ids are CLI ids: `<provider>/<gateway-id>`, i.e. `kilo/z-ai/glm-5.2`. A
# prefix-less override that exists as `kilo/<id>` is repaired with a warning
# (the missing prefix is how this lane died twice, #3080).
set -euo pipefail
set -f  # preference list is word-split on purpose; never glob-expanded

KILO_CLI_VERSION="${KILO_CLI_VERSION:-7.6.2}"
# Container-internal mount targets (see kilo_review_tier.sh); the prompt
# tells the model to read the diff at /review/kilo-review.diff.
REVIEW_PROMPT="${REVIEW_PROMPT:-/review/kilo-review-prompt.md}"
CATALOG="${KILO_CATALOG_FILE:-/tmp/kilo-catalog.txt}"

npm install -g "@kilocode/cli@${KILO_CLI_VERSION}" >/dev/null 2>&1
mkdir -p ~/.config/kilo && cd ~/.config/kilo
npm init -y >/dev/null 2>&1
npm install --no-audit --no-fund "@kilocode/plugin@${KILO_CLI_VERSION}" >/dev/null 2>&1
kilo models kilo 2>/dev/null | grep -E '^kilo/' | sort -u > "$CATALOG" || true
n=$(wc -l < "$CATALOG")
if [ "$n" -eq 0 ]; then
  echo "::error::kilo model catalog query ('kilo models kilo') returned 0 ids - cannot validate any model (could-not-measure)" >&2
  echo "KILO_TIER_STATUS=catalog-empty" >&2
  exit 1
fi
echo "::notice::kilo catalog: ${n} ids (kilo/*) from @kilocode/cli@${KILO_CLI_VERSION}" >&2

in_catalog() { grep -Fxq -- "$1" "$CATALOG"; }
excluded() { case " ${KILO_EXCLUDE_MODELS:-} " in *" $1 "*) return 0 ;; esac; return 1; }
suggest() {
  echo "valid ids in the live catalog (sample):" >&2
  { for p in ${KILO_REVIEW_MODEL_PREFERENCES:-}; do in_catalog "$p" && echo "$p"; done
    grep -E '^kilo/(z-ai|moonshotai|qwen|deepseek|minimax)/' "$CATALOG" | grep -v ':free$' | tail -n 8
  } | awk '!seen[$0]++' | head -n 12 | sed 's/^/  /' >&2 || true
}

MODEL=""
if [ -n "${KILO_REVIEW_MODEL:-}" ] && [ -z "${KILO_IGNORE_OVERRIDE:-}" ]; then
  cand="${KILO_REVIEW_MODEL}"
  if ! in_catalog "$cand" && in_catalog "kilo/${cand}"; then
    echo "::warning::KILO_REVIEW_MODEL='${cand}' is a gateway id without the CLI provider prefix; using 'kilo/${cand}'. Set the repo variable to 'kilo/${cand}'." >&2
    cand="kilo/${cand}"
  fi
  if ! in_catalog "$cand"; then
    echo "::error::KILO_REVIEW_MODEL='${KILO_REVIEW_MODEL}' is not in the live kilo catalog (${n} ids). Update the repo variable (gh variable set KILO_REVIEW_MODEL) or delete it to use the preference list." >&2
    suggest
    exit 1
  fi
  MODEL="$cand"
  echo "::notice::kilo review model: ${MODEL} (from KILO_REVIEW_MODEL, validated against catalog)" >&2
else
  for cand in ${KILO_REVIEW_MODEL_PREFERENCES:-}; do
    if excluded "$cand"; then
      echo "::notice::preferred model '${cand}' already tried this run; skipping" >&2
      continue
    fi
    if in_catalog "$cand"; then MODEL="$cand"; break; fi
    echo "::warning::preferred model '${cand}' is not in the live kilo catalog; trying next" >&2
  done
  if [ -z "$MODEL" ]; then
    if [ -n "${KILO_IGNORE_OVERRIDE:-}" ]; then
      echo "::notice::no untried catalog-valid model left in KILO_REVIEW_MODEL_PREFERENCES (already tried: '${KILO_EXCLUDE_MODELS:-}')" >&2
      echo "KILO_TIER_STATUS=no-candidate" >&2
      exit 1
    fi
    echo "::error::no model in KILO_REVIEW_MODEL_PREFERENCES ('${KILO_REVIEW_MODEL_PREFERENCES:-}') is in the live kilo catalog (${n} ids). Set KILO_REVIEW_MODEL or update the preference list." >&2
    suggest
    exit 1
  fi
  echo "::notice::kilo review model: ${MODEL} (first untried catalog hit in preference list)" >&2
fi

echo "KILO_RESOLVED_MODEL=${MODEL}" >&2
printf '{"model": "%s"}' "${MODEL}" > ~/.config/kilo/kilo.json
cd /tmp
kilo run --auto "$(cat "$REVIEW_PROMPT")"
