/* ═══════════════════════════════════════════════════════════════════════════
   Component: TierNavigation
   Category filter pills for service catalog
   ═══════════════════════════════════════════════════════════════════════════ */

'use client';

import { type ServiceCategory } from '@/lib/serviceCatalog';

export interface TierNavigationProps {
  activeTier: ServiceCategory | 'all';
  onTierChange: (tier: ServiceCategory | 'all') => void;
  tierStats?: {
    tier: ServiceCategory;
    total: number;
    healthy: number;
    percentage: number;
  }[];
  className?: string;
}

const TIERS: { value: ServiceCategory | 'all'; label: string; color: string; icon?: string }[] = [
  { value: 'all', label: 'All Services', color: 'cyan', icon: '▣' },
  { value: 'observability', label: 'Observability', color: 'cyan', icon: '◈' },
  { value: 'database', label: 'Database', color: 'violet', icon: '◐' },
  { value: 'data', label: 'Data', color: 'forest', icon: '◍' },
  { value: 'bus', label: 'Message Bus', color: 'gold', icon: '◈' },
  { value: 'workers', label: 'Workers', color: 'ember', icon: '⚙' },
  { value: 'agents', label: 'Agents', color: 'cyan', icon: '◈' },
  { value: 'gpu', label: 'GPU', color: 'forest', icon: 'Δ' },
  { value: 'media', label: 'Media', color: 'ember', icon: '◉' },
  { value: 'llm', label: 'LLM', color: 'gold', icon: '◫' },
  { value: 'ui', label: 'UI', color: 'violet', icon: '◻' },
  { value: 'integration', label: 'Integrations', color: 'cyan', icon: '⎋' },
];

const TIER_COLOR_CLASSES: Record<string, {
  bg: string;
  border: string;
  text: string;
  textActive: string;
  bgActive: string;
  borderActive: string;
}> = {
  cyan: {
    bg: 'bg-cata-cyan/5',
    border: 'border-cata-cyan/20',
    text: 'text-cata-cyan',
    textActive: 'text-void',
    bgActive: 'bg-cata-cyan',
    borderActive: 'border-cata-cyan',
  },
  violet: {
    bg: 'bg-cata-violet/5',
    border: 'border-cata-violet/20',
    text: 'text-cata-violet',
    textActive: 'text-void',
    bgActive: 'bg-cata-violet',
    borderActive: 'border-cata-violet',
  },
  forest: {
    bg: 'bg-cata-forest/5',
    border: 'border-cata-forest/20',
    text: 'text-cata-forest',
    textActive: 'text-void',
    bgActive: 'bg-cata-forest',
    borderActive: 'border-cata-forest',
  },
  gold: {
    bg: 'bg-cata-gold/5',
    border: 'border-cata-gold/20',
    text: 'text-cata-gold',
    textActive: 'text-void',
    bgActive: 'bg-cata-gold',
    borderActive: 'border-cata-gold',
  },
  ember: {
    bg: 'bg-cata-ember/5',
    border: 'border-cata-ember/20',
    text: 'text-cata-ember',
    textActive: 'text-void',
    bgActive: 'bg-cata-ember',
    borderActive: 'border-cata-ember',
  },
};

/**
 * Tier/category navigation pills for filtering services
 */
export function TierNavigation({
  activeTier,
  onTierChange,
  tierStats,
  className = '',
}: TierNavigationProps) {
  return (
    <nav
      className={`
        flex items-center gap-2 overflow-x-auto
        pb-2 scrollbar-hide
        -mx-4 px-4 md:mx-0 md:px-0
        ${className}
      `}
      aria-label="Service categories"
    >
      {TIERS.map((tier) => {
        const isActive = activeTier === tier.value;
        const colors = TIER_COLOR_CLASSES[tier.color] || TIER_COLOR_CLASSES.cyan;

        // Find stats for this tier
        const stats = tierStats?.find(t => t.tier === tier.value);
        const healthText = stats && isActive
          ? `${stats.healthy}/${stats.total}`
          : '';

        return (
          <button
            key={tier.value}
            onClick={() => onTierChange(tier.value as ServiceCategory | 'all')}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-full
              font-display font-bold text-sm uppercase tracking-wider
              border transition-all duration-200 whitespace-nowrap
              group relative overflow-hidden
              ${isActive
                ? `${colors.bgActive} ${colors.textActive} ${colors.borderActive} shadow-lg`
                : `${colors.bg} ${colors.text} ${colors.border} hover:${colors.bg}/20`
              }
            `}
            aria-pressed={isActive}
            aria-label={`Filter by ${tier.label}`}
          >
            {/* Icon */}
            <span className="opacity-70 group-hover:opacity-100 transition-opacity">
              {tier.icon}
            </span>

            {/* Label */}
            <span>{tier.label}</span>

            {/* Health indicator (when active) */}
            {healthText && (
              <span className={`
                text-xs font-pixel opacity-80
                ${isActive ? colors.textActive : colors.text}
              `}>
                {healthText}
              </span>
            )}

            {/* Active indicator line */}
            {isActive && (
              <span className={`
                absolute bottom-0 left-0 right-0 h-0.5
                ${colors.bgActive}
              `} />
            )}
          </button>
        );
      })}
    </nav>
  );
}
