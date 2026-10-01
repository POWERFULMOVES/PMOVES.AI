// Read-only check of the 010 fixture, after
// docs/pmoves_chit_all_in_one/.../neo4j/seed/002_smoke.cql.
// Always returns exactly one row (OPTIONAL MATCH + aggregation without a grouping
// key), so a missing fixture reads as CHIT_SMOKE_FAIL with zero counts rather than
// as no output. Labels are in every pattern, so the unlabeled pairs the old 003
// created cannot satisfy it. scripts/neo4j_bootstrap.sh exits non-zero unless the
// verdict is CHIT_SMOKE_OK.

OPTIONAL MATCH (a:Anchor {id:'6d8d2e65-b6b9-4d3a-9b5e-3a9c42c1b111'})-[:FORMS]->(c:Constellation {id:'8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111'})
OPTIONAL MATCH (c)-[:HAS]->(p:Point)
OPTIONAL MATCH (p)-[:LOCATES]->(m:MediaRef)
WITH count(DISTINCT a) AS anchors, count(DISTINCT p) AS points, count(DISTINCT m) AS media_refs,
     size(collect(DISTINCT m.modality)) AS modalities
RETURN CASE WHEN anchors = 1 AND points = 3 AND media_refs = 3 AND modalities >= 2
            THEN 'CHIT_SMOKE_OK' ELSE 'CHIT_SMOKE_FAIL' END AS verdict,
       anchors, points, media_refs, modalities;
