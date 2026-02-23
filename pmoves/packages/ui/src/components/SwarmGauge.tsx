import React from 'react';
import { cn } from '../lib/utils';

export interface SwarmGaugeProps {
  potential: number;
  activeAgents: number;
  indexedChunks: number;
  connectionDensity: number;
  className?: string;
}

export function SwarmGauge({
  potential,
  activeAgents,
  indexedChunks,
  connectionDensity,
  className,
}: SwarmGaugeProps) {
  // Normalize potential to 0-100 scale for display
  const normalizedPotential = Math.min(100, potential);
  const gaugeAngle = (normalizedPotential / 100) * 180;

  return (
    <div
      className={cn(
        'rounded-lg border border-gray-200 bg-white p-4',
        className,
      )}
    >
      <h3 className="text-xs font-medium uppercase tracking-wider text-gray-500">
        Swarm Potential
      </h3>

      {/* Gauge arc */}
      <div className="relative mx-auto mt-2 h-20 w-40">
        <svg viewBox="0 0 160 80" className="h-full w-full">
          {/* Background arc */}
          <path
            d="M 10 75 A 65 65 0 0 1 150 75"
            fill="none"
            stroke="#e5e7eb"
            strokeWidth="8"
            strokeLinecap="round"
          />
          {/* Value arc */}
          <path
            d="M 10 75 A 65 65 0 0 1 150 75"
            fill="none"
            stroke="url(#swarm-gradient)"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={`${(gaugeAngle / 180) * 204} 204`}
          />
          <defs>
            <linearGradient id="swarm-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#ef4444" />
              <stop offset="50%" stopColor="#eab308" />
              <stop offset="100%" stopColor="#22c55e" />
            </linearGradient>
          </defs>
        </svg>
        <div className="absolute inset-0 flex items-end justify-center pb-1">
          <span className="text-xl font-bold text-gray-900">
            {potential.toFixed(1)}
          </span>
        </div>
      </div>

      {/* Sub-metrics */}
      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div>
          <p className="text-lg font-semibold text-gray-900">{activeAgents}</p>
          <p className="text-xs text-gray-500">Agents</p>
        </div>
        <div>
          <p className="text-lg font-semibold text-gray-900">
            {indexedChunks > 1000 ? `${(indexedChunks / 1000).toFixed(1)}k` : indexedChunks}
          </p>
          <p className="text-xs text-gray-500">Chunks</p>
        </div>
        <div>
          <p className="text-lg font-semibold text-gray-900">
            {(connectionDensity * 100).toFixed(1)}%
          </p>
          <p className="text-xs text-gray-500">Density</p>
        </div>
      </div>
    </div>
  );
}
