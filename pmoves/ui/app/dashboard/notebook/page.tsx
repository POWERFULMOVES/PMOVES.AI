"use client";

import { useEffect, useState } from "react";
import DashboardNavigation from "../../../components/DashboardNavigation";

export default function NotebookDashboardPage() {
  const nbUrl = process.env.NEXT_PUBLIC_OPEN_NOTEBOOK_URL || "http://localhost:8503";
  const [items, setItems] = useState<any[]>([]);
  const [endpoint, setEndpoint] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const res = await fetch('/api/notebook/sources', { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const j = await res.json();
        if (!active) return;
        setItems(Array.isArray(j.items) ? j.items : []);
        setEndpoint(j.endpoint || null);
      } catch (e: any) {
        if (active) setErr(e?.message || String(e));
      }
    })();
    return () => { active = false; };
  }, []);

  return (
    <div className="p-6 space-y-6">
      <DashboardNavigation active="notebook" />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Open Notebook</h1>
        <p className="text-sm text-neutral-600">Recent sources from the Notebook API and a link to the full UI.</p>
      </header>
      <div className="rounded border border-neutral-200 p-4 text-sm">
        <div className="mb-2">Notebook UI: <a className="underline" href={nbUrl} target="_blank" rel="noreferrer">{nbUrl}</a></div>
        {endpoint && <div className="mb-2 text-xs text-neutral-500">API: {endpoint}</div>}
        {err ? (
          <div className="text-red-600">Failed to load sources: {err}</div>
        ) : items.length ? (
          <ul className="list-disc pl-4">
            {items.slice(0, 10).map((it: any, idx: number) => (
              <li key={idx} className="mb-1">
                <span className="font-medium">{it.title || it.name || it.id || 'item'}</span>
                {it.url || it.href ? (
                  <> – <a className="underline" href={(it.url || it.href) as string} target="_blank" rel="noreferrer">open</a></>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-neutral-500">No sources to display (or API does not expose a sources/items endpoint).</div>
        )}
      </div>
    </div>
  );
}
