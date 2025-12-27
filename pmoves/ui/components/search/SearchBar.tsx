/* ═══════════════════════════════════════════════════════════════════════════
   Search Bar Component
   Debounced search input with keyboard shortcuts and history
   ═══════════════════════════════════════════════════════════════════════════ */

"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import type { HiragFilters } from "@/lib/api/hirag";

// Tailwind JIT static classes
const INPUT_BASE_CLASSES = "flex-1 rounded border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition";
const INPUT_DISABLED_CLASSES = "disabled:bg-neutral-100 disabled:cursor-not-allowed";
const BUTTON_BASE_CLASSES = "rounded px-4 py-2 text-sm font-medium transition";
const BUTTON_ENABLED_CLASSES = "bg-blue-600 text-white hover:bg-blue-700";
const BUTTON_DISABLED_CLASSES = "disabled:opacity-60 disabled:cursor-not-allowed bg-blue-600 text-white";

// Search history storage key
const SEARCH_HISTORY_KEY = "pmoves_search_history";
const MAX_HISTORY_ITEMS = 10;

interface SearchHistoryItem {
  query: string;
  timestamp: number;
}

interface SearchBarProps {
  /** Callback when search is triggered */
  onSearch: (query: string, filters?: HiragFilters) => void;
  /** Currently loading state */
  loading?: boolean;
  /** Placeholder text */
  placeholder?: string;
  /** Default query value */
  defaultValue?: string;
  /** Whether filters are currently active */
  hasActiveFilters?: boolean;
  /** Callback to toggle filter panel */
  onToggleFilters?: () => void;
}

export function SearchBar({
  onSearch,
  loading = false,
  placeholder = "Search knowledge base...",
  defaultValue = "",
  hasActiveFilters = false,
  onToggleFilters,
}: SearchBarProps) {
  const [query, setQuery] = useState(defaultValue);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<SearchHistoryItem[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load search history from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(SEARCH_HISTORY_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as SearchHistoryItem[];
        setHistory(parsed.slice(0, MAX_HISTORY_ITEMS));
      }
    } catch {
      // Silently fail if localStorage is unavailable
    }
  }, []);

  // Save query to history after search
  const saveToHistory = useCallback((searchQuery: string) => {
    if (!searchQuery.trim()) return;

    const newItem: SearchHistoryItem = {
      query: searchQuery.trim(),
      timestamp: Date.now(),
    };

    setHistory((prev) => {
      const filtered = prev.filter((item) => item.query !== newItem.query);
      const updated = [newItem, ...filtered].slice(0, MAX_HISTORY_ITEMS);

      try {
        localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(updated));
      } catch {
        // Silently fail if localStorage is unavailable
      }

      return updated;
    });
  }, []);

  // Debounced search handler
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (query.trim()) {
        onSearch(query.trim());
        setShowHistory(false);
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [query, onSearch]);

  // Keyboard shortcut: Cmd+K / Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setShowHistory(true);
      }
      if (e.key === "Escape") {
        setShowHistory(false);
        inputRef.current?.blur();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      saveToHistory(query);
      onSearch(query.trim());
      setShowHistory(false);
    }
  };

  const handleHistoryClick = (item: SearchHistoryItem) => {
    setQuery(item.query);
    saveToHistory(item.query);
    onSearch(item.query);
    setShowHistory(false);
  };

  const clearHistory = () => {
    setHistory([]);
    try {
      localStorage.removeItem(SEARCH_HISTORY_KEY);
    } catch {
      // Silently fail
    }
  };

  return (
    <div className="relative">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <div className="relative flex-1">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setShowHistory(true)}
            placeholder={placeholder}
            className={`${INPUT_BASE_CLASSES} ${INPUT_DISABLED_CLASSES}`}
            disabled={loading}
            autoComplete="off"
          />

          {/* Keyboard shortcut hint */}
          {!query && (
            <kbd className="absolute right-3 top-1/2 -translate-y-1/2 hidden md:inline-flex items-center gap-1 px-2 py-0.5 text-xs text-neutral-500 bg-neutral-100 rounded border border-neutral-200 pointer-events-none">
              <span>⌘</span>K
            </kbd>
          )}

          {/* Search history dropdown */}
          {showHistory && history.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-neutral-200 rounded-md shadow-lg z-50">
              <div className="p-2 border-b border-neutral-100 flex items-center justify-between">
                <span className="text-xs font-medium text-neutral-500">Recent Searches</span>
                <button
                  type="button"
                  onClick={clearHistory}
                  className="text-xs text-blue-600 hover:text-blue-800"
                >
                  Clear
                </button>
              </div>
              <ul className="max-h-60 overflow-auto py-1">
                {history.map((item, index) => (
                  <li key={index}>
                    <button
                      type="button"
                      onClick={() => handleHistoryClick(item)}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 transition"
                    >
                      <span className="block truncate">{item.query}</span>
                      <span className="text-xs text-neutral-400">
                        {new Date(item.timestamp).toLocaleDateString()}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Filter toggle button */}
        {onToggleFilters && (
          <button
            type="button"
            onClick={onToggleFilters}
            className={`rounded border px-3 py-2 text-sm transition ${
              hasActiveFilters
                ? "bg-blue-50 border-blue-500 text-blue-700"
                : "border-neutral-300 hover:bg-neutral-50"
            }`}
            aria-label="Toggle filters"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
              />
            </svg>
          </button>
        )}

        <button
          type="submit"
          disabled={loading || !query.trim()}
          className={`${BUTTON_BASE_CLASSES} ${BUTTON_ENABLED_CLASSES} ${BUTTON_DISABLED_CLASSES}`}
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Searching...
            </span>
          ) : (
            "Search"
          )}
        </button>
      </form>
    </div>
  );
}
