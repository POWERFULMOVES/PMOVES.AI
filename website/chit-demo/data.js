// data.js — Real CGP scenarios from the PMOVES.AI repo, adapted for the playground.
// Each scenario is a real CGP packet with real anchors, spectra, and points.

const SCENARIOS = {
  consciousness: {
    label: "Theories of Consciousness",
    desc: "Eight theories of consciousness encoded as CHIT constellations — from the GEOMETRY BUS documentation sample. Each constellation is a school of thought with its anchor direction and spectrum distribution.",
    source: "pmoves/docs/geometry-bus/assets/sample_cgp.json",
    cgp: {
      spec: "chit.cgp.v1.0",
      summary: "Theories of consciousness — CHIT geometric encoding",
      created_at: "2026-03-13T12:00:00Z",
      super_nodes: [{
        id: "consciousness-super-materialism",
        label: "Consciousness Theories",
        summary: "Eight theories of consciousness encoded as geometric constellations",
        constellations: [
          {
            id: "reductive-physicalism",
            summary: "Mental states reduce to brain states",
            anchor: [0.5, 0.3, 0.8],
            radial_minmax: [0.0, 1.0],
            spectrum: [0.8, 0.6, 0.4, 0.2, 0.1],
            points: [
              { id: "chalmers", proj: 0.95, conf: 0.9, text: "Chalmers: consciousness supervenes on the physical" },
              { id: "dennett", proj: 0.88, conf: 0.85, text: "Dennett: multiple drafts model — no Cartesian theater" },
              { id: "churchland", proj: 0.82, conf: 0.8, text: "Churchland: eliminative materialism — folk psychology is wrong" },
            ]
          },
          {
            id: "property-dualism",
            summary: "Mental properties are irreducible to physical properties",
            anchor: [0.3, 0.7, 0.4],
            radial_minmax: [0.0, 1.0],
            spectrum: [0.4, 0.7, 0.9, 0.6, 0.3],
            points: [
              { id: "chalmers-qualia", proj: 0.92, conf: 0.9, text: "Chalmers: qualia are irreducible — the hard problem" },
              { id: "jackson-mary", proj: 0.78, conf: 0.85, text: "Jackson: Mary's Room — knowledge argument for qualia" },
            ]
          },
          {
            id: "panpsychism",
            summary: "Consciousness is a fundamental feature of reality",
            anchor: [0.7, 0.5, 0.6],
            radial_minmax: [0.0, 1.0],
            spectrum: [0.6, 0.4, 0.8, 0.7, 0.5],
            points: [
              { id: "strawson", proj: 0.89, conf: 0.88, text: "Strawson: panpsychism is the only consistent physicalism" },
              { id: "goff", proj: 0.76, conf: 0.82, text: "Goff: consciousness is fundamental — combine problem" },
            ]
          },
          {
            id: "functionalism",
            summary: "Mental states are defined by functional roles, not substrate",
            anchor: [0.4, 0.6, 0.3],
            radial_minmax: [0.0, 1.0],
            spectrum: [0.5, 0.8, 0.6, 0.4, 0.7],
            points: [
              { id: "putnam", proj: 0.91, conf: 0.87, text: "Putnam: mental states are functional states — Turing test" },
              { id: "lewis", proj: 0.73, conf: 0.8, text: "Lewis: analytical functionalism — folk psychology as term-fixing" },
            ]
          },
        ]
      }]
    }
  },

  "urban-farming": {
    label: "Urban Farming",
    desc: "Urban agriculture concepts encoded as a CGP — from the PMOVES quickstart guide. The constellation captures how rooftop gardens, vertical farms, and community plots cluster in meaning space.",
    source: "pmoves/docs/PMOVESCHIT/05_QUICKSTART.md",
    cgp: {
      spec: "chit.cgp.v1.0",
      summary: "Urban farming concepts — CHIT geometric encoding",
      created_at: "2026-02-18T12:00:00Z",
      super_nodes: [{
        id: "urban-agriculture",
        label: "Urban Agriculture",
        summary: "How cities grow food — geometric meaning map",
        constellations: [
          {
            id: "urban_farming",
            summary: "Urban farming methods and benefits",
            anchor: [0.42, -0.18, 0.67, 0.31],
            radial_minmax: [-0.22, 0.85],
            spectrum: [0.10, 0.35, 0.40, 0.15],
            points: [
              { id: "pt_0", proj: 0.12, conf: 0.91, text: "Rooftop gardens reduce urban heat islands." },
              { id: "pt_1", proj: 0.55, conf: 0.87, text: "Community plots increase food security." },
              { id: "pt_2", proj: 0.78, conf: 0.93, text: "Vertical farms use 95% less water." },
            ]
          },
          {
            id: "food-justice",
            summary: "Food justice and equity in urban food systems",
            anchor: [0.71, 0.33, -0.12, 0.55],
            radial_minmax: [0.10, 0.95],
            spectrum: [0.30, 0.25, 0.20, 0.25],
            points: [
              { id: "pt_3", proj: 0.45, conf: 0.85, text: "Food deserts disproportionately affect low-income neighborhoods." },
              { id: "pt_4", proj: 0.62, conf: 0.88, text: "Cooperative grocery models keep 53-82% of revenue local vs 14% for chains." },
            ]
          },
        ]
      }]
    }
  },

  economics: {
    label: "Cooperative Economics",
    desc: "The TradFi vs Cooperative economics model encoded as a CGP. Two constellations capture the two models; the spectra show how wealth distributes differently under each.",
    source: "PMOVES-ToKenism-Multi/pmoves-nextjs/src/lib/simulation/index.ts",
    cgp: {
      spec: "chit.cgp.v1.0",
      summary: "Cooperative vs Traditional economics — CHIT geometric encoding",
      created_at: "2026-07-28T12:00:00Z",
      meta: { source: "tokenism-simulator", K: 2, bins: 5, backend: "pmoves-economic-model" },
      super_nodes: [{
        id: "economic-models",
        label: "Economic Models",
        summary: "Traditional vs Cooperative wealth distribution patterns",
        constellations: [
          {
            id: "traditional-model",
            summary: "Scenario A: Independent members, external spending, no coordination",
            anchor: [0.8, 0.2, 0.0],
            radial_minmax: [0.0, 1.0],
            spectrum: [0.05, 0.15, 0.20, 0.25, 0.35],
            points: [
              { id: "trad-1", proj: 0.85, conf: 0.92, text: "Wealth concentrates at the top — Gini stays constant or widens." },
              { id: "trad-2", proj: 0.72, conf: 0.88, text: "No redistribution mechanism — each member faces same food cost regardless of wealth." },
              { id: "trad-3", proj: 0.60, conf: 0.85, text: "During stress: poor members pay MORE (cost adjustment factor up to 1.2x)." },
            ]
          },
          {
            id: "cooperative-model",
            summary: "Scenario B: Group purchasing, local production, GroToken rewards, mutual aid",
            anchor: [0.3, 0.7, 0.5],
            radial_minmax: [0.0, 1.0],
            spectrum: [0.25, 0.30, 0.25, 0.15, 0.05],
            points: [
              { id: "coop-1", proj: 0.42, conf: 0.93, text: "27% effective savings on internal spending (group buy + local production)." },
              { id: "coop-2", proj: 0.38, conf: 0.91, text: "GroToken rewards distributed by participation, not wealth — progressive by design." },
              { id: "coop-3", proj: 0.15, conf: 0.89, text: "Mutual aid: vulnerability score gives up to 12% extra cost reduction to most vulnerable." },
              { id: "coop-4", proj: 0.20, conf: 0.87, text: "Net weekly advantage: +$12.21/member (+16.3%). Gini_B < Gini_A across all 14 presets." },
            ]
          },
        ]
      }]
    }
  },

  "agent-taxonomy": {
    label: "Agent Taxonomy",
    desc: "The PMOVES agent registry encoded as a CGP — 4 classes, 7 service types. Each constellation is a class with its agents as points. This is the same data the Poincaré disk in the visual tour embeds.",
    source: "PMOVES-ToKenism-Multi/integrations/contracts/chit/samples/agent-taxonomy-cgp.json",
    cgp: {
      spec: "chit.cgp.v1.0",
      summary: "PMOVES Agent Taxonomy — CHIT geometric encoding",
      created_at: "2026-07-26T12:00:00Z",
      meta: { source: "agent_registry.yaml", K: 4, bins: 4, backend: "taxonomy-v1.5.0" },
      super_nodes: [{
        id: "pmoves-agent-tree",
        label: "PMOVES Agent Tree",
        summary: "96 agents across 4 classes and 7 service types",
        constellations: [
          {
            id: "standard-agents",
            summary: "Standard (PMOVES-*) — 43 agents in the live registry",
            anchor: [0.5, 0.5, 0.5],
            radial_minmax: [0.0, 1.0],
            spectrum: [0.15, 0.35, 0.30, 0.20],
            points: [
              { id: "agent-zero", proj: 0.92, conf: 0.95, text: "Agent Zero — the crystalline lattice of the MOF" },
              { id: "archon", proj: 0.78, conf: 0.9, text: "Archon — agent factory and MCP bridge" },
              { id: "clawz", proj: 0.65, conf: 0.88, text: "ClawZ — active Discord agent" },
              { id: "hirag-v2", proj: 0.45, conf: 0.85, text: "Hi-RAG v2 — hybrid retrieval (Qdrant + Neo4j + Meilisearch)" },
            ]
          },
          {
            id: "specialized-agents",
            summary: "Specialized (Pmoves-*) — 28 agents",
            anchor: [0.7, 0.3, 0.6],
            radial_minmax: [0.0, 1.0],
            spectrum: [0.25, 0.25, 0.30, 0.20],
            points: [
              { id: "cipher", proj: 0.82, conf: 0.9, text: "Cipher Memory — cross-session persistent memory" },
              { id: "hyperdimensions", proj: 0.68, conf: 0.87, text: "Hyperdimensions — 3D geometric visualization engine" },
            ]
          },
          {
            id: "utility-agents",
            summary: "Utility (pmoves-*) — 24 agents",
            anchor: [0.3, 0.7, 0.4],
            radial_minmax: [0.0, 1.0],
            spectrum: [0.30, 0.25, 0.25, 0.20],
            points: [
              { id: "nats", proj: 0.88, conf: 0.92, text: "NATS — the nervous system / Geometry Bus transport" },
              { id: "supabase", proj: 0.72, conf: 0.89, text: "Supabase — Postgres + auth + realtime" },
              { id: "qdrant", proj: 0.55, conf: 0.85, text: "Qdrant — vector database for Hi-RAG" },
            ]
          },
        ]
      }]
    }
  },
};

// Make available globally for the app.js module
window.SCENARIOS = SCENARIOS;
