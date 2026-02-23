import React from 'react';
import { cn } from '../lib/utils';

export interface AgentCardProps {
  name: string;
  id: string;
  tier: string;
  theme?: {
    character: string;
    faction?: string;
    colors: string[];
    icon?: string;
  };
  capabilities?: string[];
  models?: string[];
  port?: number;
  status?: 'active' | 'idle' | 'offline';
  className?: string;
}

const tierBadgeStyles = {
  data: 'bg-blue-100 text-blue-800',
  api: 'bg-violet-100 text-violet-800',
  llm: 'bg-amber-100 text-amber-800',
  worker: 'bg-emerald-100 text-emerald-800',
  media: 'bg-pink-100 text-pink-800',
  agent: 'bg-indigo-100 text-indigo-800',
  ui: 'bg-cyan-100 text-cyan-800',
} as const;

export function AgentCard({
  name,
  id,
  tier,
  theme,
  capabilities,
  models,
  port,
  status = 'idle',
  className,
}: AgentCardProps) {
  const borderColor = theme?.colors?.[0] || '#6366f1';

  return (
    <article
      className={cn(
        'rounded-lg border-2 bg-white p-4 shadow-sm transition-shadow hover:shadow-md',
        className,
      )}
      style={{ borderColor }}
      aria-label={`Agent: ${name}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">{name}</h3>
          <p className="text-xs text-gray-500">{id}</p>
        </div>
        <span
          className={cn(
            'rounded-full px-2 py-0.5 text-xs font-medium',
            tierBadgeStyles[tier as keyof typeof tierBadgeStyles] || 'bg-gray-100 text-gray-600',
          )}
        >
          {tier}
        </span>
      </div>

      {/* Theme */}
      {theme && (
        <div className="mt-2 flex items-center gap-2">
          <div className="flex gap-1">
            {theme.colors.map((color, i) => (
              <span
                key={i}
                className="h-3 w-3 rounded-full border border-gray-200"
                style={{ backgroundColor: color }}
                aria-hidden="true"
              />
            ))}
          </div>
          <span className="text-xs text-gray-600">{theme.character}</span>
        </div>
      )}

      {/* Capabilities */}
      {capabilities && capabilities.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {capabilities.map((cap) => (
            <span
              key={cap}
              className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600"
            >
              {cap}
            </span>
          ))}
        </div>
      )}

      {/* Footer */}
      <div className="mt-3 flex items-center justify-between text-xs text-gray-400">
        {port && <span>:{port}</span>}
        {models && <span>{models.length} models</span>}
        <span
          className={cn(
            'h-2 w-2 rounded-full',
            status === 'active' ? 'bg-emerald-500' : status === 'idle' ? 'bg-amber-400' : 'bg-gray-300',
          )}
          aria-label={status}
        />
      </div>
    </article>
  );
}
