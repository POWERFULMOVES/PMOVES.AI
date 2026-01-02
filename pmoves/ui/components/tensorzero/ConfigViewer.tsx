/* ═══════════════════════════════════════════════════════════════════════════
   TensorZero Config Viewer Component
   Displays current configuration in TOML and JSON formats
   ═══════════════════════════════════════════════════════════════════════════ */

'use client';

import { useState } from 'react';
import type { TensorZeroConfig } from './types';
import { exportAsToml, exportAsJson } from './api';

type ViewFormat = 'json' | 'toml';

interface ConfigViewerProps {
  config: TensorZeroConfig;
  className?: string;
}

export function ConfigViewer({ config, className = '' }: ConfigViewerProps) {
  const [format, setFormat] = useState<ViewFormat>('json');

  const content = format === 'json' ? exportAsJson(config) : exportAsToml(config);

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(content);
      // In production, show a toast notification
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  const downloadFile = () => {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tensorzero-config.${format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className={`card-mech p-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="font-display font-bold text-lg uppercase tracking-wide text-cata-cyan">
            Configuration View
          </h3>
          <p className="text-sm text-ink-secondary mt-1 font-body">
            Current TensorZero configuration
          </p>
        </div>

        {/* Format toggle */}
        <div className="flex gap-2">
          <button
            onClick={() => setFormat('json')}
            className={`px-4 py-2 font-pixel text-[7px] uppercase tracking-wider transition-all ${
              format === 'json'
                ? 'bg-cata-cyan text-void font-semibold'
                : 'bg-void-soft text-ink-muted hover:text-cata-cyan'
            }`}
          >
            JSON
          </button>
          <button
            onClick={() => setFormat('toml')}
            className={`px-4 py-2 font-pixel text-[7px] uppercase tracking-wider transition-all ${
              format === 'toml'
                ? 'bg-cata-cyan text-void font-semibold'
                : 'bg-void-soft text-ink-muted hover:text-cata-cyan'
            }`}
          >
            TOML
          </button>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3 mb-4">
        <button
          onClick={copyToClipboard}
          className="px-4 py-2 font-pixel text-[7px] uppercase tracking-wider bg-void-soft text-ink-secondary hover:text-cata-cyan hover:bg-void-elevated transition-all"
        >
          Copy to Clipboard
        </button>
        <button
          onClick={downloadFile}
          className="px-4 py-2 font-pixel text-[7px] uppercase tracking-wider bg-void-soft text-ink-secondary hover:text-cata-cyan hover:bg-void-elevated transition-all"
        >
          Download {format.toUpperCase()}
        </button>
      </div>

      {/* Content display */}
      <div className="bg-void-soft rounded-lg p-4 border border-border-subtle overflow-auto max-h-[600px]">
        <pre className="font-mono text-xs text-ink-secondary leading-relaxed">
          {content}
        </pre>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-border-subtle">
        <div>
          <div className="font-pixel text-[6px] text-ink-muted uppercase">Providers</div>
          <div className="font-display text-2xl font-bold text-cata-cyan mt-1">
            {config.providers.length}
          </div>
        </div>
        <div>
          <div className="font-pixel text-[6px] text-ink-muted uppercase">Functions</div>
          <div className="font-display text-2xl font-bold text-cata-violet mt-1">
            {config.functions.length}
          </div>
        </div>
        <div>
          <div className="font-pixel text-[6px] text-ink-muted uppercase">Total Variants</div>
          <div className="font-display text-2xl font-bold text-cata-gold mt-1">
            {config.functions.reduce((sum, fn) => sum + fn.variants.length, 0)}
          </div>
        </div>
      </div>
    </div>
  );
}
