import { redirect } from 'next/navigation';
import type { SupabaseClient } from '@supabase/supabase-js';
import DashboardNavigation from '../../../components/DashboardNavigation';
import { UploadDropzone } from '../../../components/UploadDropzone';
import { callPresignService } from '../../../lib/presign';
import type { Database } from '../../../lib/database.types';
import { createSupabaseServerClient, createSupabaseServiceRoleClient, getBootUser, hasBootJwt, isBootJwtExpired, getBootJwt } from '@/lib/supabaseClient';

export const dynamic = 'force-dynamic';

const DEFAULT_BUCKET = process.env.NEXT_PUBLIC_UPLOAD_BUCKET || process.env.PMOVES_UPLOAD_BUCKET || 'assets';
const DEFAULT_NAMESPACE = process.env.PMOVES_DEFAULT_NAMESPACE || 'pmoves';
const DEFAULT_AUTHOR = process.env.PMOVES_DEFAULT_AUTHOR;

type UploadEventRow = Database['public']['Tables']['upload_events']['Row'];

type EnrichedUploadEvent = UploadEventRow & {
  presignedGetUrl?: string | null;
};

function formatDate(value: string) {
  try {
    return new Intl.DateTimeFormat('en-US', {
      dateStyle: 'short',
      timeStyle: 'short',
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function formatSize(bytes: number | null) {
  if (!bytes) return '—';
  const KB = 1024;
  const MB = KB * 1024;
  if (bytes >= MB) return `${(bytes / MB).toFixed(1)} MB`;
  if (bytes >= KB) return `${(bytes / KB).toFixed(1)} KB`;
  return `${bytes} B`;
}

function resolveNamespace(row: UploadEventRow): string {
  if (row.meta && typeof row.meta === 'object' && 'namespace' in row.meta) {
    const namespace = (row.meta as Record<string, unknown>).namespace;
    if (typeof namespace === 'string' && namespace.trim().length > 0) {
      return namespace;
    }
  }
  return DEFAULT_NAMESPACE;
}

function isSafeObjectKey(row: UploadEventRow, userId: string): boolean {
  if (!row.object_key) return false;
  const namespace = resolveNamespace(row);
  const expectedPrefix = `${namespace}/users/${userId}/uploads/${row.upload_id}/`;
  return row.object_key.startsWith(expectedPrefix);
}

async function fetchRecentUploads(
  supabase: SupabaseClient<Database, 'public'>,
  userId: string
): Promise<EnrichedUploadEvent[]> {
  const { data, error } = await supabase
    .from('upload_events')
    .select('*')
    .eq('owner_id', userId)
    .order('created_at', { ascending: false })
    .limit(20);

  if (error) {
    console.error('[ingest/page] Failed to fetch upload events', error);
    return [];
  }

  const rows = (data ?? []) as UploadEventRow[];
  return Promise.all(
    rows.map(async (row) => {
      if (!row.bucket || row.owner_id !== userId || !isSafeObjectKey(row, userId)) {
        return row;
      }
      try {
        const presign = await callPresignService({
          bucket: row.bucket,
          key: row.object_key!,
          method: 'get',
          expires: 900,
        });
        return { ...row, presignedGetUrl: presign.url };
      } catch (err) {
        console.warn('[ingest/page] Failed to fetch presigned URL', err);
        return { ...row, presignedGetUrl: null };
      }
    })
  );
}

export default async function IngestDashboardPage() {
  // Prefer boot JWT path for zero-click auth; if absent or expired fall back to login
  let user = hasBootJwt() ? await getBootUser(createSupabaseServerClient()) : null;
  // Avoid redirect loops when a stale/expired boot token is present
  const bootExpired = hasBootJwt() && isBootJwtExpired(5);
  if (!user && !bootExpired) {
    redirect(`/login?next=/dashboard/ingest`);
  }
  // Use service-role for server reads of recent uploads (RLS-safe by owner_id)
  const supabase: SupabaseClient<Database, 'public'> = createSupabaseServiceRoleClient() as unknown as SupabaseClient<Database, 'public'>;

  // Derive an ownerId even when the boot token is expired by parsing the JWT `sub`.
  let ownerId = user?.id || '';
  if (!ownerId) {
    try {
      const token = getBootJwt();
      if (token) {
        const [, payload] = token.split('.') as [string, string, string];
        const json = JSON.parse(Buffer.from(payload, 'base64').toString('utf-8')) as { sub?: string };
        if (json?.sub && typeof json.sub === 'string') {
          ownerId = json.sub;
        }
      }
    } catch {
      // ignore
    }
  }
  const uploads = ownerId
    ? await fetchRecentUploads(
        supabase as SupabaseClient<Database, 'public', any>,
        ownerId
      )
    : [];

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

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-brand-ink">Recent uploads</h2>
          <p className="text-xs text-brand-subtle">Showing the last {uploads.length} records from Supabase.</p>
        </div>
        <div className="overflow-hidden rounded-lg border border-brand-border bg-brand-inverse">
          <table className="min-w-full divide-y divide-brand-border">
            <thead className="bg-brand-surface-muted">
              <tr className="text-left text-xs font-semibold uppercase tracking-wide text-brand-muted">
                <th className="px-4 py-3">File</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Progress</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">Updated</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border bg-brand-inverse text-sm text-brand-ink">
              {uploads.map((upload) => (
                <tr key={upload.id}>
                  <td className="px-4 py-3">
                    <div className="font-medium text-brand-ink">{upload.filename || upload.object_key}</div>
                    <div className="text-xs text-brand-subtle">
                      {upload.bucket}/{upload.object_key}
                    </div>
                    {upload.error_message && (
                      <div className="mt-1 text-xs text-brand-crimson">{upload.error_message}</div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded bg-brand-surface-muted px-2 py-1 text-xs font-medium text-brand-muted">
                      {upload.status || 'unknown'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {typeof upload.progress === 'number' ? `${upload.progress}%` : '—'}
                  </td>
                  <td className="px-4 py-3">{formatSize(upload.size_bytes)}</td>
                  <td className="px-4 py-3">{formatDate(upload.updated_at)}</td>
                  <td className="px-4 py-3">
                    {upload.presignedGetUrl ? (
                      <a
                        href={upload.presignedGetUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-medium text-brand-ink hover:text-brand-ink-strong hover:underline"
                      >
                        Open asset
                      </a>
                    ) : (
                      <span className="text-xs text-brand-subtle">No link</span>
                    )}
                  </td>
                </tr>
              ))}
              {uploads.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-sm text-brand-muted">
                    No uploads have been recorded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
