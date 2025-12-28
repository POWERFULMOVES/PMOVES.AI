"use client";

import { useEffect, useState, useCallback } from "react";
import DashboardNavigation from "../../../components/DashboardNavigation";
import { SearchBar } from "../../../components/search/SearchBar";
import { SearchResults } from "../../../components/search/SearchResults";
import { SearchFilters } from "../../../components/search/SearchFilters";
import { hiragQuery, hiragHealth, exportToNotebook } from "../../../lib/api/hirag";
import type { HiragResult, HiragFilters } from "../../../lib/api/hirag";

export default function SearchDashboardPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<HiragResult[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [queryTime, setQueryTime] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [healthy, setHealthy] = useState(false);
  const [filters, setFilters] = useState<HiragFilters>({});
  const [showFilters, setShowFilters] = useState(false);
  const [copiedNotification, setCopiedNotification] = useState<string | null>(null);

  useEffect(() => {
    // Check Hi-RAG health on mount
    hiragHealth()
      .then((result) => {
        if (result.ok) {
          setHealthy(result.data.healthy);
        }
      })
      .catch(() => {
        setHealthy(false);
      });
  }, []);

  const handleSearch = useCallback(async (searchQuery: string, searchFilters?: HiragFilters) => {
    if (!searchQuery.trim()) return;

    setLoading(true);
    setError(null);
    setQuery(searchQuery);

    const result = await hiragQuery(searchQuery, {
      topK: 20,
      rerank: true,
      filters: searchFilters || filters,
    });

    if (result.ok) {
      setResults(result.data.results);
      setTotal(result.data.total);
      setQueryTime(result.data.queryTime);
    } else {
      setError(result.error);
      setResults([]);
      setTotal(0);
    }

    setLoading(false);
  }, [filters]);

  const handleExport = useCallback(async (result: HiragResult) => {
    // For now, just show a notification
    // In production, this would prompt for notebook selection
    const exportResult = await exportToNotebook([result], "default");
    if (exportResult.ok) {
      setCopiedNotification("Exported to notebook");
      setTimeout(() => setCopiedNotification(null), 2000);
    }
  }, []);

  const handleCopy = useCallback((content: string) => {
    setCopiedNotification("Copied to clipboard");
    setTimeout(() => setCopiedNotification(null), 2000);
  }, []);

  const hasActiveFilters = Object.keys(filters).some(
    (key) => filters[key as keyof HiragFilters] !== undefined
  );

  return (
    <div className="p-6 space-y-6">
      <DashboardNavigation active="search" />

      {/* Skip link - WCAG 2.1 SC 2.4.1 */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white rounded"
      >
        Skip to main content
      </a>

      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Knowledge Search</h1>
        <p className="text-sm text-neutral-600">
          Search across all PMOVES knowledge sources using Hi-RAG hybrid retrieval.
          Combines vector search (Qdrant), graph traversal (Neo4j), and full-text search (Meilisearch).
        </p>
        <div className="flex items-center gap-2 text-xs">
          <span
            className={`px-2 py-1 rounded ${
              healthy
                ? "bg-green-100 text-green-800"
                : "bg-red-100 text-red-800"
            }`}
          >
            Hi-RAG v2: {healthy ? "Connected" : "Disconnected"}
          </span>
          <kbd className="hidden md:inline-flex items-center gap-1 px-2 py-0.5 text-neutral-500 bg-neutral-100 rounded border border-neutral-200">
            <span>⌘</span>K to focus
          </kbd>
        </div>
      </header>

      {/* Search Bar */}
      <SearchBar
        onSearch={handleSearch}
        loading={loading}
        placeholder="Search knowledge base..."
        defaultValue={query}
        hasActiveFilters={hasActiveFilters}
        onToggleFilters={() => setShowFilters(!showFilters)}
      />

      {/* Error Display */}
      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-4 text-sm text-red-800" role="alert" aria-live="assertive">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Copy/Export Notification */}
      {copiedNotification && (
        <div className="fixed bottom-4 right-4 bg-neutral-800 text-white px-4 py-2 rounded-lg shadow-lg text-sm animate-fade-in">
          {copiedNotification}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Filters Sidebar */}
        {showFilters && (
          <aside className="lg:col-span-1">
            <SearchFilters
              filters={filters}
              onChange={setFilters}
              isOpen={showFilters}
              onToggle={() => setShowFilters(false)}
            />
          </aside>
        )}

        {/* Results Area - Skip link target for WCAG 2.1 SC 2.4.1 */}
        <main id="main-content" tabIndex={-1} className={showFilters ? "lg:col-span-3" : "lg:col-span-4"}>
          {!query && !loading && (
            <div className="rounded border border-dashed border-neutral-300 p-12 text-center text-sm text-neutral-500">
              <div className="text-4xl mb-4">🔍</div>
              <p className="font-medium mb-2">Search the PMOVES knowledge base</p>
              <p>Enter a query above to search across videos, notebooks, PDFs, and more.</p>
            </div>
          )}

          {query && (
            <SearchResults
              results={results}
              total={total}
              queryTime={queryTime}
              onExport={handleExport}
              onCopy={handleCopy}
              verbose
            />
          )}
        </main>
      </div>
    </div>
  );
}
