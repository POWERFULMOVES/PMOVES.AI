/* ═══════════════════════════════════════════════════════════════════════════
   Jellyfin Media Browser Component
   Search and browse Jellyfin library with link management
   ═══════════════════════════════════════════════════════════════════════════ */

"use client";

import { useState } from "react";
import type { JellyfinItem } from "@/lib/api/jellyfin";

// Tailwind JIT static class lookup objects
const CARD_CLASSES = "rounded border border-neutral-200 p-3 hover:shadow-md transition bg-white";
const IMAGE_PLACEHOLDER_CLASSES = "w-full h-32 object-cover rounded mb-2 bg-neutral-200 flex items-center justify-center text-neutral-400";

interface JellyfinMediaBrowserProps {
  /** Search results to display */
  items: JellyfinItem[];
  /** Whether search is in progress */
  loading?: boolean;
  /** Callback to link a video to this item */
  onLink?: (item: JellyfinItem) => void;
  /** Callback to generate playback URL */
  onPlaybackUrl?: (item: JellyfinItem, timestamp?: number) => void;
  /** Error message */
  error?: string | null;
}

export function JellyfinMediaBrowser({
  items,
  loading = false,
  onLink,
  onPlaybackUrl,
  error,
}: JellyfinMediaBrowserProps) {
  const [selectedItem, setSelectedItem] = useState<JellyfinItem | null>(null);

  const handleLink = (item: JellyfinItem, e: React.MouseEvent) => {
    e.stopPropagation();
    if (onLink) {
      onLink(item);
    }
  };

  const handlePlaybackUrl = (item: JellyfinItem, e: React.MouseEvent) => {
    e.stopPropagation();
    if (onPlaybackUrl) {
      onPlaybackUrl(item);
    }
  };

  const getItemTypeBadge = (type: string) => {
    const badges: Record<string, string> = {
      Movie: "bg-purple-100 text-purple-800",
      Series: "bg-blue-100 text-blue-800",
      Episode: "bg-green-100 text-green-800",
      Season: "bg-amber-100 text-amber-800",
    };
    return badges[type] || "bg-gray-100 text-gray-800";
  };

  if (error) {
    return (
      <div className="rounded border border-red-300 bg-red-50 p-4 text-sm text-red-800" role="alert">
        {error}
      </div>
    );
  }

  if (items.length === 0 && !loading) {
    return (
      <div className="rounded border border-dashed border-neutral-300 p-12 text-center text-sm text-neutral-500">
        <div className="text-4xl mb-4">🎬</div>
        <p className="font-medium mb-2">No items found</p>
        <p>Try a different search term or sync your Jellyfin library.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Results count */}
      {items.length > 0 && (
        <div className="text-sm text-neutral-600">
          Found {items.length} item{items.length !== 1 ? "s" : ""}
        </div>
      )}

      {/* Loading indicator */}
      {loading && (
        <div className="flex justify-center py-8">
          <div className="flex items-center gap-2 text-neutral-500">
            <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            Searching library...
          </div>
        </div>
      )}

      {/* Media grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((item) => (
          <div
            key={item.id}
            className={`${CARD_CLASSES} ${selectedItem?.id === item.id ? "ring-2 ring-blue-500" : ""}`}
            onClick={() => setSelectedItem(item)}
          >
            {/* Thumbnail */}
            {item.imageUrl ? (
              <img
                src={item.imageUrl}
                alt={item.name}
                className="w-full h-32 object-cover rounded mb-2"
                loading="lazy"
              />
            ) : (
              <div className={IMAGE_PLACEHOLDER_CLASSES}>
                <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
                </svg>
              </div>
            )}

            {/* Title and type */}
            <h3 className="font-medium text-sm line-clamp-2">{item.name}</h3>
            <p className="text-xs text-neutral-500 mt-1">
              <span className={`inline-block px-2 py-0.5 rounded ${getItemTypeBadge(item.type)}`}>
                {item.type}
              </span>
              {item.seriesName && (
                <span className="ml-2">{item.seriesName}</span>
              )}
              {item.seasonNumber !== undefined && (
                <span className="ml-2">S{item.seasonNumber}</span>
              )}
              {item.episodeNumber !== undefined && (
                <span className="ml-2">E{item.episodeNumber}</span>
              )}
            </p>

            {/* YouTube link status */}
            {item.youtubeId && (
              <div className="mt-2 flex items-center gap-1">
                <span className="inline-block text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded">
                  ✓ Linked to {item.youtubeId}
                </span>
              </div>
            )}

            {/* Actions */}
            <div className="mt-3 flex gap-2">
              {!item.youtubeId && onLink && (
                <button
                  onClick={(e) => handleLink(item, e)}
                  className="flex-1 text-xs bg-blue-600 text-white px-2 py-1.5 rounded hover:bg-blue-700 transition"
                >
                  Link Video
                </button>
              )}
              {onPlaybackUrl && (
                <button
                  onClick={(e) => handlePlaybackUrl(item, e)}
                  className="flex-1 text-xs border border-neutral-300 px-2 py-1.5 rounded hover:bg-neutral-50 transition"
                >
                  Playback URL
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Selected item details */}
      {selectedItem && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-neutral-200 p-4 shadow-lg md:relative md:shadow-none md:border-t-0 md:p-0">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-start justify-between">
              <div>
                <h4 className="font-medium">{selectedItem.name}</h4>
                <p className="text-sm text-neutral-500">
                  {selectedItem.type} • {selectedItem.id}
                </p>
                {selectedItem.productionYear && (
                  <p className="text-xs text-neutral-400">Year: {selectedItem.productionYear}</p>
                )}
              </div>
              <button
                onClick={() => setSelectedItem(null)}
                className="text-neutral-400 hover:text-neutral-600"
                aria-label="Close details"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
