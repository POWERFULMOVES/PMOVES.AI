// Neo4j seed script for persona alias relationships
// Expected to run after placing `person_aliases_seed.csv` in the Neo4j import directory.

LOAD CSV WITH HEADERS FROM 'file:///person_aliases_seed.csv' AS row
WITH row,
     CASE row.confidence WHEN '' THEN NULL ELSE toFloat(row.confidence) END AS confidence
WHERE row.alias IS NOT NULL AND trim(row.alias) <> ''

MERGE (persona:Persona {slug: trim(row.persona_slug)})
ON CREATE SET persona.name = row.persona_name
SET persona.name = coalesce(persona.name, row.persona_name)

MERGE (alias:Alias {value: trim(row.alias)})
SET alias.alias_type = row.alias_type,
    alias.source = row.source,
    alias.source_reference = row.source_reference,
    alias.notes = row.notes,
    alias.last_seeded_at = datetime()
FOREACH (_ IN CASE WHEN confidence IS NULL THEN [] ELSE [1] END |
    SET alias.confidence = confidence)

MERGE (persona)-[rel:HAS_ALIAS]->(alias)
SET rel.source = row.source,
    rel.source_reference = row.source_reference,
    rel.last_seeded_at = datetime()
FOREACH (_ IN CASE WHEN confidence IS NULL THEN [] ELSE [1] END |
    SET rel.confidence = confidence)

RETURN persona.slug AS persona_slug,
       alias.value AS alias,
       rel.confidence AS confidence
ORDER BY persona_slug, alias;
