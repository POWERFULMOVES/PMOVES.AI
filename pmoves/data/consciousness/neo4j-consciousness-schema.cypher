// PMOVES Consciousness Mind Map - Neo4j Schema
// Kuhn's Landscape of Consciousness (325 theories)
// Generated: 2025-12-09

// =============================================================================
// CONSTRAINTS AND INDEXES
// =============================================================================

// Node constraints
CREATE CONSTRAINT consciousness_category_name IF NOT EXISTS
FOR (c:ConsciousnessCategory) REQUIRE c.name IS UNIQUE;

CREATE CONSTRAINT consciousness_subcategory_name IF NOT EXISTS
FOR (s:ConsciousnessSubcategory) REQUIRE s.id IS UNIQUE;

CREATE CONSTRAINT consciousness_theory_name IF NOT EXISTS
FOR (t:ConsciousnessTheory) REQUIRE t.name IS UNIQUE;

CREATE CONSTRAINT consciousness_proponent_name IF NOT EXISTS
FOR (p:Proponent) REQUIRE p.name IS UNIQUE;

CREATE CONSTRAINT consciousness_implication_name IF NOT EXISTS
FOR (i:Implication) REQUIRE i.name IS UNIQUE;

// Indexes for faster queries
CREATE INDEX consciousness_theory_category IF NOT EXISTS
FOR (t:ConsciousnessTheory) ON (t.category);

CREATE INDEX consciousness_proponent_search IF NOT EXISTS
FOR (p:Proponent) ON (p.name);

// =============================================================================
// CLEAR EXISTING CONSCIOUSNESS DATA (optional - uncomment to reset)
// =============================================================================
// MATCH (n) WHERE n:ConsciousnessCategory OR n:ConsciousnessSubcategory
//   OR n:ConsciousnessTheory OR n:Proponent OR n:Implication
// DETACH DELETE n;

// =============================================================================
// CREATE ROOT NODE
// =============================================================================

MERGE (root:ConsciousnessRoot {name: "Landscape of Consciousness"})
SET root.description = "Robert Lawrence Kuhn's taxonomy of 325 consciousness theories",
    root.source = "Progress in Biophysics and Molecular Biology (2024)",
    root.doi = "10.1016/j.pbiomolbio.2023.12.003",
    root.namespace = "pmoves.consciousness";

// =============================================================================
// 1. MATERIALISM THEORIES
// =============================================================================

MERGE (mat:ConsciousnessCategory {name: "Materialism Theories"})
SET mat.id = "materialism",
    mat.description = "Theories holding that consciousness arises from or is identical to physical brain processes",
    mat.order = 1;

MERGE (root)-[:HAS_CATEGORY]->(mat);

// 1.1 Philosophical Materialism
MERGE (phil:ConsciousnessSubcategory {id: "materialism-philosophical"})
SET phil.name = "Philosophical Materialism",
    phil.description = "Philosophical arguments for consciousness as purely physical";
MERGE (mat)-[:HAS_SUBCATEGORY]->(phil);

WITH phil
UNWIND [
  {name: "Eliminative Materialism", proponents: ["Paul Churchland", "Patricia Churchland"], desc: "Folk psychology concepts will be eliminated by neuroscience"},
  {name: "Reductive Materialism", proponents: ["J.J.C. Smart", "U.T. Place"], desc: "Mental states are identical to brain states"},
  {name: "Type Identity Theory", proponents: ["Herbert Feigl", "J.J.C. Smart"], desc: "Each mental type is identical to a brain state type"},
  {name: "Token Identity Theory", proponents: ["Donald Davidson"], desc: "Each mental token is identical to a physical token"},
  {name: "Functionalism", proponents: ["Hilary Putnam", "Jerry Fodor"], desc: "Mental states defined by functional roles"},
  {name: "Analytical Functionalism", proponents: ["David Lewis", "Frank Jackson"], desc: "Mental concepts analyzed as functional concepts"},
  {name: "Psychofunctionalism", proponents: ["Jerry Fodor"], desc: "Mental states identified via psychological theory"},
  {name: "Machine Functionalism", proponents: ["Hilary Putnam"], desc: "Mind as computational state machine"},
  {name: "Homuncular Functionalism", proponents: ["William Lycan"], desc: "Hierarchical functional decomposition"},
  {name: "Teleofunctionalism", proponents: ["Ruth Millikan", "Fred Dretske"], desc: "Functions defined by evolutionary history"}
] AS theory
MERGE (t:ConsciousnessTheory {name: theory.name})
SET t.description = theory.desc,
    t.category = "Materialism Theories",
    t.subcategory = "Philosophical Materialism"
