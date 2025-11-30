import 'server-only';

async function fetchHealth(base: string) {
  const baseClean = base.replace(/\/$/, '');
  const custom = (process.env.NEXT_PUBLIC_AGENT_ZERO_HEALTH_PATH || '').trim();
  const urls = [
    custom && (custom.startsWith('/') ? baseClean + custom : `${baseClean}/${custom}`),
    `${baseClean}/healthz`,
    `${baseClean}/api/health`,
    `${baseClean}/`,
  ].filter(Boolean) as string[];
  for (const u of urls) {
    try {
      const res = await fetch(u, { next: { revalidate: 0 } });
      if (res.ok) {
        const text = await res.text();
        try {
          return { url: u, payload: JSON.parse(text) };
        } catch {
          return { url: u, payload: { status: res.status, body: text } };
        }
      }
    } catch {}
  }
  return null;
}

export default async function AgentZeroPage() {
  const base = (process.env.NEXT_PUBLIC_AGENT_ZERO_URL || 'http://localhost:8080').replace(/\/$/, '');
  const uiUrl = (process.env.NEXT_PUBLIC_AGENT_ZERO_UI_URL || 'http://localhost:8081').replace(/\/$/, '');
  const health = await fetchHealth(base);
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="mb-2 text-2xl font-semibold text-slate-900">Agent Zero</h1>
      <p className="mb-6 text-sm text-slate-600">
        The Agent Zero API runs headless (MCP). This page checks the API and links your console to the MCP endpoint.
      </p>
      <section className="mb-6 rounded border border-slate-200 bg-white p-4">
        <h2 className="mb-2 text-base font-semibold">Health</h2>
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
        <h2 className="mb-2 text-base font-semibold">Connect MCP client</h2>
        <ul className="list-disc pl-5 text-sm text-slate-700">
          <li>Endpoint: <code>{base}</code></li>
          <li>Health path: <code>{(process.env.NEXT_PUBLIC_AGENT_ZERO_HEALTH_PATH || '/healthz')}</code></li>
          <li>Broker: NATS at <code>{process.env.NATS_URL || 'nats://nats:4222'}</code> (internal)</li>
        </ul>
        <div className="mt-3 flex gap-3">
          <a href={uiUrl} target="_blank" rel="noreferrer" className="inline-block rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-800 hover:border-slate-400">Open native UI</a>
          <a href={base} target="_blank" rel="noreferrer" className="inline-block rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-800 hover:border-slate-400">Open API root</a>
        </div>
      </section>
    </main>
  );
}
