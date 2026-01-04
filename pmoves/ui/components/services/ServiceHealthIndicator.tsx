/* ═══════════════════════════════════════════════════════════════════════════
   Component: ServiceHealthIndicator
   Visual health status indicator for services
   ═══════════════════════════════════════════════════════════════════════════ */

import { type ServiceHealthStatus } from '@/lib/serviceHealth';

export interface ServiceHealthIndicatorProps {
  status: ServiceHealthStatus;
  size?: 'sm' | 'md' | 'lg';
  showPulse?: boolean;
  className?: string;
}

/**
 * Health status indicator dot with animation
 *
 * @example
 * <ServiceHealthIndicator status="healthy" size="md" showPulse />
 */
export function ServiceHealthIndicator({
  status,
  size = 'md',
  showPulse = true,
  className = '',
}: ServiceHealthIndicatorProps) {
  const sizeClasses = {
    sm: 'w-1.5 h-1.5',
    md: 'w-2 h-2',
    lg: 'w-3 h-3',
  };

  const statusClasses: Record<ServiceHealthStatus, string> = {
    healthy: 'bg-cata-forest shadow-[0_0_8px_rgba(0,255,136,0.5)]',
    unhealthy: 'bg-cata-ember shadow-[0_0_8px_rgba(255,61,61,0.5)]',
    unknown: 'bg-ink-muted',
    checking: 'bg-cata-gold animate-spin',
  };

  const pulseClasses = showPulse && status === 'healthy'
    ? 'animate-pulse'
    : '';

  const pingClasses = showPulse && status === 'healthy'
    ? 'before:absolute before:inset-0 before:rounded-full before:bg-cata-forest before:opacity-50 before:animate-ping'
    : '';

  return (
    <div
      className={`
        relative rounded-full
        ${sizeClasses[size]}
        ${statusClasses[status]}
        ${pulseClasses}
        ${pingClasses}
        ${className}
      `}
      aria-label={`Service status: ${status}`}
    />
  );
}

/**
 * Health status badge with text
 */
export interface ServiceHealthBadgeProps {
  status: ServiceHealthStatus;
  size?: 'sm' | 'md' | 'lg';
  showText?: boolean;
  className?: string;
}

export function ServiceHealthBadge({
  status,
  size = 'md',
  showText = false,
  className = '',
}: ServiceHealthBadgeProps) {
  const sizeClasses = {
    sm: 'text-[8px] px-1.5 py-0.5',
    md: 'text-[10px] px-2 py-1',
    lg: 'text-xs px-2.5 py-1.5',
  };

  const statusClasses: Record<ServiceHealthStatus, string> = {
    healthy: 'text-cata-forest bg-cata-forest/10 border-cata-forest/30',
    unhealthy: 'text-cata-ember bg-cata-ember/10 border-cata-ember/30',
    unknown: 'text-ink-muted bg-void-soft border-ink-muted/30',
    checking: 'text-cata-gold bg-cata-gold/10 border-cata-gold/30',
  };

  const statusText: Record<ServiceHealthStatus, string> = {
    healthy: 'Online',
    unhealthy: 'Offline',
    unknown: 'Unknown',
    checking: 'Checking...',
  };

  return (
    <div
      className={`
        inline-flex items-center gap-1.5 rounded-full border
        font-pixel uppercase
        ${sizeClasses[size]}
        ${statusClasses[status]}
        ${className}
      `}
    >
      <ServiceHealthIndicator status={status} size={size} showPulse={false} />
      {showText && <span>{statusText[status]}</span>}
    </div>
  );
}
