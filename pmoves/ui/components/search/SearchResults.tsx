/* ═══════════════════════════════════════════════════════════════════════════
   Search Results Component
   Displays Hi-RAG search results with source attribution and actions
   ═══════════════════════════════════════════════════════════════════════════ */

"use client";

import { useState } from "react";
import type { HiragResult, HiragSource } from "@/lib/api/hirag";

// Tailwind JIT static class lookup objects
const SOURCE_BADGE_CLASSES: Record<HiragSource, string> = {
  youtube: "bg-red-100 text-red-800",
  notebook: "bg-purple-100 text-purple-800",
  pdf: "bg-amber-100 text-amber-800",
  webpage: "bg-blue-100 text-blue-800",
  transcript: "bg-green-100 text-green-800",
  unknown: "bg-gray-100 text-gray-800",
};

const SOURCE_ICONS: Record<HiragSource, string> = {
  youtube: "📺",
  notebook: "📓",
  pdf: "📄",
  webpage: "🌐",
  transcript: "📝",
  unknown: "❓",
};

const SCORE_COLOR_CLASSES = [
  "text-green-600", // 0.9 - 1.0
  "text-green-600", // 0.8 - 0.9
  "text-lime-600",  // 0.7 - 0.8
  "text-yellow-600", // 0.6 - 0.7
  "text-orange-600", // 0.5 - 0.6
  "text-red-600",    // < 0.5
];

function getScoreColor(score: number): string {
  const index = Math.min(Math.floor(score * 5), 5);
  return SCORE_COLOR_CLASSES[Math.max(0, 5 - index)];
}

interface SearchResultsProps {
  /** Search results to display */
  results: HiragResult[];
  /** Total results available */
  total?: number;
  /** Query execution time in ms */
  queryTime?: number;
  /** Callback to export result to notebook */
  onExport?: (result: HiragResult) => void;
  /** Callback to copy content to clipboard */
  onCopy?: (content: string) => void;
  /** Whether to show verbose details */
  verbose?: boolean;
}

export function SearchResults({
  results,
  total,
  queryTime,
  onExport,
  onCopy,
  verbose = false,
}: SearchResultsProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleCopy = async (content: string, id: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
      if (onCopy) {
        onCopy(content);
      }
    } catch (error) {
      // Log but don't interrupt UX - clipboard may be unavailable in some contexts
      console.warn('Clipboard access denied:', error);
    }
  };

  if (results.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="text-4xl mb-4">🔍</div>
        <h3 className="text-lg font-medium text-neutral-700 mb-2">No results found</h3>
        <p className="text-sm text-neutral-500">
          Try adjusting your search query or filters
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Results summary */}
      <div className="flex items-center justify-between text-sm text-neutral-600">
        <div>
          Found <span className="font-medium">{total ?? results.length}</span> results
          {queryTime && (
            <span className="ml-2 text-neutral-400">
              ({queryTime.toFixed(0)}ms)
            </span>
          )}
        </div>
      </div>

      {/* Results list */}
      <div className="space-y-3">
        {results.map((result) => {
          const isExpanded = expandedIds.has(result.id);
          const scorePercent = Math.round(result.score * 100);

          return (
            <div
              key={result.id}
              className="border border-neutral-200 rounded-lg bg-white hover:shadow-md transition"
            >
              <div className="p-4">
                {/* Header: Source badge and score */}
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${SOURCE_BADGE_CLASSES[result.source]}`}
                    >
                      <span className="mr-1">{SOURCE_ICONS[result.source]}</span>
                      {result.source}
                    </span>

                    {result.metadata.title && (
                      <span className="text-sm font-medium text-neutral-800">
                        {result.metadata.title}
                      </span>
                    )}

                    {result.metadata.channel && (
                      <span className="text-xs text-neutral-500">
                        from {result.metadata.channel}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`text-sm font-mono ${getScoreColor(result.score)}`}
                      title="Relevance score"
                    >
                      {scorePercent}%
                    </span>

                    {/* Actions dropdown */}
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => toggleExpanded(result.id)}
                        className="p-1 text-neutral-400 hover:text-neutral-600 rounded hover:bg-neutral-100"
                        aria-label={isExpanded ? "Collapse" : "Expand"}
                      >
                        <svg
                          className={`w-4 h-4 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M19 9l-7 7-7-7"
                          />
                        </svg>
                      </button>

                      {onCopy && (
                        <button
                          onClick={() => handleCopy(result.content, result.id)}
                          className={`p-1 rounded hover:bg-neutral-100 ${
                            copiedId === result.id
                              ? "text-green-600"
                              : "text-neutral-400 hover:text-neutral-600"
                          }`}
                          aria-label={copiedId === result.id ? "Copied!" : "Copy to clipboard"}
                        >
                          {copiedId === result.id ? (
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M5 13l4 4L19 7"
                              />
                            </svg>
                          ) : (
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                              />
                            </svg>
                          )}
                        </button>
                      )}

                      {onExport && (
                        <button
                          onClick={() => onExport(result)}
                          className="p-1 text-neutral-400 hover:text-blue-600 rounded hover:bg-neutral-100"
                          aria-label="Export to notebook"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M12 6v6m0 0v6m0-6h6m-6 0H6"
                            />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Content preview */}
                <p
                  className={`text-sm text-neutral-700 ${
                    isExpanded ? "" : "line-clamp-2"
                  } transition-all`}
                >
                  {result.content}
                </p>

                {/* Expanded details */}
                {isExpanded && verbose && (
                  <div className="mt-3 pt-3 border-t border-neutral-100 space-y-2">
                    {/* Metadata */}
                    <div className="text-xs text-neutral-500 space-y-1">
                      {result.metadata.video_id && (
                        <div>
                          <span className="font-medium">Video ID:</span> {result.metadata.video_id}
                        </div>
                      )}
                      {result.metadata.timestamp && (
                        <div>
                          <span className="font-medium">Timestamp:</span> {result.metadata.timestamp}
                        </div>
                      )}
                      {result.metadata.url && (
                        <div>
                          <span className="font-medium">URL:</span>{" "}
                          <a
                            href={result.metadata.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:underline break-all"
                          >
                            {result.metadata.url}
                          </a>
                        </div>
                      )}
                    </div>

                    {/* Raw metadata */}
                    {Object.keys(result.metadata).filter(k => !['video_id','title','channel','timestamp','url'].includes(k)).length > 0 && (
                      <details className="text-xs">
                        <summary className="cursor-pointer text-neutral-500 hover:text-neutral-700">
                          Additional metadata
                        </summary>
                        <pre className="mt-1 p-2 bg-neutral-50 rounded overflow-auto">
                          {JSON.stringify(
                            Object.fromEntries(
                              Object.entries(result.metadata).filter(
                                ([k]) => !['video_id','title','channel','timestamp','url'].includes(k)
                              )
                            ),
                            null,
                            2
                          )}
                        </pre>
                      </details>
                    )}
                  </div>
                )}

                {/* Timestamp footer */}
                {result.metadata.timestamp && (
                  <div className="mt-2 text-xs text-neutral-400">
                    {result.metadata.timestamp}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
