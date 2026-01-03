/* ═══════════════════════════════════════════════════════════════════════════
   Category Section Component
   Displays services grouped by category with health summary
   ═══════════════════════════════════════════════════════════════════════════ */

import { ServiceCard } from './ServiceCard';
import type { ServiceDefinition, ServiceCategory } from '@/lib/serviceCatalog';
import type { ServiceHealthMap } from '@/lib/serviceHealth';
// Helper functions imported but currently unused - available for future status display
// import { getStatusBadgeClass, getStatusText } from '@/lib/serviceHealth';

interface CategorySectionProps {
  category: ServiceCategory;
  services: ServiceDefinition[];
  healthMap?: ServiceHealthMap;
  collapsed?: boolean;
}

// Category display names and icons
const CATEGORY_INFO: Record<ServiceCategory, { name: string; icon: string; description: string }> = {
  observability: { name: 'Observability', icon: '📊', description: 'Monitoring, metrics, and logging' },
  database: { name: 'Database', icon: '🗄️', description: 'Data persistence and storage' },
  data: { name: 'Data Tier', icon: '📦', description: 'Vector, graph, and search engines' },
  bus: { name: 'Message Bus', icon: '🚌', description: 'Event-driven communication' },
  workers: { name: 'Workers', icon: '⚙️', description: 'Background processing services' },
  agents: { name: 'Agents', icon: '🤖', description: 'AI agent orchestration' },
  gpu: { name: 'GPU Services', icon: '🎮', description: 'GPU-accelerated services' },
  media: { name: 'Media', icon: '🎬', description: 'Media ingestion and processing' },
  llm: { name: 'LLM Gateway', icon: '🧠', description: 'Language model services' },
  ui: { name: 'User Interface', icon: '🖥️', description: 'Web interfaces and dashboards' },
  integration: { name: 'Integrations', icon: '🔌', description: 'External service integrations' },
  dox: { name: 'Document Intelligence', icon: '📄', description: 'PMOVES-DoX document processing' },
  mcp: { name: 'MCP Servers', icon: '🔗', description: 'Model Context Protocol servers' },
};

export function CategorySection({ category, services, healthMap }: CategorySectionProps) {
  const info = CATEGORY_INFO[category];

  // Calculate health stats
  const healthyCount = services.filter((s) => healthMap?.[s.slug]?.status === 'healthy').length;
  const unhealthyCount = services.filter((s) => healthMap?.[s.slug]?.status === 'unhealthy').length;
  const unknownCount = services.filter((s) => !healthMap?.[s.slug] || healthMap?.[s.slug]?.status === 'unknown').length;

  return (
    <section className="space-y-6">
      {/* Category header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-4">
          <span className="text-2xl">{info.icon}</span>
          <div>
            <h2 className="font-display font-bold text-xl uppercase tracking-wide">
              {info.name}
            </h2>
            <p className="text-sm text-ink-muted">{info.description}</p>
          </div>
        </div>

        {/* Health summary */}
        {healthMap && (
          <div className="flex items-center gap-4 font-pixel text-[6px] uppercase">
            <span className="text-cata-forest">{healthyCount} Online</span>
            <span className="text-cata-ember">{unhealthyCount} Offline</span>
            <span className="text-ink-muted">{unknownCount} Unknown</span>
          </div>
        )}
      </div>

      {/* Services grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {services.map((service) => (
          <ServiceCard
            key={service.slug}
            service={service}
            healthStatus={healthMap?.[service.slug]?.status}
            responseTime={healthMap?.[service.slug]?.responseTime}
          />
        ))}
      </div>
    </section>
  );
}
