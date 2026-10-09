import React, { useCallback, useEffect, useState } from 'react';
import './App.css';

const formatMs = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  const numeric = Number(value);
  if (numeric >= 1000) {
    return `${(numeric / 1000).toFixed(2)} s`;
  }
  return `${numeric.toFixed(1)} ms`;
};

const formatTimestamp = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString();
};

const LogPanel = ({ title, state }) => (
  <div className="log-panel">
    <h3>{title}</h3>
    {state.loading && <p>Loading…</p>}
    {state.error && <p className="error">{state.error}</p>}
    {!state.loading && !state.error && state.entries.length === 0 && (
      <p>No log entries available.</p>
    )}
    {!state.loading && !state.error && state.entries.length > 0 && (
      <pre className="log-output">{state.entries.join('\n')}</pre>
    )}
    {!state.loading && !state.error && state.source && (
      <p className="meta">Source: {state.source}</p>
    )}
  </div>
);

function App() {
  const [analyticsState, setAnalyticsState] = useState({ data: null, loading: true, error: null });
  const [migrationState, setMigrationState] = useState({ data: null, loading: true, error: null });
  const [bridgeLogsState, setBridgeLogsState] = useState({ entries: [], source: null, loading: true, error: null });
  const [publisherLogsState, setPublisherLogsState] = useState({ entries: [], source: null, loading: true, error: null });
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  const loadAnalytics = useCallback(async () => {
    setAnalyticsState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const response = await fetch('/api/analytics');
      if (!response.ok) {
        throw new Error('Failed to fetch analytics');
      }
      const data = await response.json();
      setAnalyticsState({ data, loading: false, error: null });
    } catch (error) {
      setAnalyticsState({ data: null, loading: false, error: error.message || 'Unable to load analytics' });
    }
  }, []);

  const loadMigration = useCallback(async () => {
    setMigrationState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const response = await fetch('/api/migrations/latest');
      if (!response.ok) {
        throw new Error('Failed to fetch migration status');
      }
      const data = await response.json();
      setMigrationState({ data, loading: false, error: null });
    } catch (error) {
      setMigrationState({ data: null, loading: false, error: error.message || 'Unable to load migration status' });
    }
  }, []);

  const loadBridgeLogs = useCallback(async () => {
    setBridgeLogsState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const response = await fetch('/api/logs/bridge?lines=120');
      if (!response.ok) {
        throw new Error('Failed to fetch bridge logs');
      }
      const data = await response.json();
      setBridgeLogsState({
        entries: data.entries || [],
        source: data.source || null,
        loading: false,
        error: null
      });
    } catch (error) {
      setBridgeLogsState({ entries: [], source: null, loading: false, error: error.message || 'Unable to load bridge logs' });
    }
  }, []);

  const loadPublisherLogs = useCallback(async () => {
    setPublisherLogsState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const response = await fetch('/api/logs/publisher?lines=120');
      if (!response.ok) {
        throw new Error('Failed to fetch publisher logs');
      }
      const data = await response.json();
      setPublisherLogsState({
        entries: data.entries || [],
        source: data.source || null,
        loading: false,
        error: null
      });
    } catch (error) {
      setPublisherLogsState({ entries: [], source: null, loading: false, error: error.message || 'Unable to load publisher logs' });
    }
  }, []);

  const refreshAll = useCallback(async () => {
    setRefreshing(true);
    await Promise.allSettled([
      loadAnalytics(),
      loadMigration(),
      loadBridgeLogs(),
      loadPublisherLogs()
    ]);
    setLastUpdated(new Date().toISOString());
    setRefreshing(false);
  }, [loadAnalytics, loadMigration, loadBridgeLogs, loadPublisherLogs]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  const checklist = migrationState.data?.checklist || [];
  const latency = migrationState.data?.webhookLatency || null;

  return (
    <div className="App">
      <header className="App-header">
        <h1>Media Analysis Dashboard</h1>
        <div className="toolbar">
          <button className="refresh-button" onClick={refreshAll} disabled={refreshing}>
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
          {lastUpdated && (
            <span className="timestamp">Last updated: {formatTimestamp(lastUpdated)}</span>
          )}
        </div>
      </header>
      <main className="App-main">
        <div className="dashboard-grid">
          <section className="card">
            <h2>Migration Checklist</h2>
            {migrationState.loading && <p>Loading…</p>}
            {migrationState.error && <p className="error">{migrationState.error}</p>}
            {!migrationState.loading && !migrationState.error && checklist.length === 0 && (
              <p>No checklist items reported yet.</p>
            )}
            {!migrationState.loading && !migrationState.error && checklist.length > 0 && (
              <ul className="checklist">
                {checklist.map((item) => (
                  <li key={item.id} className={`checklist-item ${item.completed ? 'completed' : ''}`}>
                    <span className="status" aria-hidden="true" />
                    <div>
                      <div className="label">{item.label}</div>
                      {item.detail && <div className="detail">{item.detail}</div>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card">
            <h2>Webhook Latency</h2>
            {migrationState.loading && <p>Loading…</p>}
            {migrationState.error && <p className="error">{migrationState.error}</p>}
            {!migrationState.loading && !migrationState.error && !latency && (
              <p>No webhook telemetry provided.</p>
            )}
            {!migrationState.loading && !migrationState.error && latency && (
              <div className="latency-metric">
                <div>
                  <span className="latency-label">Average</span>
                  <span className="latency-value">{formatMs(latency.averageMs ?? latency.avgMs ?? latency.meanMs)}</span>
                </div>
                {(latency.p95Ms || latency.p95) && (
                  <div>
                    <span className="latency-label">p95</span>
                    <span className="latency-value">{formatMs(latency.p95Ms ?? latency.p95)}</span>
                  </div>
                )}
                {(latency.p99Ms || latency.p99) && (
                  <div>
                    <span className="latency-label">p99</span>
                    <span className="latency-value">{formatMs(latency.p99Ms ?? latency.p99)}</span>
                  </div>
                )}
                {(latency.sampleSize || latency.samples || latency.count) && (
                  <div className="latency-footnote">Sample size: {latency.sampleSize ?? latency.samples ?? latency.count}</div>
                )}
                {latency.lastEventAt && (
                  <div className="latency-footnote">Last webhook: {formatTimestamp(latency.lastEventAt)}</div>
                )}
              </div>
            )}
          </section>

          <section className="card wide">
            <h2>Log Viewer</h2>
            <div className="log-grid">
              <LogPanel title="Jellyfin Bridge" state={bridgeLogsState} />
              <LogPanel title="Publisher" state={publisherLogsState} />
            </div>
          </section>

          <section className="card wide">
            <h2>Analytics Snapshot</h2>
            {analyticsState.loading && <p>Loading…</p>}
            {analyticsState.error && <p className="error">{analyticsState.error}</p>}
            {!analyticsState.loading && !analyticsState.error && analyticsState.data && (
              <pre className="analytics-pre">{JSON.stringify(analyticsState.data, null, 2)}</pre>
            )}
            {!analyticsState.loading && !analyticsState.error && !analyticsState.data && (
              <p>No analytics data reported.</p>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}

export default App;
