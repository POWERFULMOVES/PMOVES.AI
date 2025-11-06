"use client";

import { useEffect, useState } from "react";
import DashboardNavigation from "../../../components/DashboardNavigation";

export default function MonitorDashboardPage() {
  const statsUrl = "/api/monitor/stats";
  const [stats, setStats] = useState<any | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const res = await fetch(statsUrl, { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (active) setStats(json);
      } catch (e: any) {
        if (active) setErr(e?.message || String(e));
      }
    })();
    const t = setInterval(async () => {
      try {
        const res = await fetch(statsUrl, { cache: 'no-store' });
        if (!res.ok) return;
        const json = await res.json();
        if (active) setStats(json);
      } catch {}
    }, 5000);
    return () => { active = false; clearInterval(t); };
  }, [statsUrl]);

  return (
    <div className="p-6 space-y-6">
      <DashboardNavigation active="monitor" />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Channel Monitor</h1>
        <p className="text-sm text-neutral-600">Track YouTube channel polling and ingestion queue status.</p>
      </header>
      <div className="rounded border border-neutral-200 p-4 text-sm">
        <div className="mb-2">Stats endpoint: <a className="underline" href={statsUrl} target="_blank" rel="noreferrer">{statsUrl}</a></div>
        {err ? (
          <div className="text-red-600">Failed to fetch stats: {err}</div>
        ) : stats ? (
          <pre className="max-h-[360px] overflow-auto whitespace-pre-wrap">{JSON.stringify(stats, null, 2)}</pre>
        ) : (
          <div className="text-neutral-500">Loading…</div>
        )}
      </div>
    </div>
  );
}
