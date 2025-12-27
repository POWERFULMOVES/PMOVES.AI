"use client";

import { useEffect, useState } from "react";
import DashboardNavigation from "../../../components/DashboardNavigation";
import { hiragQuery, hiragHealth } from "../../../lib/api/hirag";
import type { HiragResult } from "../../../lib/api/hirag";

export default function SearchDashboardPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<HiragResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [healthy, setHealthy] = useState(false);

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

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);

    const result = await hiragQuery(query, {
      topK: 10,
      rerank: true,
    });

    if (result.ok) {
      setResults(result.data.results);
    } else {
      setError(result.error);
      setResults([]);
    }

    setLoading(false);
  };

  return (
    <div className="p-6 space-y-6">
      <DashboardNavigation active="search" />

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
        </div>
      </header>

      <form onSubmit={handleSearch} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search knowledge base..."
          className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-4 text-sm text-red-800">
          {error}
        </div>
      )}

      {results.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-medium">
            Found {results.length} results
          </h2>
          <div className="space-y-3">
            {results.map((result, index) => (
              <div
                key={`${result.id}-${index}`}
                className="rounded border border-neutral-200 bg-white p-4"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <p className="text-sm text-neutral-800">
                      {result.content}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-neutral-500">
                      <span className="rounded bg-neutral-100 px-2 py-0.5">
                        {result.source}
                      </span>
                      <span>Score: {(result.score * 100).toFixed(1)}%</span>
                      {result.metadata.title && (
                        <span>📄 {result.metadata.title}</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {results.length === 0 && !loading && !error && query && (
        <div className="rounded border border-dashed border-neutral-300 p-8 text-center text-sm text-neutral-500">
          No results found. Try a different search query.
        </div>
      )}

      {!query && (
        <div className="rounded border border-dashed border-neutral-300 p-8 text-center text-sm text-neutral-500">
          Enter a search query to search the PMOVES knowledge base.
        </div>
      )}
    </div>
  );
}
