"use client";

import { useCallback, useEffect, useState } from "react";
import DashboardNavigation from "../../../../components/DashboardNavigation";
import { AlertBanner } from "@/components/common";

type RuntimeHealth = {
  service: string;
  endpoint: string;
  health: string;
  metrics: Record<string, number | string> | null;
  error?: string;
};

type SyncResult = {
  ok: boolean;
  error?: string;
  synced?: number;
  skipped?: number;
  failed?: number;
};

export default function NotebookRuntimePage() {
  const [runtime, setRuntime] = useState<RuntimeHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchRuntime = useCallback(async () => {
    try {
      const res = await fetch('/api/notebook/runtime', { cache: 'no-store' });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setRuntime(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSync = useCallback(async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const res = await fetch('/api/notebook/runtime/sync', {
        method: 'POST',
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || 'HTTP ' + res.status);
      }
      const data = await res.json();
      setSyncResult(data);
      if (data.ok) {
        // Refresh runtime status after sync
        fetchRuntime();
      }
    } catch (err) {
      setSyncResult({ ok: false, error: err instanceof Error ? err.message : String(err) });
    } finally {
      setSyncing(false);
    }
  }, [fetchRuntime]);

  useEffect(() => {
    fetchRuntime();

    if (autoRefresh) {
      const interval = setInterval(fetchRuntime, 10000); // Refresh every 10 seconds
      return () => clearInterval(interval);
    }
  }, [fetchRuntime, autoRefresh]);

  const healthColor = {
    healthy: 'bg-green-500',
    starting: 'bg-yellow-500',
    error: 'bg-red-500',
    unknown: 'bg-gray-400',
  }[runtime?.health === 'ok' || runtime?.health === 'healthy' ? 'healthy' : runtime?.health || 'unknown'];

  const healthText = runtime?.health === 'ok' || runtime?.health === 'healthy'
    ? 'Healthy'
    : runtime?.health || 'Unknown';

  return (
    <div className="p-6 space-y-6">
      <DashboardNavigation active="notebook-runtime" />

      <header className="space-y-2">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">Notebook Runtime</h1>
          <div className="flex items-center gap-1.5 text-xs">
            <span className={`w-2 h-2 rounded-full ${healthColor} ${runtime?.health === 'ok' || runtime?.health === 'healthy' ? 'animate-pulse' : ''}`} />
            <span className="text-neutral-500">{healthText}</span>
          </div>
        </div>
        <p className="text-sm text-neutral-600">
          Monitor the Notebook Sync service that syncs Open Notebook content to the search infrastructure.
        </p>
      </header>

      {/* Error Banner */}
      {error && (
        <AlertBanner message={error} variant="error" onDismiss={() => setError(null)} />
      )}

      {/* Sync Result Banner */}
      {syncResult && (
        <AlertBanner
          message={syncResult.ok
            ? `Sync completed: ${syncResult.synced || 0} synced, ${syncResult.skipped || 0} skipped, ${syncResult.failed || 0} failed`
            : syncResult.error || 'Sync failed'
          }
          variant={syncResult.ok ? 'success' : 'error'}
          onDismiss={() => setSyncResult(null)}
        />
      )}

      <div className="grid gap-4 md:grid-cols-3">
        {/* Service Status */}
        <div className="md:col-span-2 rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
          <h2 className="text-lg font-medium mb-4">Service Status</h2>

          {loading ? (
            <div className="text-sm text-neutral-500">Loading...</div>
          ) : runtime ? (
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-neutral-500">Service</dt>
                <dd className="font-medium">{runtime.service}</dd>
              </div>
              <div>
                <dt className="text-neutral-500">Health</dt>
                <dd className="font-medium capitalize">{runtime.health}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-neutral-500">Endpoint</dt>
                <dd className="font-mono text-xs break-all">{runtime.endpoint}</dd>
              </div>
            </dl>
          ) : (
            <div className="text-sm text-neutral-500">No runtime data available</div>
          )}

          <div className="flex items-center gap-3 mt-4 pt-4 border-t border-neutral-200">
            <button
              onClick={fetchRuntime}
              disabled={loading}
              className="rounded border border-neutral-300 px-3 py-1.5 text-sm hover:bg-neutral-50 disabled:opacity-50 transition"
            >
              Refresh
            </button>
            <label htmlFor="auto-refresh-toggle" className="flex items-center gap-2 text-sm text-neutral-600">
              <input
                id="auto-refresh-toggle"
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded"
              />
              Auto-refresh (10s)
            </label>
          </div>
        </div>

        {/* Actions */}
        <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
          <h2 className="text-lg font-medium mb-4">Actions</h2>
          <div className="space-y-2">
            <button
              onClick={handleSync}
              disabled={syncing}
              className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {syncing ? 'Syncing...' : 'Trigger Sync'}
            </button>
            <p className="text-xs text-neutral-500">
              Manually trigger a sync from Open Notebook to the search infrastructure.
            </p>
          </div>
        </div>
      </div>

      {/* Metrics */}
      {runtime?.metrics && Object.keys(runtime.metrics).length > 0 && (
        <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
          <h2 className="text-lg font-medium mb-4">Metrics</h2>
          <dl className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            {Object.entries(runtime.metrics).slice(0, 12).map(([key, value]) => (
              <div key={key} className="p-2 bg-neutral-50 rounded">
                <dt className="text-xs text-neutral-500 truncate" title={key}>{key}</dt>
                <dd className="font-medium text-lg">{typeof value === 'number' ? value.toLocaleString() : value}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {/* Links */}
      <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
        <h2 className="text-lg font-medium mb-4">Related Links</h2>
        <ul className="space-y-2 text-sm">
          <li>
            <a
              href={process.env.NEXT_PUBLIC_OPEN_NOTEBOOK_URL || 'http://localhost:8503'}
              target="_blank"
              rel="noreferrer"
              className="text-blue-600 hover:underline"
            >
              Open Notebook UI
            </a>
          </li>
          <li>
            <a
              href="/dashboard/notebook"
              className="text-blue-600 hover:underline"
            >
              Notebook Sources
            </a>
          </li>
          <li>
            <a
              href="/notebook-workbench"
              className="text-blue-600 hover:underline"
            >
              Notebook Workbench
            </a>
          </li>
        </ul>
      </div>
    </div>
  );
}
