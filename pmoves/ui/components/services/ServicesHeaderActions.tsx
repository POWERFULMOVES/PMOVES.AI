'use client';

/* ═══════════════════════════════════════════════════════════════════════════
   Services Header Actions Component
   Client Component for interactive header elements
   ═══════════════════════════════════════════════════════════════════════════ */

import React from 'react';

interface ServicesHeaderActionsProps {
  healthPercentage: number;
  isHealthy: boolean;
}

export function ServicesHeaderActions({ healthPercentage, isHealthy }: ServicesHeaderActionsProps) {
  return (
    <div className="flex items-center gap-3">
      {/* Health indicator */}
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 ${isHealthy ? 'bg-cata-forest animate-pulse' : 'bg-cata-ember'}`} />
        <span className="font-pixel text-[6px] uppercase text-ink-muted">
          {healthPercentage}%
        </span>
      </div>

      {/* Refresh button */}
      <button
        onClick={() => window.location.reload()}
        className="tag tag-cyan hover:tag-cyan/80 transition-colors cursor-pointer"
      >
        Refresh
      </button>
    </div>
  );
}
