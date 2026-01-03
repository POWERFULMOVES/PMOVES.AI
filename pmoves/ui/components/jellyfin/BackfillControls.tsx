/* ═══════════════════════════════════════════════════════════════════════════
   Backfill Controls Component
   Configure and manage Jellyfin backfill operations
   ═══════════════════════════════════════════════════════════════════════════ */

"use client";

import { useState } from "react";

// Tailwind JIT static class lookup objects
const INPUT_BASE_CLASSES = "w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";
const BUTTON_PRIMARY_CLASSES = "rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50";
const BUTTON_SECONDARY_CLASSES = "rounded border border-neutral-300 px-4 py-2 text-sm font-medium hover:bg-neutral-50 disabled:opacity-50";

interface BackfillControlsProps {
  /** Callback to start backfill */
  onStart: (options: BackfillOptions) => void;
  /** Callback to cancel backfill */
  onCancel?: () => void;
  /** Whether backfill is in progress */
  running?: boolean;
  /** Current progress (0-100) */
  progress?: number;
  /** Number of items queued */
  queued?: number;
  /** Number of items processed */
  processed?: number;
}

export interface BackfillOptions {
  limit: number;
  priority?: "low" | "normal" | "high";
  skipLinked?: boolean;
  dateFrom?: string;
  dateTo?: string;
}

const DEFAULT_OPTIONS: BackfillOptions = {
  limit: 50,
  priority: "normal",
  skipLinked: true,
};

export function BackfillControls({
  onStart,
  onCancel,
  running = false,
  progress = 0,
  queued = 0,
  processed = 0,
}: BackfillControlsProps) {
  const [options, setOptions] = useState<BackfillOptions>(DEFAULT_OPTIONS);
  const [expanded, setExpanded] = useState(false);

  const handleStart = () => {
    onStart(options);
  };

  const handleCancel = () => {
    if (onCancel) {
      onCancel();
    }
  };

  const updateOption = <K extends keyof BackfillOptions>(
    key: K,
    value: BackfillOptions[K]
  ) => {
    setOptions((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="rounded border border-neutral-200 bg-white p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-medium">Backfill Controls</h3>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-neutral-400 hover:text-neutral-600"
          aria-label={expanded ? "Collapse" : "Expand"}
        >
          <svg
            className={`w-5 h-5 transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {/* Progress bar */}
      {running && (
        <div className="mb-4">
          <div className="flex items-center justify-between text-sm mb-1">
            <span className="text-neutral-600">Processing...</span>
            <span className="text-neutral-500">{progress}%</span>
          </div>
          <div className="w-full bg-neutral-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          {processed > 0 && (
            <div className="text-xs text-neutral-500 mt-1">
              {processed} of {queued} items processed
            </div>
          )}
        </div>
      )}

      {/* Expanded options */}
      {expanded && (
        <div className="space-y-4">
          {/* Limit */}
          <div>
            <label htmlFor="backfill-limit" className="block text-sm font-medium text-neutral-700 mb-1">
              Batch Size
            </label>
            <select
              id="backfill-limit"
              value={options.limit}
              onChange={(e) => updateOption("limit", parseInt(e.target.value))}
              disabled={running}
              className={INPUT_BASE_CLASSES}
            >
              <option value={10}>10 items</option>
              <option value={25}>25 items</option>
              <option value={50}>50 items</option>
              <option value={100}>100 items</option>
              <option value={250}>250 items</option>
              <option value={500}>500 items</option>
            </select>
          </div>

          {/* Priority */}
          <div>
            <label htmlFor="backfill-priority" className="block text-sm font-medium text-neutral-700 mb-1">
              Priority
            </label>
            <select
              id="backfill-priority"
              value={options.priority}
              onChange={(e) => updateOption("priority", e.target.value as "low" | "normal" | "high")}
              disabled={running}
              className={INPUT_BASE_CLASSES}
            >
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
            </select>
          </div>

          {/* Skip linked */}
          <div className="flex items-center">
            <input
              id="skip-linked"
              type="checkbox"
              checked={options.skipLinked}
              onChange={(e) => updateOption("skipLinked", e.target.checked)}
              disabled={running}
              className="rounded border-neutral-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="skip-linked" className="ml-2 text-sm text-neutral-700">
              Skip already linked items
            </label>
          </div>

          {/* Date range */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label htmlFor="date-from" className="block text-xs text-neutral-500 mb-1">
                From Date
              </label>
              <input
                id="date-from"
                type="date"
                value={options.dateFrom ?? ""}
                onChange={(e) => updateOption("dateFrom", e.target.value || undefined)}
                disabled={running}
                className={`${INPUT_BASE_CLASSES} text-xs`}
              />
            </div>
            <div>
              <label htmlFor="date-to" className="block text-xs text-neutral-500 mb-1">
                To Date
              </label>
              <input
                id="date-to"
                type="date"
                value={options.dateTo ?? ""}
                onChange={(e) => updateOption("dateTo", e.target.value || undefined)}
                disabled={running}
                className={`${INPUT_BASE_CLASSES} text-xs`}
              />
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 mt-4">
        {!running ? (
          <button
            onClick={handleStart}
            className={BUTTON_PRIMARY_CLASSES}
          >
            Start Backfill ({options.limit} items)
          </button>
        ) : (
          <button
            onClick={handleCancel}
            className="rounded border border-red-600 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
          >
            Cancel Backfill
          </button>
        )}
      </div>

      {/* Info */}
      <div className="mt-3 text-xs text-neutral-500">
        <p>Backfill matches unlinked YouTube videos to Jellyfin library items.</p>
      </div>
    </div>
  );
}
