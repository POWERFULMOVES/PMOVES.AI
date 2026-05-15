#!/usr/bin/env bash
# pmoves-living-docs-refresh — surface stale living docs + their regen recipe.
set -u
set -o pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
REGISTRY="${REPO_ROOT}/pmoves/configs/living_docs_registry.yaml"
MAKE_DIR="${REPO_ROOT}/pmoves"

if [[ ! -d "${MAKE_DIR}" ]]; then
  echo "ERROR: pmoves/ not found at ${MAKE_DIR}" >&2
  exit 2
fi

# Capture make output (don't fail this script just because docs are stale — surface it).
make_out="$(make -C "${MAKE_DIR}" docs-reconcile-check 2>&1 || true)"
make_exit=$?

echo "${make_out}"
echo "---"

# Extract candidate stale doc paths from the make output. The reconcile target
# tends to print lines containing "STALE", "stale", or doc-relative paths.
mapfile -t STALE_DOCS < <(
  echo "${make_out}" \
    | grep -oE '(pmoves/)?docs/[A-Za-z0-9_./-]+\.md' \
    | sort -u
)

if [[ ${#STALE_DOCS[@]} -eq 0 ]]; then
  echo "(no stale docs detected in make output)"
  echo "exit_code=${make_exit}"
  exit "${make_exit}"
fi

if [[ ! -f "${REGISTRY}" ]]; then
  echo "WARN: registry not found at ${REGISTRY}; printing stale paths only" >&2
  for d in "${STALE_DOCS[@]}"; do
    echo "[STALE] ${d} last-refreshed=? source=?"
  done
  echo "exit_code=${make_exit}"
  exit "${make_exit}"
fi

# Prefer PyYAML if present; fall back to grep-based mini-parser otherwise.
if python3 -c "import yaml" >/dev/null 2>&1; then
  python3 - "${REGISTRY}" "${STALE_DOCS[@]}" <<'PYEOF'
import sys, yaml, os

registry_path = sys.argv[1]
stale = sys.argv[2:]
try:
    with open(registry_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
except Exception as exc:
    print(f"WARN: failed to parse {registry_path}: {exc}", file=sys.stderr)
    for d in stale:
        print(f"[STALE] {d} last-refreshed=? source=?")
    sys.exit(0)

# Registry may be {documents: [{path, last_refreshed, source}, ...]} or a flat dict.
entries = []
if isinstance(data, dict):
    if "documents" in data and isinstance(data["documents"], list):
        entries = data["documents"]
    else:
        for k, v in data.items():
            if isinstance(v, dict):
                v = {**v, "path": v.get("path", k)}
                entries.append(v)

def find(path):
    for e in entries:
        ep = e.get("path") or e.get("doc") or ""
        if not ep:
            continue
        if ep.endswith(path) or path.endswith(ep) or os.path.basename(ep) == os.path.basename(path):
            return e
    return None

for d in stale:
    e = find(d)
    if e:
        lr = e.get("last_refreshed") or e.get("last-refreshed") or "?"
        src = e.get("source") or e.get("generator") or e.get("regen") or "?"
        print(f"[STALE] {d} last-refreshed={lr} source={src}")
    else:
        print(f"[STALE] {d} last-refreshed=? source=(not in registry)")
PYEOF
else
  # Grep fallback: hunt for the doc path in the yaml and grab nearby last_refreshed/source.
  for d in "${STALE_DOCS[@]}"; do
    basename_doc="$(basename "${d}")"
    # Pull a 6-line window around the path match.
    block="$(grep -A5 -F "${basename_doc}" "${REGISTRY}" 2>/dev/null | head -n6 || true)"
    lr="$(echo "${block}" | grep -oE 'last_refreshed:[[:space:]]*[^[:space:]]+' | head -n1 | awk -F: '{print $2}' | tr -d ' ')"
    src="$(echo "${block}" | grep -oE 'source:[[:space:]]*[^[:space:]]+' | head -n1 | awk -F: '{print $2}' | tr -d ' ')"
    echo "[STALE] ${d} last-refreshed=${lr:-?} source=${src:-?}"
  done
fi

echo "exit_code=${make_exit}"
exit "${make_exit}"
