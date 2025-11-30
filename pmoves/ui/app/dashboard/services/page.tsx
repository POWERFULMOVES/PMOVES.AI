import Link from 'next/link';
import type { Metadata } from 'next';
import DashboardNavigation from '../../../components/DashboardNavigation';
import { INTEGRATION_SERVICES } from '../../../lib/services';

export const metadata: Metadata = {
  title: 'Integration services | PMOVES Console',
  description:
    'Browse the PMOVES operator integrations including Open Notebook, PMOVES.YT, Jellyfin, Wger, and Firefly.',
};

export default function ServicesIndexPage() {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 p-8">
      <DashboardNavigation active="services" />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-slate-900">Integration services</h1>
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-slate-600">
            Quick links to the external integrations that power ingestion, review, and finance workflows across the PMOVES stack.
          </p>
          <Link
            href="/dashboard/services/yt-dlp"
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:border-slate-400 hover:text-slate-900"
            title="Open yt-dlp live status"
          >
            yt-dlp Status →
          </Link>
        </div>
      </header>
      <div className="flex flex-wrap gap-4">
        {INTEGRATION_SERVICES.map((service) => (
          <Link
            key={service.slug}
            href={`/dashboard/services/${service.slug}`}
            className="group flex min-h-[160px] w-full flex-col justify-between gap-3 rounded-lg border border-slate-200 bg-white p-5 transition-shadow hover:border-slate-300 hover:shadow"
          >
            <div className="space-y-2">
              <div className="text-xs font-semibold uppercase tracking-widest text-slate-500">Integration</div>
              <h2 className="text-xl font-semibold text-slate-900 group-hover:text-slate-700">{service.title}</h2>
              <p className="text-sm text-slate-600">{service.summary}</p>
            </div>
            <span className="text-sm font-semibold text-slate-900 group-hover:text-slate-700">View runbook →</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
