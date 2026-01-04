/* ═══════════════════════════════════════════════════════════════════════════
   Component: SystemStatsBar
   Overall system health statistics display
   ═══════════════════════════════════════════════════════════════════════════ */

'use client';

import { ServiceHealthIndicator } from '../services/ServiceHealthIndicator';

export interface SystemStatsBarProps {
  totalServices: number;
  healthyCount: number;
  unhealthyCount: number;
  unknownCount: number;
  percentage: number;
  isChecking?: boolean;
  lastUpdate?: Date | null;
  onRefresh?: () => void;
  className?: string;
}

/**
 * System-wide health statistics bar
 */
export function SystemStatsBar({
  totalServices,
  healthyCount,
  unhealthyCount,
  unknownCount,
  percentage,
  isChecking = false,
  lastUpdate,
  onRefresh,
  className = '',
}: SystemStatsBarProps) {
  const statusColor = percentage >= 80 ? 'text-cata-forest' :
                     percentage >= 50 ? 'text-cata-gold' : 'text-cata-ember';

  const statusBg = percentage >= 80 ? 'bg-cata-forest/10' :
                   percentage >= 50 ? 'bg-cata-gold/10' : 'bg-cata-ember/10';

  // Format last update time
  const formatTime = (date: Date | null) => {
    if (!date) return 'Never';
    const now = new Date();
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  };

  return (
    <div className={`
      flex flex-wrap items-center justify-between gap-4
      p-4 rounded-lg border border-brand-border bg-void-soft
      ${className}
    `}>
      {/* Left: Overall Health */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <ServiceHealthIndicator
            status={isChecking ? 'checking' : percentage >= 80 ? 'healthy' : 'unhealthy'}
            size="lg"
            showPulse={!isChecking && percentage >= 80}
          />
          <div>
            <div className="text-xs text-brand-subtle uppercase tracking-wider">
              System Health
            </div>
            <div className={`text-2xl font-display font-bold ${statusColor}`}>
              {isChecking ? 'Checking...' : `${percentage}%`}
            </div>
          </div>
        </div>

        {/* Stats Breakdown */}
        <div className="hidden sm:flex items-center gap-4 text-sm">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 bg-cata-forest rounded-full"></span>
            <span className="text-brand-subtle">
              {healthyCount} healthy
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 bg-cata-ember rounded-full"></span>
            <span className="text-brand-subtle">
              {unhealthyCount} down
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 bg-ink-muted rounded-full"></span>
            <span className="text-brand-subtle">
              {unknownCount} unknown
            </span>
          </div>
          <div className="text-brand-subtle">
            of {totalServices} services
          </div>
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-4">
        {/* Last Update */}
        {lastUpdate && (
          <div className="text-xs text-brand-subtle">
            Updated {formatTime(lastUpdate)}
          </div>
        )}

        {/* Refresh Button */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isChecking}
            className={`
              px-4 py-2 rounded font-display font-bold text-sm uppercase
              border border-brand-border bg-brand-inverse
              hover:border-cata-cyan hover:text-cata-cyan
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-all
            `}
          >
            {isChecking ? 'Refreshing...' : 'Refresh'}
          </button>
        )}
      </div>
    </div>
  );
}
