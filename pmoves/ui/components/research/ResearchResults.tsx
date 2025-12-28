/* ═══════════════════════════════════════════════════════════════════════════
   Research Results Component
   Displays detailed research results with sources and actions
   ═══════════════════════════════════════════════════════════════════════════ */

"use client";

import { useState } from "react";
import type { ResearchResult } from "@/lib/api/research";

// Tailwind JIT static class lookup objects
const SECTION_CLASSES = "border-t pt-4 space-y-4";
const NOTE_CLASSES = "text-sm bg-neutral-50 rounded p-2";
const SOURCE_LINK_CLASSES = "text-sm text-blue-600 hover:underline";

interface ResearchResultsProps {
  /** Research result to display */
  result: ResearchResult;
  /** Callback to publish to notebook */
  onPublish?: (notebookId?: string) => void;
  /** Callback to copy content */
  onCopy?: () => void;
  /** Whether publish is in progress */
  publishing?: boolean;
}

export function ResearchResults({
  result,
  onPublish,
  onCopy,
  publishing = false,
}: ResearchResultsProps) {
  const [expandedNotes, setExpandedNotes] = useState(true);
  const [expandedSources, setExpandedSources] = useState(true);
  const [copiedSection, setCopiedSection] = useState<string | null>(null);

  const handleCopy = (content: string, section: string) => {
    navigator.clipboard.writeText(content)
      .then(() => {
        setCopiedSection(section);
        setTimeout(() => setCopiedSection(null), 2000);
        if (onCopy) onCopy();
      })
      .catch((err) => {
        console.error('Failed to copy to clipboard:', err);
        // Optionally show user-facing error feedback
      });
  };

  const formatDuration = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div>
        <h3 className="font-medium mb-2">Research Summary</h3>
        <div className="bg-neutral-50 rounded p-4">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{result.summary}</p>
          <button
            onClick={() => handleCopy(result.summary, "summary")}
            className="mt-2 text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            {copiedSection === "summary" ? "Copied!" : "Copy summary"}
          </button>
        </div>
      </div>

      {/* Notes */}
      {result.notes.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-medium">Notes ({result.notes.length})</h3>
            <button
              onClick={() => setExpandedNotes(!expandedNotes)}
              className="text-xs text-blue-600 hover:text-blue-800"
            >
              {expandedNotes ? "Collapse" : "Expand"}
            </button>
          </div>
          {expandedNotes && (
            <ul className="space-y-2">
              {result.notes.map((note, index) => (
                <li key={index} className={NOTE_CLASSES}>
                  <p className="text-sm">{note}</p>
                  <button
                    onClick={() => handleCopy(note, `note-${index}`)}
                    className="mt-1 text-xs text-neutral-500 hover:text-blue-600"
                  >
                    {copiedSection === `note-${index}` ? "Copied!" : "Copy"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Sources */}
      {result.sources.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-medium">Sources ({result.sources.length})</h3>
            <button
              onClick={() => setExpandedSources(!expandedSources)}
              className="text-xs text-blue-600 hover:text-blue-800"
            >
              {expandedSources ? "Collapse" : "Expand"}
            </button>
          </div>
          {expandedSources && (
            <ul className="space-y-1">
              {result.sources.map((source, index) => (
                <li key={index}>
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noreferrer"
                    className={SOURCE_LINK_CLASSES}
                  >
                    <span className="line-clamp-1">{source.title}</span>
                  </a>
                  {source.snippet && (
                    <p className="text-xs text-neutral-500 mt-1 line-clamp-2">{source.snippet}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Metadata */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <div>
          <span className="text-neutral-500">Iterations:</span>{" "}
          <span className="font-medium">{result.iterations}</span>
        </div>
        <div>
          <span className="text-neutral-500">Duration:</span>{" "}
          <span className="font-medium">{formatDuration(result.duration)}</span>
        </div>
        <div>
          <span className="text-neutral-500">Completed:</span>{" "}
          <span className="font-medium">{new Date(result.completedAt).toLocaleString()}</span>
        </div>
        <div className={result.sources.length > 0 ? "" : "col-span-2"}>
          <span className="text-neutral-500">Sources:</span>{" "}
          <span className="font-medium">{result.sources.length}</span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        {onPublish && (
          <button
            onClick={() => onPublish()}
            disabled={publishing}
            className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {publishing ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Publishing...
              </span>
            ) : (
              "Publish to Notebook"
            )}
          </button>
        )}
      </div>
    </div>
  );
}
