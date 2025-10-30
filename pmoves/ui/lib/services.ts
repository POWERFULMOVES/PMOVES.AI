export interface ServiceDefinition {
  slug: string;
  title: string;
  summary: string;
  docPath: string;
}

export const INTEGRATION_SERVICES: ServiceDefinition[] = [
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
    slug: 'wger',
    title: 'Wger',
    summary:
      'Fitness tracker integration aligning the external stack with upstream Django + Nginx deployment recommendations.',
    docPath: '../docs/services/wger/README.md',
  },
  {
    slug: 'firefly-iii',
    title: 'Firefly',
    summary:
      'Personal finance management suite bundled into the PMOVES external stack for revenue and spend tracking.',
    docPath: '../docs/services/firefly-iii/README.md',
  },
];

export function resolveService(slug: string): ServiceDefinition | undefined {
  return INTEGRATION_SERVICES.find((service) => service.slug === slug);
}
