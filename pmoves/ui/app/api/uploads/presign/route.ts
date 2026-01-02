import { NextRequest, NextResponse } from 'next/server';
import { callPresignService, type PresignMethod } from '../../../../lib/presign';
import { createSupabaseRouteHandlerClient, getServiceSupabaseClient } from '../../../../lib/supabaseServer';
import type { Database } from '../../../../lib/database.types';

type UploadEventSelection = Pick<Database['public']['Tables']['upload_events']['Row'], 'bucket' | 'object_key' | 'owner_id' | 'meta'>;

function resolveNamespace(meta: Record<string, unknown> | null | undefined, fallback: string): string {
  if (meta && typeof meta === 'object' && 'namespace' in meta) {
    const namespace = (meta as Record<string, unknown>).namespace;
    if (typeof namespace === 'string' && namespace.trim().length > 0) {
      return namespace;
    }
  }
  return fallback;
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const bucket = body.bucket as string | undefined;
    const key = body.key as string | undefined;
    const contentType = body.contentType as string | undefined;
    const expires = body.expires as number | undefined;
    const method = (body.method as PresignMethod | undefined) ?? 'put';
    const uploadId = body.uploadId as string | undefined;

    if (!bucket || !key || !uploadId) {
      return NextResponse.json({ error: 'bucket, key, and uploadId are required' }, { status: 400 });
    }

    const cookieStore = request.cookies;
    const supabase = createSupabaseRouteHandlerClient(() => cookieStore);
    const {
      data: { session },
    } = await supabase.auth.getSession();
    const bootJwt = process.env.NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT || process.env.SUPABASE_BOOT_USER_JWT;

    // When running with a boot JWT (no browser cookie session), switch to service-role client
    const readClient = (session ? supabase : getServiceSupabaseClient()) as ReturnType<typeof getServiceSupabaseClient>;
    const userId = session?.user?.id;

    // Security: User identity must come from authenticated session only
    if (!userId) {
      return NextResponse.json({ error: 'Authentication required' }, { status: 401 });
    }

    const { data: eventRow, error: eventError } = await readClient
      .from('upload_events')
      .select('bucket, object_key, owner_id, meta')
      .eq('upload_id', uploadId)
      .single<UploadEventSelection>();

    if (eventError || !eventRow) {
      return NextResponse.json({ error: 'Upload event not found' }, { status: 404 });
    }

    if (userId && eventRow.owner_id !== userId) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    if (!eventRow.object_key || eventRow.object_key !== key || eventRow.bucket !== bucket) {
      return NextResponse.json({ error: 'Upload metadata mismatch' }, { status: 400 });
    }

    const namespace = resolveNamespace(eventRow.meta as Record<string, unknown> | null, process.env.PMOVES_DEFAULT_NAMESPACE || 'pmoves');
    const expectedPrefix = `${namespace}/users/${userId}/uploads/${uploadId}/`;
    if (!eventRow.object_key.startsWith(expectedPrefix)) {
      return NextResponse.json({ error: 'Object key outside authorised prefix' }, { status: 403 });
    }

    const result = await callPresignService({
      bucket,
      key,
      contentType,
      expires,
      method,
    });

    return NextResponse.json(result, { status: 200 });
  } catch (error) {
    console.error('[api/uploads/presign] Failed to proxy presign request', error);
    const message = error instanceof Error ? error.message : 'Unexpected error';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
