import Link from 'next/link';

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-100 p-8 text-center">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold text-slate-900">PMOVES UI</h1>
        <p className="text-sm text-slate-600">
          Jump into the ingestion workflow to upload new renders and monitor Supabase progress.
        </p>
      </div>
      <Link
        href="/dashboard/ingest"
        className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow hover:bg-slate-700"
      >
        Go to ingestion dashboard
      </Link>
    </main>
  );
}
