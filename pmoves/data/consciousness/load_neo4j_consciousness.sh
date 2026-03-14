#!/bin/bash
# PMOVES Consciousness Neo4j Schema Loader
# Simplified version for cypher-shell compatibility

set -euo pipefail

NEO4J_PASSWORD="${NEO4J_PASSWORD:-pm_kDhuaogcUc1oOOVeGMNCkQ}"
NEO4J_USER="neo4j"

echo "[PMOVES] Loading consciousness schema into Neo4j..."

# Create constraints and indexes
docker exec pmoves-neo4j-1 cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "
CREATE CONSTRAINT consciousness_category_name IF NOT EXISTS FOR (c:ConsciousnessCategory) REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT consciousness_theory_name IF NOT EXISTS FOR (t:ConsciousnessTheory) REQUIRE t.name IS UNIQUE;
CREATE CONSTRAINT consciousness_proponent_name IF NOT EXISTS FOR (p:Proponent) REQUIRE p.name IS UNIQUE;
CREATE INDEX consciousness_theory_category IF NOT EXISTS FOR (t:ConsciousnessTheory) ON (t.category);
" 2>&1

echo "[PMOVES] Constraints created, loading root node..."

# Create root node
docker exec pmoves-neo4j-1 cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "
MERGE (root:ConsciousnessRoot {name: 'Landscape of Consciousness'})
SET root.description = 'Robert Lawrence Kuhn\\'s taxonomy of 325 consciousness theories',
    root.source = 'Progress in Biophysics and Molecular Biology (2024)',
    root.namespace = 'pmoves.consciousness';
" 2>&1

echo "[PMOVES] Root node created, loading categories..."

# Create the 10 main categories (simplified)
docker exec pmoves-neo4j-1 cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "
MERGE (mat:ConsciousnessCategory {name: 'Materialism Theories'})
SET mat.id = 'materialism', mat.description = 'Theories holding that consciousness arises from physical brain processes', mat.order = 1;
MERGE (dual:ConsciousnessCategory {name: 'Dualisms'})
SET dual.id = 'dualism', dual.description = 'Mind and matter are fundamentally distinct', dual.order = 2;
MERGE (ideal:ConsciousnessCategory {name: 'Idealisms'})
SET ideal.id = 'idealism', ideal.description = 'Reality is fundamentally mental', ideal.order = 3;
MERGE (pan:ConsciousnessCategory {name: 'Panpsychisms'})
SET pan.id = 'panpsychism', pan.description = 'Consciousness is fundamental and ubiquitous', pan.order = 4;
MERGE (mon:ConsciousnessCategory {name: 'Monisms'})
SET mon.id = 'monism', mon.description = 'Reality consists of one fundamental substance', mon.order = 5;
MERGE (nrp:ConsciousnessCategory {name: 'Non-Reductive Physicalism'})
SET nrp.id = 'non-reductive-physicalism', nrp.description = 'Physicalism without reduction to brain states', nrp.order = 6;
MERGE (quant:ConsciousnessCategory {name: 'Quantum Theories'})
SET quant.id = 'quantum', quant.description = 'Quantum mechanical explanations of consciousness', quant.order = 7;
MERGE (iit:ConsciousnessCategory {name: 'Integrated Information Theory'})
SET iit.id = 'iit', iit.description = 'Consciousness as integrated information (Phi)', iit.order = 8;
MERGE (anom:ConsciousnessCategory {name: 'Anomalous Altered States'})
SET anom.id = 'anomalous', anom.description = 'Studies informed by altered states and anomalous experiences', anom.order = 9;
MERGE (chal:ConsciousnessCategory {name: 'Challenge Theories'})
SET chal.id = 'challenge', chal.description = 'Theories challenging standard assumptions', chal.order = 10;
" 2>&1

echo "[PMOVES] Categories created, linking to root..."

# Link categories to root
docker exec pmoves-neo4j-1 cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "
MATCH (root:ConsciousnessRoot {name: 'Landscape of Consciousness'})
MATCH (c:ConsciousnessCategory)
MERGE (root)-[:HAS_CATEGORY]->(c);
" 2>&1

echo "[PMOVES] Categories created, linking to root..."

# Link categories to root
docker exec pmoves-neo4j-1 cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "
MATCH (root:ConsciousnessRoot {name: 'Landscape of Consciousness'})
MATCH (c:ConsciousnessCategory)
MERGE (root)-[:HAS_CATEGORY]->(c);
" 2>&1

echo "[PMOVES] Adding Entity constraint for graph_match..."
docker exec pmoves-neo4j-1 cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;
" 2>&1

echo "[PMOVES] Creating sample theory Entity nodes..."

# Create sample theory Entity nodes with Entity label for graph_match
docker exec pmoves-neo4j-1 cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "
// Materialism Theories
MERGE (t1:ConsciousnessTheory:Entity {id: 'theory-identity-theory', name: 'Identity Theory'})
SET t1.category = 'Materialism Theories', t1.description = 'Mental states are identical to brain states', t1.type = 'theory';
MERGE (t2:ConsciousnessTheory:Entity {id: 'theory-functionalism', name: 'Functionalism'})
SET t2.category = 'Materialism Theories', t2.description = 'Mental states are functional roles', t2.type = 'theory';
MERGE (t3:ConsciousnessTheory:Entity {id: 'theory-eliminative-materialism', name: 'Eliminative Materialism'})
SET t3.category = 'Materialism Theories', t3.description = 'Folk psychology will be eliminated', t3.type = 'theory';

