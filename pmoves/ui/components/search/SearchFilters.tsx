/* ═══════════════════════════════════════════════════════════════════════════
   Search Filters Component
   Filter controls for Hi-RAG search queries
   ═══════════════════════════════════════════════════════════════════════════ */

"use client";

import type { HiragFilters, HiragSource } from "@/lib/api/hirag";

// Tailwind JIT static classes
const LABEL_CLASSES = "block text-sm font-medium text-neutral-700 mb-1";
const INPUT_BASE_CLASSES = "w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent";
const SELECT_BASE_CLASSES = "w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white";

const SOURCE_OPTIONS: { value: HiragSource | ""; label: string }[] = [
  { value: "", label: "All Sources" },
  { value: "youtube", label: "YouTube" },
  { value: "notebook", label: "Notebook" },
  { value: "pdf", label: "PDF Documents" },
  { value: "webpage", label: "Web Pages" },
  { value: "transcript", label: "Transcripts" },
];

const MIN_SCORE_OPTIONS = [
  { value: "", label: "Any Relevance" },
  { value: "0.9", label: "Very High (90%+)" },
  { value: "0.7", label: "High (70%+)" },
  { value: "0.5", label: "Medium (50%+)" },
  { value: "0.3", label: "Low (30%+)" },
];

interface SearchFiltersProps {
  /** Current filter values */
  filters: HiragFilters;
  /** Callback when filters change */
  onChange: (filters: HiragFilters) => void;
  /** Whether the filter panel is visible */
  isOpen?: boolean;
  /** Callback to toggle panel visibility */
  onToggle?: () => void;
}

export function SearchFilters({
  filters,
  onChange,
  isOpen = true,
  onToggle,
}: SearchFiltersProps) {
  const updateFilter = <K extends keyof HiragFilters>(
    key: K,
    value: HiragFilters[K]
  ) => {
    onChange({ ...filters, [key]: value });
  };

  const clearFilters = () => {
    onChange({});
  };

  const hasActiveFilters =
    filters.sourceType ||
    filters.startDate ||
    filters.endDate ||
    filters.minScore !== undefined ||
    filters.channelId;

  if (!isOpen) {
    return null;
  }

  return (
    <div className="rounded border border-neutral-200 bg-white p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-neutral-800">Filters</h3>
        <div className="flex items-center gap-2">
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-xs text-blue-600 hover:text-blue-800"
            >
              Clear All
            </button>
          )}
          {onToggle && (
            <button
              onClick={onToggle}
              className="md:hidden text-neutral-400 hover:text-neutral-600"
              aria-label="Close filters"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Source Type Filter */}
      <div>
        <label htmlFor="source-type" className={LABEL_CLASSES}>
          Source Type
        </label>
        <select
          id="source-type"
          value={filters.sourceType ?? ""}
          onChange={(e) =>
            updateFilter(
              "sourceType",
              e.target.value ? (e.target.value as HiragSource) : undefined
            )
          }
          className={SELECT_BASE_CLASSES}
        >
          {SOURCE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {/* Date Range Filter */}
      <div className="space-y-2">
        <label className={LABEL_CLASSES}>Date Range</label>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label htmlFor="start-date" className="text-xs text-neutral-500 mb-1 block">
              From
            </label>
            <input
              id="start-date"
              type="date"
              value={filters.startDate ?? ""}
              onChange={(e) => updateFilter("startDate", e.target.value || undefined)}
              className={INPUT_BASE_CLASSES}
            />
          </div>
          <div>
            <label htmlFor="end-date" className="text-xs text-neutral-500 mb-1 block">
              To
            </label>
            <input
              id="end-date"
              type="date"
              value={filters.endDate ?? ""}
              onChange={(e) => updateFilter("endDate", e.target.value || undefined)}
              className={INPUT_BASE_CLASSES}
            />
          </div>
        </div>
      </div>

      {/* Minimum Score Filter */}
      <div>
        <label htmlFor="min-score" className={LABEL_CLASSES}>
          Minimum Relevance
        </label>
        <select
          id="min-score"
          value={filters.minScore?.toString() ?? ""}
          onChange={(e) =>
            updateFilter(
              "minScore",
              e.target.value ? parseFloat(e.target.value) : undefined
            )
          }
          className={SELECT_BASE_CLASSES}
        >
          {MIN_SCORE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {/* Channel ID Filter */}
      <div>
        <label htmlFor="channel-id" className={LABEL_CLASSES}>
          Channel ID
        </label>
        <input
          id="channel-id"
          type="text"
          value={filters.channelId ?? ""}
          onChange={(e) =>
            updateFilter("channelId", e.target.value || undefined)
          }
          placeholder="e.g., UCxxxxxxxxxxxxxxxxxx"
          className={INPUT_BASE_CLASSES}
        />
        <p className="text-xs text-neutral-500 mt-1">
          Filter by YouTube channel ID
        </p>
      </div>

      {/* Active filters summary */}
      {hasActiveFilters && (
        <div className="pt-3 border-t border-neutral-200">
          <div className="text-xs text-neutral-500 mb-2">Active Filters:</div>
          <div className="flex flex-wrap gap-2">
            {filters.sourceType && (
              <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded">
                Source: {filters.sourceType}
              </span>
            )}
            {filters.startDate && (
              <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded">
                From: {filters.startDate}
              </span>
            )}
            {filters.endDate && (
              <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded">
                To: {filters.endDate}
              </span>
            )}
            {filters.minScore !== undefined && (
              <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded">
                Score: {Math.round(filters.minScore * 100)}%+
              </span>
            )}
            {filters.channelId && (
              <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded">
                Channel: {filters.channelId.slice(0, 8)}...
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
