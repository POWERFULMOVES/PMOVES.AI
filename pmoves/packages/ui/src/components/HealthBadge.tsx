import React from 'react';
import { cn } from '../lib/utils';

export interface HealthBadgeProps {
  service: string;
  status: 'healthy' | 'degraded' | 'down' | 'unknown';
  port?: number;
  latency_ms?: number;
  className?: string;
}

const statusStyles = {
  healthy: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  degraded: 'bg-amber-100 text-amber-800 border-amber-200',
  down: 'bg-red-100 text-red-800 border-red-200',
  unknown: 'bg-gray-100 text-gray-600 border-gray-200',
} as const;

const statusDots = {
  healthy: 'bg-emerald-500',
  degraded: 'bg-amber-500',
  down: 'bg-red-500',
  unknown: 'bg-gray-400',
} as const;

export function HealthBadge({
  service,
  status,
  port,
  latency_ms,
  className,
}: HealthBadgeProps) {
  return (
    <div
      className={cn(
        'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium',
        statusStyles[status],
        className,
      )}
      role="status"
      aria-label={`${service}: ${status}`}
    >
      <span
        className={cn('h-2 w-2 rounded-full', statusDots[status])}
        aria-hidden="true"
      />
      <span>{service}</span>
      {port && <span className="opacity-60">:{port}</span>}
      {latency_ms !== undefined && (
        <span className="opacity-60">{latency_ms}ms</span>
      )}
    </div>
  );
}
