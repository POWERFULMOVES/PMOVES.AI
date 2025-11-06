import Link from 'next/link';

type LinkDef = { label: string; href: string; health?: string; optional?: boolean };

async function probe(url?: string) {
  if (!url) return undefined;
  try {
    const res = await fetch(url, { next: { revalidate: 0 } });
    return res.ok;
  } catch {
    return false;
  }
}

export default async function HomePage() {
  const hasBootJwt = Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT || process.env.SUPABASE_BOOT_USER_JWT
  );
  const primaryHref = hasBootJwt ? '/dashboard/ingest' : '/login';
  const primaryLabel = hasBootJwt ? 'Open dashboard' : 'Continue to login';
  const gpuPort = process.env.HIRAG_V2_GPU_HOST_PORT || '8087';
  const links: LinkDef[] = [
    { label: 'Personas', href: '/dashboard/personas' },
    {
      label: 'Agent Zero',
      href: '/dashboard/agent-zero',
      health: (() => {
        const base = (process.env.NEXT_PUBLIC_AGENT_ZERO_URL || 'http://localhost:8080').replace(/\/$/, '');
        const custom = (process.env.NEXT_PUBLIC_AGENT_ZERO_HEALTH_PATH || '').trim();
        if (custom) return base + (custom.startsWith('/') ? custom : '/' + custom);
        return base + '/healthz';
      })(),
    },
    {
      label: 'Archon',
      href: '/dashboard/archon',
      health: (() => {
        const base = (process.env.NEXT_PUBLIC_ARCHON_URL || 'http://localhost:8091').replace(/\/$/, '');
        const custom = (process.env.NEXT_PUBLIC_ARCHON_HEALTH_PATH || '').trim();
        if (custom) return base + (custom.startsWith('/') ? custom : '/' + custom);
        return base + '/healthz';
      })(),
    },
    {
      label: 'Hi‑RAG Geometry (GPU)',
      href: `http://localhost:${gpuPort}/geometry/`,
      health: `http://localhost:${gpuPort}/hirag/admin/stats`,
    },
    { label: 'TensorZero UI (4000)', href: process.env.NEXT_PUBLIC_TENSORZERO_UI || 'http://localhost:4000', health: process.env.NEXT_PUBLIC_TENSORZERO_UI || 'http://localhost:4000' },
    // Gateway root may not return 200; omit health to avoid false negatives
    { label: 'TensorZero Gateway (3030)', href: process.env.NEXT_PUBLIC_TENSORZERO_GATEWAY || 'http://localhost:3030', optional: true },
    { label: 'Jellyfin (8096)', href: process.env.NEXT_PUBLIC_JELLYFIN_URL || 'http://localhost:8096', health: (process.env.NEXT_PUBLIC_JELLYFIN_URL || 'http://localhost:8096').replace(/\/$/, '') + '/System/Info' },
    { label: 'Open Notebook (8503)', href: process.env.NEXT_PUBLIC_OPEN_NOTEBOOK_URL || 'http://localhost:8503', health: process.env.NEXT_PUBLIC_OPEN_NOTEBOOK_URL || 'http://localhost:8503' },
    { label: 'Supabase Studio (65433)', href: process.env.NEXT_PUBLIC_SUPABASE_STUDIO_URL || 'http://127.0.0.1:65433', health: process.env.NEXT_PUBLIC_SUPABASE_STUDIO_URL || 'http://127.0.0.1:65433' },
    { label: 'Invidious (3000)', href: process.env.NEXT_PUBLIC_INVIDIOUS_URL || 'http://127.0.0.1:3000', health: process.env.NEXT_PUBLIC_INVIDIOUS_URL || 'http://127.0.0.1:3000' },
  ];

  const statuses = await Promise.all(links.map(l => probe(l.health)));
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 bg-slate-100 p-8 text-center">
      <div className="space-y-3">
        <h1 className="text-3xl font-semibold text-slate-900">PMOVES Operator Console</h1>
        <p className="max-w-md text-sm text-slate-600">
          Sign in to manage ingestion workflows, upload new assets, and monitor Supabase processing pipelines.
        </p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Link
          href={primaryHref}
          className="rounded bg-slate-900 px-5 py-2 text-sm font-semibold text-white shadow hover:bg-slate-700"
        >
          {primaryLabel}
        </Link>
        <Link
          href="/dashboard/ingest"
          className="rounded border border-slate-300 px-5 py-2 text-sm font-semibold text-slate-700 hover:border-slate-400 hover:text-slate-900"
        >
          View ingestion dashboard
        </Link>
      </div>
      <div className="w-full max-w-5xl">
        <div className="mx-auto grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {links.map((l, idx) => {
            const ok = statuses[idx];
            const badge = l.health
              ? ok === true
                ? (<span className="ml-2 rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-700">healthy</span>)
                : ok === false
                  ? (<span className="ml-2 rounded bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-700">down</span>)
                  : (<span className="ml-2 rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">n/a</span>)
              : (<span className="ml-2 rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">link</span>);
            return (
              <a
                key={l.href}
                href={l.href}
                target={l.href.startsWith('http') ? '_blank' : undefined}
                rel={l.href.startsWith('http') ? 'noreferrer' : undefined}
                className="rounded border border-slate-200 bg-white px-4 py-3 text-left text-sm font-medium text-slate-800 shadow-sm hover:border-slate-300 hover:shadow"
              >
                {l.label}
                {badge}
              </a>
            );
          })}
        </div>
      </div>
    </main>
  );
}
