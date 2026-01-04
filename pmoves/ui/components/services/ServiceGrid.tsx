/* ═══════════════════════════════════════════════════════════════════════════
   Service Grid Component
   Grid layout for services with filtering and search
   ═══════════════════════════════════════════════════════════════════════════ */

'use client';

import { useState, useMemo } from 'react';
import { ServiceCard } from './ServiceCard';
import type { ServiceDefinition, ServiceCategory } from '@/lib/serviceCatalog';
import type { ServiceHealthMap } from '@/lib/serviceHealth';

interface ServiceGridProps {
  services: ServiceDefinition[];
  healthMap?: ServiceHealthMap;
  compact?: boolean;
}

export function ServiceGrid({ services, healthMap, compact = false }: ServiceGridProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<ServiceCategory | 'all'>('all');

  // Get unique categories from services
  const categories = useMemo(() => {
    const cats = new Set(services.map((s) => s.category));
    return Array.from(cats).sort();
  }, [services]);

  // Filter services
  const filteredServices = useMemo(() => {
    return services.filter((service) => {
      // Category filter
      if (selectedCategory !== 'all' && service.category !== selectedCategory) {
        return false;
      }

      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        return (
          service.title.toLowerCase().includes(query) ||
          service.summary.toLowerCase().includes(query) ||
          service.slug.includes(query) ||
          service.capabilities?.some((cap) => cap.toLowerCase().includes(query))
        );
      }

      return true;
    });
  }, [services, selectedCategory, searchQuery]);

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <input
            type="text"
            placeholder="Search services..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-void border border-border-subtle px-4 py-2 font-mono text-sm focus:outline-none focus:border-cata-cyan transition-colors"
          />
          <div className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted text-xs">
            {filteredServices.length} / {services.length}
          </div>
        </div>

        {/* Category filter */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setSelectedCategory('all')}
            className={`font-pixel text-[6px] uppercase px-3 py-1 transition-colors ${
              selectedCategory === 'all'
                ? 'bg-cata-cyan text-void'
                : 'bg-void-soft text-ink-muted hover:text-cata-cyan'
            }`}
          >
            All ({services.length})
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`font-pixel text-[6px] uppercase px-3 py-1 transition-colors ${
                selectedCategory === cat
                  ? 'bg-cata-cyan text-void'
                  : 'bg-void-soft text-ink-muted hover:text-cata-cyan'
              }`}
            >
              {cat} ({services.filter((s) => s.category === cat).length})
            </button>
          ))}
        </div>
      </div>

      {/* Results count */}
      {filteredServices.length === 0 && (
        <div className="text-center py-12">
          <p className="text-ink-muted font-pixel text-[8px] uppercase">
            No services found matching &quot;{searchQuery}&quot;
          </p>
        </div>
      )}

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {filteredServices.map((service) => (
          <ServiceCard
            key={service.slug}
            service={service}
            healthStatus={healthMap?.[service.slug]?.status}
            responseTime={healthMap?.[service.slug]?.responseTime}
            compact={compact}
          />
        ))}
      </div>
    </div>
  );
}
