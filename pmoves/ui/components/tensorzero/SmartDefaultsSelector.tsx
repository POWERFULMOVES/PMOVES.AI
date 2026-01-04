/* ═══════════════════════════════════════════════════════════════════════════
   TensorZero Smart Defaults Selector Component
   Pre-built configuration templates for common use cases
   ═══════════════════════════════════════════════════════════════════════════ */

'use client';

import { useState } from 'react';
import type { TensorZeroConfig, DashboardTab } from './types';
import { smartDefaultsTemplates, variantTemplates } from './smart-defaults';

interface SmartDefaultsSelectorProps {
  onSelectTemplate: (config: TensorZeroConfig) => void;
  onApplyVariantTemplate: (template: any) => void;
  currentConfig: TensorZeroConfig;
  className?: string;
}

export function SmartDefaultsSelector({
  onSelectTemplate,
  onApplyVariantTemplate,
  currentConfig,
  className = '',
}: SmartDefaultsSelectorProps) {
  const [selectedTab, setSelectedTab] = useState<DashboardTab['id']>('configs');

  const tabs: DashboardTab[] = [
    { id: 'configs', label: 'Smart Defaults', icon: '⚙️', description: 'Pre-built configurations' },
    { id: 'variants', label: 'Variant Templates', icon: '🔀', description: 'A/B testing & routing' },
  ];

  return (
    <div className={`card-mech p-6 ${className}`}>
      {/* Header */}
      <div className="mb-6">
        <h3 className="font-display font-bold text-lg uppercase tracking-wide text-cata-gold">
          Smart Defaults
        </h3>
        <p className="text-sm text-ink-secondary mt-1 font-body">
          Quick-start configurations for common scenarios
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setSelectedTab(tab.id)}
            className={`px-4 py-2 font-pixel text-[7px] uppercase tracking-wider transition-all ${
              selectedTab === tab.id
                ? 'bg-cata-gold text-void font-semibold'
                : 'bg-void-soft text-ink-muted hover:text-cata-gold'
            }`}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {selectedTab === 'configs' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {smartDefaultsTemplates.map((template) => (
            <div
              key={template.id}
              className="bg-void-soft rounded-lg p-6 border border-border-subtle hover:border-cata-gold transition-all group"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="text-3xl">{template.icon}</div>
                  <div>
                    <h4 className="font-display font-semibold text-base uppercase tracking-wide group-hover:text-cata-gold transition-colors">
                      {template.name}
                    </h4>
                  </div>
                </div>
              </div>

              {/* Description */}
              <p className="text-sm text-ink-secondary font-body mb-4 leading-relaxed">
                {template.description}
              </p>

              {/* Tags */}
              <div className="flex flex-wrap gap-2 mb-4">
                {template.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-2 py-1 font-pixel text-[6px] uppercase tracking-wider bg-void text-ink-muted"
                  >
                    {tag}
                  </span>
                ))}
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-3 mb-4 pt-4 border-t border-border-subtle">
                <div>
                  <div className="font-pixel text-[6px] text-ink-muted uppercase">Providers</div>
                  <div className="font-display text-lg font-bold text-cata-cyan mt-1">
                    {template.config.providers.length}
                  </div>
                </div>
                <div>
                  <div className="font-pixel text-[6px] text-ink-muted uppercase">Functions</div>
                  <div className="font-display text-lg font-bold text-cata-violet mt-1">
                    {template.config.functions.length}
                  </div>
                </div>
                <div>
                  <div className="font-pixel text-[6px] text-ink-muted uppercase">Variants</div>
                  <div className="font-display text-lg font-bold text-cata-gold mt-1">
                    {template.config.functions.reduce((sum, fn) => sum + fn.variants.length, 0)}
                  </div>
                </div>
              </div>

              {/* Apply Button */}
              <button
                onClick={() => onSelectTemplate(template.config)}
                className="w-full px-4 py-2 font-pixel text-[7px] uppercase tracking-wider bg-void text-ink-secondary hover:text-cata-gold hover:bg-cata-gold hover:text-void border border-border-subtle hover:border-cata-gold transition-all"
              >
                Apply Configuration
              </button>
            </div>
          ))}
        </div>
      )}

      {selectedTab === 'variants' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {variantTemplates.map((template, idx) => (
            <div
              key={idx}
              className="bg-void-soft rounded-lg p-6 border border-border-subtle hover:border-cata-gold transition-all group"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="font-pixel text-[6px] text-ink-muted uppercase mb-1">
                    {template.type.replace(/_/g, ' ')}
                  </div>
                  <h4 className="font-display font-semibold text-base uppercase tracking-wide group-hover:text-cata-gold transition-colors">
                    {template.name}
                  </h4>
                </div>
              </div>

              {/* Description */}
              <p className="text-sm text-ink-secondary font-body mb-4 leading-relaxed">
                {template.description}
              </p>

              {/* Routing Logic */}
              <div className="bg-void rounded p-3 mb-4">
                <div className="font-pixel text-[6px] text-ink-muted uppercase mb-2">Routing Logic</div>
                <p className="text-xs text-ink-secondary font-body leading-relaxed">
                  {template.routing_logic}
                </p>
              </div>

              {/* Variants Preview */}
              <div className="mb-4">
                <div className="font-pixel text-[6px] text-ink-muted uppercase mb-2">
                  Variants ({template.variants.length})
                </div>
                <div className="space-y-2">
                  {template.variants.map((variant, vIdx) => (
                    <div
                      key={vIdx}
                      className="flex items-center justify-between px-3 py-2 bg-void rounded border border-border-subtle"
                    >
                      <div className="flex-1">
                        <div className="font-mono text-xs text-ink-primary">{variant.name}</div>
                        <div className="font-pixel text-[6px] text-ink-muted uppercase mt-0.5">
                          {variant.model} via {variant.provider}
                        </div>
                      </div>
                      {template.weights && (
                        <div className="px-2 py-1 bg-cata-gold/10 text-cata-gold font-mono text-xs rounded">
                          {Math.round((template.weights[vIdx]?.weight || 0) * 100)}%
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Apply Button */}
              <button
                onClick={() => onApplyVariantTemplate(template)}
                className="w-full px-4 py-2 font-pixel text-[7px] uppercase tracking-wider bg-void text-ink-secondary hover:text-cata-gold hover:bg-cata-gold hover:text-void border border-border-subtle hover:border-cata-gold transition-all"
              >
                Use This Template
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
