/**
 * PMOVES Service Registry — shared data module.
 * Imported by pinokio.js, health.js, and network-map.js.
 *
 * `name`    — Docker Compose service name (used in `docker compose up -d <name>`)
 * `script`  — Short name for the start script filename (defaults to `name` if omitted)
 *             Resolved path: services/<group>/start-<script>.js
 * `lanSafe` — Whether this service is safe for LAN-Wide-Web exposure.
 *             false = admin/data service, should be localhost-only.
 *             true  = user-facing UI, safe for LAN discovery.
 *             Defaults to false (deny-by-default).
 *
 * Groups define the nested menu categories in pinokio.js.
 */
module.exports = {
  data: [
    // ── Data Layer ──
    // lanSafe: false — data services should NEVER be LAN-exposed without auth
    { name: "nats",        port: 4222,  healthPort: 8222, health: "/varz",              group: "data",       label: "NATS Bus",       ui: false, lanSafe: false },
    { name: "neo4j",       port: 7474,  healthPort: 7474, health: "/db/neo4j/health",   group: "data",       label: "Neo4j",          ui: true,  uiPort: 7474, lanSafe: false },
    { name: "qdrant",      port: 6333,  healthPort: 6333, health: "/healthz",           group: "data",       label: "Qdrant",         ui: true,  uiPort: 6333, lanSafe: false },
    { name: "meilisearch", port: 7700,  healthPort: 7700, health: "/health",            group: "data",       label: "Meilisearch",    ui: false, lanSafe: false },
    { name: "minio",       port: 9000,  healthPort: 9000, health: "/minio/health/live", group: "data",       label: "MinIO",          ui: true,  uiPort: 9001, lanSafe: false },
    { name: "supabase-db", script: "supabase", port: 54322, healthPort: null, health: null, group: "data", label: "Supabase", ui: true, uiPort: 54323, lanSafe: false, compose: "--profile supabase-local" },

    // ── Agent Swarm ──
    { name: "agent-zero",  port: 8080,  healthPort: 8080, health: "/healthz",           group: "agents",     label: "Agent Zero",     ui: true,  uiPort: 8081, lanSafe: true },
    { name: "archon",      port: 8091,  healthPort: 8091, health: "/healthz",           group: "agents",     label: "Archon",         ui: true,  uiPort: 3737, lanSafe: true },
    { name: "cipher-api",  script: "cipher", port: 8096, healthPort: 8096, health: "/health", group: "agents", label: "Cipher Memory", ui: false, lanSafe: false, compose: "--profile agents" },
    { name: "botz-gateway", script: "botz", port: 8054, healthPort: 8054, health: "/healthz", group: "agents", label: "BoTZ Gateway", ui: false, lanSafe: false, compose: "--profile agents" },

    // ── Knowledge & RAG ──
    { name: "hi-rag-gateway-v2", script: "hirag", port: 8086, healthPort: 8086, health: "/hirag/admin/stats", group: "knowledge", label: "Hi-RAG v2", ui: false, lanSafe: false },
    { name: "tensorzero-gateway", script: "tensorzero", port: 3030, healthPort: 3030, health: "/health", group: "knowledge", label: "TensorZero", ui: true, uiPort: 4000, lanSafe: true },
    { name: "deepresearch", port: 8098, healthPort: 8098, health: "/healthz",           group: "knowledge",  label: "DeepResearch",   ui: false, lanSafe: false },
    { name: "supaserch",    port: 8099, healthPort: 8099, health: "/healthz",           group: "knowledge",  label: "SupaSerch",      ui: false, lanSafe: false },

    // ── Voice Pipeline ──
    { name: "flute-gateway", script: "flute", port: 8055, healthPort: 8055, health: "/healthz", group: "voice", label: "Flute Gateway", ui: false, lanSafe: false },
    { name: "ultimate-tts-studio", script: "tts", port: 7861, healthPort: 7861, health: "/gradio_api/info", group: "voice", label: "TTS Studio", ui: true, uiPort: 7861, lanSafe: true, note: "Runs via Pinokio native on GPU hosts" },

    // ── Media & Workers ──
    { name: "extract-worker", port: 8083, healthPort: 8083, health: "/healthz",          group: "media",  label: "Extract Worker", ui: false, lanSafe: false },
    { name: "pmoves-yt",     port: 8077, healthPort: 8077, health: "/healthz",          group: "media",  label: "PMOVES.YT",      ui: false, lanSafe: false },
    { name: "channel-monitor",port: 8097, healthPort: 8097, health: null,               group: "media",  label: "Channel Monitor", ui: false, lanSafe: false },
  ],

  groups: {
    data:      { label: "Data Layer",       icon: "fa-solid fa-database" },
    agents:    { label: "Agent Swarm",      icon: "fa-solid fa-robot" },
    knowledge: { label: "Knowledge & RAG",  icon: "fa-solid fa-brain" },
    voice:     { label: "Voice Pipeline",   icon: "fa-solid fa-microphone" },
    media:     { label: "Media & Workers",  icon: "fa-solid fa-film" },
  },

  /** Get services by group name */
  byGroup(groupName) {
    return this.data.filter(s => s.group === groupName)
  },

  /** Find a service by compose name */
  find(name) {
    return this.data.find(s => s.name === name)
  },

  /** Get only LAN-safe services (for LWW custom domain setup) */
  lanSafe() {
    return this.data.filter(s => s.lanSafe === true)
  },
}
