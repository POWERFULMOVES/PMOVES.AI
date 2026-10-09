// Uniqueness for the CHIT geometry keys that 010 (and services/gateway workflow.py)
// MERGE on. Ported verbatim from
// docs/pmoves_all_in_one/pmoves_chit_patch/neo4j/migrations/001_chit.cql:1-4,
// which 010 ported the seed from but not the migration.
// CREATE CONSTRAINT fails if duplicates already exist; on a live graph run the
// duplicate precheck in docs/TAC/TAC_NEO4J.md section 6 first.
CREATE CONSTRAINT anchor_id IF NOT EXISTS FOR (a:Anchor) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT constellation_id IF NOT EXISTS FOR (c:Constellation) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT point_id IF NOT EXISTS FOR (p:Point) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT media_ref_id IF NOT EXISTS FOR (m:MediaRef) REQUIRE m.uid IS UNIQUE;
