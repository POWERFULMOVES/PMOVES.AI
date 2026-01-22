#!/usr/bin/env bash
set -eu

# Load env if present
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -f "$REPO_ROOT/pmoves/scripts/with-env.sh" ]; then
  # shellcheck source=/dev/null
  . "$REPO_ROOT/pmoves/scripts/with-env.sh"
else
  if [ -f "$REPO_ROOT/pmoves/env.shared" ]; then
    set -a; . "$REPO_ROOT/pmoves/env.shared"; set +a
  fi
fi

BASE="${JELLYFIN_PUBLIC_BASE_URL:-http://localhost:8096}"
API="${JELLYFIN_API_KEY:-}"

if [ -z "$API" ] && [ -f "$REPO_ROOT/pmoves/env.shared" ]; then
  API=$(grep -m1 '^JELLYFIN_API_KEY=' "$REPO_ROOT/pmoves/env.shared" 2>/dev/null | cut -d= -f2- || true)
fi
if [ -z "$API" ]; then
  for f in "$REPO_ROOT/pmoves/.env.local" "$REPO_ROOT/pmoves/env.shared.generated" "$REPO_ROOT/pmoves/.env.generated"; do
    [ -f "$f" ] || continue
    L=$(grep -m1 '^JELLYFIN_API_KEY=' "$f" || true)
    if [ -n "$L" ]; then API="${L#JELLYFIN_API_KEY=}"; break; fi
  done
fi

if ! command -v jq >/dev/null 2>&1; then echo "jq is required"; exit 1; fi

if [ -z "$API" ]; then echo "Missing JELLYFIN_API_KEY"; exit 1; fi

echo "[Jellyfin] /System/Info"
curl -fsS "$BASE/System/Info?api_key=$API" | jq -e '.Version | length > 0' >/dev/null && echo OK

echo "[Jellyfin] /Plugins"
curl -fsS "$BASE/Plugins?api_key=$API" | jq -e 'type=="array"' >/dev/null && echo OK

echo "[Jellyfin] /web front-end"
curl -fsS "$BASE/web/index.html" >/dev/null && echo OK
