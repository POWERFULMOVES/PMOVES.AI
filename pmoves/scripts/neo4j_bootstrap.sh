#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
# The compose-declared name (scripts/neo4j_container.py, #3193). The old default,
# pmoves-neo4j-1, matched no container, so this script skipped every run.
CONTAINER=${1:-$("${PYTHON_BIN:-python3}" "$ROOT/scripts/neo4j_container.py")} || exit 3
CSV_SRC="$ROOT/neo4j/datasets/person_aliases_seed.csv"
# The password comes from the canonical env (make neo4j-bootstrap sources
# with-env.sh) and reaches cypher-shell through its NEO4J_USERNAME / NEO4J_PASSWORD
# env vars (`cypher-shell --help`: "Can also be specified using the environment
# variable NEO4J_PASSWORD"), copied in by `docker exec -e NAME`: never argv, never
# read back out of the container, and never a fallback. Unset or empty fails closed.
if [ -z "${NEO4J_PASSWORD:-}" ]; then
  echo "ERROR: NEO4J_PASSWORD is unset or empty (env.shared via with-env.sh); refusing to fall back to a default password" >&2
  exit 1
fi
export NEO4J_PASSWORD
export NEO4J_USERNAME="${NEO4J_USER:-neo4j}"
cypher() { docker exec -i -e NEO4J_USERNAME -e NEO4J_PASSWORD "$CONTAINER" cypher-shell "$@"; }
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "↷ Neo4j container ${CONTAINER} not running; skipping bootstrap."
  exit 0
fi
if [ ! -f "$CSV_SRC" ]; then
  echo "⚠️  Seed CSV $CSV_SRC missing; skipping Neo4j bootstrap." >&2
  exit 0
fi
PYTHON_BIN=${PYTHON_BIN:-$(command -v python3 || command -v python || true)}
if [ -z "$PYTHON_BIN" ]; then
  echo "⚠️  python3/python not found on host; skipping Neo4j bootstrap." >&2
  exit 0
fi
echo "→ Applying Neo4j constraints and seed aliases via cypher-shell"
# Every file once, in name order; the smoke is a check, not a migration, and runs last.
CHIT_SMOKE="$ROOT/neo4j/cypher/011_chit_geometry_smoke.cypher"
for cypher in "$ROOT/neo4j/cypher/"*.cypher; do
  [ -f "$cypher" ] || continue
  [ "$cypher" = "$CHIT_SMOKE" ] && continue
  echo "   • $(basename "$cypher")"
  cypher < "$cypher" >/dev/null
done
$PYTHON_BIN - "$CSV_SRC" <<'PY' | cypher >/dev/null
import csv
import sys

path = sys.argv[1]
rows = []
with open(path, newline='', encoding='utf-8') as fh:
    reader = csv.DictReader(fh)
    for raw in reader:
        alias = (raw.get('alias') or '').strip()
        if not alias:
            continue
        persona_slug = (raw.get('persona_slug') or '').strip()
        persona_name = (raw.get('persona_name') or '').strip() or None
        alias_type = (raw.get('alias_type') or '').strip() or None
        source = (raw.get('source') or '').strip() or None
        source_reference = (raw.get('source_reference') or '').strip() or None
        notes = (raw.get('notes') or '').strip() or None
        confidence_raw = (raw.get('confidence') or '').strip()
        try:
            confidence = float(confidence_raw) if confidence_raw else None
        except ValueError:
            confidence = None
        rows.append({
            'persona_slug': persona_slug,
            'persona_name': persona_name,
            'alias': alias,
            'alias_type': alias_type,
            'source': source,
            'source_reference': source_reference,
            'notes': notes,
            'confidence': confidence,
        })

def cypher_literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, float):
        return repr(value)
    escaped = value.replace('\\\\', '\\\\\\').replace("'", "\\'")
    return f"'{escaped}'"

print("UNWIND [")
for idx, row in enumerate(rows):
    entries = []
    for key, value in row.items():
        entries.append(f"{key}: {cypher_literal(value)}")
    line = "  {" + ", ".join(entries) + "}"
    if idx < len(rows) - 1:
        line += ","
    print(line)
print("] AS row")
print(
"""
MERGE (persona:Persona {slug: row.persona_slug})
ON CREATE SET persona.name = row.persona_name
SET persona.name = coalesce(persona.name, row.persona_name)

MERGE (alias:Alias {value: row.alias})
SET alias.alias_type = row.alias_type,
    alias.source = row.source,
    alias.source_reference = row.source_reference,
    alias.notes = row.notes,
    alias.last_seeded_at = datetime()
FOREACH (_ IN CASE WHEN row.confidence IS NULL THEN [] ELSE [1] END |
    SET alias.confidence = row.confidence)

MERGE (persona)-[rel:HAS_ALIAS]->(alias)
SET rel.source = row.source,
    rel.source_reference = row.source_reference,
    rel.last_seeded_at = datetime()
FOREACH (_ IN CASE WHEN row.confidence IS NULL THEN [] ELSE [1] END |
    SET rel.confidence = row.confidence)

RETURN count(row) AS aliases_seeded;
"""
)
PY

# 010 already ran in the loop above. Until 2026-10 it and the smoke ran a second
# time here, and the smoke's `ok=false` was printed and ignored (exit 0).
if [ -f "$CHIT_SMOKE" ]; then
    echo "   • CHIT geometry smoke check"
    smoke=$(cypher --format plain < "$CHIT_SMOKE")
    echo "$smoke"
    if ! grep -q 'CHIT_SMOKE_OK' <<<"$smoke"; then
        echo "ERROR: CHIT geometry smoke failed (expected CHIT_SMOKE_OK; see neo4j/cypher/011_chit_geometry_smoke.cypher)" >&2
        exit 1
    fi
fi
echo "✔ Neo4j bootstrap complete."
