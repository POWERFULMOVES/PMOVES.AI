/* ═══════════════════════════════════════════════════════════════════════════
   Sync Status Component
   Displays Jellyfin sync status with controls and real-time updates
   ═══════════════════════════════════════════════════════════════════════════ */

"use client";

import { useCallback, useEffect, useState } from "react";
import type { JellyfinSyncStatusInfo } from "@/lib/api/jellyfin";
import { formatTimeAgo } from "@/lib/timeUtils";
import { AlertBanner } from "@/components/common";

// Tailwind JIT static class lookup objects
const STAT_CARD_CLASSES = "p-3 bg-neutral-50 rounded min-w-0";
const STAT_VALUE_CLASSES = "text-2xl font-bold truncate";
const STAT_LABEL_CLASSES = "text-xs text-neutral-500";

const STAT_COLORS: Record<keyof Pick<JellyfinSyncStatusInfo, "videosLinked" | "pendingBackfill" | "status" | "errors">, string> = {
  videosLinked: "text-blue-600",
  pendingBackfill: "text-amber-600",
  status: "text-green-600",
  errors: "text-red-600",
};

interface SyncStatusProps {
  /** Current sync status */
  status: JellyfinSyncStatusInfo | null;
  /** Callback to refresh status */
  onRefresh: () => void;
  /** Callback to trigger sync */
  onSync: () => void;
  /** Callback to trigger backfill */
  onBackfill: (limit?: number) => void;
  /** Whether sync is in progress */
  syncing?: boolean;
  /** Whether backfill is in progress */
  backfilling?: boolean;
  /** Sync error message */
  error?: string | null;
}

export function SyncStatus({
  status,
  onRefresh,
  onSync,
  onBackfill,
  syncing = false,
  backfilling = false,
  error,
}: SyncStatusProps) {
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

  useEffect(() => {
    setLastRefreshed(new Date());
  }, [status]);

  const handleSync = useCallback(async () => {
    onSync();
  }, [onSync]);

  const handleBackfill = useCallback(() => {
    onBackfill(50);
  }, [onBackfill]);

  const hasErrors = status && status.errors > 0;
  const isHealthy = status && (status.status === "idle" || status.status === "completed");

  return (
    <div className="rounded border border-neutral-200 bg-white p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-medium">Sync Status</h2>
          {isHealthy && (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-neutral-500">
            Last: {formatTimeAgo(status?.lastSync ?? null)}
          </span>
          <button
            onClick={onRefresh}
            disabled={syncing || backfilling}
            className="rounded border border-neutral-300 px-3 py-1 text-sm hover:bg-neutral-50 disabled:opacity-50 transition"
            aria-label="Refresh sync status"
          >
            Refresh
          </button>
        </div>
      </div>

      {status && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            {/* Videos Linked */}
            <div className={STAT_CARD_CLASSES}>
              <div className={`${STAT_VALUE_CLASSES} ${STAT_COLORS.videosLinked}`}>
                {status.videosLinked}
              </div>
              <div className={STAT_LABEL_CLASSES}>Videos Linked</div>
            </div>

            {/* Pending Backfill */}
            <div className={STAT_CARD_CLASSES}>
              <div className={`${STAT_VALUE_CLASSES} ${STAT_COLORS.pendingBackfill}`}>
                {status.pendingBackfill}
              </div>
              <div className={STAT_LABEL_CLASSES}>Pending Backfill</div>
            </div>

            {/* Status */}
            <div className={STAT_CARD_CLASSES}>
              <div className={`${STAT_VALUE_CLASSES} ${STAT_COLORS.status}`}>
                {status.status}
              </div>
              <div className={STAT_LABEL_CLASSES}>Status</div>
            </div>

            {/* Errors */}
            <div className={STAT_CARD_CLASSES}>
              <div className={`${STAT_VALUE_CLASSES} ${STAT_COLORS.errors} ${hasErrors ? "animate-pulse" : ""}`}>
                {status.errors}
              </div>
              <div className={STAT_LABEL_CLASSES}>Errors</div>
            </div>
          </div>

          {/* Error details */}
          {hasErrors && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded">
              <div className="text-sm text-red-800">
                ⚠️ {status.errors} error(s) detected. Check logs for details.
              </div>
            </div>
          )}

          {/* Sync error */}
          {error && (
            <div className="mt-4">
              <AlertBanner message={error} variant="error" />
            </div>
          )}

          {/* Action buttons */}
          <div className="flex flex-wrap gap-2 mt-4">
            <button
              onClick={handleSync}
              disabled={syncing}
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center gap-2"
            >
              {syncing ? (
                <>
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Syncing...
                </>
              ) : (
                "Sync Now"
              )}
            </button>

            <button
              onClick={handleBackfill}
              disabled={backfilling}
              className="rounded border border-blue-600 px-4 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center gap-2"
            >
              {backfilling ? (
                <>
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Backfilling...
                </>
              ) : (
                "Run Backfill"
              )}
            </button>

            {status.pendingBackfill > 0 && (
              <span className="text-xs text-neutral-500 self-center">
                {status.pendingBackfill} items pending
              </span>
            )}
          </div>
        </>
      )}

      {!status && (
        <div className="text-center py-8 text-sm text-neutral-500">
          No sync status available. Click Refresh to check.
        </div>
      )}
    </div>
  );
}
