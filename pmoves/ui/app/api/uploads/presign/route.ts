import { NextRequest, NextResponse } from 'next/server';
import { callPresignService, type PresignMethod } from '../../../../lib/presign';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const bucket = body.bucket as string | undefined;
    const key = body.key as string | undefined;
    const contentType = body.contentType as string | undefined;
    const expires = body.expires as number | undefined;
    const method = (body.method as PresignMethod | undefined) ?? 'put';

    if (!bucket || !key) {
      return NextResponse.json({ error: 'bucket and key are required' }, { status: 400 });
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
