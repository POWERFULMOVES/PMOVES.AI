import Link from 'next/link';
import type { Metadata } from 'next';
import { DashboardShell } from '../../../components/DashboardNavigation';
import { INTEGRATION_SERVICES } from '../../../lib/services';

export const metadata: Metadata = {
  title: 'Integration Services',
  description: 'Browse the PMOVES operator integrations including Open Notebook, PMOVES.YT, Jellyfin, Wger, and Firefly.',
};

const SERVICE_COLORS: Record<string, string> = {
  'open-notebook': 'cyan',
  'pmoves-yt': 'ember',
  'jellyfin': 'violet',
  'wger': 'forest',
  'firefly': 'gold',
};

export default function ServicesIndexPage() {
  return (
    <DashboardShell
      title="Integration Services"
      subtitle="External integrations powering ingestion, review, and finance workflows"
      active="services"
      actions={
        <Link href="/dashboard/services/yt-dlp" className="tag tag-ember">
          yt-dlp Status
        </Link>
      }
    >
      <div className="p-6 lg:p-8 space-y-8">
        {/* Services grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {INTEGRATION_SERVICES.map((service) => {
            const color = SERVICE_COLORS[service.slug] || 'cyan';
            const colorClasses: Record<string, string> = {
              cyan: 'border-cata-cyan/30 hover:border-cata-cyan group-hover:text-cata-cyan',
              ember: 'border-cata-ember/30 hover:border-cata-ember group-hover:text-cata-ember',
              violet: 'border-cata-violet/30 hover:border-cata-violet group-hover:text-cata-violet',
              forest: 'border-cata-forest/30 hover:border-cata-forest group-hover:text-cata-forest',
              gold: 'border-cata-gold/30 hover:border-cata-gold group-hover:text-cata-gold',
            };

            return (
              <Link
                key={service.slug}
                href={`/dashboard/services/${service.slug}`}
                className={`group card-brutal p-6 flex flex-col gap-4 border ${colorClasses[color]}`}
              >
                {/* Header */}
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <span className={`tag tag-${color}`}>Integration</span>
                    <h2 className={`font-display font-bold text-xl mt-2 transition-colors ${colorClasses[color]}`}>
                      {service.title}
                    </h2>
                  </div>
                  <div className={`w-12 h-12 flex items-center justify-center bg-${color === 'cyan' ? 'cata-cyan' : color === 'ember' ? 'cata-ember' : color === 'violet' ? 'cata-violet' : color === 'forest' ? 'cata-forest' : 'cata-gold'}/10 font-display font-bold text-lg opacity-50 group-hover:opacity-100 transition-opacity`}>
                    {service.title.charAt(0)}
                  </div>
                </div>

                {/* Description */}
                <p className="text-sm text-ink-secondary leading-relaxed flex-1">
                  {service.summary}
                </p>

                {/* Footer */}
                <div className="flex items-center justify-between pt-4 border-t border-border-subtle">
                  <span className="text-xs text-ink-muted font-mono uppercase tracking-wider">
                    {service.slug}
                  </span>
                  <span className="text-xs font-mono text-ink-muted group-hover:text-cata-cyan transition-colors flex items-center gap-1">
                    View runbook
                    <span className="transform group-hover:translate-x-1 transition-transform">&rarr;</span>
                  </span>
                </div>
              </Link>
            );
          })}
        </div>

        {/* Quick links section */}
        <section className="space-y-4">
          <h2 className="font-display font-semibold text-lg">External Dashboards</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border-subtle">
            {[
              { name: 'TensorZero UI', port: '4000', href: 'http://localhost:4000' },
              { name: 'Grafana', port: '3000', href: 'http://localhost:3000' },
              { name: 'Prometheus', port: '9090', href: 'http://localhost:9090' },
              { name: 'Supabase Studio', port: '65433', href: 'http://127.0.0.1:65433' },
              { name: 'Agent Zero UI', port: '8081', href: 'http://localhost:8081' },
              { name: 'Archon UI', port: '3737', href: 'http://localhost:3737' },
              { name: 'Jellyfin', port: '8096', href: 'http://localhost:8096' },
              { name: 'MinIO Console', port: '9001', href: 'http://localhost:9001' },
            ].map((item) => (
              <a
                key={item.name}
                href={item.href}
                target="_blank"
                rel="noreferrer"
                className="bg-void p-4 hover:bg-void-elevated transition-colors group"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-2xs text-ink-muted">:{item.port}</span>
                </div>
                <span className="font-display font-semibold text-sm group-hover:text-cata-cyan transition-colors">
                  {item.name}
                </span>
              </a>
            ))}
          </div>
        </section>
      </div>
    </DashboardShell>
  );
}
