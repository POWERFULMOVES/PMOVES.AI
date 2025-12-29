/**
 * @fileoverview Jellyfin Bridge API Client for PMOVES UI
 *
 * Integrates with Jellyfin media server for:
 * - Library search and browsing
 * - Video-to-media linking
 * - Playback URL generation
 * - Sync status monitoring
 *
 * @module api/jellyfin
 */

import { logError, Result, ok, err, getErrorMessage } from '../errorUtils';

/**
 * Media types in Jellyfin library.
 */
export type JellyfinMediaType =
  | 'Movie'
  | 'Episode'
  | 'Series'
  | 'Season'
  | 'Audio'
  | 'Video';

/**
 * Sync status for Jellyfin operations.
 */
export type JellyfinSyncStatus =
  | 'idle'
  | 'syncing'
  | 'completed'
  | 'failed';

/**
 * A Jellyfin library item.
 */
export interface JellyfinItem {
  /** Jellyfin item ID */
  id: string;
  /** Item name/title */
  name: string;
  /** Media type */
  type: JellyfinMediaType;
  /** Series name (if episode) */
  seriesName?: string;
  /** Season number (if episode) */
  seasonNumber?: number;
  /** Episode number (if episode) */
  episodeNumber?: string;
  /** Thumbnail image URL */
  imageUrl?: string;
  /** Year of release */
  productionYear?: number;
  /** Run time in ticks (1 tick = 100ns) */
  runTimeTicks?: number;
  /** Linked YouTube video ID (if linked) */
  youtubeId?: string;
  /** Date linked to YouTube */
  linkedAt?: string;
}

/**
 * Sync status and statistics.
 */
export interface JellyfinSyncStatusInfo {
  /** Current sync status */
  status: JellyfinSyncStatus;
  /** ISO timestamp of last sync */
  lastSync: string | null;
  /** Number of videos linked to Jellyfin items */
  videosLinked: number;
  /** Number of items pending backfill */
  pendingBackfill: number;
  /** Number of errors during sync */
  errors: number;
  /** Last error message */
  lastError?: string;
}

/**
 * Playback URL with timestamp.
 */
export interface JellyfinPlaybackUrl {
  /** Direct playback URL */
  url: string;
  /** Start position in seconds */
  startPosition?: number;
  /** URL expiration time */
  expiresAt: string;
}

/**
 * Default configuration for Jellyfin Bridge API.
 */
const JELLYFIN_BRIDGE_DEFAULT_URL = 'http://localhost:8093';
const JELLYFIN_TIMEOUT = 30000; // 30 seconds

/**
 * Resolves Jellyfin Bridge base URL from environment or default.
 */
function getJellyfinBridgeUrl(): string {
  return (
    process.env.NEXT_PUBLIC_JELLYFIN_BRIDGE_URL ||
    process.env.JELLYFIN_BRIDGE_URL ||
    JELLYFIN_BRIDGE_DEFAULT_URL
  ).replace(/\/$/, '');
}

/**
 * Searches the Jellyfin library for items.
 *
 * @param searchTerm - Search query
 * @param options - Optional filters
 * @returns Result with search results or error message
 *
 * @example
 * ```typescript
 * const result = await jellyfinSearch('tutorial video', {
 *   mediaType: 'Video',
 *   limit: 20
 * });
 * ```
 */
