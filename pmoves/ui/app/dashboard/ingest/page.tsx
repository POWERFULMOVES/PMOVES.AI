import { redirect } from 'next/navigation';
import DashboardNavigation from '../../../components/DashboardNavigation';
import { UploadDropzone } from '../../../components/UploadDropzone';
import UploadEventsTable from '../../../components/UploadEventsTable';
import { createSupabaseServerClient, getBootUser, hasBootJwt, isBootJwtExpired, getBootJwt } from '@/lib/supabaseClient';

export const dynamic = 'force-dynamic';

const DEFAULT_BUCKET = process.env.NEXT_PUBLIC_UPLOAD_BUCKET || process.env.PMOVES_UPLOAD_BUCKET || 'assets';
const DEFAULT_NAMESPACE = process.env.PMOVES_DEFAULT_NAMESPACE || 'pmoves';
const DEFAULT_AUTHOR = process.env.PMOVES_DEFAULT_AUTHOR;

export default async function IngestDashboardPage() {
  // Prefer boot JWT path for zero-click auth; if absent or expired fall back to login
  const user = hasBootJwt() ? await getBootUser(createSupabaseServerClient()) : null;
  // Avoid redirect loops when a stale/expired boot token is present
  const bootExpired = hasBootJwt() && isBootJwtExpired(5);
  if (!user && !bootExpired) {
    redirect(`/login?next=/dashboard/ingest`);
  }
  // Derive an ownerId even when the boot token is expired by parsing the JWT `sub`.
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
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 p-8">
      <DashboardNavigation active="ingest" />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-slate-900">Cooperative Ingestion Bay</h1>
        <p className="text-sm text-slate-600">
          Drop the assets that fuel our cooperative empowerment story—DARKXSIDE counts on each upload to arm the crew with fresh media.
          {' '}Lock in bucket and row-level guardrails with the{' '}
          <a
            className="underline"
            href="https://github.com/Cataclysm-Studios-Inc/PMOVES.AI/blob/main/pmoves/docs/PMOVES.AI%20PLANS/SUPABASE_RLS_HARDENING_CHECKLIST.md"
            target="_blank"
            rel="noreferrer"
          >
            Supabase RLS hardening checklist
          </a>{' '}
          before inviting collaborators to ingest alongside you.
        </p>
      </header>

      {ownerId ? (
        <section>
          <UploadDropzone
            bucket={DEFAULT_BUCKET}
            namespace={DEFAULT_NAMESPACE}
            author={DEFAULT_AUTHOR}
            ownerId={ownerId}
          />
        </section>
      ) : (
        <section className="rounded-md border border-amber-300 bg-amber-50 p-4 text-amber-800">
          <div className="font-semibold">Boot token expired</div>
          <p className="mt-1 text-sm">
            The console detected an expired boot JWT. Rotate it with
            <code className="ml-1 rounded bg-slate-900 px-1 py-0.5 text-white">make -C pmoves supabase-boot-user</code>
            , then restart the UI dev server.
          </p>
        </section>
      )}
      <UploadEventsTable ownerId={ownerId} limit={25} />
    </div>
  );
}
