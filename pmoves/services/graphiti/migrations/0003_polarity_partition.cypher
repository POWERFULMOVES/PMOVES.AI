// Migration 0003: Polarity Layer Partition
// Partitions graphiti nodes by polarity layer, making the
// Archon(1) ↔ Agent-Zero(0) polarity visible in the graph.
// Layers: intent | execution | arbiter | observation

// ── Layer nodes ──────────────────────────────────────────────
MERGE (li:Layer {name: 'intent'});
MERGE (le:Layer {name: 'execution'});
MERGE (la:Layer {name: 'arbiter'});
MERGE (lo:Layer {name: 'observation'});

// ── Constraint: unique agent_id ──────────────────────────────
CREATE CONSTRAINT agent_agent_id_unique IF NOT EXISTS
FOR (a:Agent) REQUIRE a.agent_id IS UNIQUE;

// ── Constraint: unique layer name ────────────────────────────
CREATE CONSTRAINT layer_name_unique IF NOT EXISTS
FOR (l:Layer) REQUIRE l.name IS UNIQUE;

// ── OPERATES_AT relationship type index ─────────────────────
CREATE INDEX operates_at_index IF NOT EXISTS
FOR ()-[r:OPERATES_AT]->()
ON (r.assigned_at);

// ── Partition agents by polarity layer ───────────────────────
// Archon → intent/arbiter, Agent-Zero → execution/observation
MATCH (a:Agent)
WHERE a.polarity = 1
WITH a
MATCH (l:Layer {name: 'intent'})
MERGE (a)-[:OPERATES_AT {assigned_at: datetime(), partition: 'polarity_1'}]->(l);

MATCH (a:Agent)
WHERE a.polarity = 1
WITH a
MATCH (l:Layer {name: 'arbiter'})
MERGE (a)-[:OPERATES_AT {assigned_at: datetime(), partition: 'polarity_1'}]->(l);

MATCH (a:Agent)
WHERE a.polarity = 0
WITH a
MATCH (l:Layer {name: 'execution'})
MERGE (a)-[:OPERATES_AT {assigned_at: datetime(), partition: 'polarity_0'}]->(l);

MATCH (a:Agent)
WHERE a.polarity = 0
WITH a
MATCH (l:Layer {name: 'observation'})
MERGE (a)-[:OPERATES_AT {assigned_at: datetime(), partition: 'polarity_0'}]->(l);

// ── Add layer property to Agent nodes for fast filtering ────
MATCH (a:Agent)-[:OPERATES_AT]->(l:Layer)
SET a.layer = l.name;
