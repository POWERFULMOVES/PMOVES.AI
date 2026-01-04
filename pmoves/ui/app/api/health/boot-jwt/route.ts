import { NextResponse } from 'next/server';
import { getBootJwt } from '@/lib/supabaseClient';

function decode(token?: string) {
  try {
    if (!token) return null;
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf-8')) as any;
    return payload;
  } catch {
    return null;
  }
}

export async function GET() {
  const token = getBootJwt();
  const payload = decode(token || undefined);
  const now = Math.floor(Date.now() / 1000);
  const exp = payload?.exp as number | undefined;
  const expired = !!(exp && now >= exp);
  return NextResponse.json({
    hasToken: Boolean(token),
    exp,
    now,
    expired,
    iss: payload?.iss,
    sub: payload?.sub,
  });
}

