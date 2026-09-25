#!/usr/bin/env bash
# Pattern B consumer: install the newest CI CHIT bundle at the canonical
# user-scoped path so consumer nodes never juggle run IDs or paths.
#
# Producers vs consumers: only the LINUX ai-lab runners (spark, b850) can run
# sync-secrets-local.yml. The 4090 and 5090 DO have online Windows runners,
# but they are consumers: the workflow's `shell: bash` steps run under WSL
# bash there and die on the mangled Windows script path, so the workflow now
# refuses those targets. Windows nodes run THIS script instead.
#
#   make -C pmoves secrets-pull                # this script
#   make -C pmoves secrets-funnel-from-prod    # pull + materialize tier files
#
# Contract (SECRETS_DISTRIBUTION_PATTERNS.md, Pattern B):
#   - producer: .github/workflows/sync-secrets-local.yml uploads
#     chit-bundle-<target>-<run_id> (CHIT hex-encoded env.cgp.json, no
#     cleartext) with 1-day retention.
#   - consumer (this script): resolve the newest SUCCESSFUL run, pick this
#     node's bundle (PMOVES_NODE, default 5090; falls back to any
#     chit-bundle-*), validate the payload, install 0600 at CHIT_EXPORT_PATH.
#
# History: originally shipped with PR #2214 but pmoves/scripts/secrets/ is
# gitignored, so the file never landed — the make target dangled until this
# restoration (PR #2310).
set -euo pipefail

REPO="${PMOVES_REPO:-POWERFULMOVES/PMOVES.AI}"
WORKFLOW="sync-secrets-local.yml"
NODE="${PMOVES_NODE:-5090}"
# Ordered producer targets for recovery dispatch hints. Must be LINUX
# runner-backed labels and must stay in step with PRODUCER_TARGETS in
# .github/workflows/sync-secrets-local.yml, which rejects any other target.
# (4090/5090 have Windows runners but are consumers -- dispatching
# targets=5090 fails fast by design.) PMOVES_BUNDLE_PRODUCER (singular) is the
# legacy override and is still honoured when the list is unset.
PRODUCERS="${PMOVES_BUNDLE_PRODUCERS:-${PMOVES_BUNDLE_PRODUCER:-spark,b850}}"

# Canonical bundle path — mirrors mk/codex.mk CHIT_EXPORT_PATH resolution.
if [ -n "${CHIT_EXPORT_PATH:-}" ]; then
  DEST="$CHIT_EXPORT_PATH"
elif [ -n "${APPDATA:-}" ]; then
  DEST="$APPDATA/pmoves/chit/env.cgp.json"
else
  DEST="${XDG_CONFIG_HOME:-$HOME/.config}/pmoves/chit/env.cgp.json"
fi
# gh on Windows handles forward slashes; normalize backslashes for bash.
DEST="${DEST//\\//}"
DEST_DIR="$(dirname "$DEST")"

command -v gh >/dev/null || { echo "❌ gh CLI required"; exit 1; }

# Distinguish gh auth/API failures from a genuine absence of successful runs.
GH_ERR="$(mktemp)"
RUN_ID="$(gh run list --repo "$REPO" --workflow "$WORKFLOW" --status success \
  --limit 1 --json databaseId --jq '.[0].databaseId' 2>"$GH_ERR" || true)"
if [ -s "$GH_ERR" ] && { [ -z "$RUN_ID" ] || [ "$RUN_ID" = "null" ]; }; then
  echo "❌ gh query failed (auth/API error, NOT necessarily missing runs):"
  sed 's/^/   /' "$GH_ERR"
  command rm -- "$GH_ERR"
  exit 1
fi
command rm -- "$GH_ERR"
if [ -z "$RUN_ID" ] || [ "$RUN_ID" = "null" ]; then
  echo "❌ No successful $WORKFLOW run found. Dispatch one on the Linux producers ($PRODUCERS):"
  echo "   gh workflow run $WORKFLOW --ref main -f targets=$PRODUCERS"
  exit 1
fi

