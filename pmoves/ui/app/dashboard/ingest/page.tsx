import { redirect } from 'next/navigation';
import { DashboardShell } from '../../../components/DashboardNavigation';
import { UploadDropzone } from '../../../components/UploadDropzone';
import UploadEventsTable from '../../../components/UploadEventsTable';
import { createSupabaseServerClient, getBootUser, hasBootJwt, isBootJwtExpired, getBootJwt } from '@/lib/supabaseClient';

export const dynamic = 'force-dynamic';

const DEFAULT_BUCKET = process.env.NEXT_PUBLIC_UPLOAD_BUCKET || process.env.PMOVES_UPLOAD_BUCKET || 'assets';
const DEFAULT_NAMESPACE = process.env.PMOVES_DEFAULT_NAMESPACE || 'pmoves';
const DEFAULT_AUTHOR = process.env.PMOVES_DEFAULT_AUTHOR;

export default async function IngestDashboardPage() {
  const user = hasBootJwt() ? await getBootUser(createSupabaseServerClient()) : null;
  const bootExpired = hasBootJwt() && isBootJwtExpired(5);
  if (!user && !bootExpired) {
    redirect(`/login?next=/dashboard/ingest`);
  }

  const ownerIdFromUser = user?.id || '';
  const ownerIdFromToken = (() => {
    try {
      const token = getBootJwt();
      if (!token) return '';
      const [, payload] = token.split('.') as [string, string, string];
      const json = JSON.parse(Buffer.from(payload, 'base64').toString('utf-8')) as { sub?: string };
      return typeof json.sub === 'string' ? json.sub : '';
    } catch {
      return '';
    }
  })();
  const ownerId = ownerIdFromUser || ownerIdFromToken;

  return (
    <DashboardShell
      title="Cooperative Ingestion Bay"
      subtitle="Drop assets that fuel our cooperative empowerment story"
      active="ingest"
    >
      <div className="p-6 lg:p-8 space-y-8">
        {/* Info banner */}
        <div className="card-glass p-4 flex items-start gap-4">
          <div className="w-8 h-8 flex items-center justify-center bg-cata-cyan/20 text-cata-cyan font-mono text-sm flex-shrink-0">
            i
          </div>
          <div className="space-y-1">
            <p className="text-sm text-ink-secondary">
              DARKXSIDE counts on each upload to arm the crew with fresh media. Lock in bucket and row-level guardrails with the{' '}
              <a
                className="text-cata-cyan hover:text-cata-forest transition-colors"
                href="https://github.com/Cataclysm-Studios-Inc/PMOVES.AI/blob/main/pmoves/docs/PMOVES.AI%20PLANS/SUPABASE_RLS_HARDENING_CHECKLIST.md"
                target="_blank"
                rel="noreferrer"
              >
                Supabase RLS hardening checklist
              </a>{' '}
              before inviting collaborators.
            </p>
          </div>
        </div>

        {/* Upload section */}
        {ownerId ? (
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-display font-semibold text-lg">Upload Assets</h2>
              <div className="flex items-center gap-2">
                <span className="tag tag-cyan">{DEFAULT_BUCKET}</span>
                <span className="text-xs text-ink-muted font-mono">/{DEFAULT_NAMESPACE}</span>
              </div>
            </div>
            <UploadDropzone
              bucket={DEFAULT_BUCKET}
              namespace={DEFAULT_NAMESPACE}
              author={DEFAULT_AUTHOR}
              ownerId={ownerId}
            />
          </section>
        ) : (
          <section className="card-brutal p-6 border-cata-gold">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 flex items-center justify-center bg-cata-gold/20 text-cata-gold font-display font-bold">
                !
              </div>
              <div className="space-y-2">
                <h3 className="font-display font-semibold text-cata-gold">Boot token expired</h3>
                <p className="text-sm text-ink-secondary">
                  The console detected an expired boot JWT. Rotate it with:
                </p>
                <code className="block mt-2 p-3 bg-void font-mono text-xs text-cata-cyan">
                  make -C pmoves supabase-boot-user
                </code>
                <p className="text-xs text-ink-muted mt-2">
                  Then restart the UI dev server.
                </p>
              </div>
            </div>
          </section>
        )}

        {/* Events table */}
        <section className="space-y-4">
          <h2 className="font-display font-semibold text-lg">Recent Uploads</h2>
          <UploadEventsTable ownerId={ownerId} limit={25} />
        </section>
      </div>
    </DashboardShell>
  );
}
