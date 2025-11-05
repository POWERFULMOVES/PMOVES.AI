import Link from 'next/link';

export default function HomePage() {
  const hasBootJwt = Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT || process.env.SUPABASE_BOOT_USER_JWT
  );
  const primaryHref = hasBootJwt ? '/dashboard/ingest' : '/login';
  const primaryLabel = hasBootJwt ? 'Open dashboard' : 'Continue to login';
  const links: { label: string; href: string }[] = [
    { label: 'Agent Zero', href: '/dashboard/agent-zero' },
    { label: 'Archon', href: '/dashboard/archon' },
    { label: 'Hi‑RAG Geometry (GPU)', href: `http://localhost:${process.env.HIRAG_V2_GPU_HOST_PORT || '8087'}/geometry/` },
    { label: 'TensorZero UI (4000)', href: process.env.NEXT_PUBLIC_TENSORZERO_UI || 'http://localhost:4000' },
    { label: 'TensorZero Gateway (3030)', href: process.env.NEXT_PUBLIC_TENSORZERO_GATEWAY || 'http://localhost:3030' },
    { label: 'Jellyfin (8096)', href: process.env.NEXT_PUBLIC_JELLYFIN_URL || 'http://localhost:8096' },
    { label: 'Open Notebook (8503)', href: process.env.NEXT_PUBLIC_OPEN_NOTEBOOK_URL || 'http://localhost:8503' },
    { label: 'Supabase Studio (65433)', href: process.env.NEXT_PUBLIC_SUPABASE_STUDIO_URL || 'http://127.0.0.1:65433' },
  ];
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
      <div className="w-full max-w-4xl">
        <div className="mx-auto grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              target="_blank"
              rel="noreferrer"
              className="rounded border border-slate-200 bg-white px-4 py-3 text-left text-sm font-medium text-slate-800 shadow-sm hover:border-slate-300 hover:shadow"
            >
              {l.label}
            </a>
          ))}
        </div>
      </div>
    </main>
  );
}