ARTIFACT="$(gh api "repos/$REPO/actions/runs/$RUN_ID/artifacts" \
  --jq "[.artifacts[]|select(.name|startswith(\"chit-bundle-\"))|select(.expired|not)]
        | (map(select(.name|startswith(\"chit-bundle-$NODE-\"))) + .) | .[0].name // empty")"
if [ -z "$ARTIFACT" ]; then
  echo "❌ Run $RUN_ID has no unexpired chit-bundle-* artifact (retention is 1 day)."
  echo "   Dispatch a fresh run on the Linux producers ($PRODUCERS):"
  echo "   gh workflow run $WORKFLOW --ref main -f targets=$PRODUCERS"
  exit 1
fi

TMP="$(mktemp -d)"
cleanup() { command rm -r -f -- "$TMP"; }
trap cleanup EXIT
echo "→ Downloading $ARTIFACT from run $RUN_ID"
gh run download "$RUN_ID" --repo "$REPO" --name "$ARTIFACT" --dir "$TMP"

BUNDLE="$(find "$TMP" -name 'env.cgp.json' | head -1)"
[ -n "$BUNDLE" ] || { echo "❌ Artifact did not contain env.cgp.json"; exit 1; }

# Validate the payload BEFORE touching the destination — an empty/corrupt
# artifact must never clobber a working bundle.
python - "$BUNDLE" <<'PYEOF' || { echo "❌ Downloaded bundle failed validation — keeping any existing bundle."; exit 1; }
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)
if not isinstance(data, dict) or not data:
    raise SystemExit("empty or non-object CGP payload")
PYEOF

mkdir -p "$DEST_DIR"
# Owner-only perms, atomic replace: stage next to the destination, chmod,
# then move over any old bundle (matches the workflow's 0600 install).
STAGE="$DEST.tmp.$$"
cp "$BUNDLE" "$STAGE"
chmod 600 "$STAGE"
# -f: on a producer node the runner (root) may own the old bundle; without -f
# mv PROMPTS on a tty before replacing a read-only file.
mv -f -- "$STAGE" "$DEST"

# PROVENANCE MARKER -- who wrote this bundle.
#
# `chit-export` writes to the SAME path (CHIT_EXPORT_PATH, mk/codex.mk:4), and it
# runs as the second step of `secrets-rotate`. So rotating ANY unrelated secret
# silently replaces a CI bundle with a local export derived from env.shared --
# which is a strict subset, because prod-only keys never live in env.shared.
#
# Measured 2026-09-03 on the 4090: MINIMAX_TOKEN_PLAN_API_KEY arrived via this
# bundle, reached env.tier-llm, and TensorZero came up healthy. Three later
# `secrets-rotate` runs (for NATS_PASSWORD and DEFAULT_VOICE_PROVIDER) each
# overwrote the bundle, the next ordinary funnel regenerated env.tier-llm without
# the key, and the gateway crash-looped again hours later -- presenting as an
# unrelated regression in a service nobody had touched.
#
# Nothing warned, because a producer and a consumer shared one path with no way
# to tell the two apart. This marker is that way: chit-export reads it and
# refuses rather than clobbering a bundle it did not produce.
#
# Stage-and-rename, like the bundle above. On a PRODUCER node the runner
# container (root) stamps this same marker through its bind mount, leaving it
# root-owned 0600; a direct `> "$DEST.provenance"` from the operator then fails
# with "Permission denied" (measured on B850, 2026-09-25) and the marker keeps
# naming the runner's artifact instead of the one just installed. A rename only
# needs write permission on the (user-owned) directory, so it replaces it;
# -f because mv would otherwise PROMPT on a tty for a read-only destination.
PROV_STAGE="$DEST.provenance.tmp.$$"
if printf '%s\n' \
     "source=ci" \
     "artifact=$ARTIFACT" \
     "installed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     > "$PROV_STAGE" 2>/dev/null \
   && chmod 600 "$PROV_STAGE" 2>/dev/null \
   && mv -f -- "$PROV_STAGE" "$DEST.provenance" 2>/dev/null; then
  :
else
  if [ -e "$PROV_STAGE" ]; then command rm -- "$PROV_STAGE" 2>/dev/null || true; fi
  echo "⚠ Could not write the provenance marker $DEST.provenance -- chit-export may not recognise this bundle as CI-pulled."
fi

echo "✔ CHIT bundle installed at $DEST (artifact: $ARTIFACT, mode 0600)"
echo "  Next: make -C pmoves secrets-funnel-sync-from-bundle (or the one-shot secrets-funnel-from-prod)"
