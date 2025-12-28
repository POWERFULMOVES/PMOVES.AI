import { NextRequest, NextResponse } from 'next/server';
import { logError } from '@/lib/errorUtils';

// Notebook Sync service endpoint
const NOTEBOOK_SYNC_URL = (
  process.env.NOTEBOOK_SYNC_URL ||
  process.env.NEXT_PUBLIC_NOTEBOOK_SYNC_URL ||
  'http://localhost:8095'
).replace(/\/$/, '');

export async function POST(_req: NextRequest) {
  const syncUrl = `${NOTEBOOK_SYNC_URL}/sync`;

  try {
    const syncRes = await fetch(syncUrl, {
      method: 'POST',
      cache: 'no-store',
      signal: AbortSignal.timeout(30000), // 30 second timeout for sync operation
    });

    if (!syncRes.ok) {
      const errorText = await syncRes.text().catch(() => 'Unknown error');
      logError(`Notebook sync returned ${syncRes.status}`, new Error(errorText), 'warning', {
        component: 'notebook-sync-api',
        endpoint: syncUrl,
      });
      return NextResponse.json(
        { ok: false, error: `Sync returned ${syncRes.status}` },
        { status: 502 }
      );
    }

    const data = await syncRes.json();
    return NextResponse.json({ ok: true, ...data });
  } catch (err) {
    logError('Failed to trigger notebook sync', err instanceof Error ? err : new Error(String(err)), 'error', {
      component: 'notebook-sync-api',
      endpoint: syncUrl,
    });
    return NextResponse.json(
      { ok: false, error: 'Failed to trigger sync' },
      { status: 502 }
    );
  }
}
