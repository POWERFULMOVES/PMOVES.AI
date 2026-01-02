/* ═══════════════════════════════════════════════════════════════════════════
   Component: SystemHubSection
   Client-side service hub with real-time health monitoring
   ═══════════════════════════════════════════════════════════════════════════ */

'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { SystemStatsBar } from './SystemStatsBar';
import { TierOverviewGrid } from '../services/TierOverview';
import { useServiceHealth } from '@/lib/useServiceHealth';
import type { ServiceCategory } from '@/lib/serviceCatalog';
import type { TierStats } from '../services/TierOverview';

export interface SystemHubData {
  services?: unknown[];
  health?: unknown;
  tiers: Record<ServiceCategory, TierStats>;
  stats: {
    totalServices?: number;
    healthyPercentage?: number;
    total?: number;
    healthy?: number;
    unhealthy?: number;
    unknown?: number;
    percentage?: number;
    criticalDown?: string[];
  };
}

/**
 * Client component that fetches and displays real-time service hub data
 *
 * Features:
 * - Auto-refresh every 30 seconds
 * - System-wide health statistics
 * - Expandable tier overview cards
 * - One-click access to all services
 */
export function SystemHubSection() {
  const { health, isPolling, refresh, lastUpdate } = useServiceHealth({
    pollInterval: 30000,
    enabled: true,
  });

  const [hubData, setHubData] = useState<SystemHubData | null>(null);
  const [expandedTier, setExpandedTier] = useState<ServiceCategory | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch hub data (catalog + tier stats)
  useEffect(() => {
    async function fetchHubData() {
      try {
        const res = await fetch('/api/services-hub');
        if (res.ok) {
          const data = await res.json();
          setHubData(data);
        }
      } catch (err) {
        console.error('Failed to fetch hub data:', err);
      } finally {
        setIsLoading(false);
      }
    }

    fetchHubData();
  }, []);

  // Handle manual refresh
  const handleRefresh = async () => {
    await refresh();
    // Also refetch hub data
    try {
      const res = await fetch('/api/services-hub');
      if (res.ok) {
        const data = await res.json();
        setHubData(data);
      }
    } catch (err) {
      console.error('Failed to refresh hub data:', err);
    }
  };

  if (isLoading || !hubData) {
    return (
      <section className="relative py-32 px-6 lg:px-12 bg-void-elevated">
        <div className="max-w-7xl mx-auto text-center">
          <div className="inline-flex items-center gap-3 text-cata-cyan">
            <div className="w-4 h-4 border-2 border-cata-cyan border-t-transparent rounded-full animate-spin" />
            <span className="font-pixel text-xs uppercase">Loading Service Hub...</span>
          </div>
        </div>
      </section>
    );
  }

  const { stats, tiers } = hubData;

  // Transform stats from API format to component format
  const componentStats = {
    total: stats.total ?? stats.totalServices ?? 0,
    healthy: stats.healthy ?? 0,
    unhealthy: stats.unhealthy ?? 0,
    unknown: stats.unknown ?? 0,
    percentage: stats.percentage ?? stats.healthyPercentage ?? 0,
  };

  // Transform tiers Record to array format for TierOverviewGrid
  const tierArray = Object.entries(tiers).map(([tier, stats]) => ({
    tier: tier as ServiceCategory,
    stats,
  }));

  return (
    <section className="relative py-20 px-6 lg:px-12 bg-void-elevated">
      {/* Background accent */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute right-0 top-1/3 w-1/3 h-1/2 bg-glow-cyan opacity-10 blur-[150px]" />
      </div>

      <div className="relative max-w-7xl mx-auto space-y-12">
        {/* Section header */}
        <div>
          <div className="flex items-end justify-between gap-8 flex-wrap">
            <div>
              <span className="font-pixel text-[8px] text-cata-cyan tracking-wider mb-4 block">
                [ SERVICE HUB ]
              </span>
              <h2 className="heading-display text-4xl sm:text-5xl lg:text-6xl mt-4">
                ALL SYSTEMS
                <br />
                <span className="text-gradient-cyan">ONE DASHBOARD</span>
              </h2>
            </div>
            <p className="max-w-md text-ink-secondary font-body">
              Real-time health monitoring across {componentStats.total} PMOVES services.
              Grouped by category with one-click access.
            </p>
          </div>
          <div className="line-accent w-full mt-12" />
        </div>

        {/* System Stats Bar */}
        <SystemStatsBar
          totalServices={componentStats.total}
          healthyCount={componentStats.healthy}
          unhealthyCount={componentStats.unhealthy}
          unknownCount={componentStats.unknown}
          percentage={componentStats.percentage}
          isChecking={isPolling}
          lastUpdate={lastUpdate}
          onRefresh={handleRefresh}
        />

        {/* Tier Overview Grid */}
        <TierOverviewGrid
          tierStats={tierArray}
          healthMap={health}
          expandedTier={expandedTier}
          onTierExpand={(tier) => setExpandedTier(expandedTier === tier ? null : tier)}
        />

        {/* Quick links to critical services */}
        <div className="pt-8 border-t border-border-subtle">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <span className="font-pixel text-[7px] text-ink-muted uppercase tracking-wider">
                Quick Access
              </span>
              <div className="flex flex-wrap gap-3 mt-3">
                <Link href="/dashboard/agent-zero" className="btn-ghost text-xs">
                  Agent Zero
                </Link>
                <Link href="/dashboard/archon" className="btn-ghost text-xs">
                  Archon
                </Link>
                <Link href="/dashboard/services/hi-rag" className="btn-ghost text-xs">
                  Hi-RAG v2
                </Link>
                <Link href="/dashboard/services/tensorzero" className="btn-ghost text-xs">
                  TensorZero
                </Link>
                <Link href="/dashboard/services/supaserch" className="btn-ghost text-xs">
                  SupaSerch
                </Link>
              </div>
            </div>
            <Link
              href="/dashboard/services"
              className="btn-primary"
            >
              View All Services →
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
