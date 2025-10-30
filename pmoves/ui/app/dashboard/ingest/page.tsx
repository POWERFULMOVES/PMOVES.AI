import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import type { SupabaseClient } from '@supabase/supabase-js';
import { createServerComponentClient } from '@supabase/auth-helpers-nextjs';
import DashboardNavigation from '../../../components/DashboardNavigation';
import { UploadDropzone } from '../../../components/UploadDropzone';
import { callPresignService } from '../../../lib/presign';
import type { Database } from '../../../lib/database.types';

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
  const cookieStore = cookies();
  const supabase = createServerComponentClient<Database>({ cookies: () => cookieStore });
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect(`/login?next=/dashboard/ingest`);
  }

  const uploads = await fetchRecentUploads(
    supabase as SupabaseClient<Database, 'public', any>,
    user.id
  );

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 p-8">
      <DashboardNavigation active="ingest" />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-slate-900">Ingestion dashboard</h1>
        <p className="text-sm text-slate-600">
          Upload new creative assets and monitor ingestion progress across Supabase and MinIO.
        </p>
      </header>

      <section>
        <UploadDropzone
          bucket={DEFAULT_BUCKET}
          namespace={DEFAULT_NAMESPACE}
          author={DEFAULT_AUTHOR}
          ownerId={user.id}
        />
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Recent uploads</h2>
          <p className="text-xs text-slate-500">Showing the last {uploads.length} records from Supabase.</p>
        </div>
        <div className="overflow-hidden rounded-lg border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3">File</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Progress</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">Updated</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white text-sm text-slate-700">
              {uploads.map((upload) => (
                <tr key={upload.id}>
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">{upload.filename || upload.object_key}</div>
                    <div className="text-xs text-slate-500">
                      {upload.bucket}/{upload.object_key}
                    </div>
                    {upload.error_message && (
                      <div className="mt-1 text-xs text-rose-600">{upload.error_message}</div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
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
                        className="text-xs font-medium text-slate-700 hover:underline"
                      >
                        Open asset
                      </a>
                    ) : (
                      <span className="text-xs text-slate-400">No link</span>
                    )}
                  </td>
                </tr>
              ))}
              {uploads.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-sm text-slate-500">
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
