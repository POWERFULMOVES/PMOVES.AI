import 'server-only';

async function fetchHealth(base: string) {
  const baseClean = base.replace(/\/$/, '');
  const custom = (process.env.NEXT_PUBLIC_ARCHON_HEALTH_PATH || '').trim();
  const urls = [
    custom && (custom.startsWith('/') ? baseClean + custom : `${baseClean}/${custom}`),
    `${baseClean}/healthz`,
    `${baseClean}/api/health`,
    `${baseClean}/`,
  ].filter(Boolean) as string[];
  for (const url of urls) {
    try {
      const res = await fetch(url, { next: { revalidate: 0 } });
      if (res.ok) {
        const text = await res.text();
        try {
          return { url, payload: JSON.parse(text) };
        } catch {
          return { url, payload: { status: res.status, body: text } };
        }
      }
    } catch {}
  }
  return null;
}

export default async function ArchonPage() {
  const base = (process.env.NEXT_PUBLIC_ARCHON_URL || 'http://localhost:8091').replace(/\/$/, '');
  const uiUrl = (process.env.NEXT_PUBLIC_ARCHON_UI_URL || 'http://localhost:3737').replace(/\/$/, '');
  const health = await fetchHealth(base);
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="mb-2 text-2xl font-semibold text-slate-900">Archon</h1>
      <p className="mb-6 text-sm text-slate-600">
        Archon runs headless (MCP) and exposes a health/info endpoint. Use the prompts editor under the PMOVES console to manage knowledge packs.
      </p>
      <section className="mb-6 rounded border border-slate-200 bg-white p-4">
        <h2 className="mb-2 text-base font-semibold">Health / Info</h2>
        {health ? (
          <>
            <div className="mb-2 text-xs text-slate-500">checked: {health.url}</div>
            <pre className="overflow-x-auto rounded bg-slate-50 p-3 text-xs text-slate-800">
{JSON.stringify(health.payload, null, 2)}
            </pre>
          </>
        ) : (
          <div className="text-sm text-amber-700">No response from {base}. Is the agents profile up? Try: <code>make -C pmoves up-agents</code>.</div>
        )}
      </section>
      <section className="rounded border border-slate-200 bg-white p-4">
        <h2 className="mb-2 text-base font-semibold">Prompts & Knowledge Packs</h2>
        <p className="mb-3 text-sm text-slate-700">Edit Archon prompts in the PMOVES console or open the native API root:</p>
        <div className="flex gap-3">
          <a href="/dashboard/archon-prompts" className="inline-block rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-800 hover:border-slate-400">Open prompts editor</a>
          <a href={uiUrl} target="_blank" rel="noreferrer" className="inline-block rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-800 hover:border-slate-400">Open Archon UI</a>
          <a href={base} target="_blank" rel="noreferrer" className="inline-block rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-800 hover:border-slate-400">Open native API</a>
          <a href={`${base}/docs`} target="_blank" rel="noreferrer" className="inline-block rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-800 hover:border-slate-400">Open API docs</a>
        </div>
      </section>
    </main>
  );
}