export async function jellyfinSearch(
  searchTerm: string,
  options: {
    /** Filter by media type */
    mediaType?: JellyfinMediaType;
    /** Maximum results to return */
    limit?: number;
  } = {}
): Promise<Result<JellyfinItem[], string>> {
  try {
    const { mediaType, limit = 50 } = options;
    const params = new URLSearchParams({
      query: searchTerm,
      limit: limit.toString(),
    });

    if (mediaType) {
      params.set('media_type', mediaType);
    }

    const response = await fetch(
      `${getJellyfinBridgeUrl()}/jellyfin/search?${params}`,
      {
        signal: AbortSignal.timeout(JELLYFIN_TIMEOUT),
      }
    );

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      logError(
        `Jellyfin search failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        { component: 'jellyfin', action: 'search', searchTerm }
      );
      return err(message);
    }

    const data = (await response.json()) as { items?: JellyfinItem[] };
    return ok(data.items ?? []);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Jellyfin search error', error, 'error', {
      component: 'jellyfin',
      action: 'search',
    });
    return err(message);
  }
}

/**
 * Gets current sync status from Jellyfin Bridge.
 *
 * @returns Result with sync status or error message
 */
export async function jellyfinSyncStatus(): Promise<
  Result<JellyfinSyncStatusInfo, string>
> {
  try {
    const response = await fetch(
      `${getJellyfinBridgeUrl()}/jellyfin/sync-status`,
      {
        signal: AbortSignal.timeout(10000),
      }
    );

    if (!response.ok) {
      return err('Failed to fetch sync status');
    }

    const data = (await response.json()) as JellyfinSyncStatusInfo;
    return ok(data);
  } catch (error) {
    logError('Jellyfin sync status error', error, 'warning', {
      component: 'jellyfin',
      action: 'sync-status',
    });
    return err('Jellyfin sync status unavailable');
  }
}

/**
 * Links a YouTube video to a Jellyfin item.
 *
 * @param videoId - YouTube video ID
 * @param jellyfinItemId - Jellyfin item ID
 * @returns Result with success confirmation or error message
 */
export async function linkJellyfinItem(
  videoId: string,
  jellyfinItemId: string
): Promise<Result<{ linked: true }, string>> {
  try {
    const response = await fetch(
      `${getJellyfinBridgeUrl()}/jellyfin/link`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video_id: videoId,
          jellyfin_item_id: jellyfinItemId,
        }),
        signal: AbortSignal.timeout(JELLYFIN_TIMEOUT),
      }
    );

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      logError(
        `Jellyfin link failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        { component: 'jellyfin', action: 'link', videoId, jellyfinItemId }
      );
      return err(message);
    }

    return ok({ linked: true });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Jellyfin link error', error, 'error', {
      component: 'jellyfin',
      action: 'link',
    });
    return err(message);
  }
}

/**
 * Generates a playback URL for a Jellyfin item with optional timestamp.
 *
 * @param jellyfinItemId - Jellyfin item ID
 * @param startPosition - Start position in seconds (optional)
 * @returns Result with playback URL or error message
 */
export async function getJellyfinPlaybackUrl(
  jellyfinItemId: string,
  startPosition?: number
): Promise<Result<JellyfinPlaybackUrl, string>> {
  try {
    const response = await fetch(
      `${getJellyfinBridgeUrl()}/jellyfin/playback-url`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_id: jellyfinItemId,
          start_position: startPosition,
        }),
        signal: AbortSignal.timeout(JELLYFIN_TIMEOUT),
      }
    );

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      return err(message);
    }

    const data = (await response.json()) as JellyfinPlaybackUrl;
    return ok(data);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Jellyfin playback URL error', error, 'error', {
      component: 'jellyfin',
      action: 'playback-url',
    });
    return err(message);
  }
}

/**
 * Triggers a manual sync of Jellyfin library.
 *
 * @returns Result with success confirmation or error message
 */
export async function triggerJellyfinSync(): Promise<
  Result<{ started: true }, string>
> {
  try {
    const response = await fetch(
      `${getJellyfinBridgeUrl()}/jellyfin/sync`,
      {
        method: 'POST',
        signal: AbortSignal.timeout(60000), // 1 minute timeout for sync
      }
    );

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      return err(message);
    }

    return ok({ started: true });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Jellyfin sync trigger error', error, 'error', {
      component: 'jellyfin',
      action: 'sync',
    });
    return err(message);
  }
}

/**
 * Triggers backfill operation for unlinked videos.
 *
 * @param options - Backfill options
 * @returns Result with success confirmation or error message
 */
export async function triggerBackfill(options: {
  /** Only backfill specific channel */
  channelId?: string;
  /** Maximum number of items to process */
  limit?: number;
}): Promise<Result<{ started: true }, string>> {
  try {
    const response = await fetch(
      `${getJellyfinBridgeUrl()}/jellyfin/backfill`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(options),
        signal: AbortSignal.timeout(120000), // 2 minute timeout for backfill
      }
    );

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      return err(message);
    }

    return ok({ started: true });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Jellyfin backfill error', error, 'error', {
      component: 'jellyfin',
      action: 'backfill',
    });
    return err(message);
  }
}