MERGE (phil)-[:CONTAINS_THEORY]->(t)
WITH t, theory
UNWIND theory.proponents AS proponentName
MERGE (p:Proponent {name: proponentName})
MERGE (t)-[:PROPOSED_BY]->(p);

// 1.2 Neurobiological
MERGE (neuro:ConsciousnessSubcategory {id: "materialism-neurobiological"})
SET neuro.name = "Neurobiological",
    neuro.description = "Consciousness explained through neural mechanisms";
MERGE (mat)-[:HAS_SUBCATEGORY]->(neuro);

WITH neuro
UNWIND [
  {name: "Global Workspace Theory", proponents: ["Bernard Baars", "Stanislas Dehaene"], desc: "Consciousness as global information broadcast"},
  {name: "Global Neuronal Workspace", proponents: ["Stanislas Dehaene", "Jean-Pierre Changeux"], desc: "Cortical workspace for conscious access"},
  {name: "Neural Correlates of Consciousness", proponents: ["Christof Koch", "Francis Crick"], desc: "Neural patterns correlating with consciousness"},
  {name: "Recurrent Processing Theory", proponents: ["Victor Lamme"], desc: "Recurrent cortical loops generate consciousness"},
  {name: "Predictive Processing", proponents: ["Karl Friston", "Andy Clark"], desc: "Consciousness from prediction error minimization"},
  {name: "Active Inference", proponents: ["Karl Friston"], desc: "Free energy minimization framework"},
  {name: "Higher-Order Thought Theory", proponents: ["David Rosenthal"], desc: "Consciousness requires higher-order representations"},
  {name: "Higher-Order Perception Theory", proponents: ["William Lycan"], desc: "Inner perception of mental states"},
  {name: "Self-Representationalism", proponents: ["Uriah Kriegel"], desc: "Conscious states represent themselves"},
  {name: "Attended Intermediate Representations", proponents: ["Jesse Prinz"], desc: "Attention to mid-level representations"},
  {name: "Thalamo-Cortical Theory", proponents: ["Rodolfo Llinas"], desc: "Thalamic-cortical oscillations generate consciousness"},
  {name: "Dynamic Core Hypothesis", proponents: ["Gerald Edelman", "Giulio Tononi"], desc: "Integrated neural activity cluster"},
  {name: "Claustrum Theory", proponents: ["Francis Crick", "Christof Koch"], desc: "Claustrum as consciousness conductor"},
  {name: "Neuronal Synchrony", proponents: ["Wolf Singer"], desc: "Gamma oscillation binding"},
  {name: "Neural Darwinism", proponents: ["Gerald Edelman"], desc: "Selectionist neural development"},
  {name: "Reentry Theory", proponents: ["Gerald Edelman"], desc: "Recursive signaling loops"},
  {name: "Microconsciousness", proponents: ["Semir Zeki"], desc: "Distributed micro-conscious processes"}
] AS theory
MERGE (t:ConsciousnessTheory {name: theory.name})
SET t.description = theory.desc,
    t.category = "Materialism Theories",
    t.subcategory = "Neurobiological"
MERGE (neuro)-[:CONTAINS_THEORY]->(t)
WITH t, theory
UNWIND theory.proponents AS proponentName
MERGE (p:Proponent {name: proponentName})
MERGE (t)-[:PROPOSED_BY]->(p);

// 1.3 Electromagnetic Field
MERGE (em:ConsciousnessSubcategory {id: "materialism-electromagnetic"})
SET em.name = "Electromagnetic Field",
    em.description = "Consciousness as electromagnetic field phenomenon";
MERGE (mat)-[:HAS_SUBCATEGORY]->(em);

