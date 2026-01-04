import { NextRequest, NextResponse } from 'next/server';
import { callPresignService } from '../../../../lib/presign';
import { createSupabaseRouteHandlerClient, getServiceSupabaseClient } from '../../../../lib/supabaseServer';
import type { Database } from '../../../../lib/database.types';

type UploadEventSelection = Pick<Database['public']['Tables']['upload_events']['Row'], 'bucket' | 'object_key' | 'owner_id' | 'meta'>;

const DEFAULT_NAMESPACE = process.env.PMOVES_DEFAULT_NAMESPACE || 'pmoves';
const RENDER_WEBHOOK_URL =
  process.env.RENDER_WEBHOOK_URL ||
  process.env.RENDER_WEBHOOK_ENDPOINT ||
  'http://localhost:8085/comfy/webhook';
const RENDER_WEBHOOK_SECRET = process.env.RENDER_WEBHOOK_SHARED_SECRET;

async function notifyRenderWebhook(payload: Record<string, unknown>) {
  if (!RENDER_WEBHOOK_URL) {
    return null;
  }
  const headers: Record<string, string> = {
    'content-type': 'application/json',
  };
  if (RENDER_WEBHOOK_SECRET) {
    headers.authorization = `Bearer ${RENDER_WEBHOOK_SECRET}`;
  }
  const response = await fetch(RENDER_WEBHOOK_URL, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Render webhook failed (${response.status})`);
  }
  return response.json();
}

function buildAssetUri(bucket: string, key: string) {
  return `s3://${bucket}/${key}`;
}

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
    const cookieStore = request.cookies;
    const supabaseAuth = createSupabaseRouteHandlerClient(() => cookieStore);
    const {
      data: { session },
    } = await supabaseAuth.auth.getSession();
    const bootJwt = process.env.NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT || process.env.SUPABASE_BOOT_USER_JWT;

    const body = await request.json();
    const uploadId = body.uploadId as string | undefined;
    const bucket = body.bucket as string | undefined;
    const key = body.key as string | undefined;
    const requestedNamespace = (body.namespace as string | undefined) || DEFAULT_NAMESPACE;
    const title = (body.title as string | undefined) || (key ? key.split('/').pop() : undefined) || 'uploaded asset';
    const size = body.size as number | undefined;
    const contentType = body.contentType as string | undefined;
    const tags = (Array.isArray(body.tags) ? body.tags : []).map(String);
    const language = (body.language as string | undefined) || 'en';
    const transcriptText = (body.transcriptText as string | undefined) || '';
    const author = body.author as string | undefined;

    if (!uploadId || !bucket || !key) {
      return NextResponse.json({ error: 'uploadId, bucket, and key are required' }, { status: 400 });
    }

    // Security: User identity must come from authenticated session only
    const effectiveUserId = session?.user?.id;
    if (!effectiveUserId) {
      return NextResponse.json({ error: 'Authentication required' }, { status: 401 });
    }

    const readClient = (session ? supabaseAuth : getServiceSupabaseClient()) as ReturnType<typeof getServiceSupabaseClient>;
    const { data: uploadEvent, error: uploadError } = await readClient
      .from('upload_events')
      .select('bucket, object_key, owner_id, meta')
      .eq('upload_id', uploadId)
      .single<UploadEventSelection>();

    if (uploadError || !uploadEvent) {
      return NextResponse.json({ error: 'Upload event not found' }, { status: 404 });
    }

    if (effectiveUserId && uploadEvent.owner_id !== effectiveUserId) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    if (!uploadEvent.object_key || uploadEvent.object_key !== key || uploadEvent.bucket !== bucket) {
      return NextResponse.json({ error: 'Upload metadata mismatch' }, { status: 400 });
    }

    const namespace = resolveNamespace(uploadEvent.meta as Record<string, unknown> | null, requestedNamespace);
    const expectedPrefix = `${namespace}/users/${effectiveUserId}/uploads/${uploadId}/`;
    if (!uploadEvent.object_key.startsWith(expectedPrefix)) {
      return NextResponse.json({ error: 'Object key outside authorised prefix' }, { status: 403 });
    }

    const presignedGet = await callPresignService({
      bucket,
      key,
      method: 'get',
      expires: body.expires || 3600,
    });

    const s3Uri = buildAssetUri(bucket, key);
    const studioBoardMeta = {
      upload_id: uploadId,
      ingest: 'ui-dropzone',
      source: 'ui-dropzone',
      tags,
      size_bytes: size,
      content_type: contentType,
      presigned_get: presignedGet.url,
      author,
      owner_id: effectiveUserId,
    };

    const supabase = getServiceSupabaseClient();

    let webhookResult: unknown = null;
    if (RENDER_WEBHOOK_URL) {
      try {
        webhookResult = await notifyRenderWebhook({
          bucket,
          key,
          s3_uri: s3Uri,
          presigned_get: presignedGet.url,
          namespace,
          title,
          author,
          tags,
          meta: studioBoardMeta,
        });
      } catch (err) {
        console.warn('[api/uploads/persist] Render webhook failed, falling back to PostgREST insert', err);
        const fallback = await supabase
          .from('studio_board')
          .insert({
            title,
            namespace,
            content_url: s3Uri,
            status: 'submitted',
            meta: studioBoardMeta,
          })
          .select()
          .single();
        if (fallback.error) {
          throw fallback.error;
        }
        webhookResult = {
          ok: false,
          fallback: fallback.data,
          error: err instanceof Error ? err.message : String(err),
        };
      }
    } else {
      const fallback = await supabase
        .from('studio_board')
        .insert({
          title,
          namespace,
          content_url: s3Uri,
          status: 'submitted',
          meta: studioBoardMeta,
        })
        .select()
        .single();
      if (fallback.error) {
        throw fallback.error;
      }
      webhookResult = { ok: true, fallback: fallback.data };
    }
    const videoMeta = {
      upload_id: uploadId,
      ingest: 'ui-dropzone',
      tags,
      size_bytes: size,
      content_type: contentType,
      presigned_get: presignedGet.url,
      author,
      owner_id: effectiveUserId,
    };

    const videoResult = await supabase
      .from('videos')
      .upsert(
        {
          video_id: uploadId,
          namespace,
          title,
          source_url: s3Uri,
          s3_base_prefix: key.split('/').slice(0, -1).join('/') || key,
          meta: videoMeta,
        },
        { onConflict: 'video_id' }
      );
    if (videoResult.error) {
      throw videoResult.error;
    }

    const transcriptResult = await supabase
      .from('transcripts')
      .upsert(
        {
          video_id: uploadId,
          language,
          text: transcriptText,
          s3_uri: s3Uri,
          meta: {
            upload_id: uploadId,
            ingest: 'ui-dropzone',
            status: transcriptText ? 'available' : 'pending',
            author,
            owner_id: effectiveUserId ?? session?.user?.id ?? null,
          },
        },
        { onConflict: 'video_id' }
      );
    if (transcriptResult.error) {
      throw transcriptResult.error;
    }

    const uploadEventResult = await supabase
      .from('upload_events')
      .update({
        status: 'complete',
        progress: 100,
        owner_id: effectiveUserId,
        meta: {
          namespace,
          tags,
          bucket,
          object_key: key,
          completed_at: new Date().toISOString(),
          presigned_get: presignedGet.url,
          ingest: 'ui-dropzone',
          author,
          owner_id: effectiveUserId,
        },
      })
      .eq('upload_id', uploadId);
    if (uploadEventResult.error) {
      throw uploadEventResult.error;
    }

    return NextResponse.json(
      {
        ok: true,
        presignedGetUrl: presignedGet.url,
        webhookResult,
      },
      { status: 200 }
    );
  } catch (error) {
    console.error('[api/uploads/persist] Failed to persist upload metadata', error);
    const message = error instanceof Error ? error.message : 'Unexpected error';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
