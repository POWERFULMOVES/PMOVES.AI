"use client";

import { useEffect, useState } from "react";
import { DashboardShell } from "../../../components/DashboardNavigation";

// Monitoring service URLs (configured via NEXT_PUBLIC_* env vars for client-side access)
const GRAFANA_URL = process.env.NEXT_PUBLIC_GRAFANA_URL || 'http://localhost:3002';
const PROMETHEUS_URL = process.env.NEXT_PUBLIC_PROMETHEUS_URL || 'http://localhost:9090';
const LOKI_URL = process.env.NEXT_PUBLIC_LOKI_URL || 'http://localhost:3100';

export default function MonitorDashboardPage() {
  const statsUrl = "/api/monitor/stats";
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  useEffect(() => {
    let active = true;

    const fetchStats = async () => {
      try {
        const res = await fetch(statsUrl, { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (active) {
          setStats(json);
          setLastUpdate(new Date());
          setErr(null);
        }
      } catch (e: unknown) {
        if (active) setErr(e instanceof Error ? e.message : String(e));
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 5000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [statsUrl]);

  return (
    <DashboardShell
      title="Channel Monitor"
      subtitle="Track YouTube channel polling and ingestion queue status"
      active="monitor"
    >
      <div className="p-6 lg:p-8 space-y-6">
        {/* Status bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="tag tag-forest">
              <span className={`w-2 h-2 rounded-full ${err ? 'bg-cata-ember' : 'bg-cata-forest animate-pulse'}`} />
              {err ? 'Error' : 'Live'}
            </span>
            <a
              href={statsUrl}
              target="_blank"
              rel="noreferrer"
              className="text-xs font-mono text-ink-muted hover:text-cata-cyan transition-colors"
            >
              {statsUrl}
            </a>
          </div>
          {lastUpdate && (
            <span className="text-xs text-ink-muted font-mono">
              Updated: {lastUpdate.toLocaleTimeString()}
            </span>
          )}
        </div>

        {/* Stats panel */}
        <div className="card-brutal">
          {err ? (
            <div className="p-6">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 flex items-center justify-center bg-cata-ember/20 text-cata-ember font-display font-bold flex-shrink-0">
                  !
                </div>
                <div className="space-y-2">
                  <h3 className="font-display font-semibold text-cata-ember">Failed to fetch stats</h3>
                  <p className="text-sm text-ink-secondary">{err}</p>
                  <p className="text-xs text-ink-muted">
                    Ensure the monitor API is running and accessible.
                  </p>
                </div>
              </div>
            </div>
          ) : stats ? (
            <div className="divide-y divide-border-subtle">
              {/* Quick stats row */}
              <div className="p-6 grid grid-cols-2 md:grid-cols-4 gap-6">
                {Object.entries(stats).slice(0, 4).map(([key, value]) => (
                  <div key={key} className="space-y-1">
                    <span className="text-xs text-ink-muted uppercase tracking-wider font-mono">
                      {key.replace(/_/g, ' ')}
                    </span>
                    <div className="font-display font-bold text-2xl text-cata-cyan">
                      {typeof value === 'number' ? value.toLocaleString() : String(value)}
                    </div>
                  </div>
                ))}
              </div>

              {/* Full JSON */}
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs text-ink-muted uppercase tracking-wider">Raw Response</span>
                  <button
                    onClick={() => navigator.clipboard.writeText(JSON.stringify(stats, null, 2))}
                    className="btn-ghost text-xs"
                  >
                    Copy JSON
                  </button>
                </div>
                <pre className="p-4 bg-void font-mono text-xs text-ink-secondary overflow-auto max-h-[400px] border border-border-subtle">
                  {JSON.stringify(stats, null, 2)}
                </pre>
              </div>
            </div>
          ) : (
            <div className="p-12 flex flex-col items-center justify-center gap-4">
              <div className="w-8 h-8 border-2 border-cata-cyan border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-ink-muted">Loading stats...</span>
            </div>
          )}
        </div>

        {/* Quick links */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a
            href={GRAFANA_URL}
            target="_blank"
            rel="noreferrer"
            className="card-glass p-4 group"
          >
            <div className="flex items-center justify-between">
              <span className="font-display font-semibold text-sm group-hover:text-cata-cyan transition-colors">
                Grafana
              </span>
              <span className="font-mono text-2xs text-ink-muted">{new URL(GRAFANA_URL).port || '80'}</span>
            </div>
            <p className="text-xs text-ink-muted mt-1">Dashboard visualization</p>
          </a>

          <a
            href={PROMETHEUS_URL}
            target="_blank"
            rel="noreferrer"
            className="card-glass p-4 group"
          >
            <div className="flex items-center justify-between">
              <span className="font-display font-semibold text-sm group-hover:text-cata-cyan transition-colors">
                Prometheus
              </span>
              <span className="font-mono text-2xs text-ink-muted">{new URL(PROMETHEUS_URL).port || '80'}</span>
            </div>
            <p className="text-xs text-ink-muted mt-1">Metrics queries</p>
          </a>

          <a
            href={LOKI_URL}
            target="_blank"
            rel="noreferrer"
            className="card-glass p-4 group"
          >
            <div className="flex items-center justify-between">
              <span className="font-display font-semibold text-sm group-hover:text-cata-cyan transition-colors">
                Loki
              </span>
              <span className="font-mono text-2xs text-ink-muted">{new URL(LOKI_URL).port || '80'}</span>
            </div>
            <p className="text-xs text-ink-muted mt-1">Log aggregation</p>
          </a>
        </div>
      </div>
    </DashboardShell>
  );
}
