/* ═══════════════════════════════════════════════════════════════════════════
   Component: TierOverview
   Expandable tier/category summary cards
   ═══════════════════════════════════════════════════════════════════════════ */

'use client';

import { useState } from 'react';
import Link from 'next/link';
import type { ServiceCategory } from '@/lib/serviceCatalog';
import { ServiceHealthIndicator } from './ServiceHealthIndicator';

export interface TierStats {
  total: number;
  healthy: number;
  unhealthy: number;
  unknown: number;
  percentage: number;
}

export interface TierOverviewProps {
  tier: ServiceCategory;
  stats: TierStats;
  healthMap?: Record<string, { status: string; responseTime?: number }>;
  isExpanded?: boolean;
  onExpandChange?: (tier: ServiceCategory, expanded: boolean) => void;
  className?: string;
}

const TIER_INFO: Record<ServiceCategory, {
  label: string;
  color: 'cyan' | 'ember' | 'gold' | 'forest' | 'violet';
  icon: string;
  description: string;
}> = {
  observability: {
    label: 'Observability',
    color: 'cyan',
    icon: '◈',
    description: 'Metrics, logs, and dashboards',
  },
  database: {
    label: 'Databases',
    color: 'violet',
    icon: '◐',
    description: 'Vector, graph, full-text search, object storage',
  },
  data: {
    label: 'Data Stores',
    color: 'forest',
    icon: '◍',
    description: 'Vector embeddings and knowledge graphs',
  },
  bus: {
    label: 'Message Bus',
    color: 'gold',
    icon: '◈',
    description: 'NATS event streaming',
  },
  workers: {
    label: 'Workers',
    color: 'ember',
    icon: '⚙',
    description: 'Ingestion, extraction, and processing',
  },
  agents: {
    label: 'Agents',
    color: 'cyan',
    icon: '◈',
    description: 'Orchestration and research agents',
  },
  gpu: {
    label: 'GPU Services',
    color: 'forest',
    icon: 'Δ',
    description: 'Model serving and acceleration',
  },
  media: {
    label: 'Media',
    color: 'ember',
    icon: '◉',
    description: 'Audio, video, and transcription',
  },
  llm: {
    label: 'LLM',
    color: 'gold',
    icon: '◫',
    description: 'Local model hosting',
  },
  ui: {
    label: 'User Interfaces',
    color: 'violet',
    icon: '◻',
    description: 'Web dashboards and consoles',
  },
  integration: {
    label: 'Integrations',
    color: 'cyan',
    icon: '⎋',
    description: 'External service integrations',
  },
};

const COLOR_CLASSES: Record<string, {
  bg: string;
  border: string;
  text: string;
  accent: string;
  bgSoft: string;
}> = {
  cyan: {
    bg: 'bg-cata-cyan/5',
    border: 'border-cata-cyan/20',
    text: 'text-cata-cyan',
    accent: 'text-cata-cyan',
    bgSoft: 'bg-cata-cyan/10',
  },
  ember: {
    bg: 'bg-cata-ember/5',
    border: 'border-cata-ember/20',
    text: 'text-cata-ember',
    accent: 'text-cata-ember',
    bgSoft: 'bg-cata-ember/10',
  },
  gold: {
    bg: 'bg-cata-gold/5',
    border: 'border-cata-gold/20',
    text: 'text-cata-gold',
    accent: 'text-cata-gold',
    bgSoft: 'bg-cata-gold/10',
  },
  forest: {
    bg: 'bg-cata-forest/5',
    border: 'border-cata-forest/20',
    text: 'text-cata-forest',
    accent: 'text-cata-forest',
    bgSoft: 'bg-cata-forest/10',
  },
  violet: {
    bg: 'bg-cata-violet/5',
    border: 'border-cata-violet/20',
    text: 'text-cata-violet',
    accent: 'text-cata-violet',
    bgSoft: 'bg-cata-violet/10',
  },
};

/**
 * Expandable tier summary card
 */
