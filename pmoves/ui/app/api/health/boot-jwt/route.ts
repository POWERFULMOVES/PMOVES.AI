import { NextResponse } from 'next/server';
import { getBootJwt } from '@/lib/supabaseClient';

function decode(token?: string) {
  try {
    if (!token) return null;
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    // JWT uses base64url encoding: replace - and _ before decoding
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(Buffer.from(base64, 'base64').toString('utf-8')) as any;
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

