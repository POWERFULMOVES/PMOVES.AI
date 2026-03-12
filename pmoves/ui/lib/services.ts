export interface ServiceDefinition {
  slug: string;
  title: string;
  summary: string;
  docPath: string;
}

export const INTEGRATION_SERVICES: ServiceDefinition[] = [
  {
    slug: 'agent-zero',
    title: 'Agent Zero',
    summary:
      'Control-plane orchestrator exposing the supervisor API, MCP execution surface, and the native Agent Zero UI.',
    docPath: '../docs/services/agent-zero/README.md',
  },
  {
    slug: 'archon',
    title: 'Archon',
    summary:
      'Supabase-backed prompt and persona studio used for form routing, agent configuration, and headless orchestration.',
    docPath: '../docs/services/archon/README.md',
  },
  {
    slug: 'botz-gateway',
    title: 'BotZ Gateway',
    summary:
      'Work-item distribution service for PMOVES-BoTZ instances, NATS coordination, and Supabase-backed task claims.',
    docPath: '../docs/services/botz-gateway/README.md',
  },
  {
    slug: 'channel-monitor',
    title: 'Channel Monitor',
    summary:
      'YouTube channel and Discord drop watcher that queues PMOVES.YT ingestion and records status in Supabase.',
    docPath: '../docs/services/channel-monitor/README.md',
  },
  {
    slug: 'evo-controller',
    title: 'Evo Controller',
    summary:
      'EvoSwarm controller that polls geometry packets, upserts draft parameter packs, and emits swarm metadata events.',
    docPath: '../docs/services/evo-controller/README.md',
  },
  {
    slug: 'flute-gateway',
    title: 'Flute Gateway',
    summary:
      'Voice synthesis and recognition gateway for PMOVES audio flows, Pipecat pipelines, and CHIT voice attribution.',
    docPath: '../docs/services/flute-gateway/README.md',
  },
  {
    slug: 'supaserch',
    title: 'SupaSerch',
    summary:
      'Multimodal research orchestrator combining DeepResearch, Archon/Agent Zero tooling, and Supabase/Qdrant indices.',
    docPath: '../docs/services/supaserch/README.md',
  },
  {
    slug: 'open-notebook',
    title: 'Open Notebook',
    summary:
      'Notebook UI and API pairing used for local experimentation, workflow prototyping, and SurrealDB-backed notebooks.',
    docPath: '../docs/services/open-notebook/README.md',
  },
  {
    slug: 'pmoves-yt',
    title: 'PMOVES.YT',
    summary:
      'YouTube ingestion bridge responsible for scheduling downloads, syncing metadata, and pushing Supabase-ready assets.',
    docPath: '../docs/services/pmoves-yt/README.md',
  },
  {
    slug: 'jellyfin',
    title: 'Jellyfin',
    summary:
      'Self-hosted media server integration providing preview, review, and streaming workflows for ingested assets.',
    docPath: '../docs/services/jellyfin/README.md',
  },
  {
    slug: 'jellyfin-bridge',
    title: 'Jellyfin Bridge',
    summary:
      'Metadata bridge and playback helper that links ingested PMOVES assets into Jellyfin review and creator workflows.',
    docPath: '../docs/services/jellyfin-bridge/README.md',
  },
  {
    slug: 'publisher-discord',
    title: 'Publisher Discord',
    summary:
      'Discord publishing worker for approval loops, webhook fan-out, and operator notifications.',
    docPath: '../docs/services/publisher-discord/README.md',
  },
  {
    slug: 'wger',
    title: 'Wger',
    summary:
      'Fitness tracker integration aligning the external stack with upstream Django + Nginx deployment recommendations.',
    docPath: '../docs/services/wger/README.md',
  },
  {
    slug: 'firefly',
    title: 'Firefly',
    summary:
      'Personal finance management suite bundled into the PMOVES external stack for revenue and spend tracking.',
    docPath: '../docs/services/firefly-iii/README.md',
  },
];

export function resolveService(slug: string): ServiceDefinition | undefined {
  return INTEGRATION_SERVICES.find((service) => service.slug === slug);
}