export function TierOverviewCard({
  tier,
  stats,
  healthMap,
  isExpanded = false,
  onExpandChange,
  className = '',
}: TierOverviewProps) {
  const info = TIER_INFO[tier];
  const colors = COLOR_CLASSES[info.color];
  const [localExpanded, setLocalExpanded] = useState(isExpanded);

  const expanded = onExpandChange !== undefined ? isExpanded : localExpanded;
  const setExpanded = (value: boolean) => {
    if (onExpandChange) {
      onExpandChange(tier, value);
    } else {
      setLocalExpanded(value);
    }
  };

  // Calculate status
  const status = stats.percentage >= 80 ? 'healthy' :
                  stats.percentage >= 50 ? 'warning' : 'unhealthy';

  return (
    <div
      className={`
        group card-brutal border ${colors.border}
        transition-all duration-300
        ${expanded ? 'col-span-full' : ''}
        ${className}
      `}
    >
      {/* Header - Always Visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className={`
          w-full flex items-center justify-between gap-4 p-4
          text-left transition-colors
          ${expanded ? colors.bgSoft : ''}
          hover:${colors.bgSoft}
        `}
      >
        <div className="flex items-center gap-4 flex-1 min-w-0">
          {/* Icon */}
          <div className={`
            w-12 h-12 flex items-center justify-center rounded-lg
            ${colors.bg} ${colors.text}
            font-display font-bold text-xl
          `}>
            {info.icon}
          </div>

          {/* Title & Description */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className={`font-display font-bold text-lg ${colors.text}`}>
                {info.label}
              </h3>
              <span className={`font-pixel text-[8px] uppercase px-2 py-0.5 rounded ${colors.bg} ${colors.text}`}>
                {stats.total}
              </span>
            </div>
            <p className="text-sm text-brand-subtle truncate">
              {info.description}
            </p>
          </div>
        </div>

        {/* Health Status */}
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className={`text-2xl font-display font-bold ${colors.text}`}>
              {stats.percentage}%
            </div>
            <div className="text-xs text-brand-subtle">
              {stats.healthy} / {stats.total} healthy
            </div>
          </div>

          {/* Expand/Collapse Icon */}
          <div className={`
            w-8 h-8 flex items-center justify-center rounded
            ${colors.bg} ${colors.text}
            transition-transform duration-300
            ${expanded ? 'rotate-180' : ''}
          `}>
            ▼
          </div>
        </div>
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3">
          {/* Status Breakdown */}
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 bg-cata-forest rounded-full"></span>
              <span className="text-brand-subtle">
                Healthy: {stats.healthy}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 bg-cata-ember rounded-full"></span>
              <span className="text-brand-subtle">
                Unhealthy: {stats.unhealthy}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 bg-ink-muted rounded-full"></span>
              <span className="text-brand-subtle">
                Unknown: {stats.unknown}
              </span>
            </div>
          </div>

          {/* Services Link */}
          <Link
            href={`/dashboard/services?tier=${tier}`}
            className={`
              inline-flex items-center gap-2 px-4 py-2 rounded
              ${colors.bg} ${colors.text} ${colors.border}
              font-display font-bold text-sm uppercase
              hover:shadow-lg transition-all
            `}
          >
            View All {info.label} Services →
          </Link>
        </div>
      )}
    </div>
  );
}

export interface TierOverviewGridProps {
  tierStats: {
    tier: ServiceCategory;
    stats: TierStats;
  }[];
  healthMap?: Record<string, { status: string; responseTime?: number }>;
  expandedTier?: ServiceCategory | null;
  onTierExpand?: (tier: ServiceCategory) => void;
  className?: string;
}

/**
 * Grid of all tier overview cards
 */
export function TierOverviewGrid({
  tierStats,
  healthMap,
  expandedTier,
  onTierExpand,
  className = '',
}: TierOverviewGridProps) {
  return (
    <div className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 ${className}`}>
      {tierStats.map(({ tier, stats }) => (
        <TierOverviewCard
          key={tier}
          tier={tier}
          stats={stats}
          healthMap={healthMap}
          isExpanded={expandedTier === tier}
          onExpandChange={onTierExpand ? (t, exp) => {
            if (exp) onTierExpand(t);
          } : undefined}
        />
      ))}
    </div>
  );
}
