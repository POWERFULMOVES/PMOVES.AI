import { NextResponse } from 'next/server';
import { getBootJwt } from '@/lib/supabaseClient';

/**
 * Decodes a JWT payload using base64url encoding.
 *
 * JWT uses base64url encoding which differs from standard base64:
 * - '-' (62) instead of '+'
 * - '_' (63) instead of '/'
 * - No padding '=' characters
 *
 * This function properly handles base64url decoding.
 */
function decode(token?: string) {
  try {
    if (!token) return null;
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    // Convert base64url to base64 by replacing characters
    // base64url: '-' (minus) and '_' (underscore)
    // base64: '+' (plus) and '/' (slash)
    let base64 = parts[1];
    base64 = base64.replace(/-/g, '+');
    base64 = base64.replace(/_/g, '/');

    // Add padding if needed (base64url omits padding)
    while (base64.length % 4) {
      base64 += '=';
    }

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

