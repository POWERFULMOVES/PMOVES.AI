import { NextRequest, NextResponse } from 'next/server';
import { randomUUID } from 'crypto';
import { getServiceSupabaseClient } from '@/lib/supabaseServer';

const DEFAULT_BUCKET = process.env.NEXT_PUBLIC_UPLOAD_BUCKET || process.env.PMOVES_UPLOAD_BUCKET || 'assets';
const DEFAULT_NAMESPACE = process.env.PMOVES_DEFAULT_NAMESPACE || 'pmoves';
const SMOKE_SECRET = process.env.SMOKE_SHARED_SECRET || process.env.PMOVES_SMOKE_SHARED_SECRET;
const SINGLE_USER = String(process.env.NEXT_PUBLIC_SINGLE_USER_MODE || process.env.SINGLE_USER_MODE || '1') === '1';

async function getBootUserId(): Promise<string | null> {
  const email = process.env.SUPABASE_BOOT_USER_EMAIL;
  const url = (process.env.SUPABASE_SERVICE_URL || process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL || '').replace(/\/$/, '');
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_SERVICE_KEY || '';
  if (!email || !url || !key) return null;
  try {
    const resp = await fetch(`${url}/auth/v1/admin/users?email=${encodeURIComponent(email)}`, {
      headers: { apikey: key, Authorization: `Bearer ${key}` },
      cache: 'no-store',
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    const users = Array.isArray(data?.users) ? data.users : data;
    if (Array.isArray(users) && users[0]?.id) return users[0].id as string;
    return null;
  } catch {
    return null;
  }
}

export async function POST(request: NextRequest) {
  // Auth: allow in single-user mode, else require the shared secret
  if (!SINGLE_USER) {
    if (!SMOKE_SECRET) {
      return NextResponse.json({ error: 'SMOKE_SHARED_SECRET not set' }, { status: 500 });
    }
    const auth = request.headers.get('authorization') || '';
    if (auth !== `Bearer ${SMOKE_SECRET}`) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
  }

  const ownerId = (await getBootUserId()) || request.headers.get('x-owner-id') || '';
  if (!ownerId) {
    return NextResponse.json({ error: 'ownerId not resolvable' }, { status: 400 });
  }

  const supabase = getServiceSupabaseClient();

  // Ensure bucket exists
  try {
    await fetch(`${process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3001'}/api/uploads/presign`, { method: 'OPTIONS' });
    // OPTIONS noop to warm middleware; ignored
  } catch {}
  try {
    // storage.buckets is only available via PostgREST; use RPC via SQL if needed.
    // Here we rely on UI upload flow to create buckets; if missing, we proceed anyway.
  } catch {}
  const uploadId = randomUUID();
  const key = `${DEFAULT_NAMESPACE}/users/${ownerId}/uploads/${uploadId}/smoke.txt`;

  // Seed an upload_events row the same way the UI does
  const insert = await supabase.from('upload_events').upsert([
    {
      upload_id: uploadId,
      filename: 'smoke.txt',
      bucket: DEFAULT_BUCKET,
      object_key: key,
      status: 'preparing',
      progress: 0,
      size_bytes: 11,
      content_type: 'text/plain',
      meta: { namespace: DEFAULT_NAMESPACE, ingest: 'ui-smoke' },
      owner_id: ownerId,
    },
  ]);
  if (insert.error) {
    return NextResponse.json({ error: insert.error.message }, { status: 500 });
  }

  // Call the presign route (internal) just to verify path validation & service proxying
  const presignRes = await fetch(`${process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3001'}/api/uploads/presign`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ bucket: DEFAULT_BUCKET, key, method: 'get', uploadId, ownerId }),
  });
  const presign = presignRes.ok ? await presignRes.json() : { error: await presignRes.text() };

  return NextResponse.json({ ok: true, uploadId, key, ownerId, presign }, { status: 200 });
}
