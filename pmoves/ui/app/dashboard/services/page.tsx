'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { DashboardShell } from '../../../components/DashboardNavigation';
import { SystemStatsBar } from '../../../components/hub/SystemStatsBar';
import { TierNavigation } from '../../../components/services/TierNavigation';
import { ServiceHealthIndicator } from '../../../components/services/ServiceHealthIndicator';
import { useServiceHealth } from '../../../lib/useServiceHealth';
import { SERVICE_CATALOG, type ServiceCategory, type ServiceColor } from '../../../lib/serviceCatalog';
import type { ServiceHealthMap } from '../../../lib/serviceHealth';

// Lookup objects for Tailwind JIT - all class names must be statically analyzable
const TAG_CLASSES: Record<string, string> = {
  cyan: 'tag tag-cyan',
  ember: 'tag tag-ember',
  violet: 'tag tag-violet',
  forest: 'tag tag-forest',
  gold: 'tag tag-gold',
};

const ICON_BG_CLASSES: Record<string, string> = {
  cyan: 'bg-cata-cyan/10 text-cata-cyan',
  ember: 'bg-cata-ember/10 text-cata-ember',
  violet: 'bg-cata-violet/10 text-cata-violet',
  forest: 'bg-cata-forest/10 text-cata-forest',
  gold: 'bg-cata-gold/10 text-cata-gold',
};

const BORDER_CLASSES: Record<string, string> = {
  cyan: 'border-cata-cyan/30 hover:border-cata-cyan group-hover:text-cata-cyan',
  ember: 'border-cata-ember/30 hover:border-cata-ember group-hover:text-cata-ember',
  violet: 'border-cata-violet/30 hover:border-cata-violet group-hover:text-cata-violet',
  forest: 'border-cata-forest/30 hover:border-cata-forest group-hover:text-cata-forest',
  gold: 'border-cata-gold/30 hover:border-cata-gold group-hover:text-cata-gold',
};

const PORT_LINKS = [
  { name: 'TensorZero UI', port: '4000', href: 'http://localhost:4000' },
  { name: 'Grafana', port: '3000', href: 'http://localhost:3000' },
  { name: 'Prometheus', port: '9090', href: 'http://localhost:9090' },
  { name: 'Supabase Studio', port: '65433', href: 'http://127.0.0.1:65433' },
  { name: 'Agent Zero UI', port: '8081', href: 'http://localhost:8081' },
  { name: 'Archon UI', port: '3737', href: 'http://localhost:3737' },
  { name: 'Jellyfin', port: '8096', href: 'http://localhost:8096' },
  { name: 'MinIO Console', port: '9001', href: 'http://localhost:9001' },
];

/**
 * Services Dashboard with full catalog, tier filtering, and health monitoring
 */