WITH em
UNWIND [
  {name: "CEMI Field Theory", proponents: ["Johnjoe McFadden"], desc: "Consciousness is the brain's EM field"},
  {name: "EM Field Theory", proponents: ["Susan Pockett"], desc: "Experience identical to EM patterns"},
  {name: "Resonance Theory", proponents: ["Tam Hunt", "Jonathan Schooler"], desc: "Shared resonance creates consciousness"}
] AS theory
MERGE (t:ConsciousnessTheory {name: theory.name})
SET t.description = theory.desc,
    t.category = "Materialism Theories",
    t.subcategory = "Electromagnetic Field"
MERGE (em)-[:CONTAINS_THEORY]->(t)
WITH t, theory
UNWIND theory.proponents AS proponentName
MERGE (p:Proponent {name: proponentName})
MERGE (t)-[:PROPOSED_BY]->(p);

// 1.4 Computational/Informational
MERGE (comp:ConsciousnessSubcategory {id: "materialism-computational"})
SET comp.name = "Computational Informational",
    comp.description = "Consciousness as information processing";
MERGE (mat)-[:HAS_SUBCATEGORY]->(comp);

WITH comp
UNWIND [
  {name: "Computational Theory of Mind", proponents: ["Jerry Fodor", "Zenon Pylyshyn"], desc: "Mind as computational system"},
  {name: "Attention Schema Theory", proponents: ["Michael Graziano"], desc: "Brain models attention as consciousness"},
  {name: "Multiple Drafts Model", proponents: ["Daniel Dennett"], desc: "Parallel content fixation"},
  {name: "Virtual Machine Consciousness", proponents: ["Daniel Dennett"], desc: "Consciousness as software"},
  {name: "Society of Mind", proponents: ["Marvin Minsky"], desc: "Mind as agent society"},
  {name: "Strange Loop Theory", proponents: ["Douglas Hofstadter"], desc: "Self-referential loops create self"},
  {name: "Predictive Coding", proponents: ["Rajesh Rao", "Dana Ballard"], desc: "Hierarchical prediction"},
  {name: "Bayesian Brain", proponents: ["Karl Friston"], desc: "Probabilistic inference"}
] AS theory
MERGE (t:ConsciousnessTheory {name: theory.name})
SET t.description = theory.desc,
    t.category = "Materialism Theories",
    t.subcategory = "Computational Informational"
MERGE (comp)-[:CONTAINS_THEORY]->(t)
WITH t, theory
UNWIND theory.proponents AS proponentName
MERGE (p:Proponent {name: proponentName})
MERGE (t)-[:PROPOSED_BY]->(p);

// 1.5 Homeostatic/Affective
MERGE (home:ConsciousnessSubcategory {id: "materialism-homeostatic"})
SET home.name = "Homeostatic Affective",
    home.description = "Consciousness rooted in bodily regulation and affect";
MERGE (mat)-[:HAS_SUBCATEGORY]->(home);

WITH home
UNWIND [
  {name: "Somatic Marker Hypothesis", proponents: ["Antonio Damasio"], desc: "Emotions guide conscious decisions"},
  {name: "Affective Neuroscience", proponents: ["Jaak Panksepp"], desc: "Subcortical affective systems"},
  {name: "Core Consciousness", proponents: ["Antonio Damasio"], desc: "Proto-self and core self"},
  {name: "Interoceptive Inference", proponents: ["Anil Seth"], desc: "Body-based predictive processing"},
  {name: "Primordial Emotions", proponents: ["Derek Denton"], desc: "Ancient emotional substrates"}
] AS theory
MERGE (t:ConsciousnessTheory {name: theory.name})
SET t.description = theory.desc,
    t.category = "Materialism Theories",
    t.subcategory = "Homeostatic Affective"
MERGE (home)-[:CONTAINS_THEORY]->(t)
WITH t, theory
UNWIND theory.proponents AS proponentName
MERGE (p:Proponent {name: proponentName})
MERGE (t)-[:PROPOSED_BY]->(p);

// 1.6 Embodied/Enactive
MERGE (emb:ConsciousnessSubcategory {id: "materialism-embodied"})
SET emb.name = "Embodied Enactive",
    emb.description = "Consciousness from embodied interaction";
MERGE (mat)-[:HAS_SUBCATEGORY]->(emb);

