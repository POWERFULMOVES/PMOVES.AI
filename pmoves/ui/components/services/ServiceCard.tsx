/* ═══════════════════════════════════════════════════════════════════════════
   Service Card Component
   Displays a single service with health status and endpoints
   ═══════════════════════════════════════════════════════════════════════════ */

import Link from 'next/link';
import type { ServiceDefinition, ServiceColor } from '@/lib/serviceCatalog';
import type { ServiceHealthStatus } from '@/lib/serviceHealth';
import { getStatusIndicatorClass, getStatusBadgeClass, formatResponseTime, getStatusText } from '@/lib/serviceHealth';

// Tailwind JIT lookup objects
const TAG_CLASSES: Record<ServiceColor, string> = {
  cyan: 'tag tag-cyan',
  ember: 'tag tag-ember',
  violet: 'tag tag-violet',
  forest: 'tag tag-forest',
  gold: 'tag tag-gold',
};

const ICON_BG_CLASSES: Record<ServiceColor, string> = {
  cyan: 'bg-cata-cyan/10',
  ember: 'bg-cata-ember/10',
  violet: 'bg-cata-violet/10',
  forest: 'bg-cata-forest/10',
  gold: 'bg-cata-gold/10',
};

const BORDER_CLASSES: Record<ServiceColor, string> = {
  cyan: 'border-cata-cyan/30 hover:border-cata-cyan group-hover:text-cata-cyan',
  ember: 'border-cata-ember/30 hover:border-cata-ember group-hover:text-cata-ember',
  violet: 'border-cata-violet/30 hover:border-cata-violet group-hover:text-cata-violet',
  forest: 'border-cata-forest/30 hover:border-cata-forest group-hover:text-cata-forest',
  gold: 'border-cata-gold/30 hover:border-cata-gold group-hover:text-cata-gold',
};

interface ServiceCardProps {
  service: ServiceDefinition;
  healthStatus?: ServiceHealthStatus;
  responseTime?: number;
  compact?: boolean;
}

export function ServiceCard({
  service,
  healthStatus,
  responseTime,
  compact = false,
}: ServiceCardProps) {
  const color = service.color;
  const primaryEndpoint = service.endpoints.find((e) => e.type === 'ui') || service.endpoints[0];
  const href = primaryEndpoint ? `http://localhost:${primaryEndpoint.port}${primaryEndpoint.path}` : '#';

  return (
    <Link
      href={href}
      target={service.external ? '_blank' : undefined}
      rel={service.external ? 'noreferrer' : undefined}
      className={`group card-brutal p-6 flex flex-col gap-4 border ${BORDER_CLASSES[color]}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1 flex-1">
          <span className={TAG_CLASSES[color]}>{service.category}</span>
          <h3 className={`font-display font-bold text-lg mt-2 transition-colors ${BORDER_CLASSES[color]}`}>
            {service.title}
          </h3>
        </div>

        {/* Status indicator */}
        <div className="flex items-center gap-2">
          {healthStatus && (
            <div className={getStatusIndicatorClass(healthStatus)} title={getStatusText(healthStatus)} />
          )}
          <div className={`w-10 h-10 flex items-center justify-center ${ICON_BG_CLASSES[color]} font-display font-bold text-sm opacity-50 group-hover:opacity-100 transition-transform group-hover:scale-110`}>
            {service.title.charAt(0)}
          </div>
        </div>
      </div>

      {/* Description */}
      {!compact && (
        <p className="text-sm text-ink-secondary leading-relaxed">
          {service.summary}
        </p>
      )}

      {/* Capabilities */}
      {service.capabilities && service.capabilities.length > 0 && !compact && (
        <div className="flex flex-wrap gap-2">
          {service.capabilities.slice(0, 3).map((cap) => (
            <span
              key={cap}
              className="font-pixel text-[6px] text-ink-muted uppercase bg-void-soft px-2 py-1"
            >
              {cap}
            </span>
          ))}
          {service.capabilities.length > 3 && (
            <span className="font-pixel text-[6px] text-ink-muted uppercase">
              +{service.capabilities.length - 3}
            </span>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-4 border-t border-border-subtle">
        <div className="flex items-center gap-3">
          {/* Primary port */}
          {primaryEndpoint && (
            <span className="font-mono text-2xs text-ink-muted bg-void px-2 py-1">
              :{primaryEndpoint.port}
            </span>
          )}

          {/* Response time */}
          {responseTime !== undefined && (
            <span className="font-mono text-2xs text-ink-muted">
              {formatResponseTime(responseTime)}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Health badge */}
          {healthStatus && (
            <span className={getStatusBadgeClass(healthStatus)}>
              {getStatusText(healthStatus)}
            </span>
          )}

          {/* Endpoint count */}
          {service.endpoints.length > 1 && (
            <span className="font-pixel text-[6px] text-ink-muted uppercase">
              {service.endpoints.length} endpoints
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
