/* ═══════════════════════════════════════════════════════════════════════════
   Task Initiation Form Component
   Form to create new Deep Research tasks with options
   ═══════════════════════════════════════════════════════════════════════════ */

"use client";

import { useState } from "react";

// Tailwind JIT static class lookup objects
const TEXTAREA_BASE_CLASSES = "w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none";
const SELECT_BASE_CLASSES = "w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white";
const BUTTON_PRIMARY_CLASSES = "rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed";
const BUTTON_SECONDARY_CLASSES = "rounded border border-neutral-300 px-4 py-2 text-sm font-medium hover:bg-neutral-50";

export interface ResearchOptions {
  mode: "tensorzero" | "openrouter" | "local" | "hybrid";
  notebookId?: string;
  maxIterations: number;
  priority: number;
}

const DEFAULT_OPTIONS: ResearchOptions = {
  mode: "tensorzero",
  maxIterations: 10,
  priority: 5,
};

interface TaskInitiationFormProps {
  /** Callback when form is submitted */
  onSubmit: (query: string, options: ResearchOptions) => void;
  /** Whether submission is in progress */
  loading?: boolean;
  /** Available notebooks for publishing results */
  notebooks?: Array<{ id: string; name: string }>;
}

export function TaskInitiationForm({
  onSubmit,
  loading = false,
  notebooks = [],
}: TaskInitiationFormProps) {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<ResearchOptions>(DEFAULT_OPTIONS);
  const [expanded, setExpanded] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    onSubmit(query.trim(), options);
  };

  const updateOption = <K extends keyof ResearchOptions>(
    key: K,
    value: ResearchOptions[K]
  ) => {
    setOptions((prev) => ({ ...prev, [key]: value }));
  };

  const MODE_OPTIONS = [
    { value: "tensorzero" as const, label: "TensorZero", description: "GPU-accelerated local models" },
    { value: "openrouter" as const, label: "OpenRouter", description: "Cloud API gateway" },
    { value: "local" as const, label: "Local", description: "CPU-only local models" },
    { value: "hybrid" as const, label: "Hybrid", description: "Automatic fallback" },
  ];

  return (
    <div className="rounded border border-neutral-200 bg-white p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-medium">Start New Research</h3>
        <button
          onClick={() => setExpanded(!expanded)}
          type="button"
          className="text-neutral-400 hover:text-neutral-600"
          aria-label={expanded ? "Collapse" : "Expand options"}
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

      <form onSubmit={handleSubmit}>
        {/* Query Input */}
        <div className="mb-4">
          <label htmlFor="research-query" className="block text-sm font-medium text-neutral-700 mb-1">
            Research Question
          </label>
          <textarea
            id="research-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter your research question..."
            className={TEXTAREA_BASE_CLASSES}
            disabled={loading}
            rows={3}
            maxLength={1000}
          />
          <div className="text-xs text-neutral-500 mt-1 text-right">
            {query.length} / 1000
          </div>
        </div>

        {/* Expanded Options */}
        {expanded && (
          <div className="space-y-4 mb-4">
            {/* Mode Selection */}
            <div>
              <label htmlFor="research-mode" className="block text-sm font-medium text-neutral-700 mb-1">
                Execution Mode
              </label>
              <select
                id="research-mode"
                value={options.mode}
                onChange={(e) => updateOption("mode", e.target.value as ResearchOptions["mode"])}
                disabled={loading}
                className={SELECT_BASE_CLASSES}
              >
                {MODE_OPTIONS.map((mode) => (
                  <option key={mode.value} value={mode.value}>
                    {mode.label} - {mode.description}
                  </option>
                ))}
              </select>
            </div>

            {/* Max Iterations */}
            <div>
              <label htmlFor="max-iterations" className="block text-sm font-medium text-neutral-700 mb-1">
                Max Iterations: {options.maxIterations}
              </label>
              <input
                id="max-iterations"
                type="range"
                min={3}
                max={30}
                value={options.maxIterations}
                onChange={(e) => updateOption("maxIterations", parseInt(e.target.value))}
                disabled={loading}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-neutral-500">
                <span>3 (fast)</span>
                <span>30 (thorough)</span>
              </div>
            </div>

            {/* Priority */}
            <div>
              <label htmlFor="priority" className="block text-sm font-medium text-neutral-700 mb-1">
                Priority: {options.priority}
              </label>
              <input
                id="priority"
                type="range"
                min={1}
                max={10}
                value={options.priority}
                onChange={(e) => updateOption("priority", parseInt(e.target.value))}
                disabled={loading}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-neutral-500">
                <span>1 (low)</span>
                <span>10 (urgent)</span>
              </div>
            </div>

            {/* Notebook Selection */}
            {notebooks.length > 0 && (
              <div>
                <label htmlFor="notebook" className="block text-sm font-medium text-neutral-700 mb-1">
                  Publish to Notebook (optional)
                </label>
                <select
                  id="notebook"
                  value={options.notebookId ?? ""}
                  onChange={(e) => updateOption("notebookId", e.target.value || undefined)}
                  disabled={loading}
                  className={SELECT_BASE_CLASSES}
                >
                  <option value="">No notebook</option>
                  {notebooks.map((notebook) => (
                    <option key={notebook.id} value={notebook.id}>
                      {notebook.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className={BUTTON_PRIMARY_CLASSES}
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Starting Research...
              </span>
            ) : (
              "Start Research"
            )}
          </button>
          {query && (
            <button
              type="button"
              onClick={() => setQuery("")}
              disabled={loading}
              className={BUTTON_SECONDARY_CLASSES}
            >
              Clear
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
