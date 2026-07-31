#!/usr/bin/env bash
# Pattern B consumer: install the newest CI CHIT bundle at the canonical
# user-scoped path so runnerless nodes never juggle run IDs or paths.
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
#     chit-bundle-*), download, install at CHIT_EXPORT_PATH.
#
# History: originally shipped with PR #2214 but the script file was lost to a
# same-tree collision before the squash — the make target dangled until this
# restoration.
set -euo pipefail

REPO="${PMOVES_REPO:-POWERFULMOVES/PMOVES.AI}"
WORKFLOW="sync-secrets-local.yml"
NODE="${PMOVES_NODE:-5090}"

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

RUN_ID="$(gh run list --repo "$REPO" --workflow "$WORKFLOW" --status success \
  --limit 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null || true)"
if [ -z "$RUN_ID" ] || [ "$RUN_ID" = "null" ]; then
  echo "❌ No successful $WORKFLOW run found. Dispatch one first:"
  echo "   gh workflow run $WORKFLOW --ref main -f targets=$NODE"
  exit 1
fi

ARTIFACT="$(gh api "repos/$REPO/actions/runs/$RUN_ID/artifacts" \
  --jq "[.artifacts[]|select(.name|startswith(\"chit-bundle-\"))|select(.expired|not)]
        | (map(select(.name|startswith(\"chit-bundle-$NODE-\"))) + .) | .[0].name // empty")"
if [ -z "$ARTIFACT" ]; then
  echo "❌ Run $RUN_ID has no unexpired chit-bundle-* artifact (retention is 1 day)."
  echo "   Dispatch a fresh run: gh workflow run $WORKFLOW --ref main -f targets=$NODE"
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo "→ Downloading $ARTIFACT from run $RUN_ID"
gh run download "$RUN_ID" --repo "$REPO" --name "$ARTIFACT" --dir "$TMP"

BUNDLE="$(find "$TMP" -name 'env.cgp.json' | head -1)"
[ -n "$BUNDLE" ] || { echo "❌ Artifact did not contain env.cgp.json"; exit 1; }

mkdir -p "$DEST_DIR"
cp "$BUNDLE" "$DEST"
echo "✔ CHIT bundle installed at $DEST (artifact: $ARTIFACT)"
echo "  Next: make -C pmoves secrets-funnel-sync-from-bundle (or the one-shot secrets-funnel-from-prod)"