WITH emb
UNWIND [
  {name: "Enactivism", proponents: ["Francisco Varela", "Evan Thompson", "Eleanor Rosch"], desc: "Sensorimotor coupling with world"},
  {name: "Autopoiesis", proponents: ["Humberto Maturana", "Francisco Varela"], desc: "Self-creating living systems"},
  {name: "Extended Mind", proponents: ["Andy Clark", "David Chalmers"], desc: "Cognition extends beyond brain"},
  {name: "Radical Embodiment", proponents: ["Lawrence Shapiro"], desc: "Body shapes cognition fundamentally"},
  {name: "Sensorimotor Contingency", proponents: ["Kevin O'Regan", "Alva Noe"], desc: "Knowledge of sensorimotor laws"},
  {name: "4E Cognition", proponents: ["Various"], desc: "Embodied, Embedded, Enacted, Extended"},
  {name: "Ecological Psychology", proponents: ["James Gibson"], desc: "Direct perception of affordances"},
  {name: "Grounded Cognition", proponents: ["Lawrence Barsalou"], desc: "Modal simulations ground concepts"}
] AS theory
MERGE (t:ConsciousnessTheory {name: theory.name})
SET t.description = theory.desc,
    t.category = "Materialism Theories",
    t.subcategory = "Embodied Enactive"
MERGE (emb)-[:CONTAINS_THEORY]->(t)
WITH t, theory
UNWIND theory.proponents AS proponentName
MERGE (p:Proponent {name: proponentName})
MERGE (t)-[:PROPOSED_BY]->(p);

// =============================================================================
// 2. NON-REDUCTIVE PHYSICALISM
// =============================================================================

MERGE (nrp:ConsciousnessCategory {name: "Non-Reductive Physicalism"})
SET nrp.id = "non-reductive-physicalism",
    nrp.description = "Mental properties are physical but not reducible to lower-level descriptions",
    nrp.order = 2;

MERGE (root)-[:HAS_CATEGORY]->(nrp);

WITH nrp
UNWIND [
  {name: "Nonreductive Physicalism", proponents: ["Donald Davidson"], desc: "Mental properties not reducible to physical"},
  {name: "Emergentism", proponents: ["C.D. Broad", "Samuel Alexander"], desc: "Consciousness as emergent property"},
  {name: "Anomalous Monism", proponents: ["Donald Davidson"], desc: "Mental events physical but anomalous"},
  {name: "Supervenience Physicalism", proponents: ["Jaegwon Kim"], desc: "Mental supervenes on physical"},
  {name: "Strong Emergence", proponents: ["Timothy O'Connor"], desc: "Irreducible causal powers"},
  {name: "Downward Causation", proponents: ["Roger Sperry"], desc: "Higher levels cause lower"}
] AS theory
MERGE (t:ConsciousnessTheory {name: theory.name})
SET t.description = theory.desc,
    t.category = "Non-Reductive Physicalism"
MERGE (nrp)-[:CONTAINS_THEORY]->(t)
WITH t, theory
UNWIND theory.proponents AS proponentName
MERGE (p:Proponent {name: proponentName})
MERGE (t)-[:PROPOSED_BY]->(p);

// =============================================================================
// 3. QUANTUM THEORIES
// =============================================================================

MERGE (qt:ConsciousnessCategory {name: "Quantum Theories"})
SET qt.id = "quantum",
    qt.description = "Consciousness involves quantum mechanical processes",
    qt.order = 3;

MERGE (root)-[:HAS_CATEGORY]->(qt);

WITH qt
UNWIND [
  {name: "Orchestrated Objective Reduction", proponents: ["Roger Penrose", "Stuart Hameroff"], desc: "Quantum computations in microtubules"},
  {name: "Quantum Mind", proponents: ["Henry Stapp"], desc: "QM essential for consciousness"},
  {name: "Quantum Brain Dynamics", proponents: ["Giuseppe Vitiello", "Mari Jibu"], desc: "Quantum field dynamics in brain"},
  {name: "Bohm Implicate Order", proponents: ["David Bohm"], desc: "Consciousness in implicate order"},
  {name: "Quantum Holonomic Brain", proponents: ["Karl Pribram"], desc: "Holographic brain theory"},
  {name: "Many Minds Interpretation", proponents: ["David Albert", "Barry Loewer"], desc: "Minds in quantum superposition"},
  {name: "Quantum Cognition", proponents: ["Jerome Busemeyer"], desc: "Quantum probability in decisions"},
  {name: "Penrose-Lucas Argument", proponents: ["Roger Penrose"], desc: "Godel implies non-algorithmic mind"},
  {name: "Quantum Zeno Effect", proponents: ["Henry Stapp"], desc: "Attention as quantum measurement"}
] AS theory
MERGE (t:ConsciousnessTheory {name: theory.name})
SET t.description = theory.desc,
    t.category = "Quantum Theories"