// Dualisms
MERGE (t4:ConsciousnessTheory:Entity {id: 'theory-property-dualism', name: 'Property Dualism'})
SET t4.category = 'Dualisms', t4.description = 'Mental properties are non-physical', t4.type = 'theory';
MERGE (t5:ConsciousnessTheory:Entity {id: 'theory-substance-dualism', name: 'Substance Dualism'})
SET t5.category = 'Dualisms', t5.description = 'Mind and body are distinct substances', t5.type = 'theory';

// Panpsychisms
MERGE (t6:ConsciousnessTheory:Entity {id: 'theory-panpsychism', name: 'Panpsychism'})
SET t6.category = 'Panpsychisms', t6.description = 'Consciousness is fundamental and ubiquitous', t6.type = 'theory';
MERGE (t7:ConsciousnessTheory:Entity {id: 'theory-panprotopsychism', name: 'Panprotopsychism'})
SET t7.category = 'Panpsychisms', t7.description = 'Consciousness emerges from proto-conscious properties', t7.type = 'theory';

// IIT
MERGE (t8:ConsciousnessTheory:Entity {id: 'theory-iit', name: 'Integrated Information Theory'})
SET t8.category = 'Integrated Information Theory', t8.description = 'Consciousness as integrated information (Phi)', t8.type = 'theory';

// Quantum Theories
MERGE (t9:ConsciousnessTheory:Entity {id: 'theory-orch-or', name: 'Orch-OR'})
SET t9.category = 'Quantum Theories', t9.description = 'Penrose-Hameroff orchestrated objective reduction', t9.type = 'theory';
" 2>&1

echo "[PMOVES] Creating proponent Entity nodes..."
docker exec pmoves-neo4j-1 cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "
// Proponents as Entity nodes
MERGE (p1:Proponent:Entity {id: 'proponent-david-chalmers', name: 'David Chalmers'})
SET p1.type = 'proponent', p1.affiliation = 'NYU';
MERGE (p2:Proponent:Entity {id: 'proponent-daniel-dennett', name: 'Daniel Dennett'})
SET p2.type = 'proponent', p2.affiliation = 'Tufts University';
MERGE (p3:Proponent:Entity {id: 'proponent-galen-strawson', name: 'Galen Strawson'})
SET p3.type = 'proponent', p3.affiliation = 'University of Texas';
MERGE (p4:Proponent:Entity {id: 'proponent-roger-penrose', name: 'Roger Penrose'})
SET p4.type = 'proponent', p4.affiliation = 'Oxford University';
MERGE (p5:Proponent:Entity {id: 'proponent-stuart-hameroff', name: 'Stuart Hameroff'})
SET p5.type = 'proponent', p5.affiliation = 'University of Arizona';
MERGE (p6:Proponent:Entity {id: 'proponent-giulio-tononi', name: 'Giulio Tononi'})
SET p6.type = 'proponent', p6.affiliation = 'University of Wisconsin';
MERGE (p7:Proponent:Entity {id: 'proponent-christof-koch', name: 'Christof Koch'})
SET p7.type = 'proponent', p7.affiliation = 'Allen Institute';
" 2>&1

echo "[PMOVES] Linking theories to proponents..."
docker exec pmoves-neo4j-1 cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "
// Link theories to proponents
MATCH (t:ConsciousnessTheory {name: 'Property Dualism'})
MATCH (p:Proponent {name: 'David Chalmers'})
MERGE (p)-[:PROPOSED]->(t);

MATCH (t:ConsciousnessTheory {name: 'Functionalism'})
MATCH (p:Proponent {name: 'Daniel Dennett'})
MERGE (p)-[:PROPOSED]->(t);

MATCH (t:ConsciousnessTheory {name: 'Panpsychism'})
MATCH (p:Proponent {name: 'Galen Strawson'})
MERGE (p)-[:PROPOSED]->(t);

MATCH (t:ConsciousnessTheory {name: 'Orch-OR'})
MATCH (p1:Proponent {name: 'Roger Penrose'})
MATCH (p2:Proponent {name: 'Stuart Hameroff'})
MERGE (p1)-[:PROPOSED]->(t);
MERGE (p2)-[:PROPOSED]->(t);

MATCH (t:ConsciousnessTheory {name: 'Integrated Information Theory'})
MATCH (p1:Proponent {name: 'Giulio Tononi'})
MATCH (p2:Proponent {name: 'Christof Koch'})
MERGE (p1)-[:PROPOSED]->(t);
MERGE (p2)-[:PROPOSED]->(t);
" 2>&1

echo "[PMOVES] Verifying Entity nodes..."
docker exec pmoves-neo4j-1 cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "
MATCH (e:Entity) RETURN count(e) as entity_count;
" 2>&1

echo "[PMOVES] Verifying load..."
docker exec pmoves-neo4j-1 cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "
MATCH (c:ConsciousnessCategory) RETURN c.name, c.id ORDER BY c.order;
" 2>&1

echo "[PMOVES] Consciousness schema loaded successfully!"
