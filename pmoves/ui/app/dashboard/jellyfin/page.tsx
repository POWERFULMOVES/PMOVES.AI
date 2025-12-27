"use client";

import { useEffect, useState } from "react";
import DashboardNavigation from "../../../components/DashboardNavigation";
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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Load sync status on mount
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
    const result = await triggerJellyfinSync();
    if (result.ok) {
      await refreshSyncStatus();
    } else {
      setError(result.error);
    }
  };

  const handleBackfill = async () => {
    const result = await triggerBackfill({ limit: 50 });
    if (result.ok) {
      await refreshSyncStatus();
    } else {
      setError(result.error);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <DashboardNavigation active="jellyfin" />

      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Jellyfin Integration</h1>
        <p className="text-sm text-neutral-600">
          Manage media library synchronization and link YouTube videos to Jellyfin items.
        </p>
      </header>

      {/* Sync Status */}
      <section className="rounded border border-neutral-200 bg-white p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium">Sync Status</h2>
          <button
            onClick={refreshSyncStatus}
            className="rounded border border-neutral-300 px-3 py-1 text-sm hover:bg-neutral-50"
          >
            Refresh
          </button>
        </div>

        {syncStatus && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div className="p-3 bg-neutral-50 rounded">
              <div className="text-2xl font-bold text-blue-600">
                {syncStatus.videosLinked}
              </div>
              <div className="text-xs text-neutral-500">Videos Linked</div>
            </div>
            <div className="p-3 bg-neutral-50 rounded">
              <div className="text-2xl font-bold text-amber-600">
                {syncStatus.pendingBackfill}
              </div>
              <div className="text-xs text-neutral-500">Pending Backfill</div>
            </div>
            <div className="p-3 bg-neutral-50 rounded">
              <div className="text-2xl font-bold text-green-600">
                {syncStatus.status}
              </div>
              <div className="text-xs text-neutral-500">Status</div>
            </div>
            <div className="p-3 bg-neutral-50 rounded">
              <div className="text-2xl font-bold text-red-600">
                {syncStatus.errors}
              </div>
              <div className="text-xs text-neutral-500">Errors</div>
            </div>
          </div>
        )}

        <div className="flex gap-2 mt-4">
          <button
            onClick={handleSync}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Sync Now
          </button>
          <button
            onClick={handleBackfill}
            className="rounded border border-blue-600 px-4 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50"
          >
            Run Backfill
          </button>
        </div>
      </section>

      {/* Library Search */}
      <section className="rounded border border-neutral-200 bg-white p-4">
        <h2 className="text-lg font-medium mb-4">Library Search</h2>

        <form onSubmit={handleSearch} className="flex gap-2 mb-4">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search Jellyfin library..."
            className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !searchTerm.trim()}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {loading ? "Searching..." : "Search"}
          </button>
        </form>

        {error && (
          <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800 mb-4">
            {error}
          </div>
        )}

        {searchResults.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {searchResults.map((item) => (
              <div
                key={item.id}
                className="rounded border border-neutral-200 p-3 hover:shadow-md transition"
              >
                {item.imageUrl && (
                  <img
                    src={item.imageUrl}
                    alt={item.name}
                    className="w-full h-32 object-cover rounded mb-2"
                  />
                )}
                <h3 className="font-medium text-sm">{item.name}</h3>
                <p className="text-xs text-neutral-500">
                  {item.type}
                  {item.seriesName && ` • ${item.seriesName}`}
                </p>
                {item.youtubeId && (
                  <span className="inline-block mt-2 text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded">
                    Linked to {item.youtubeId}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
