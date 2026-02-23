import React from 'react';
import { cn } from '../lib/utils';

export interface MetricChartProps {
  label: string;
  value: number;
  unit?: string;
  trend?: 'up' | 'down' | 'flat';
  sparkline?: number[];
  className?: string;
}

const SPARK_HEIGHT = 24;
const SPARK_WIDTH_PER_POINT = 3;

export function MetricChart({
  label,
  value,
  unit = '',
  trend,
  sparkline,
  className,
}: MetricChartProps) {
  const trendIcon = trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→';
  const trendColor = trend === 'up' ? 'text-emerald-600' : trend === 'down' ? 'text-red-600' : 'text-gray-400';

  return (
    <div
      className={cn(
        'rounded-lg border border-gray-200 bg-white p-3',
        className,
      )}
    >
      <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
        {label}
      </p>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-2xl font-semibold text-gray-900">
          {typeof value === 'number' ? value.toLocaleString() : value}
        </span>
        {unit && <span className="text-sm text-gray-500">{unit}</span>}
        {trend && (
          <span className={cn('text-sm font-medium', trendColor)}>
            {trendIcon}
          </span>
        )}
      </div>

      {/* SVG sparkline */}
      {sparkline && sparkline.length > 1 && (
        <svg
          className="mt-2 w-full"
          height={SPARK_HEIGHT}
          viewBox={`0 0 ${sparkline.length * SPARK_WIDTH_PER_POINT} ${SPARK_HEIGHT}`}
          aria-label={`Sparkline for ${label}`}
          role="img"
        >
          <polyline
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="text-indigo-400"
            points={sparkline
              .map((v, i) => {
                const min = Math.min(...sparkline);
                const max = Math.max(...sparkline);
                const range = max - min || 1;
                const x = i * SPARK_WIDTH_PER_POINT;
                const y = SPARK_HEIGHT - ((v - min) / range) * (SPARK_HEIGHT - 4) - 2;
                return `${x},${y}`;
              })
              .join(' ')}
          />
        </svg>
      )}
    </div>
  );
}