MERGE (qt)-[:CONTAINS_THEORY]->(t)
WITH t, theory
UNWIND theory.proponents AS proponentName
MERGE (p:Proponent {name: proponentName})
MERGE (t)-[:PROPOSED_BY]->(p);

// =============================================================================
// 4. INTEGRATED INFORMATION THEORY
// =============================================================================

MERGE (iit:ConsciousnessCategory {name: "Integrated Information Theory"})
SET iit.id = "iit",
    iit.description = "Consciousness is integrated information (Phi)",
    iit.order = 4;

MERGE (root)-[:HAS_CATEGORY]->(iit);

WITH iit
UNWIND [
  {name: "IIT 3.0", proponents: ["Giulio Tononi", "Masafumi Oizumi"], desc: "Causal structure analysis"},
  {name: "IIT 4.0", proponents: ["Giulio Tononi"], desc: "Latest formulation with intrinsicality"},
  {name: "Phi as Consciousness", proponents: ["Giulio Tononi"], desc: "Phi identical to consciousness"},
  {name: "Exclusion Postulate", proponents: ["Giulio Tononi"], desc: "One maximum of Phi"},
  {name: "Intrinsic Cause-Effect Power", proponents: ["Giulio Tononi"], desc: "Irreducible causal structure"},
  {name: "Qualia Space", proponents: ["Giulio Tononi"], desc: "Geometric structure of experience"}
] AS theory
MERGE (t:ConsciousnessTheory {name: theory.name})
SET t.description = theory.desc,
    t.category = "Integrated Information Theory"
MERGE (iit)-[:CONTAINS_THEORY]->(t)
WITH t, theory
UNWIND theory.proponents AS proponentName
MERGE (p:Proponent {name: proponentName})
MERGE (t)-[:PROPOSED_BY]->(p);

// =============================================================================
// 5. PANPSYCHISMS
// =============================================================================

MERGE (pan:ConsciousnessCategory {name: "Panpsychisms"})
SET pan.id = "panpsychism",
    pan.description = "Consciousness is fundamental feature of reality",
    pan.order = 5;

MERGE (root)-[:HAS_CATEGORY]->(pan);

WITH pan
UNWIND [
  {name: "Constitutive Panpsychism", proponents: ["Philip Goff"], desc: "Macro-consciousness from micro"},
  {name: "Cosmopsychism", proponents: ["Itay Shani", "Philip Goff"], desc: "Universe itself is conscious"},
  {name: "Panprotopsychism", proponents: ["David Chalmers"], desc: "Proto-conscious fundamental properties"},
  {name: "Russellian Monism", proponents: ["Bertrand Russell", "Galen Strawson"], desc: "Intrinsic nature is experiential"},
  {name: "Panexperientialism", proponents: ["Alfred North Whitehead"], desc: "Experience in all occasions"},
  {name: "Process Philosophy", proponents: ["Alfred North Whitehead"], desc: "Reality as experiential processes"},
  {name: "Micropsychism", proponents: ["William Seager"], desc: "Fundamental particles conscious"},
  {name: "Combination Problem", proponents: ["William James", "Philip Goff"], desc: "How micro-experience combines"},
  {name: "Subject Summing", proponents: ["Luke Roelofs"], desc: "Combining subjects of experience"},
  {name: "Panpsychist IIT", proponents: ["Hedda Hassel Morch"], desc: "IIT with panpsychist interpretation"}
] AS theory
MERGE (t:ConsciousnessTheory {name: theory.name})
SET t.description = theory.desc,
    t.category = "Panpsychisms"
MERGE (pan)-[:CONTAINS_THEORY]->(t)
WITH t, theory
UNWIND theory.proponents AS proponentName
MERGE (p:Proponent {name: proponentName})
MERGE (t)-[:PROPOSED_BY]->(p);

// =============================================================================
// 6. MONISMS
// =============================================================================

