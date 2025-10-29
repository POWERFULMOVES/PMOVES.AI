import Link from 'next/link';

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-brand-surface p-8 text-center">
      <div className="space-y-3">
        <h1 className="text-3xl font-semibold text-brand-ink">PMOVES Operator Console</h1>
        <p className="max-w-md text-sm text-brand-muted">
          Sign in to manage ingestion workflows, upload new assets, and monitor Supabase processing pipelines.
        </p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Link
          href="/login"
          className="rounded bg-brand-sky px-5 py-2 text-sm font-semibold text-brand-ink-strong shadow hover:bg-brand-gold"
        >
          Continue to login
        </Link>
        <Link
          href="/dashboard/ingest"
          className="rounded border border-brand-border px-5 py-2 text-sm font-semibold text-brand-ink hover:border-brand-slate hover:text-brand-ink-strong"
        >
          View ingestion dashboard
        </Link>
      </div>
    </main>
  );
}
