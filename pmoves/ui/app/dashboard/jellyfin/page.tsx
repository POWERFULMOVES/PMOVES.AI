"use client";

import { useCallback, useEffect, useState } from "react";
import DashboardNavigation from "../../../components/DashboardNavigation";
import { SyncStatus } from "../../../components/jellyfin/SyncStatus";
import { JellyfinMediaBrowser } from "../../../components/jellyfin/JellyfinMediaBrowser";
import { BackfillControls } from "../../../components/jellyfin/BackfillControls";
import {
  jellyfinSyncStatus,
  jellyfinSearch,
  linkJellyfinItem,
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

  useEffect(() => {
    refreshSyncStatus();
  }, []);

  const refreshSyncStatus = async () => {
    const result = await jellyfinSyncStatus();
    if (result.ok) {
      setSyncStatus(result.data);
    }
  };

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

    // Simulate progress (in real implementation, this would come from WebSocket/polling)
    setBackfillProgress({ queued: limit, processed: 0, progress: 0 });

    const result = await triggerBackfill({ limit });
    if (result.ok) {
      await refreshSyncStatus();
      setBackfillProgress({ queued: limit, processed: limit, progress: 100 });
    } else {
      setError(result.error);
      setBackfillProgress({ queued: 0, processed: 0, progress: 0 });
    }

    setTimeout(() => {
      setBackfilling(false);
      setBackfillProgress({ queued: 0, processed: 0, progress: 0 });
    }, 1000);
  };

  const handleLinkItem = useCallback(async (item: JellyfinItem) => {
    // For now, this is a placeholder - in production would prompt for video selection
    setError(`Link feature: Select a YouTube video to link to "${item.name}"`);
  }, []);

  const handlePlaybackUrl = useCallback(async (item: JellyfinItem) => {
    // For now, this is a placeholder - would call the playback-url endpoint
    setError(`Playback URL: Feature coming soon for "${item.name}"`);
  }, []);

  return (
    <>
      <main id="main-content" tabIndex={-1} className="p-6 space-y-6">
        <DashboardNavigation active="jellyfin" />

        {/* Skip link - WCAG 2.1 SC 2.4.1 */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white rounded"
        >
          Skip to main content
        </a>

      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Jellyfin Integration</h1>
        <p className="text-sm text-neutral-600">
          Manage media library synchronization and link YouTube videos to Jellyfin items.
        </p>
      </header>

      {/* Error Display */}
      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-4 text-sm text-red-800" role="alert" aria-live="assertive">
          <div className="flex items-center justify-between">
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="text-red-600 hover:text-red-800"
              aria-label="Dismiss error"
            >
              ×
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sync Status - Full Width on mobile, 1 column on desktop */}
        <section className="lg:col-span-3">
          <SyncStatus
            status={syncStatus}
            onRefresh={refreshSyncStatus}
            onSync={handleSync}
            onBackfill={handleBackfill}
            syncing={syncing}
            backfilling={backfilling}
            error={null}
          />
        </section>

        {/* Backfill Controls */}
        <section className="lg:col-span-1">
          <BackfillControls
            onStart={(options) => handleBackfill(options.limit)}
            running={backfilling}
            progress={backfillProgress.progress}
            queued={backfillProgress.queued}
            processed={backfillProgress.processed}
          />
        </section>

        {/* Library Search */}
        <section className="lg:col-span-2 rounded border border-neutral-200 bg-white p-4">
          <h2 className="text-lg font-medium mb-4">Library Search</h2>

          <form onSubmit={handleSearch} className="flex gap-2 mb-4">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search Jellyfin library..."
              className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !searchTerm.trim()}
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Searching..." : "Search"}
            </button>
          </form>

          <JellyfinMediaBrowser
            items={searchResults}
            loading={loading}
            onLink={handleLinkItem}
            onPlaybackUrl={handlePlaybackUrl}
            error={null}
          />
        </section>
      </div>
      </main>
    </>
  );
}