MERGE (mon:ConsciousnessCategory {name: "Monisms"})
SET mon.id = "monism",
    mon.description = "Reality is fundamentally one kind of substance",
    mon.order = 6;

MERGE (root)-[:HAS_CATEGORY]->(mon);

WITH mon
UNWIND [
  {name: "Neutral Monism", proponents: ["William James", "Bertrand Russell"], desc: "Reality neither mental nor physical"},
  {name: "Double-Aspect Monism", proponents: ["Baruch Spinoza"], desc: "Mind and matter two aspects"},
  {name: "Dual-Aspect Monism", proponents: ["Harald Atmanspacher"], desc: "Complementary aspects"},
  {name: "Reflexive Monism", proponents: ["Max Velmans"], desc: "Subject and object aspects"},
  {name: "Priority Monism", proponents: ["Jonathan Schaffer"], desc: "Whole prior to parts"},
  {name: "Substance Monism", proponents: ["Spinoza"], desc: "One substance, many modes"},
  {name: "Experiential Monism", proponents: ["William James"], desc: "Pure experience base"}
] AS theory
MERGE (t:ConsciousnessTheory {name: theory.name})
SET t.description = theory.desc,
    t.category = "Monisms"
MERGE (mon)-[:CONTAINS_THEORY]->(t)
WITH t, theory
UNWIND theory.proponents AS proponentName
MERGE (p:Proponent {name: proponentName})
MERGE (t)-[:PROPOSED_BY]->(p);

// =============================================================================
// 7. DUALISMS
// =============================================================================

MERGE (dual:ConsciousnessCategory {name: "Dualisms"})
SET dual.id = "dualism",
    dual.description = "Mind and matter are fundamentally distinct",
    dual.order = 7;

MERGE (root)-[:HAS_CATEGORY]->(dual);

WITH dual
UNWIND [
  {name: "Substance Dualism", proponents: ["Rene Descartes", "Richard Swinburne"], desc: "Mind and body distinct substances"},
  {name: "Property Dualism", proponents: ["David Chalmers"], desc: "Mental properties non-physical"},
  {name: "Interactionist Dualism", proponents: ["Karl Popper", "John Eccles"], desc: "Mind and brain causally interact"},
  {name: "Epiphenomenalism", proponents: ["Thomas Huxley", "Frank Jackson"], desc: "Mental states causally inert"},
  {name: "Parallelism", proponents: ["Gottfried Leibniz"], desc: "Pre-established harmony"},
  {name: "Emergent Dualism", proponents: ["William Hasker"], desc: "Soul emerges from brain"},
  {name: "Naturalistic Dualism", proponents: ["David Chalmers"], desc: "Non-reductive but natural"},
  {name: "Explanatory Gap", proponents: ["Joseph Levine"], desc: "Gap between physical and phenomenal"}
] AS theory
MERGE (t:ConsciousnessTheory {name: theory.name})
SET t.description = theory.desc,
    t.category = "Dualisms"
MERGE (dual)-[:CONTAINS_THEORY]->(t)
WITH t, theory
UNWIND theory.proponents AS proponentName
MERGE (p:Proponent {name: proponentName})
MERGE (t)-[:PROPOSED_BY]->(p);

// =============================================================================
// 8. IDEALISMS
// =============================================================================

MERGE (ideal:ConsciousnessCategory {name: "Idealisms"})
SET ideal.id = "idealism",
    ideal.description = "Reality is fundamentally mental",
    ideal.order = 8;

MERGE (root)-[:HAS_CATEGORY]->(ideal);

WITH ideal
UNWIND [
  {name: "Analytic Idealism", proponents: ["Bernardo Kastrup"], desc: "Reality is mental, matter appearance"},
  {name: "Conscious Realism", proponents: ["Donald Hoffman"], desc: "Consciousness fundamental, spacetime interface"},
  {name: "Objective Idealism", proponents: ["G.W.F. Hegel"], desc: "Reality as absolute mind"},
  {name: "Subjective Idealism", proponents: ["George Berkeley"], desc: "Esse est percipi"},
  {name: "Transcendental Idealism", proponents: ["Immanuel Kant"], desc: "Mind structures experience"},
  {name: "Interface Theory of Perception", proponents: ["Donald Hoffman"], desc: "Perception hides reality"},
  {name: "Conscious Agent Theory", proponents: ["Donald Hoffman"], desc: "Network of conscious agents"},
  {name: "Mind-at-Large", proponents: ["Aldous Huxley", "Bernardo Kastrup"], desc: "Individual minds as dissociations"}
] AS theory
MERGE (t:ConsciousnessTheory {name: theory.name})
SET t.description = theory.desc,
    t.category = "Idealisms"
