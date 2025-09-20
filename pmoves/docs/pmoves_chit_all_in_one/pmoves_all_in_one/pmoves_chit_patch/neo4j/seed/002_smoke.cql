MATCH (c:Constellation {id:'8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111'})-[:HAS]->(p:Point)-[:LOCATES]->(m:MediaRef)
RETURN size(collect(DISTINCT m.modality)) >= 2 AS ok;
