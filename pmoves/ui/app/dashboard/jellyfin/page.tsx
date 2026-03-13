"use client";

import { useCallback, useEffect, useState } from "react";
import DashboardNavigation from "../../../components/DashboardNavigation";
import { SyncStatus } from "../../../components/jellyfin/SyncStatus";
import { JellyfinMediaBrowser } from "../../../components/jellyfin/JellyfinMediaBrowser";
import { BackfillControls } from "../../../components/jellyfin/BackfillControls";
import {
  jellyfinSyncStatus,
  jellyfinSearch,
  triggerJellyfinSync,
  triggerBackfill,
} from "../../../lib/api/jellyfin";
import type { JellyfinItem, JellyfinSyncStatusInfo } from "../../../lib/api/jellyfin";

export default function JellyfinDashboardPage() {
  const [syncStatus, setSyncStatus] = useState<JellyfinSyncStatusInfo | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<JellyfinItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [backfilling, setBackfilling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backfillProgress, setBackfillProgress] = useState({ queued: 0, processed: 0, progress: 0 });

  const refreshSyncStatus = useCallback(async () => {
    const result = await jellyfinSyncStatus();
    if (result.ok) {
      setSyncStatus(result.data);
    }
  }, []);

  // Initial load - fetch sync status on mount
  useEffect(() => {
    const loadInitialStatus = async () => {
      const result = await jellyfinSyncStatus();
      if (result.ok) {
        setSyncStatus(result.data);
      }
    };
    loadInitialStatus();
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchTerm.trim()) return;

    setLoading(true);
    setError(null);

    const result = await jellyfinSearch(searchTerm);
    if (result.ok) {
      setSearchResults(result.data);
    } else {
      setError(result.error);
      setSearchResults([]);
    }

    setLoading(false);
  };

  const handleSync = async () => {
    setSyncing(true);
    setError(null);

    const result = await triggerJellyfinSync();
    if (result.ok) {
      await refreshSyncStatus();
    } else {
      setError(result.error);
    }

    setSyncing(false);
  };

  const handleBackfill = async (limit = 50) => {
    setBackfilling(true);
    setError(null);

    const result = await triggerBackfill(limit);
    if (result.ok) {
      setBackfillProgress(result.data.progress);
      await refreshSyncStatus();
    } else {
      setError(result.error);
    }

    setBackfilling(false);
  };

  return (
    <>
      {/* Skip link target - WCAG 2.1 SC 2.4.1 Bypass Blocks */}
      <main id="main-content" tabIndex={-1} className="p-6 space-y-6">
        <DashboardNavigation active="jellyfin" />

        <header className="space-y-2">
          <h1 className="text-2xl font-semibold">Jellyfin Integration</h1>
          <p className="text-sm text-neutral-600">
            Link and sync media from your Jellyfin server.
          </p>
        </header>

        {/* Sync Status Component */}
        <SyncStatus
          status={syncStatus}
          onRefresh={refreshSyncStatus}
          onSync={handleSync}
          onBackfill={handleBackfill}
          syncing={syncing}
          backfilling={backfilling}
          error={error}
        />

        {/* Search */}
        <div className="rounded border border-neutral-200 bg-white p-4">
          <h2 className="text-lg font-medium mb-4">Search Library</h2>
          <form onSubmit={handleSearch} className="flex gap-2">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search for movies, shows, episodes..."
              className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !searchTerm.trim()}
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {loading ? "Searching..." : "Search"}
            </button>
          </form>

          {/* Search Results */}
          {searchResults.length > 0 && (
            <div className="mt-4 space-y-2">
              <h3 className="text-sm font-medium text-neutral-600">Results ({searchResults.length})</h3>
              {searchResults.map((item) => (
                <div
                  key={item.Id}
                  className="flex items-center justify-between rounded border border-neutral-200 p-3 hover:bg-neutral-50 transition"
                >
                  <div className="flex-1">
                    <p className="font-medium">{item.Name}</p>
                    <p className="text-sm text-neutral-500">{item.Type} • {item.ProductionYear}</p>
                  </div>
                  <button
                    onClick={() => console.log("Link item:", item.Id)}
                    className="rounded bg-green-600 px-3 py-1 text-sm text-white hover:bg-green-700 transition"
                  >
                    Link
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Media Browser */}
        <JellyfinMediaBrowser items={searchResults} />
      </main>
    </>
  );
}