MERGE (ideal)-[:CONTAINS_THEORY]->(t)
WITH t, theory
UNWIND theory.proponents AS proponentName
MERGE (p:Proponent {name: proponentName})
MERGE (t)-[:PROPOSED_BY]->(p);

// =============================================================================
// 9. ANOMALOUS/ALTERED STATES
// =============================================================================

MERGE (anom:ConsciousnessCategory {name: "Anomalous Altered States"})
SET anom.id = "anomalous",
    anom.description = "Studies informed by altered states and anomalous experiences",
    anom.order = 9;

MERGE (root)-[:HAS_CATEGORY]->(anom);

WITH anom
UNWIND [
  {name: "NDE Research", proponents: ["Pim van Lommel", "Sam Parnia"], desc: "Near-death experiences suggest non-local consciousness"},
  {name: "AWARE Study", proponents: ["Sam Parnia"], desc: "Awareness during resuscitation"},
  {name: "Psychedelic Consciousness", proponents: ["Robin Carhart-Harris"], desc: "Entropic brain states"},
  {name: "Default Mode Network", proponents: ["Marcus Raichle"], desc: "Resting state consciousness"},
  {name: "Meditation Studies", proponents: ["Richard Davidson"], desc: "Contemplative transformation"},
  {name: "Neurophenomenology", proponents: ["Francisco Varela"], desc: "First-person methods"},
  {name: "Lucid Dreaming", proponents: ["Stephen LaBerge"], desc: "Conscious awareness in dreams"},
  {name: "Flow States", proponents: ["Mihaly Csikszentmihalyi"], desc: "Optimal experience"},
  {name: "Split-Brain Research", proponents: ["Roger Sperry", "Michael Gazzaniga"], desc: "Divided consciousness"},
  {name: "Blindsight", proponents: ["Lawrence Weiskrantz"], desc: "Vision without awareness"},
  {name: "Synesthesia", proponents: ["V.S. Ramachandran"], desc: "Cross-modal experience"}
] AS theory
MERGE (t:ConsciousnessTheory {name: theory.name})
SET t.description = theory.desc,
    t.category = "Anomalous Altered States"
MERGE (anom)-[:CONTAINS_THEORY]->(t)
WITH t, theory
UNWIND theory.proponents AS proponentName
MERGE (p:Proponent {name: proponentName})
MERGE (t)-[:PROPOSED_BY]->(p);

// =============================================================================
// 10. CHALLENGE THEORIES
// =============================================================================

MERGE (chal:ConsciousnessCategory {name: "Challenge Theories"})
SET chal.id = "challenge",
    chal.description = "Theories challenging standard assumptions",
    chal.order = 10;

MERGE (root)-[:HAS_CATEGORY]->(chal);

WITH chal
UNWIND [
  {name: "Illusionism", proponents: ["Keith Frankish", "Daniel Dennett"], desc: "Consciousness as illusion"},
  {name: "Mysterianism", proponents: ["Colin McGinn"], desc: "Mind constitutionally limited"},
  {name: "The Hard Problem", proponents: ["David Chalmers"], desc: "Why subjective experience exists"},
  {name: "Knowledge Argument", proponents: ["Frank Jackson"], desc: "Mary's Room thought experiment"},
  {name: "Zombie Argument", proponents: ["David Chalmers"], desc: "Conceivability of philosophical zombies"},
  {name: "Chinese Room", proponents: ["John Searle"], desc: "Syntax insufficient for semantics"},
  {name: "What is it Like", proponents: ["Thomas Nagel"], desc: "Subjective character of experience"},
  {name: "Other Minds Problem", proponents: ["Various"], desc: "How to know others are conscious"},
  {name: "Binding Problem", proponents: ["Various"], desc: "Unity of conscious experience"},
  {name: "Meta-Problem", proponents: ["David Chalmers"], desc: "Why we think there's a hard problem"},
  {name: "Simulation Hypothesis", proponents: ["Nick Bostrom"], desc: "We may be simulated"},
  {name: "Strong AI", proponents: ["Various"], desc: "Machines can be conscious"}
] AS theory
MERGE (t:ConsciousnessTheory {name: theory.name})
SET t.description = theory.desc,
    t.category = "Challenge Theories"