export default function ServicesIndexPage() {
  const [activeTier, setActiveTier] = useState<ServiceCategory | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const { health, isPolling, lastUpdate, refresh } = useServiceHealth({
    pollInterval: 30000,
    enabled: true,
  });

  // Filter services by tier and search query
  const filteredServices = useMemo(() => {
    return SERVICE_CATALOG.filter((service) => {
      const matchesTier = activeTier === 'all' || service.category === activeTier;
      const matchesSearch = searchQuery === '' ||
        service.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        service.summary.toLowerCase().includes(searchQuery.toLowerCase()) ||
        service.slug.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesTier && matchesSearch;
    });
  }, [activeTier, searchQuery]);

  // Calculate tier stats for navigation
  const tierStats = useMemo(() => {
    const stats: Record<string, { total: number; healthy: number; percentage: number }> = {};

    for (const service of SERVICE_CATALOG) {
      const tier = service.category;
      if (!stats[tier]) {
        stats[tier] = { total: 0, healthy: 0, percentage: 0 };
      }
      stats[tier].total++;
      if (health[service.slug]?.status === 'healthy') {
        stats[tier].healthy++;
      }
    }

    // Calculate percentages
    for (const tier in stats) {
      stats[tier].percentage = stats[tier].total > 0
        ? Math.round((stats[tier].healthy / stats[tier].total) * 100)
        : 0;
    }

    return Object.entries(stats).map(([tier, data]) => ({
      tier: tier as ServiceCategory,
      total: data.total,
      healthy: data.healthy,
      percentage: data.percentage,
    }));
  }, [health]);

  // Calculate overall stats
  const overallStats = useMemo(() => {
    const total = SERVICE_CATALOG.length;
    const healthy = Object.values(health).filter(h => h.status === 'healthy').length;
    const unhealthy = Object.values(health).filter(h => h.status === 'unhealthy').length;
    const unknown = total - healthy - unhealthy;
    const percentage = total > 0 ? Math.round((healthy / total) * 100) : 0;

    return { total, healthy, unhealthy, unknown, percentage };
  }, [health]);

  return (
    <DashboardShell
      title="Services"
      subtitle="Full service catalog with real-time health monitoring"
      active="services"
      actions={
        <Link href="/dashboard/services/yt-dlp" className="tag tag-ember">
          yt-dlp Status
        </Link>
      }
    >
      <div className="p-6 lg:p-8 space-y-8">
        {/* System Stats Bar */}
        <SystemStatsBar
          totalServices={overallStats.total}
          healthyCount={overallStats.healthy}
          unhealthyCount={overallStats.unhealthy}
          unknownCount={overallStats.unknown}
          percentage={overallStats.percentage}
          isChecking={isPolling}
          lastUpdate={lastUpdate}
          onRefresh={refresh}
        />

        {/* Tier Navigation */}
        <div>
          <h3 className="font-pixel text-[8px] text-ink-muted uppercase tracking-wider mb-4">
            Filter by Category
          </h3>
          <TierNavigation
            activeTier={activeTier}
            onTierChange={setActiveTier}
            tierStats={tierStats}
          />
        </div>

        {/* Search Bar */}
        <div className="relative">
          <input
            type="text"
            placeholder="Search services by name, description, or slug..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-4 py-3 bg-void-soft border border-border-subtle rounded-lg font-body text-sm text-ink-primary placeholder:text-ink-muted focus:outline-none focus:border-cata-cyan focus:ring-1 focus:ring-cata-cyan"
          />
          <span className="absolute right-4 top-1/2 -translate-y-1/2 text-ink-muted font-pixel text-[7px] uppercase">
            {filteredServices.length} of {SERVICE_CATALOG.length}
          </span>
        </div>

        {/* Services Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredServices.map((service) => {
            const color = service.color as string;
            const serviceHealth = health[service.slug];
            const status = serviceHealth?.status || 'unknown';
            const href = service.endpoints.length > 0
              ? `/dashboard/services/${service.slug}`
              : '#';

            return (
              <Link
                key={service.slug}
                href={href}
                className={`group card-brutal p-6 flex flex-col gap-4 border ${BORDER_CLASSES[color]} relative`}
              >
                {/* Health indicator */}
                <div className="absolute top-4 right-4">
                  <ServiceHealthIndicator status={status} size="md" showPulse={status === 'healthy'} />
                </div>

                {/* Header */}
                <div className="space-y-1 pr-8">
                  <span className={TAG_CLASSES[color]}>{service.category}</span>
                  <h2 className={`font-display font-bold text-xl mt-2 transition-colors ${BORDER_CLASSES[color]}`}>
                    {service.title}
                  </h2>
                </div>

                {/* Icon */}
                <div className={`w-12 h-12 flex items-center justify-center ${ICON_BG_CLASSES[color]} font-display font-bold text-lg`}>
                  {service.title.charAt(0)}
                </div>

                {/* Description */}
                <p className="text-sm text-ink-secondary leading-relaxed flex-1">
                  {service.summary}
                </p>

                {/* Endpoints */}
                {service.endpoints.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {service.endpoints.slice(0, 2).map((endpoint) => (
                      <span
                        key={endpoint.name}
                        className="font-pixel text-[6px] text-ink-muted uppercase bg-void-soft px-2 py-1 border border-border-subtle"
                      >
                        {endpoint.name}
                      </span>
                    ))}
                    {service.endpoints.length > 2 && (
                      <span className="font-pixel text-[6px] text-ink-muted uppercase">
                        +{service.endpoints.length - 2} more
                      </span>
                    )}
                  </div>
                )}

                {/* Footer */}
                <div className="flex items-center justify-between pt-4 border-t border-border-subtle">
                  <span className="text-xs text-ink-muted font-mono uppercase tracking-wider">
                    {service.slug}
                  </span>
                  <span className="text-xs font-mono text-ink-muted group-hover:text-cata-cyan transition-colors flex items-center gap-1">
                    {service.endpoints.length > 0 ? 'View details' : 'External link'}
                    <span className="transform group-hover:translate-x-1 transition-transform">&rarr;</span>
                  </span>
                </div>
              </Link>
            );
          })}
        </div>

        {/* No results */}
        {filteredServices.length === 0 && (
          <div className="text-center py-16">
            <div className="font-display text-4xl font-bold text-ink-muted mb-4">
              No services found
            </div>
            <p className="text-ink-secondary font-body">
              Try adjusting your search or filter criteria
            </p>
          </div>
        )}

        {/* External Dashboards */}
        <section className="space-y-4 pt-8 border-t border-border-subtle">
          <h2 className="font-display font-semibold text-lg">External Dashboards</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border-subtle">
            {PORT_LINKS.map((item) => (
              <a
                key={item.name}
                href={item.href}
                target="_blank"
                rel="noreferrer"
                className="bg-void p-4 hover:bg-void-elevated transition-colors group"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-2xs text-ink-muted">:{item.port}</span>
                </div>
                <span className="font-display font-semibold text-sm group-hover:text-cata-cyan transition-colors">
                  {item.name}
                </span>
              </a>
            ))}
          </div>
        </section>
      </div>
    </DashboardShell>
  );
}