MERGE (chal)-[:CONTAINS_THEORY]->(t)
WITH t, theory
UNWIND theory.proponents AS proponentName
MERGE (p:Proponent {name: proponentName})
MERGE (t)-[:PROPOSED_BY]->(p);

// =============================================================================
// IMPLICATIONS
// =============================================================================

MERGE (imp1:Implication {name: "Meaning Purpose Value"})
SET imp1.description = "What consciousness theories imply for meaning, purpose, and value";

MERGE (imp2:Implication {name: "AI Consciousness"})
SET imp2.description = "Whether artificial systems can be conscious";

MERGE (imp3:Implication {name: "Virtual Immortality"})
SET imp3.description = "Mind uploading and digital continuation";

MERGE (imp4:Implication {name: "Survival Beyond Death"})
SET imp4.description = "Whether consciousness survives bodily death";

MERGE (root)-[:HAS_IMPLICATION]->(imp1);
MERGE (root)-[:HAS_IMPLICATION]->(imp2);
MERGE (root)-[:HAS_IMPLICATION]->(imp3);
MERGE (root)-[:HAS_IMPLICATION]->(imp4);

// =============================================================================
// CROSS-THEORY RELATIONSHIPS (examples)
// =============================================================================

// IIT influences on other theories
MATCH (iit:ConsciousnessTheory {name: "IIT 3.0"})
MATCH (gwt:ConsciousnessTheory {name: "Global Workspace Theory"})
MERGE (iit)-[:CONTRASTS_WITH {reason: "Different mechanisms for integration"}]->(gwt);

MATCH (iit:ConsciousnessTheory {name: "Phi as Consciousness"})
MATCH (pan:ConsciousnessTheory {name: "Panpsychist IIT"})
MERGE (iit)-[:EXTENDED_BY]->(pan);

// Penrose-Hameroff connections
MATCH (orch:ConsciousnessTheory {name: "Orchestrated Objective Reduction"})
MATCH (pl:ConsciousnessTheory {name: "Penrose-Lucas Argument"})
MERGE (pl)-[:FOUNDATION_FOR]->(orch);

// Chalmers network
MATCH (hp:ConsciousnessTheory {name: "The Hard Problem"})
MATCH (pd:ConsciousnessTheory {name: "Property Dualism"})
MATCH (pp:ConsciousnessTheory {name: "Panprotopsychism"})
MERGE (hp)-[:MOTIVATES]->(pd);
MERGE (hp)-[:MOTIVATES]->(pp);

// Dennett vs Chalmers
MATCH (ill:ConsciousnessTheory {name: "Illusionism"})
MATCH (hp:ConsciousnessTheory {name: "The Hard Problem"})
MERGE (ill)-[:DENIES]->(hp);

// =============================================================================
// USEFUL QUERIES
// =============================================================================

// Query: All theories by a specific proponent
// MATCH (p:Proponent {name: "David Chalmers"})<-[:PROPOSED_BY]-(t:ConsciousnessTheory)
// RETURN t.name, t.category, t.description;

// Query: Theories in a category
// MATCH (c:ConsciousnessCategory {name: "Panpsychisms"})-[:CONTAINS_THEORY]->(t)
// RETURN t.name, t.description;

// Query: Mind map traversal from root
// MATCH path = (root:ConsciousnessRoot)-[*..3]->(t:ConsciousnessTheory)
// RETURN path LIMIT 50;

// Query: Proponents who span multiple categories
// MATCH (p:Proponent)<-[:PROPOSED_BY]-(t:ConsciousnessTheory)
// WITH p, collect(DISTINCT t.category) AS categories
// WHERE size(categories) > 1
// RETURN p.name, categories;

// =============================================================================
// STATISTICS
// =============================================================================

// After running, verify counts:
// MATCH (t:ConsciousnessTheory) RETURN count(t) AS theories;
// MATCH (c:ConsciousnessCategory) RETURN count(c) AS categories;
// MATCH (p:Proponent) RETURN count(p) AS proponents;
